"""
Supply Chain Engine: Demand Propagation, Safety Stock, and Simulation Logic
"""

import numpy as np
import pandas as pd
from scipy.stats import norm
from typing import Dict, List, Tuple, Optional
import warnings

warnings.filterwarnings('ignore')


class SupplyChainEngine:
    """
    Core engine for multi-echelon inventory optimization calculations.
    Implements demand propagation, safety stock, service levels, and cost modeling.
    """
    
    def __init__(self, 
                 nodes_df: pd.DataFrame,
                 skus_df: pd.DataFrame,
                 demand_df: pd.DataFrame,
                 leadtimes_df: pd.DataFrame,
                 transport_df: pd.DataFrame,
                 costs_df: pd.DataFrame,
                 policies_df: pd.DataFrame,
                 service_targets_df: pd.DataFrame,
                 initial_inventory_df: pd.DataFrame,
                 simulation_params_df: pd.DataFrame):
        """
        Initialize the supply chain engine with all input data.
        """
        self.nodes = nodes_df
        self.skus = skus_df
        self.demand = demand_df
        self.leadtimes = leadtimes_df
        self.transport = transport_df
        self.costs = costs_df
        self.policies = policies_df
        self.service_targets = service_targets_df
        self.initial_inventory = initial_inventory_df
        self.simulation_params = simulation_params_df
        
        # Parse simulation parameters
        self._parse_simulation_params()
        
        # Build network topology
        self._build_network_topology()
        
    def _parse_simulation_params(self):
        """Extract simulation parameters from input DataFrame."""
        params = self.simulation_params.set_index('Parameter')['Value'].to_dict()
        self.random_seed = int(params.get('RandomSeed', 42))
        self.simulation_weeks = int(params.get('SimulationWeeks', 52))
        self.demand_cv = float(params.get('DemandCV', 0.3))
        
    def _build_network_topology(self):
        """
        Build network topology: parent-child relationships and flow paths.
        """
        # Create node lookup
        self.node_info = self.nodes.set_index('NodeID').to_dict('index')
        
        # Build adjacency structure
        self.children = {}  # node -> list of child nodes
        self.parents = {}   # node -> list of parent nodes
        
        for _, row in self.transport.iterrows():
            origin = row['Origin']
            destination = row['Destination']
            
            if origin not in self.children:
                self.children[origin] = []
            self.children[origin].append(destination)
            
            if destination not in self.parents:
                self.parents[destination] = []
            self.parents[destination].append(origin)
            
    def normal_loss_function(self, z: float) -> float:
        """
        Calculate Normal Loss Function: L(z) = φ(z) - z(1-Φ(z))
        
        Args:
            z: Safety factor (z-score)
            
        Returns:
            Loss function value
        """
        phi_z = norm.pdf(z)
        Phi_z = norm.cdf(z)
        return phi_z - z * (1 - Phi_z)
    
    def propagate_demand(self, 
                         sourcing_shares: Dict[Tuple[str, str, str], float]) -> pd.DataFrame:
        """
        Propagate demand from regions (sinks) to plants (sources) using BOM explosion.
        
        Args:
            sourcing_shares: Dict mapping (origin, destination, sku) -> alpha (share)
            
        Returns:
            DataFrame with propagated demand statistics for each (node, sku)
        """
        # Initialize with sink demand
        demand_stats = []
        
        # Start with regional demand (sinks)
        for _, row in self.demand.iterrows():
            node = row['NodeID']
            sku = row['SKU']
            mean_weekly = row['MeanWeekly']
            std_weekly = row['StdWeekly']
            
            demand_stats.append({
                'NodeID': node,
                'SKU': sku,
                'MeanWeekly': mean_weekly,
                'StdWeekly': std_weekly,
                'NodeType': self.node_info[node]['NodeType']
            })
        
        demand_df = pd.DataFrame(demand_stats)
        
        # Propagate upstream using topological sort (reverse BFS)
        processed = set(demand_df['NodeID'].unique())
        
        # Get all nodes that need demand propagation (DCs and Plants)
        all_nodes = set(self.nodes['NodeID'].unique())
        nodes_to_process = all_nodes - processed
        
        max_iterations = 10
        iteration = 0
        
        while nodes_to_process and iteration < max_iterations:
            iteration += 1
            new_processed = set()
            
            for node in nodes_to_process:
                # Check if all children have been processed
                children = self.children.get(node, [])
                if not children:
                    continue
                    
                if all(child in processed for child in children):
                    # Propagate demand from children
                    for sku in self.skus['SKU'].unique():
                        child_demands = []
                        
                        for child in children:
                            # Get sourcing share
                            key = (node, child, sku)
                            alpha = sourcing_shares.get(key, 0.0)
                            
                            # Get child demand
                            child_demand = demand_df[
                                (demand_df['NodeID'] == child) & 
                                (demand_df['SKU'] == sku)
                            ]
                            
                            if not child_demand.empty and alpha > 0:
                                mean_child = child_demand.iloc[0]['MeanWeekly']
                                std_child = child_demand.iloc[0]['StdWeekly']
                                
                                child_demands.append({
                                    'mean': mean_child * alpha,
                                    'std': std_child * alpha
                                })
                        
                        if child_demands:
                            # Risk pooling: sum means, sqrt of sum of variances
                            total_mean = sum(d['mean'] for d in child_demands)
                            total_std = np.sqrt(sum(d['std']**2 for d in child_demands))
                            
                            demand_stats.append({
                                'NodeID': node,
                                'SKU': sku,
                                'MeanWeekly': total_mean,
                                'StdWeekly': total_std,
                                'NodeType': self.node_info[node]['NodeType']
                            })
                    
                    new_processed.add(node)
            
            processed.update(new_processed)
            nodes_to_process -= new_processed
        
        return pd.DataFrame(demand_stats)
    
    def calculate_effective_leadtime(self,
                                     node: str,
                                     sku: str,
                                     sourcing_shares: Dict[Tuple[str, str, str], float]) -> float:
        """
        Calculate effective lead time: L = Σ(α(u→n) · LT(u→n))
        
        Args:
            node: Destination node
            sku: SKU identifier
            sourcing_shares: Sourcing allocation
            
        Returns:
            Effective lead time in weeks
        """
        parents = self.parents.get(node, [])
        if not parents:
            return 0.0
        
        total_lt = 0.0
        for parent in parents:
            key = (parent, node, sku)
            alpha = sourcing_shares.get(key, 0.0)
            
            # Get lead time
            lt_row = self.leadtimes[
                (self.leadtimes['Origin'] == parent) &
                (self.leadtimes['Destination'] == node) &
                (self.leadtimes['SKU'] == sku)
            ]
            
            if not lt_row.empty:
                lt_mean = lt_row.iloc[0]['LeadTimeMean']
                total_lt += alpha * lt_mean
        
        return total_lt
    
    def calculate_safety_stock(self,
                               node: str,
                               sku: str,
                               z: float,
                               demand_mean: float,
                               demand_std: float,
                               lead_time: float) -> Tuple[float, float]:
        """
        Calculate safety stock and demand over lead time.
        
        Args:
            node: Node identifier
            sku: SKU identifier
            z: Safety factor
            demand_mean: Mean weekly demand
            demand_std: Std dev of weekly demand
            lead_time: Lead time in weeks
            
        Returns:
            (safety_stock, sigma_L)
        """
        # Demand over lead time
        sigma_L = demand_std * np.sqrt(lead_time) if lead_time > 0 else 0.0
        
        # Safety stock
        ss = z * sigma_L
        
        return ss, sigma_L
    
    def calculate_service_level(self,
                                z: float,
                                sigma_L: float,
                                demand_mean: float,
                                review_period: float) -> Tuple[float, float]:
        """
        Calculate fill rate and expected shortage.
        
        FR ≈ 1 - ES/(μ_weekly · ReviewPeriod)
        ES = σ_L · L(z)
        
        Args:
            z: Safety factor
            sigma_L: Std dev of demand over lead time
            demand_mean: Mean weekly demand
            review_period: Review period in weeks
            
        Returns:
            (fill_rate, expected_shortage)
        """
        # Expected shortage
        loss = self.normal_loss_function(z)
        ES = sigma_L * loss
        
        # Fill rate
        period_demand = demand_mean * review_period
        if period_demand > 0:
            fill_rate = 1 - (ES / period_demand)
        else:
            fill_rate = 1.0
        
        # Ensure fill rate is in [0, 1]
        fill_rate = max(0.0, min(1.0, fill_rate))
        
        return fill_rate, ES
    
    def calculate_cycle_stock(self,
                             demand_mean: float,
                             review_period: float,
                             order_quantity: Optional[float] = None) -> float:
        """
        Calculate cycle stock: CS = Q_eff / 2 where Q_eff = μ_weekly · ReviewPeriod
        
        Args:
            demand_mean: Mean weekly demand
            review_period: Review period in weeks
            order_quantity: Optional fixed order quantity
            
        Returns:
            Cycle stock
        """
        if order_quantity is not None:
            Q_eff = order_quantity
        else:
            Q_eff = demand_mean * review_period
        
        cs = Q_eff / 2.0
        return cs
    
    def calculate_costs(self,
                       node: str,
                       sku: str,
                       safety_stock: float,
                       cycle_stock: float,
                       expected_shortage: float,
                       demand_mean: float,
                       review_period: float,
                       sourcing_shares: Dict[Tuple[str, str, str], float]) -> Dict[str, float]:
        """
        Calculate all cost components for a (node, sku) pair.
        
        Weekly Cost = h(SS + CS) + Kλ + p(ES) + TransportCosts
        
        Args:
            node: Node identifier
            sku: SKU identifier
            safety_stock: Safety stock units
            cycle_stock: Cycle stock units
            expected_shortage: Expected shortage per period
            demand_mean: Mean weekly demand
            review_period: Review period
            sourcing_shares: Sourcing allocation
            
        Returns:
            Dictionary of cost components
        """
        # Get cost parameters
        cost_row = self.costs[
            (self.costs['NodeID'] == node) &
            (self.costs['SKU'] == sku)
        ]
        
        if cost_row.empty:
            return {
                'holding': 0.0,
                'ordering': 0.0,
                'shortage': 0.0,
                'transport': 0.0,
                'total': 0.0
            }
        
        h = cost_row.iloc[0]['HoldingCostPerUnit']  # Weekly holding cost
        K = cost_row.iloc[0]['OrderingCost']  # Fixed ordering cost
        p = cost_row.iloc[0]['ShortageCostPerUnit']  # Shortage penalty
        
        # Holding cost
        holding_cost = h * (safety_stock + cycle_stock)
        
        # Ordering cost (frequency)
        if review_period > 0:
            lambda_freq = 1.0 / review_period  # Orders per week
        else:
            lambda_freq = 0.0
        ordering_cost = K * lambda_freq
        
        # Shortage cost
        shortage_cost = p * expected_shortage
        
        # Transport costs (fixed + variable)
        transport_cost = 0.0
        parents = self.parents.get(node, [])
        
        for parent in parents:
            key = (parent, node, sku)
            alpha = sourcing_shares.get(key, 0.0)
            
            transport_row = self.transport[
                (self.transport['Origin'] == parent) &
                (self.transport['Destination'] == node) &
                (self.transport['SKU'] == sku)
            ]
            
            if not transport_row.empty and alpha > 0:
                fixed_cost = transport_row.iloc[0]['FixedCostPerShipment']
                var_cost = transport_row.iloc[0]['VariableCostPerUnit']
                
                # Flow quantity
                flow_qty = demand_mean * alpha
                
                # Shipment frequency approximation
                Q_eff = demand_mean * review_period
                if Q_eff > 0:
                    shipments_per_week = flow_qty / Q_eff
                else:
                    shipments_per_week = 0.0
                
                transport_cost += fixed_cost * shipments_per_week + var_cost * flow_qty
        
        total_cost = holding_cost + ordering_cost + shortage_cost + transport_cost
        
        return {
            'holding': holding_cost,
            'ordering': ordering_cost,
            'shortage': shortage_cost,
            'transport': transport_cost,
            'total': total_cost
        }
    
    def evaluate_solution(self,
                         z_values: Dict[Tuple[str, str], float],
                         sourcing_shares: Dict[Tuple[str, str, str], float]) -> Dict:
        """
        Analytically evaluate a complete solution.
        
        Args:
            z_values: Safety factors for each (node, sku)
            sourcing_shares: Sourcing allocation for each (origin, destination, sku)
            
        Returns:
            Dictionary with detailed results and constraint violations
        """
        # Propagate demand
        demand_df = self.propagate_demand(sourcing_shares)
        
        results = []
        total_cost = 0.0
        violations = []
        
        # Process each node-SKU combination
        for _, demand_row in demand_df.iterrows():
            node = demand_row['NodeID']
            sku = demand_row['SKU']
            demand_mean = demand_row['MeanWeekly']
            demand_std = demand_row['StdWeekly']
            
            # Get safety factor
            z = z_values.get((node, sku), 1.65)  # Default z=1.65 (95% service)
            
            # Get review period
            policy_row = self.policies[
                (self.policies['NodeID'] == node) &
                (self.policies['SKU'] == sku)
            ]
            review_period = policy_row.iloc[0]['ReviewPeriod'] if not policy_row.empty else 1.0
            
            # Calculate lead time
            lead_time = self.calculate_effective_leadtime(node, sku, sourcing_shares)
            
            # Safety stock
            ss, sigma_L = self.calculate_safety_stock(
                node, sku, z, demand_mean, demand_std, lead_time
            )
            
            # Service level
            fill_rate, ES = self.calculate_service_level(
                z, sigma_L, demand_mean, review_period
            )
            
            # Cycle stock
            cs = self.calculate_cycle_stock(demand_mean, review_period)
            
            # Costs
            costs = self.calculate_costs(
                node, sku, ss, cs, ES, demand_mean, review_period, sourcing_shares
            )
            
            # Check constraints
            # 1. Node capacity
            node_capacity = self.node_info[node].get('Capacity', float('inf'))
            current_inventory = ss + cs
            
            if current_inventory > node_capacity:
                violations.append({
                    'type': 'NodeCapacity',
                    'node': node,
                    'sku': sku,
                    'value': current_inventory,
                    'limit': node_capacity
                })
            
            # 2. Service level target
            service_target_row = self.service_targets[
                (self.service_targets['NodeID'] == node) &
                (self.service_targets['SKU'] == sku)
            ]
            
            if not service_target_row.empty:
                target = service_target_row.iloc[0]['TargetFillRate']
                if fill_rate < target - 0.001:  # Small tolerance
                    violations.append({
                        'type': 'ServiceLevel',
                        'node': node,
                        'sku': sku,
                        'value': fill_rate,
                        'limit': target
                    })
            
            results.append({
                'NodeID': node,
                'SKU': sku,
                'Z': z,
                'SafetyStock': ss,
                'CycleStock': cs,
                'BaseStock': ss + cs,
                'LeadTime': lead_time,
                'FillRate': fill_rate,
                'ExpectedShortage': ES,
                'DemandMean': demand_mean,
                'DemandStd': demand_std,
                'HoldingCost': costs['holding'],
                'OrderingCost': costs['ordering'],
                'ShortageCost': costs['shortage'],
                'TransportCost': costs['transport'],
                'TotalCost': costs['total']
            })
            
            total_cost += costs['total']
        
        return {
            'results': pd.DataFrame(results),
            'total_cost': total_cost,
            'violations': violations,
            'num_violations': len(violations)
        }
    
    def simulate_solution(self,
                         z_values: Dict[Tuple[str, str], float],
                         sourcing_shares: Dict[Tuple[str, str, str], float],
                         num_weeks: Optional[int] = None,
                         random_seed: Optional[int] = None) -> Dict:
        """
        Run Monte Carlo simulation to estimate realized costs and service.
        
        Args:
            z_values: Safety factors
            sourcing_shares: Sourcing allocation
            num_weeks: Number of weeks to simulate (default from params)
            random_seed: Random seed for reproducibility (default from params)
            
        Returns:
            Dictionary with simulation results
        """
        if num_weeks is None:
            num_weeks = self.simulation_weeks
        if random_seed is None:
            random_seed = self.random_seed
        
        np.random.seed(random_seed)
        
        # Get analytical solution for initial setup
        analytical = self.evaluate_solution(z_values, sourcing_shares)
        results_df = analytical['results']
        
        # Initialize inventory levels
        inventory = {}
        for _, row in results_df.iterrows():
            node = row['NodeID']
            sku = row['SKU']
            inventory[(node, sku)] = row['BaseStock']
        
        # Track metrics
        stockouts = {(r['NodeID'], r['SKU']): 0 for _, r in results_df.iterrows()}
        total_demand_served = {(r['NodeID'], r['SKU']): 0 for _, r in results_df.iterrows()}
        total_demand = {(r['NodeID'], r['SKU']): 0 for _, r in results_df.iterrows()}
        holding_costs = []
        shortage_costs = []
        
        # Simulate week by week
        for week in range(num_weeks):
            week_holding_cost = 0.0
            week_shortage_cost = 0.0
            
            for _, row in results_df.iterrows():
                node = row['NodeID']
                sku = row['SKU']
                key = (node, sku)
                
                # Generate demand (lognormal to avoid negative)
                mean = row['DemandMean']
                std = row['DemandStd']
                
                if std > 0 and mean > 0:
                    # Lognormal parameters
                    cv = std / mean
                    sigma_ln = np.sqrt(np.log(1 + cv**2))
                    mu_ln = np.log(mean) - 0.5 * sigma_ln**2
                    demand = np.random.lognormal(mu_ln, sigma_ln)
                else:
                    demand = mean
                
                total_demand[key] += demand
                
                # Serve demand
                served = min(inventory[key], demand)
                shortage = max(0, demand - inventory[key])
                
                total_demand_served[key] += served
                if shortage > 0:
                    stockouts[key] += 1
                
                # Update inventory
                inventory[key] = max(0, inventory[key] - demand)
                
                # Replenishment (simplified: order up to base stock)
                base_stock = row['BaseStock']
                order_qty = base_stock - inventory[key]
                
                # Receive order (assume instant for simplicity, could add lead time delay)
                inventory[key] += order_qty
                
                # Costs
                cost_row = self.costs[
                    (self.costs['NodeID'] == node) &
                    (self.costs['SKU'] == sku)
                ]
                
                if not cost_row.empty:
                    h = cost_row.iloc[0]['HoldingCostPerUnit']
                    p = cost_row.iloc[0]['ShortageCostPerUnit']
                    
                    week_holding_cost += h * inventory[key]
                    week_shortage_cost += p * shortage
            
            holding_costs.append(week_holding_cost)
            shortage_costs.append(week_shortage_cost)
        
        # Calculate realized service levels
        realized_fill_rates = {}
        for key in total_demand:
            if total_demand[key] > 0:
                realized_fill_rates[key] = total_demand_served[key] / total_demand[key]
            else:
                realized_fill_rates[key] = 1.0
        
        avg_holding_cost = np.mean(holding_costs)
        avg_shortage_cost = np.mean(shortage_costs)
        total_simulated_cost = avg_holding_cost + avg_shortage_cost
        
        return {
            'total_cost': total_simulated_cost,
            'avg_holding_cost': avg_holding_cost,
            'avg_shortage_cost': avg_shortage_cost,
            'realized_fill_rates': realized_fill_rates,
            'stockout_frequencies': stockouts,
            'num_weeks': num_weeks
        }

class InteractiveSimulator:
    """
    Step-by-step tracking simulator for Streamlit interactive scenarios.
    Allows advancing week-by-week, observing outputs, and modifying demand inputs mid-run.
    """
    def __init__(self, engine: SupplyChainEngine, z_values: Dict[Tuple[str, str], float], sourcing_shares: Dict[Tuple[str, str, str], float], random_seed: Optional[int] = None):
        self.engine = engine
        self.z_values = z_values
        self.sourcing_shares = sourcing_shares
        
        np.random.seed(random_seed or engine.random_seed)
        
        self.analytical = engine.evaluate_solution(z_values, sourcing_shares)
        self.results_df = self.analytical['results']
        
        self.inventory = {}
        for _, row in self.results_df.iterrows():
            self.inventory[(row['NodeID'], row['SKU'])] = row['BaseStock']
            
        self.stockouts = {(r['NodeID'], r['SKU']): 0 for _, r in self.results_df.iterrows()}
        self.total_demand_served = {(r['NodeID'], r['SKU']): 0 for _, r in self.results_df.iterrows()}
        self.total_demand = {(r['NodeID'], r['SKU']): 0 for _, r in self.results_df.iterrows()}
        
        self.weekly_results = []
        self.current_week = 0

    def step(self, week_overrides: Optional[Dict[Tuple[str, str], Dict[str, float]]] = None) -> Dict:
        """
        Simulates exactly one week, applying any overrides (tweaks) to mean/std values.
        Returns the data for that week.
        """
        week_overrides = week_overrides or {}
        week_holding_cost = 0.0
        week_shortage_cost = 0.0
        
        week_data = {
            'Week': self.current_week,
            'NodeDetails': []
        }
        
        for _, row in self.results_df.iterrows():
            node = row['NodeID']
            sku = row['SKU']
            key = (node, sku)
            
            # Apply overrides
            override = week_overrides.get(key, {})
            mean = override.get('DemandMean', row['DemandMean'])
            std = override.get('DemandStd', row['DemandStd'])
            
            # Generate demand
            if std > 0 and mean > 0:
                cv = std / mean
                sigma_ln = np.sqrt(np.log(1 + cv**2))
                mu_ln = np.log(mean) - 0.5 * sigma_ln**2
                demand = np.random.lognormal(mu_ln, sigma_ln)
            else:
                demand = mean
                
            self.total_demand[key] += demand
            
            served = min(self.inventory[key], demand)
            shortage = max(0, demand - self.inventory[key])
            
            self.total_demand_served[key] += served
            if shortage > 0:
                self.stockouts[key] += 1
                
            self.inventory[key] = max(0, self.inventory[key] - demand)
            
            base_stock = row['BaseStock']
            order_qty = base_stock - self.inventory[key]
            self.inventory[key] += order_qty
            
            cost_row = self.engine.costs[
                (self.engine.costs['NodeID'] == node) &
                (self.engine.costs['SKU'] == sku)
            ]
            
            h = cost_row.iloc[0]['HoldingCostPerUnit'] if not cost_row.empty else 0.0
            p = cost_row.iloc[0]['ShortageCostPerUnit'] if not cost_row.empty else 0.0
            
            hc = h * self.inventory[key]
            sc = p * shortage
            
            week_holding_cost += hc
            week_shortage_cost += sc
            
            week_data['NodeDetails'].append({
                'NodeID': node,
                'SKU': sku,
                'Demand': demand,
                'Served': served,
                'Shortage': shortage,
                'EndingInventory': self.inventory[key],
                'HoldingCost': hc,
                'ShortageCost': sc
            })
            
        week_data['TotalHoldingCost'] = week_holding_cost
        week_data['TotalShortageCost'] = week_shortage_cost
        week_data['TotalCost'] = week_holding_cost + week_shortage_cost
        
        self.weekly_results.append(week_data)
        self.current_week += 1
        
        return week_data
        
    def get_summary(self) -> Dict:
        """
        Returns average summary across all completed weeks.
        """
        holding_costs = [w['TotalHoldingCost'] for w in self.weekly_results]
        shortage_costs = [w['TotalShortageCost'] for w in self.weekly_results]
        realized_fill_rates = {}
        for key in self.total_demand:
            if self.total_demand[key] > 0:
                realized_fill_rates[key] = self.total_demand_served[key] / self.total_demand[key]
            else:
                realized_fill_rates[key] = 1.0
                 
        return {
            'total_cost': np.mean(holding_costs) + np.mean(shortage_costs) if holding_costs else 0.0,
            'avg_holding_cost': np.mean(holding_costs) if holding_costs else 0.0,
            'avg_shortage_cost': np.mean(shortage_costs) if shortage_costs else 0.0,
            'realized_fill_rates': realized_fill_rates,
            'stockout_frequencies': self.stockouts,
            'num_weeks': self.current_week
        }
