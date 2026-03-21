"""
Main Application: Streamlit UI for Multi-Echelon Inventory Optimization
"""

import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
import plotly.graph_objects as go
from io import BytesIO
from typing import Optional, Dict
import traceback

from engine import SupplyChainEngine, InteractiveSimulator
from optimizer import GeneticOptimizer, GAConfig, Chromosome

# Page configuration
st.set_page_config(
    page_title="MEIO Optimizer",
    page_icon="📦",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Styling
try:
    with open("assets/style.css", "r") as f:
        css = f.read()
    st.markdown(f"<style>{css}</style>", unsafe_allow_html=True)
except FileNotFoundError:
    st.warning("Could not load assets/style.css")


def create_template_excel() -> BytesIO:
    """
    Create a template Excel file with all required sheets and sample data.
    """
    output = BytesIO()

    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        # Sheet 1: Nodes
        nodes_df = pd.DataFrame({
            'NodeID': ['PLANT_A', 'DC_EAST', 'DC_WEST', 'REGION_NE', 'REGION_SE', 'REGION_NW', 'REGION_SW'],
            'NodeType': ['Plant', 'DC', 'DC', 'Region', 'Region', 'Region', 'Region'],
            'Capacity': [10000, 5000, 5000, np.nan, np.nan, np.nan, np.nan]
        })
        nodes_df.to_excel(writer, sheet_name='Nodes', index=False)

        # Sheet 2: SKUs
        skus_df = pd.DataFrame({
            'SKU': ['SKU_001', 'SKU_002'],
            'Description': ['Product A', 'Product B']
        })
        skus_df.to_excel(writer, sheet_name='SKUs', index=False)

        # Sheet 3: Demand (Regional demand only)
        demand_df = pd.DataFrame({
            'NodeID': ['REGION_NE', 'REGION_SE', 'REGION_NW', 'REGION_SW'] * 2,
            'SKU': ['SKU_001'] * 4 + ['SKU_002'] * 4,
            'MeanWeekly': [100, 80, 90, 70, 60, 50, 55, 45],
            'StdWeekly': [20, 16, 18, 14, 12, 10, 11, 9]
        })
        demand_df.to_excel(writer, sheet_name='Demand', index=False)

        # Sheet 4: LeadTimes
        lead_times_data = []
        for origin in ['PLANT_A']:
            for dest in ['DC_EAST', 'DC_WEST']:
                for sku in ['SKU_001', 'SKU_002']:
                    lead_times_data.append({
                        'Origin': origin,
                        'Destination': dest,
                        'SKU': sku,
                        'LeadTimeMean': 2.0,
                        'LeadTimeStd': 0.5
                    })

        for origin in ['DC_EAST', 'DC_WEST']:
            regions = ['REGION_NE', 'REGION_SE'] if origin == 'DC_EAST' else [
                'REGION_NW', 'REGION_SW']
            for dest in regions:
                for sku in ['SKU_001', 'SKU_002']:
                    lead_times_data.append({
                        'Origin': origin,
                        'Destination': dest,
                        'SKU': sku,
                        'LeadTimeMean': 1.0,
                        'LeadTimeStd': 0.2
                    })

        pd.DataFrame(lead_times_data).to_excel(
            writer, sheet_name='LeadTimes', index=False)

        # Sheet 5: Transport
        transport_data = []
        for item in lead_times_data:
            transport_data.append({
                **item,
                'FixedCostPerShipment': 500,
                'VariableCostPerUnit': 2.0
            })

        pd.DataFrame(transport_data).to_excel(
            writer, sheet_name='Transport', index=False)

        # Sheet 6: Costs
        costs_data = []
        for node in nodes_df['NodeID']:
            for sku in ['SKU_001', 'SKU_002']:
                costs_data.append({
                    'NodeID': node,
                    'SKU': sku,
                    'HoldingCostPerUnit': 0.5,
                    'OrderingCost': 100,
                    'ShortageCostPerUnit': 10
                })

        pd.DataFrame(costs_data).to_excel(
            writer, sheet_name='Costs', index=False)

        # Sheet 7: Policies
        policies_data = []
        for node in nodes_df['NodeID']:
            for sku in ['SKU_001', 'SKU_002']:
                policies_data.append({
                    'NodeID': node,
                    'SKU': sku,
                    'ReviewPeriod': 1.0
                })

        pd.DataFrame(policies_data).to_excel(
            writer, sheet_name='Policies', index=False)

        # Sheet 8: ServiceTargets
        service_data = []
        for node in ['REGION_NE', 'REGION_SE', 'REGION_NW', 'REGION_SW']:
            for sku in ['SKU_001', 'SKU_002']:
                service_data.append({
                    'NodeID': node,
                    'SKU': sku,
                    'TargetFillRate': 0.95
                })

        pd.DataFrame(service_data).to_excel(
            writer, sheet_name='ServiceTargets', index=False)

        # Sheet 9: InitialInventory
        initial_inv_data = []
        for node in nodes_df['NodeID']:
            for sku in ['SKU_001', 'SKU_002']:
                initial_inv_data.append({
                    'NodeID': node,
                    'SKU': sku,
                    'InitialStock': 100
                })

        pd.DataFrame(initial_inv_data).to_excel(
            writer, sheet_name='InitialInventory', index=False)

        # Sheet 10: SimulationParams
        sim_params_df = pd.DataFrame({
            'Parameter': ['RandomSeed', 'SimulationWeeks', 'DemandCV'],
            'Value': [42, 52, 0.3]
        })
        sim_params_df.to_excel(
            writer, sheet_name='SimulationParams', index=False)

    output.seek(0)
    return output


@st.cache_data
def load_data_excel(file):
    """Load all required sheets from the Excel file."""
    xls = pd.ExcelFile(file)
    data = {
        'Nodes': pd.read_excel(xls, 'Nodes'),
        'SKUs': pd.read_excel(xls, 'SKUs'),
        'Demand': pd.read_excel(xls, 'Demand'),
        'Policies': pd.read_excel(xls, 'Policies'),
        'Costs': pd.read_excel(xls, 'Costs'),
        'LeadTimes': pd.read_excel(xls, 'LeadTimes'),
        'Transport': pd.read_excel(xls, 'Transport'),
        'ServiceTargets': pd.read_excel(xls, 'ServiceTargets'),
        'InitialInventory': pd.read_excel(xls, 'InitialInventory'),
        'SimulationParams': pd.read_excel(xls, 'SimulationParams')
    }
    return data

@st.cache_data
def load_data_csvs(files):
    """Load matching CSVs mapped to their respective DataFrame keys."""
    data = {}
    for f in files:
        name = f.name.lower()
        if 'nodes' in name:
            data['Nodes'] = pd.read_csv(f)
        elif 'skus' in name:
            data['SKUs'] = pd.read_csv(f)
        elif 'demand' in name:
            data['Demand'] = pd.read_csv(f)
        elif 'policies' in name:
            data['Policies'] = pd.read_csv(f)
        elif 'costs' in name:
            data['Costs'] = pd.read_csv(f)
        elif 'leadtimes' in name or 'lead_times' in name:
            data['LeadTimes'] = pd.read_csv(f)
        elif 'transport' in name:
            data['Transport'] = pd.read_csv(f)
        elif 'servicetargets' in name or 'service_targets' in name or 'service' in name:
            data['ServiceTargets'] = pd.read_csv(f)
        elif 'initialinventory' in name or 'initial_inventory' in name:
            data['InitialInventory'] = pd.read_csv(f)
        elif 'simulationparams' in name or 'simulation_params' in name:
            data['SimulationParams'] = pd.read_csv(f)
            
    required = {'Nodes', 'SKUs', 'Demand', 'Policies', 'Costs', 'LeadTimes', 'Transport', 'ServiceTargets', 'InitialInventory', 'SimulationParams'}
    missing = required - set(data.keys())
    if missing:
        raise ValueError(f"Missing distinct CSV files for: {', '.join(missing)}")
    return data

@st.cache_data
def load_data_db(uri):
    """Pull tables directly from Database URI using SQLAlchemy."""
    from sqlalchemy import create_engine
    engine = create_engine(uri)
    data = {
        'Nodes': pd.read_sql_table('Nodes', engine),
        'SKUs': pd.read_sql_table('SKUs', engine),
        'Demand': pd.read_sql_table('Demand', engine),
        'Policies': pd.read_sql_table('Policies', engine),
        'Costs': pd.read_sql_table('Costs', engine),
        'LeadTimes': pd.read_sql_table('LeadTimes', engine),
        'Transport': pd.read_sql_table('Transport', engine),
        'ServiceTargets': pd.read_sql_table('ServiceTargets', engine),
        'InitialInventory': pd.read_sql_table('InitialInventory', engine),
        'SimulationParams': pd.read_sql_table('SimulationParams', engine)
    }
    return data


def validate_input_data(sheets: Dict[str, pd.DataFrame]) -> tuple[bool, str]:
    """
    Validate that all required sheets and columns are present.

    Returns:
        (is_valid, error_message)
    """
    required_sheets = [
        'Nodes', 'SKUs', 'Demand', 'LeadTimes', 'Transport',
        'Costs', 'Policies', 'ServiceTargets', 'InitialInventory', 'SimulationParams'
    ]

    for sheet in required_sheets:
        if sheet not in sheets:
            return False, f"Missing required sheet: {sheet}"

    # Validate columns
    required_columns = {
        'Nodes': ['NodeID', 'NodeType', 'Capacity'],
        'SKUs': ['SKU'],
        'Demand': ['NodeID', 'SKU', 'MeanWeekly', 'StdWeekly'],
        'LeadTimes': ['Origin', 'Destination', 'SKU', 'LeadTimeMean'],
        'Transport': ['Origin', 'Destination', 'SKU', 'FixedCostPerShipment', 'VariableCostPerUnit'],
        'Costs': ['NodeID', 'SKU', 'HoldingCostPerUnit', 'OrderingCost', 'ShortageCostPerUnit'],
        'Policies': ['NodeID', 'SKU', 'ReviewPeriod'],
        'ServiceTargets': ['NodeID', 'SKU', 'TargetFillRate'],
        'InitialInventory': ['NodeID', 'SKU', 'InitialStock'],
        'SimulationParams': ['Parameter', 'Value']
    }

    for sheet, cols in required_columns.items():
        df = sheets[sheet]
        missing_cols = set(cols) - set(df.columns)
        if missing_cols:
            return False, f"Sheet '{sheet}' missing columns: {missing_cols}"

    return True, ""


def create_output_excel(solution_summary: Dict, convergence_df: pd.DataFrame) -> BytesIO:
    """
    Create Excel file with optimization results.
    """
    output = BytesIO()

    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        # Results Z-values
        solution_summary['z_values'].to_excel(
            writer, sheet_name='ResultsZ', index=False)

        # Stock Targets
        solution_summary['stock_targets'].to_excel(
            writer, sheet_name='StockTargets', index=False)

        # Flows Optimized
        solution_summary['flows'].to_excel(
            writer, sheet_name='FlowsOptimized', index=False)

        # Cost Breakdown
        cost_df = pd.DataFrame([solution_summary['cost_breakdown']]).T
        cost_df.columns = ['WeeklyCost']
        cost_df.to_excel(writer, sheet_name='CostBreakdown')

        # Diagnostics
        if not solution_summary['violations'].empty:
            solution_summary['violations'].to_excel(
                writer, sheet_name='Diagnostics', index=False)
        else:
            pd.DataFrame({'Message': ['No constraint violations detected']}).to_excel(
                writer, sheet_name='Diagnostics', index=False
            )

        # Convergence
        convergence_df.to_excel(writer, sheet_name='Convergence', index=False)

    output.seek(0)
    return output


def build_cost_waterfall(cost_breakdown: Dict):
    """Create a Plotly Waterfall chart for cost components."""
    ordering = cost_breakdown.get('Ordering', 0)
    holding = cost_breakdown.get('Holding', 0)
    shortage = cost_breakdown.get('Shortage', 0)
    transport = cost_breakdown.get('Transport', 0)
    total = ordering + holding + shortage + transport

    x = ["Start", "Ordering", "Holding", "Shortage", "Transport", "Total weekly"]
    measure = ["absolute", "relative", "relative", "relative", "relative", "total"]
    y = [0, ordering, holding, shortage, transport, 0]

    # Calculate text labels mapping values and % of total
    text = [""] + [f"${val:,.0f}<br>({(val/total) if total else 0:.1%})" for val in y[1:-1]] + [f"${total:,.0f}"]

    fig = go.Figure(go.Waterfall(
        name="Costs",
        orientation="v",
        measure=measure,
        x=x,
        y=y,
        text=text,
        textposition="outside",
        connector={"line": {"color": "rgb(63, 63, 63)"}},
        increasing={"marker": {"color": "#e74c3c"}},  # Red for costs
        decreasing={"marker": {"color": "#2ecc71"}},
        totals={"marker": {"color": "#3498db"}},      # Blue for total
        hovertemplate="<b>%{x}</b><br>Value: $%{y:,.0f}<br>Total: %{text}<extra></extra>"
    ))

    fig.update_layout(
        title="Weekly Cost Component Contribution",
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        font=dict(color="#E0E0E0"),
        showlegend=False,
        margin=dict(t=50, l=20, r=20, b=20)
    )
    
    return fig

def build_cost_stacked_bar(history_df: pd.DataFrame, view_mode: str, current_scenario: str):
    """Create a Plotly stacked bar chart comparing scenarios."""
    fig = go.Figure()
    
    components = ['Ordering', 'Holding', 'Shortage', 'Transport']
    colors = ['#3498db', '#e74c3c', '#f1c40f', '#2ecc71']
    
    for i, col in enumerate(components):
        if view_mode == "100% Stacked":
            # Normalize each scenario
            y_data = history_df[col] / history_df['Total']
            text_data = [f"{val:.1%}" if val > 0 else "" for val in y_data]
            hover_tmpl = col + ": %{y:.1%}<extra></extra>"
        else:
            y_data = history_df[col]
            text_data = [f"${val:,.0f}" if val > 0 else "" for val in y_data]
            hover_tmpl = col + ": $%{y:,.0f}<extra></extra>"
            
        # Highlight current scenario by controlling opacity
        opacity = [1.0 if row['scenario_name'] == current_scenario else 0.4 
                   for _, row in history_df.iterrows()]
        
        fig.add_trace(go.Bar(
            name=col,
            x=history_df['scenario_name'],
            y=y_data,
            text=text_data,
            textposition='inside',
            marker=dict(color=colors[i], opacity=opacity, line=dict(width=1, color="#1E1E1E")),
            hovertemplate=hover_tmpl
        ))

    fig.update_layout(
        barmode='stack',
        title="Scenario Comparison (Highlighted: Current)",
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        font=dict(color="#E0E0E0"),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
    )
    
    if view_mode == "100% Stacked":
        fig.update_yaxes(tickformat=".0%")
        
    return fig


def plot_service_levels(stock_targets_df: pd.DataFrame, service_targets_df: pd.DataFrame):
    """Create bar chart comparing achieved vs target service levels."""
    plt.style.use('dark_background')
    # Merge achieved and target
    merged = stock_targets_df.merge(
        service_targets_df,
        on=['NodeID', 'SKU'],
        how='left'
    )

    # Filter regions only
    merged = merged[merged['NodeID'].str.contains('REGION', na=False)]

    if merged.empty:
        return None

    # Create grouped bar chart
    fig, ax = plt.subplots(figsize=(12, 6))
    fig.patch.set_facecolor('none')
    ax.set_facecolor('none')

    x = np.arange(len(merged))
    width = 0.35

    bars1 = ax.bar(x - width/2, merged['FillRate'], width,
                   label='Achieved', color='#2ecc71', alpha=0.9, edgecolor='none')
    bars2 = ax.bar(x + width/2, merged['TargetFillRate'], width,
                   label='Target', color='#3498db', alpha=0.9, edgecolor='none')

    ax.set_xlabel('Node-SKU', fontweight='bold', color='#E0E0E0')
    ax.set_ylabel('Fill Rate', fontweight='bold', color='#E0E0E0')
    ax.set_title('Service Level: Achieved vs Target',
                 fontsize=14, fontweight='bold', color='#E0E0E0')
    ax.set_xticks(x)
    ax.set_xticklabels([f"{row['NodeID']}\n{row['SKU']}"
                        for _, row in merged.iterrows()],
                       rotation=45, ha='right', fontsize=10, color='#E0E0E0')
    
    legend = ax.legend(frameon=False, loc='lower right')
    for text in legend.get_texts():
        text.set_color('#E0E0E0')
        
    ax.axhline(y=0.95, color='#e74c3c', linestyle='--', linewidth=1.5, alpha=0.8)
    ax.set_ylim([0.8, 1.0])
    ax.grid(axis='y', alpha=0.2, color='#ECECEC', linestyle=':')

    # Hide spines
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.spines['left'].set_color('#555555')
    ax.spines['bottom'].set_color('#555555')

    plt.tight_layout()

    return fig


def plot_convergence(convergence_df: pd.DataFrame):
    """Create line chart showing GA convergence."""
    plt.style.use('dark_background')
    fig, ax = plt.subplots(figsize=(10, 6))
    fig.patch.set_facecolor('none')
    ax.set_facecolor('none')

    ax.plot(convergence_df['Generation'], convergence_df['BestFitness'],
            label='Best Fitness', color='#e74c3c', linewidth=2.5, marker='o', markersize=4, markerfacecolor='#1E1E1E')
    ax.plot(convergence_df['Generation'], convergence_df['AvgFitness'],
            label='Avg Fitness', color='#34495e', linewidth=2, linestyle='--')

    ax.set_xlabel('Generation', fontweight='bold', color='#E0E0E0')
    ax.set_ylabel('Fitness (Total Cost + Penalties)', fontweight='bold', color='#E0E0E0')
    ax.set_title('Genetic Algorithm Convergence',
                 fontsize=14, fontweight='bold', color='#E0E0E0')
                 
    legend = ax.legend(frameon=False)
    for text in legend.get_texts():
        text.set_color('#E0E0E0')
        
    ax.grid(alpha=0.2, color='#ECECEC', linestyle=':')
    
    # Hide spines
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.spines['left'].set_color('#555555')
    ax.spines['bottom'].set_color('#555555')

    plt.tight_layout()

    return fig


def main():
    """Main Streamlit application."""

    # Header
    st.markdown('<p class="main-header">📦 Multi-Echelon Inventory Optimization</p>',
                unsafe_allow_html=True)
    st.markdown('<p class="sub-header">Advanced Supply Chain Network Optimizer with Constraint-Aware Genetic Algorithm</p>',
                unsafe_allow_html=True)

    # Sidebar
    with st.sidebar:
        st.header("⚙️ Configuration")

        # Download template
        st.subheader("1. Download Template")
        template_file = create_template_excel()
        st.download_button(
            label="📥 Download Excel Template",
            data=template_file,
            file_name="MEIO_Template.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

        st.markdown("---")

        # Data Upload
        st.subheader("2. Data Input")
        
        # Initialization
        if 'data' not in st.session_state:
            st.session_state['data'] = None

        data_source = st.radio("Data Source", ["File Upload", "Database Connection"])
        
        if data_source == "File Upload":
            uploaded_files = st.file_uploader(
                "Upload Excel or Multiple CSVs", 
                type=['xlsx', 'csv'], 
                accept_multiple_files=True,
                help="Upload a single Excel file with all sheets, or multiple CSV files (one per sheet, named appropriately)."
            )
            if uploaded_files:
                try:
                    # Clear cache if new files are uploaded
                    if st.session_state['data'] is not None and uploaded_files != st.session_state.get('last_uploaded_files'):
                        st.cache_data.clear()
                        st.session_state['data'] = None # Invalidate current data

                    if st.session_state['data'] is None:
                        # Check if any is excel
                        excel_files = [f for f in uploaded_files if f.name.endswith('.xlsx')]
                        if excel_files:
                            st.session_state['data'] = load_data_excel(excel_files[0])
                        else:
                            st.session_state['data'] = load_data_csvs(uploaded_files)
                        st.success("File data loaded successfully!")
                        st.session_state['last_uploaded_files'] = uploaded_files # Store for comparison
                        
                except Exception as e:
                    st.error(f"Error loading files: {str(e)}")
                    st.session_state['data'] = None # Ensure data is cleared on error
                    with st.expander("Show error details"):
                        st.code(traceback.format_exc())
                    
        else: # Database Connection
            db_uri = st.text_input("Database URI", placeholder="postgresql://user:pass@host/db")
            if st.button("Fetch Data from Database"):
                if db_uri:
                    try:
                        with st.spinner("Connecting and fetching tables..."):
                            st.cache_data.clear() # Clear cache before fetching from DB
                            fetched_data = load_data_db(db_uri)
                            st.session_state['data'] = fetched_data
                            st.success("Data successfully fetched from DB!")
                    except Exception as e:
                        st.error(f"Database Error: {str(e)}")
                        st.session_state['data'] = None # Ensure data is cleared on error
                        with st.expander("Show error details"):
                            st.code(traceback.format_exc())
                else:
                    st.warning("Please enter a Database URI.")

        st.markdown("---")

        # GA Parameters
        st.subheader("3. Optimization Settings")

        population_size = st.slider("Population Size", 20, 100, 50, 10)
        num_generations = st.slider("Generations", 20, 200, 100, 10)
        mutation_rate = st.slider("Mutation Rate", 0.05, 0.30, 0.15, 0.05)
        top_k_for_sim = st.slider("Top K for Simulation", 3, 10, 5, 1)

        st.markdown("---")
        st.subheader("4. Run Options")
        scenario_name = st.text_input("Scenario Name", value="Base Scenario")
        interactive_mode = st.checkbox("Enable Interactive Simulation", value=True, help="Pause after GA optimization to run simulation week-by-week and tweak parameters.")

        st.markdown("---")

        # Run button
        run_optimization = st.button(
            "🚀 Run Optimization", type="primary", use_container_width=True)

    # Main content area
    if st.session_state['data'] is None:
        st.info("👈 Please upload an Excel file, CSVs, or connect to a database to begin optimization.")

        # Show instructions
        st.subheader("📋 Instructions")
        st.markdown("""
        1. **Download the Template**: Click the button in the sidebar to get the Excel template
        2. **Fill in Your Data**: Complete all sheets with your supply chain network information
        3. **Upload the File**: Upload your completed Excel file (or individual CSVs)
        4. **Configure Settings**: Adjust GA parameters in the sidebar
        5. **Run Optimization**: Click the 'Run Optimization' button
        6. **Download Results**: Download the optimized solution as an Excel file
        
        **Required Sheets/Tables/CSVs:**
        - `Nodes`: Network nodes (Plants, DCs, Regions)
        - `SKUs`: Product SKUs
        - `Demand`: Regional demand statistics
        - `LeadTimes`: Transportation lead times
        - `Transport`: Transportation costs
        - `Costs`: Inventory and shortage costs
        - `Policies`: Review periods
        - `ServiceTargets`: Target fill rates
        - `InitialInventory`: Starting inventory levels
        - `SimulationParams`: Simulation parameters
        """)

        return

    # Load and validate data
    try:
        sheets = st.session_state['data']

        is_valid, error_msg = validate_input_data(sheets)
        if not is_valid:
            st.error(f"❌ Input validation failed: {error_msg}")
            st.session_state['data'] = None # Invalidate data on validation failure
            return

        st.success("✅ Input data validated successfully!")

        # Display network summary
        col1, col2, col3 = st.columns(3)

        with col1:
            st.metric("Nodes", len(sheets['Nodes']))
        with col2:
            st.metric("SKUs", len(sheets['SKUs']))
        with col3:
            st.metric("Network Links", len(sheets['Transport']))

    except Exception as e:
        st.error(f"❌ Error processing data: {str(e)}")
        st.session_state['data'] = None # Invalidate data on processing error
        with st.expander("Show error details"):
            st.code(traceback.format_exc())
        return

    # Run optimization
    if run_optimization:
        try:
            # Initialize engine
            with st.spinner("Initializing supply chain engine..."):
                engine = SupplyChainEngine(
                    nodes_df=sheets['Nodes'],
                    skus_df=sheets['SKUs'],
                    demand_df=sheets['Demand'],
                    leadtimes_df=sheets['LeadTimes'],
                    transport_df=sheets['Transport'],
                    costs_df=sheets['Costs'],
                    policies_df=sheets['Policies'],
                    service_targets_df=sheets['ServiceTargets'],
                    initial_inventory_df=sheets['InitialInventory'],
                    simulation_params_df=sheets['SimulationParams']
                )

            # Configure GA
            config = GAConfig(
                population_size=population_size,
                num_generations=num_generations,
                mutation_rate=mutation_rate,
                top_k_for_sim=top_k_for_sim,
                random_seed=engine.random_seed
            )

            # Progress tracking
            progress_bar = st.progress(0)
            status_text = st.empty()

            def progress_callback(current_gen, total_gen, best_fitness, violations, simulation=False):
                progress = current_gen / total_gen
                progress_bar.progress(progress)

                if simulation:
                    status_text.text(
                        f"Running Monte Carlo simulation on top {top_k_for_sim} candidates...")
                else:
                    status_text.text(
                        f"Generation {current_gen}/{total_gen} | "
                        f"Best Fitness: {best_fitness:,.2f} | "
                        f"Violations: {violations}"
                    )

            # Run optimizer
            st.subheader("🔄 Optimization in Progress")

            optimizer = GeneticOptimizer(
                engine=engine,
                config=config,
                progress_callback=progress_callback
            )

            best_solution, convergence_df = optimizer.optimize()

            progress_bar.progress(1.0)
            status_text.text("✅ Optimization complete!")

            solution_summary = optimizer.get_solution_summary(best_solution)

            st.session_state['scenario_name'] = scenario_name
            st.session_state['interactive_mode'] = interactive_mode
            st.session_state['best_solution'] = best_solution
            st.session_state['solution_summary'] = solution_summary
            st.session_state['convergence_df'] = convergence_df
            st.session_state['engine'] = engine
            st.session_state['sheets'] = sheets

            if interactive_mode:
                st.session_state['simulator'] = InteractiveSimulator(
                    engine=engine,
                    z_values=best_solution.z_values,
                    sourcing_shares=best_solution.sourcing_shares
                )
                st.session_state['simulation_complete'] = False
            else:
                # If not interactive, run full simulation and store results
                simulator = InteractiveSimulator(
                    engine=engine,
                    z_values=best_solution.z_values,
                    sourcing_shares=best_solution.sourcing_shares
                )
                for _ in range(engine.simulation_weeks):
                    simulator.step()
                st.session_state['simulator'] = simulator
                st.session_state['simulation_complete'] = True

            # Store simulation results (either from interactive or full run)
            sim_summary = st.session_state['simulator'].get_summary()
            st.session_state['simulation_results'] = {
                'metrics': sim_summary,
                'cost_breakdown': solution_summary.get('cost_breakdown', {}),
                'weekly_series': st.session_state['simulator'].weekly_results,
                'monthly_series': None # Will be derived later if needed
            }
            
            # Scenario History Management for Stacked Charts
            if 'scenario_history' not in st.session_state:
                st.session_state['scenario_history'] = []
                
            cb = solution_summary.get('cost_breakdown', {})
            history_entry = {
                'scenario_name': scenario_name,
                'Holding': cb.get('Holding', 0),
                'Ordering': cb.get('Ordering', 0),
                'Shortage': cb.get('Shortage', 0),
                'Transport': cb.get('Transport', 0),
                'Total': solution_summary.get('total_cost', 0)
            }
            
            # Upsert by scenario_name
            st.session_state['scenario_history'] = [
                h for h in st.session_state['scenario_history'] if h['scenario_name'] != scenario_name
            ]
            st.session_state['scenario_history'].append(history_entry)

        except Exception as e:
            st.error(f"❌ Optimization failed: {str(e)}")
            with st.expander("Show error details"):
                st.code(traceback.format_exc())

    # Interactive Simulation
    if 'simulator' in st.session_state and not st.session_state.get('simulation_complete', True):
        st.markdown("---")
        st.subheader("🕹️ Interactive Simulation")
        sim = st.session_state['simulator']
        
        st.write(f"**Current Week:** {sim.current_week}")
        
        st.write("Tweak Demand for Next Week (Optional):")
        with st.expander("Adjust Node Demand Parameters"):
            tweaks = {}
            # Ensure sim.results_df is available or handle its absence
            if hasattr(sim, 'results_df') and not sim.results_df.empty:
                for _, row in sim.results_df.iterrows():
                    node = row['NodeID']
                    sku = row['SKU']
                    col1, col2, col3 = st.columns([2, 1, 1])
                    with col1:
                        st.write(f"**{node}** - {sku}")
                    with col2:
                        new_mean = st.number_input(f"Mean", value=float(row['DemandMean']), key=f"mean_{node}_{sku}")
                    with col3:
                        new_std = st.number_input(f"Std", value=float(row['DemandStd']), key=f"std_{node}_{sku}")
                    tweaks[(node, sku)] = {'DemandMean': new_mean, 'DemandStd': new_std}
            else:
                st.info("No detailed node results available yet for tweaking. Run at least one week.")
                
        col_s1, col_s2 = st.columns(2)
        with col_s1:
            if st.button("Simulate Next Week", type="primary"):
                sim.step(week_overrides=tweaks)
                st.rerun()
        with col_s2:
            if st.button("Finish Simulation"):
                remaining = sim.engine.simulation_weeks - sim.current_week
                for _ in range(remaining):
                    sim.step()
                st.session_state['simulation_complete'] = True
                # Update simulation_results after full simulation
                sim_summary = st.session_state['simulator'].get_summary()
                
                # Do not override cost_breakdown with sim_summary
                if 'simulation_results' in st.session_state and st.session_state['simulation_results']:
                    st.session_state['simulation_results']['metrics'] = sim_summary
                    st.session_state['simulation_results']['weekly_series'] = st.session_state['simulator'].weekly_results
                else:    
                    st.session_state['simulation_results'] = {
                        'metrics': sim_summary,
                        'cost_breakdown': st.session_state.get('solution_summary', {}).get('cost_breakdown', {}),
                        'weekly_series': st.session_state['simulator'].weekly_results,
                        'monthly_series': None
                    }
                st.rerun()
                
        if sim.weekly_results:
            st.write(f"**Results for Week {sim.current_week - 1}:**")
            last_week = sim.weekly_results[-1]
            st.dataframe(pd.DataFrame(last_week['NodeDetails']), use_container_width=True)
            
        return  # wait for simulation to complete

    # Results display
    if st.session_state.get('simulation_complete', False) and 'solution_summary' in st.session_state:
        try:
            solution_summary = st.session_state['solution_summary']
            convergence_df = st.session_state['convergence_df']
            sheets = st.session_state['sheets']
            scenario_name = st.session_state.get('scenario_name', '')
            
            # Update simulated cost from cached simulation_results
            if 'simulation_results' in st.session_state:
                solution_summary['total_cost_simulated'] = st.session_state['simulation_results']['metrics']['total_cost']

            # Display results
            st.success(f"🎉 Optimization and Simulation completed successfully for **{scenario_name}**!")

            st.markdown("---")
            st.subheader("📊 Results Dashboard")

            # Metrics
            col1, col2, col3, col4 = st.columns(4)

            with col1:
                st.metric(
                    "Total Weekly Cost (Analytical)",
                    f"${solution_summary['total_cost_analytical']:,.2f}"
                )

            with col2:
                st.metric(
                    "Total Weekly Cost (Simulated)",
                    f"${solution_summary['total_cost_simulated']:,.2f}" if solution_summary['total_cost_simulated'] else "N/A"
                )

            with col3:
                st.metric(
                    "Constraint Violations",
                    solution_summary['num_violations'],
                    delta=None if solution_summary['num_violations'] == 0 else "Warning",
                    delta_color="inverse"
                )

            with col4:
                avg_fill_rate = solution_summary['stock_targets']['FillRate'].mean(
                )
                st.metric(
                    "Avg Fill Rate",
                    f"{avg_fill_rate:.1%}"
                )



            # Visualizations
            st.markdown("---")

            tab1, tab2, tab3, tab4, tab5 = st.tabs(
                ["💰 Cost Breakdown", "📈 Service Levels", "📉 Convergence", "📅 Weekly/Monthly View", "📸 Snapshots"])

            with tab1:
                fig_waterfall = build_cost_waterfall(solution_summary['cost_breakdown'])
                st.plotly_chart(fig_waterfall, use_container_width=True)
                
                st.markdown("---")
                st.subheader("Compare Scenarios")
                history_df = pd.DataFrame(st.session_state.get('scenario_history', []))
                if len(history_df) > 0:
                    view_mode = st.radio("View Mode", ["Absolute", "100% Stacked"], horizontal=True, key="view_mode_dashboard")
                    fig_stacked = build_cost_stacked_bar(
                        history_df, view_mode, current_scenario=scenario_name)
                    st.plotly_chart(fig_stacked, use_container_width=True)
                else:
                    st.info("Run another scenario to see comparison.")

            with tab2:
                fig2 = plot_service_levels(
                    solution_summary['stock_targets'],
                    sheets['ServiceTargets']
                )
                if fig2:
                    st.pyplot(fig2)
                else:
                    st.info("No regional service level data available")

            with tab3:
                fig3 = plot_convergence(convergence_df)
                st.pyplot(fig3)

            with tab4:
                if 'simulator' in st.session_state:
                    sim = st.session_state['simulator']
                    weekly_df = pd.DataFrame([
                        {'Week': w['Week'], 'Total Cost': w['TotalCost'], 'Total Holding': w['TotalHoldingCost'], 'Total Shortage': w['TotalShortageCost']}
                        for w in sim.weekly_results
                    ])
                    st.write("##### Weekly Aggregated Costs")
                    st.dataframe(weekly_df, use_container_width=True)
                    st.line_chart(weekly_df.set_index('Week')[['Total Cost', 'Total Holding', 'Total Shortage']])
                    
                    weekly_df['Month'] = (weekly_df['Week'] // 4) + 1
                    monthly_df = weekly_df.groupby('Month').sum().reset_index()
                    st.write("##### Monthly Aggregated Costs")
                    st.dataframe(monthly_df, use_container_width=True)
                    st.bar_chart(monthly_df.set_index('Month')[['Total Holding', 'Total Shortage']])
                else:
                    st.info("Interactive/Detailed simulation was not enabled. Enable it in the sidebar to see weekly/monthly breakdown.")

            with tab5:
                if 'simulator' in st.session_state:
                    sim = st.session_state['simulator']
                    st.write("##### Monthly Snapshot Archive")
                    st.markdown("Freeze the inventory snapshot at the end of a specific month (i.e., output the last week of the month).")
                    
                    max_month = (sim.current_week // 4)
                    if max_month > 0:
                        month_to_freeze = st.selectbox("Select Month to Freeze", range(1, max_month + 1))
                        target_week = (month_to_freeze * 4) - 1
                        
                        snapshot_data = pd.DataFrame(sim.weekly_results[target_week]['NodeDetails'])
                        
                        csv_data = snapshot_data.to_csv(index=False)
                        st.download_button(
                            label=f"📥 Download Freeze Snapshot for Month {month_to_freeze}",
                            data=csv_data,
                            file_name=f"{scenario_name.replace(' ', '_')}_snapshot_m{month_to_freeze}.csv",
                            mime="text/csv",
                            type="secondary"
                        )
                        st.dataframe(snapshot_data, use_container_width=True)
                    else:
                        st.warning("No complete months simulated yet.")
                else:
                    st.info("Interactive simulation not enabled. Snapshots require detailed weekly tracking.")

            # Download results
            st.markdown("---")
            st.subheader("💾 Download Results")

            output_file = create_output_excel(solution_summary, convergence_df)

            st.download_button(
                label="📥 Download Optimization Results (Excel)",
                data=output_file,
                file_name=f"{scenario_name.replace(' ', '_')}_MEIO_Results.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                type="primary"
            )

            # Show diagnostics if violations exist
            if solution_summary['num_violations'] > 0:
                st.markdown("---")
                st.warning("⚠️ Constraint Violations Detected")
                st.dataframe(
                    solution_summary['violations'], use_container_width=True)

        except Exception as e:
            st.error(f"❌ Error displaying results: {str(e)}")
            with st.expander("Show error details"):
                st.code(traceback.format_exc())


if __name__ == "__main__":
    main()
