"""
Main Application: Streamlit UI for Multi-Echelon Inventory Optimization
"""

import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
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
st.markdown("""
    <style>
    .main-header {
        font-size: 2.5rem;
        font-weight: 700;
        color: #1f77b4;
        margin-bottom: 0.5rem;
    }
    .sub-header {
        font-size: 1.2rem;
        color: #666;
        margin-bottom: 2rem;
    }
    .metric-card {
        background-color: #f0f2f6;
        padding: 1rem;
        border-radius: 0.5rem;
        margin: 0.5rem 0;
    }
    </style>
""", unsafe_allow_html=True)


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


def plot_cost_breakdown(cost_breakdown: Dict):
    """Create pie chart of cost breakdown."""
    labels = ['Holding', 'Ordering', 'Shortage', 'Transport']
    values = [cost_breakdown[k] for k in labels]

    fig, ax = plt.subplots(figsize=(8, 6))
    colors = sns.color_palette('Set2', len(labels))

    wedges, texts, autotexts = ax.pie(
        values,
        labels=labels,
        autopct='%1.1f%%',
        colors=colors,
        startangle=90
    )

    for autotext in autotexts:
        autotext.set_color('white')
        autotext.set_fontsize(10)
        autotext.set_weight('bold')

    ax.set_title('Weekly Cost Breakdown', fontsize=14, fontweight='bold')

    return fig


def plot_service_levels(stock_targets_df: pd.DataFrame, service_targets_df: pd.DataFrame):
    """Create bar chart comparing achieved vs target service levels."""
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

    x = np.arange(len(merged))
    width = 0.35

    bars1 = ax.bar(x - width/2, merged['FillRate'], width,
                   label='Achieved', color='#2ecc71', alpha=0.8)
    bars2 = ax.bar(x + width/2, merged['TargetFillRate'], width,
                   label='Target', color='#3498db', alpha=0.8)

    ax.set_xlabel('Node-SKU', fontweight='bold')
    ax.set_ylabel('Fill Rate', fontweight='bold')
    ax.set_title('Service Level: Achieved vs Target',
                 fontsize=14, fontweight='bold')
    ax.set_xticks(x)
    ax.set_xticklabels([f"{row['NodeID']}\n{row['SKU']}"
                        for _, row in merged.iterrows()],
                       rotation=45, ha='right', fontsize=8)
    ax.legend()
    ax.axhline(y=0.95, color='red', linestyle='--', linewidth=1, alpha=0.5)
    ax.set_ylim([0.8, 1.0])
    ax.grid(axis='y', alpha=0.3)

    plt.tight_layout()

    return fig


def plot_convergence(convergence_df: pd.DataFrame):
    """Create line chart showing GA convergence."""
    fig, ax = plt.subplots(figsize=(10, 6))

    ax.plot(convergence_df['Generation'], convergence_df['BestFitness'],
            label='Best Fitness', color='#e74c3c', linewidth=2, marker='o', markersize=3)
    ax.plot(convergence_df['Generation'], convergence_df['AvgFitness'],
            label='Avg Fitness', color='#95a5a6', linewidth=2, linestyle='--')

    ax.set_xlabel('Generation', fontweight='bold')
    ax.set_ylabel('Fitness (Total Cost + Penalties)', fontweight='bold')
    ax.set_title('Genetic Algorithm Convergence',
                 fontsize=14, fontweight='bold')
    ax.legend()
    ax.grid(alpha=0.3)

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

        # Upload input file
        st.subheader("2. Upload Input File")
        uploaded_file = st.file_uploader(
            "Choose Excel file",
            type=['xlsx'],
            help="Upload the completed template with your supply chain data"
        )

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
    if uploaded_file is None:
        st.info("👈 Please upload an Excel file to begin optimization.")

        # Show instructions
        st.subheader("📋 Instructions")
        st.markdown("""
        1. **Download the Template**: Click the button in the sidebar to get the Excel template
        2. **Fill in Your Data**: Complete all sheets with your supply chain network information
        3. **Upload the File**: Upload your completed Excel file
        4. **Configure Settings**: Adjust GA parameters in the sidebar
        5. **Run Optimization**: Click the 'Run Optimization' button
        6. **Download Results**: Download the optimized solution as an Excel file
        
        **Required Sheets:**
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
        sheets = pd.read_excel(uploaded_file, sheet_name=None)

        is_valid, error_msg = validate_input_data(sheets)
        if not is_valid:
            st.error(f"❌ Input validation failed: {error_msg}")
            return

        st.success("✅ Input file validated successfully!")

        # Display network summary
        col1, col2, col3 = st.columns(3)

        with col1:
            st.metric("Nodes", len(sheets['Nodes']))
        with col2:
            st.metric("SKUs", len(sheets['SKUs']))
        with col3:
            st.metric("Network Links", len(sheets['Transport']))

    except Exception as e:
        st.error(f"❌ Error loading file: {str(e)}")
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
                st.session_state['simulation_complete'] = True

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
            
            # Update simulated cost if simulator was used
            if 'simulator' in st.session_state:
                sim_summary = st.session_state['simulator'].get_summary()
                solution_summary['total_cost_simulated'] = sim_summary['total_cost']

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
                fig1 = plot_cost_breakdown(solution_summary['cost_breakdown'])
                st.pyplot(fig1)

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
