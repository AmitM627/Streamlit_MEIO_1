"""
Example: Programmatic Usage of MEIO System

This script demonstrates how to use the MEIO system programmatically
without the Streamlit UI, useful for batch processing or integration
into larger systems.
"""

import pandas as pd
import numpy as np
from engine import SupplyChainEngine
from optimizer import GeneticOptimizer, GAConfig


def create_simple_network():
    """
    Create a simple 3-echelon network for demonstration.
    
    Network Structure:
    PLANT_A -> DC_1 -> REGION_A
            -> DC_2 -> REGION_B
    
    Products: SKU_001, SKU_002
    """
    
    # Nodes
    nodes_df = pd.DataFrame({
        'NodeID': ['PLANT_A', 'DC_1', 'DC_2', 'REGION_A', 'REGION_B'],
        'NodeType': ['Plant', 'DC', 'DC', 'Region', 'Region'],
        'Capacity': [5000, 2000, 2000, np.nan, np.nan]
    })
    
    # SKUs
    skus_df = pd.DataFrame({
        'SKU': ['SKU_001', 'SKU_002'],
        'Description': ['Product A', 'Product B']
    })
    
    # Regional Demand
    demand_df = pd.DataFrame({
        'NodeID': ['REGION_A', 'REGION_B'] * 2,
        'SKU': ['SKU_001'] * 2 + ['SKU_002'] * 2,
        'MeanWeekly': [100, 80, 60, 50],
        'StdWeekly': [20, 16, 12, 10]
    })
    
    # Lead Times
    lead_times = []
    
    # Plant to DCs
    for dc in ['DC_1', 'DC_2']:
        for sku in ['SKU_001', 'SKU_002']:
            lead_times.append({
                'Origin': 'PLANT_A',
                'Destination': dc,
                'SKU': sku,
                'LeadTimeMean': 2.0,
                'LeadTimeStd': 0.5
            })
    
    # DCs to Regions
    dc_region_map = {'DC_1': 'REGION_A', 'DC_2': 'REGION_B'}
    for dc, region in dc_region_map.items():
        for sku in ['SKU_001', 'SKU_002']:
            lead_times.append({
                'Origin': dc,
                'Destination': region,
                'SKU': sku,
                'LeadTimeMean': 1.0,
                'LeadTimeStd': 0.2
            })
    
    leadtimes_df = pd.DataFrame(lead_times)
    
    # Transport Costs
    transport_df = leadtimes_df.copy()
    transport_df['FixedCostPerShipment'] = 300
    transport_df['VariableCostPerUnit'] = 1.5
    
    # Inventory Costs
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
    costs_df = pd.DataFrame(costs_data)
    
    # Policies
    policies_df = costs_df[['NodeID', 'SKU']].copy()
    policies_df['ReviewPeriod'] = 1.0
    
    # Service Targets
    service_df = pd.DataFrame({
        'NodeID': ['REGION_A', 'REGION_B'] * 2,
        'SKU': ['SKU_001'] * 2 + ['SKU_002'] * 2,
        'TargetFillRate': [0.95, 0.95, 0.95, 0.95]
    })
    
    # Initial Inventory
    initial_inv_df = costs_df[['NodeID', 'SKU']].copy()
    initial_inv_df['InitialStock'] = 100
    
    # Simulation Parameters
    sim_params_df = pd.DataFrame({
        'Parameter': ['RandomSeed', 'SimulationWeeks', 'DemandCV'],
        'Value': [42, 52, 0.3]
    })
    
    return {
        'nodes': nodes_df,
        'skus': skus_df,
        'demand': demand_df,
        'leadtimes': leadtimes_df,
        'transport': transport_df,
        'costs': costs_df,
        'policies': policies_df,
        'service_targets': service_df,
        'initial_inventory': initial_inv_df,
        'simulation_params': sim_params_df
    }


def run_optimization_example():
    """
    Complete example of running an optimization.
    """
    print("=" * 70)
    print("MEIO SYSTEM - PROGRAMMATIC USAGE EXAMPLE")
    print("=" * 70)
    print()
    
    # Step 1: Create network data
    print("Step 1: Creating network data...")
    network_data = create_simple_network()
    print(f"  ✓ Network with {len(network_data['nodes'])} nodes")
    print(f"  ✓ {len(network_data['skus'])} SKUs")
    print(f"  ✓ {len(network_data['transport'])} network links")
    print()
    
    # Step 2: Initialize engine
    print("Step 2: Initializing supply chain engine...")
    engine = SupplyChainEngine(
        nodes_df=network_data['nodes'],
        skus_df=network_data['skus'],
        demand_df=network_data['demand'],
        leadtimes_df=network_data['leadtimes'],
        transport_df=network_data['transport'],
        costs_df=network_data['costs'],
        policies_df=network_data['policies'],
        service_targets_df=network_data['service_targets'],
        initial_inventory_df=network_data['initial_inventory'],
        simulation_params_df=network_data['simulation_params']
    )
    print("  ✓ Engine initialized")
    print()
    
    # Step 3: Configure GA
    print("Step 3: Configuring Genetic Algorithm...")
    config = GAConfig(
        population_size=30,
        num_generations=50,
        mutation_rate=0.15,
        top_k_for_sim=3,
        random_seed=42
    )
    print(f"  ✓ Population: {config.population_size}")
    print(f"  ✓ Generations: {config.num_generations}")
    print(f"  ✓ Mutation Rate: {config.mutation_rate}")
    print()
    
    # Step 4: Run optimization
    print("Step 4: Running optimization...")
    print("-" * 70)
    
    def progress_callback(current_gen, total_gen, best_fitness, violations, simulation=False):
        if simulation:
            print(f"  → Running Monte Carlo simulation...")
        elif current_gen % 10 == 0 or current_gen == total_gen:
            print(f"  Gen {current_gen:3d}/{total_gen} | "
                  f"Fitness: {best_fitness:10,.2f} | "
                  f"Violations: {violations}")
    
    optimizer = GeneticOptimizer(
        engine=engine,
        config=config,
        progress_callback=progress_callback
    )
    
    best_solution, convergence_df = optimizer.optimize()
    
    print("-" * 70)
    print("  ✓ Optimization complete")
    print()
    
    # Step 5: Extract results
    print("Step 5: Extracting results...")
    solution_summary = optimizer.get_solution_summary(best_solution)
    
    print(f"  ✓ Total Cost (Analytical): ${solution_summary['total_cost_analytical']:,.2f}/week")
    print(f"  ✓ Total Cost (Simulated):  ${solution_summary['total_cost_simulated']:,.2f}/week")
    print(f"  ✓ Constraint Violations:   {solution_summary['num_violations']}")
    print()
    
    # Step 6: Display detailed results
    print("Step 6: Results Summary")
    print("-" * 70)
    
    # Cost breakdown
    print("\nCost Breakdown:")
    for cost_type, amount in solution_summary['cost_breakdown'].items():
        print(f"  {cost_type:12s}: ${amount:10,.2f}/week")
    
    # Safety factors
    print("\nSafety Factors (Z-values):")
    print(solution_summary['z_values'].to_string(index=False))
    
    # Service levels
    print("\nService Levels:")
    service_cols = ['NodeID', 'SKU', 'FillRate']
    service_data = solution_summary['stock_targets'][service_cols]
    service_data = service_data[service_data['NodeID'].str.contains('REGION')]
    print(service_data.to_string(index=False))
    
    # Stock targets
    print("\nStock Targets (selected nodes):")
    stock_cols = ['NodeID', 'SKU', 'SafetyStock', 'CycleStock', 'BaseStock']
    stock_data = solution_summary['stock_targets'][stock_cols].head(6)
    print(stock_data.to_string(index=False))
    
    # Convergence
    print("\nConvergence Summary:")
    print(f"  Initial Best Fitness: ${convergence_df.iloc[0]['BestFitness']:,.2f}")
    print(f"  Final Best Fitness:   ${convergence_df.iloc[-1]['BestFitness']:,.2f}")
    improvement = (1 - convergence_df.iloc[-1]['BestFitness'] / convergence_df.iloc[0]['BestFitness']) * 100
    print(f"  Improvement:          {improvement:.1f}%")
    
    print()
    print("=" * 70)
    print("EXAMPLE COMPLETE")
    print("=" * 70)
    
    return solution_summary, convergence_df


def main():
    """Main entry point."""
    try:
        solution, convergence = run_optimization_example()
        
        # Optionally save results
        save_results = input("\nSave results to Excel? (y/n): ").strip().lower()
        
        if save_results == 'y':
            # Create Excel output
            with pd.ExcelWriter('example_results.xlsx', engine='openpyxl') as writer:
                solution['z_values'].to_excel(writer, sheet_name='Z_Values', index=False)
                solution['stock_targets'].to_excel(writer, sheet_name='Stock_Targets', index=False)
                solution['flows'].to_excel(writer, sheet_name='Flows', index=False)
                convergence.to_excel(writer, sheet_name='Convergence', index=False)
            
            print("✓ Results saved to 'example_results.xlsx'")
        
    except Exception as e:
        print(f"\n❌ Error: {str(e)}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
