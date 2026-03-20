"""
Optimizer: Constraint-Aware Genetic Algorithm for MEIO
"""

import numpy as np
import pandas as pd
import time
from typing import Dict, List, Tuple, Optional, Callable
from dataclasses import dataclass
import copy


@dataclass
class GAConfig:
    """Configuration for Genetic Algorithm."""
    population_size: int = 50
    num_generations: int = 100
    mutation_rate: float = 0.15
    crossover_rate: float = 0.8
    elite_fraction: float = 0.1
    tournament_size: int = 3
    top_k_for_sim: int = 5
    random_seed: int = 42
    penalty_multiplier: float = 1000.0


class Chromosome:
    """
    Represents a solution encoding safety factors and sourcing shares.
    """
    
    def __init__(self,
                 z_values: Dict[Tuple[str, str], float],
                 sourcing_shares: Dict[Tuple[str, str, str], float]):
        """
        Initialize chromosome.
        
        Args:
            z_values: Safety factors for each (node, sku)
            sourcing_shares: Sourcing allocation for each (origin, destination, sku)
        """
        self.z_values = z_values
        self.sourcing_shares = sourcing_shares
        self.fitness = None
        self.simulated_fitness = None
        self.analytical_result = None
        self.violations = []
        
    def copy(self) -> 'Chromosome':
        """Create a deep copy of the chromosome."""
        return Chromosome(
            z_values=copy.deepcopy(self.z_values),
            sourcing_shares=copy.deepcopy(self.sourcing_shares)
        )


class GeneticOptimizer:
    """
    Two-stage Genetic Algorithm for Multi-Echelon Inventory Optimization.
    
    Stage A: Analytical evaluation with constraint penalties
    Stage B: Monte Carlo simulation for top K candidates
    """
    
    def __init__(self,
                 engine,
                 config: GAConfig,
                 progress_callback: Optional[Callable] = None):
        """
        Initialize the genetic optimizer.
        
        Args:
            engine: SupplyChainEngine instance
            config: GA configuration
            progress_callback: Optional callback for progress updates
        """
        self.engine = engine
        self.config = config
        self.progress_callback = progress_callback
        
        np.random.seed(config.random_seed)
        
        # Extract decision variables structure
        self._extract_decision_variables()
        
        # Track best solution
        self.best_chromosome = None
        self.best_fitness_history = []
        self.avg_fitness_history = []
        
    def _extract_decision_variables(self):
        """Extract the structure of decision variables from input data."""
        # Z-values: one per (node, sku) pair
        self.z_keys = []
        
        # Get all node-sku combinations from demand propagation
        for node_id in self.engine.nodes['NodeID'].unique():
            for sku in self.engine.skus['SKU'].unique():
                self.z_keys.append((node_id, sku))
        
        # Sourcing shares: one per (origin, destination, sku) with normalization
        self.sourcing_keys = []
        self.sourcing_groups = {}  # (destination, sku) -> list of origins
        
        for _, row in self.engine.transport.iterrows():
            origin = row['Origin']
            destination = row['Destination']
            sku = row['SKU']
            
            key = (origin, destination, sku)
            self.sourcing_keys.append(key)
            
            group_key = (destination, sku)
            if group_key not in self.sourcing_groups:
                self.sourcing_groups[group_key] = []
            self.sourcing_groups[group_key].append(origin)
    
    def _create_random_chromosome(self) -> Chromosome:
        """Create a random chromosome with valid constraints."""
        # Random safety factors (z between 0.5 and 3.0)
        z_values = {key: np.random.uniform(0.5, 3.0) for key in self.z_keys}
        
        # Random sourcing shares (normalized to sum to 1.0 per destination-sku)
        sourcing_shares = {}
        
        for group_key, origins in self.sourcing_groups.items():
            destination, sku = group_key
            
            if len(origins) == 1:
                # Single source: alpha = 1.0
                sourcing_shares[(origins[0], destination, sku)] = 1.0
            else:
                # Multiple sources: random allocation
                raw_shares = np.random.dirichlet(np.ones(len(origins)))
                for i, origin in enumerate(origins):
                    sourcing_shares[(origin, destination, sku)] = raw_shares[i]
        
        return Chromosome(z_values, sourcing_shares)
    
    def _repair_chromosome(self, chromosome: Chromosome):
        """
        Repair chromosome to satisfy hard constraints.
        Ensures sourcing shares sum to 1.0 per destination-sku.
        """
        # Normalize sourcing shares
        for group_key, origins in self.sourcing_groups.items():
            destination, sku = group_key
            
            # Collect shares
            shares = []
            keys = []
            for origin in origins:
                key = (origin, destination, sku)
                shares.append(chromosome.sourcing_shares.get(key, 0.0))
                keys.append(key)
            
            # Normalize
            total = sum(shares)
            if total > 0:
                for i, key in enumerate(keys):
                    chromosome.sourcing_shares[key] = shares[i] / total
            else:
                # Equal allocation if sum is zero
                for key in keys:
                    chromosome.sourcing_shares[key] = 1.0 / len(keys)
        
        # Clamp z-values to reasonable range
        for key in chromosome.z_values:
            chromosome.z_values[key] = np.clip(chromosome.z_values[key], 0.1, 5.0)
    
    def _evaluate_analytical(self, chromosome: Chromosome) -> float:
        """
        Stage A: Analytical evaluation with constraint penalties.
        
        Args:
            chromosome: Solution to evaluate
            
        Returns:
            Fitness score (lower is better)
        """
        result = self.engine.evaluate_solution(
            chromosome.z_values,
            chromosome.sourcing_shares
        )
        
        chromosome.analytical_result = result
        chromosome.violations = result['violations']
        
        # Base cost
        base_cost = result['total_cost']
        
        # Penalty for constraint violations
        penalty = 0.0
        
        for violation in result['violations']:
            if violation['type'] == 'NodeCapacity':
                excess = violation['value'] - violation['limit']
                penalty += self.config.penalty_multiplier * excess
            elif violation['type'] == 'ServiceLevel':
                shortfall = violation['limit'] - violation['value']
                penalty += self.config.penalty_multiplier * shortfall * 100
        
        fitness = base_cost + penalty
        chromosome.fitness = fitness
        
        return fitness
    
    def _evaluate_simulation(self, chromosome: Chromosome) -> float:
        """
        Stage B: Monte Carlo simulation evaluation.
        
        Args:
            chromosome: Solution to simulate
            
        Returns:
            Simulated fitness score
        """
        sim_result = self.engine.simulate_solution(
            chromosome.z_values,
            chromosome.sourcing_shares
        )
        
        simulated_cost = sim_result['total_cost']
        chromosome.simulated_fitness = simulated_cost
        
        return simulated_cost
    
    def _selection_tournament(self, population: List[Chromosome]) -> Chromosome:
        """Tournament selection."""
        tournament = np.random.choice(
            population,
            size=min(self.config.tournament_size, len(population)),
            replace=False
        )
        return min(tournament, key=lambda c: c.fitness)
    
    def _crossover(self, parent1: Chromosome, parent2: Chromosome) -> Tuple[Chromosome, Chromosome]:
        """
        Uniform crossover for both z-values and sourcing shares.
        """
        if np.random.random() > self.config.crossover_rate:
            return parent1.copy(), parent2.copy()
        
        child1 = parent1.copy()
        child2 = parent2.copy()
        
        # Crossover z-values
        for key in self.z_keys:
            if np.random.random() < 0.5:
                child1.z_values[key] = parent2.z_values[key]
                child2.z_values[key] = parent1.z_values[key]
        
        # Crossover sourcing shares (group-wise to maintain normalization)
        for group_key in self.sourcing_groups:
            if np.random.random() < 0.5:
                destination, sku = group_key
                origins = self.sourcing_groups[group_key]
                
                for origin in origins:
                    key = (origin, destination, sku)
                    child1.sourcing_shares[key] = parent2.sourcing_shares[key]
                    child2.sourcing_shares[key] = parent1.sourcing_shares[key]
        
        return child1, child2
    
    def _mutate(self, chromosome: Chromosome):
        """
        Mutation: perturb z-values and sourcing shares.
        """
        # Mutate z-values
        for key in self.z_keys:
            if np.random.random() < self.config.mutation_rate:
                # Add Gaussian noise
                chromosome.z_values[key] += np.random.normal(0, 0.3)
        
        # Mutate sourcing shares (re-randomize some groups)
        for group_key in self.sourcing_groups:
            if np.random.random() < self.config.mutation_rate:
                destination, sku = group_key
                origins = self.sourcing_groups[group_key]
                
                if len(origins) > 1:
                    # Re-randomize this group
                    raw_shares = np.random.dirichlet(np.ones(len(origins)))
                    for i, origin in enumerate(origins):
                        chromosome.sourcing_shares[(origin, destination, sku)] = raw_shares[i]
        
        # Repair after mutation
        self._repair_chromosome(chromosome)
    
    def optimize(self) -> Tuple[Chromosome, pd.DataFrame]:
        """
        Run the two-stage genetic algorithm.
        
        Returns:
            (best_chromosome, convergence_history)
        """
        # Initialize population
        population = [self._create_random_chromosome() 
                     for _ in range(self.config.population_size)]
        
        # Evaluate initial population
        for chromosome in population:
            self._evaluate_analytical(chromosome)
        
        # Track convergence
        convergence_data = []
        
        # Main GA loop
        for generation in range(self.config.num_generations):
            # Sort by fitness
            population.sort(key=lambda c: c.fitness)
            
            # Track best and average
            best_fitness = population[0].fitness
            avg_fitness = np.mean([c.fitness for c in population])
            
            self.best_fitness_history.append(best_fitness)
            self.avg_fitness_history.append(avg_fitness)
            
            convergence_data.append({
                'Generation': generation,
                'BestFitness': best_fitness,
                'AvgFitness': avg_fitness,
                'Violations': population[0].analytical_result['num_violations']
            })
            
            # Update progress
            if self.progress_callback:
                self.progress_callback(
                    generation + 1,
                    self.config.num_generations,
                    best_fitness,
                    population[0].analytical_result['num_violations']
                )
            
            # Yield the GIL to prevent Streamlit websocket timeout during heavy processing
            time.sleep(0.01)
            
            # Elitism: keep best individuals
            elite_count = max(1, int(self.config.elite_fraction * self.config.population_size))
            new_population = population[:elite_count]
            
            # Generate offspring
            while len(new_population) < self.config.population_size:
                # Selection
                parent1 = self._selection_tournament(population)
                parent2 = self._selection_tournament(population)
                
                # Crossover
                child1, child2 = self._crossover(parent1, parent2)
                
                # Mutation
                self._mutate(child1)
                self._mutate(child2)
                
                # Evaluate
                self._evaluate_analytical(child1)
                self._evaluate_analytical(child2)
                
                new_population.extend([child1, child2])
            
            # Trim to population size
            population = new_population[:self.config.population_size]
        
        # Final sort
        population.sort(key=lambda c: c.fitness)
        
        # Stage B: Simulate top K candidates
        top_k = min(self.config.top_k_for_sim, len(population))
        top_candidates = population[:top_k]
        
        if self.progress_callback:
            self.progress_callback(
                self.config.num_generations,
                self.config.num_generations,
                population[0].fitness,
                population[0].analytical_result['num_violations'],
                simulation=True
            )
        
        for i, chromosome in enumerate(top_candidates):
            self._evaluate_simulation(chromosome)
            # Yield the GIL to prevent Streamlit websocket timeout
            time.sleep(0.01)
        
        # Select best based on simulation
        top_candidates.sort(key=lambda c: c.simulated_fitness if c.simulated_fitness else float('inf'))
        self.best_chromosome = top_candidates[0]
        
        convergence_df = pd.DataFrame(convergence_data)
        
        return self.best_chromosome, convergence_df
    
    def get_solution_summary(self, chromosome: Chromosome) -> Dict:
        """
        Extract detailed summary from a chromosome solution.
        
        Args:
            chromosome: Solution to summarize
            
        Returns:
            Dictionary with solution details
        """
        analytical = chromosome.analytical_result
        
        # Build z-values DataFrame
        z_data = []
        for (node, sku), z in chromosome.z_values.items():
            z_data.append({'NodeID': node, 'SKU': sku, 'Z': z})
        z_df = pd.DataFrame(z_data)
        
        # Build sourcing flows DataFrame
        flow_data = []
        for (origin, destination, sku), alpha in chromosome.sourcing_shares.items():
            flow_data.append({
                'Origin': origin,
                'Destination': destination,
                'SKU': sku,
                'SourcingShare': alpha
            })
        flows_df = pd.DataFrame(flow_data)
        
        # Cost breakdown
        results_df = analytical['results']
        cost_breakdown = {
            'Holding': results_df['HoldingCost'].sum(),
            'Ordering': results_df['OrderingCost'].sum(),
            'Shortage': results_df['ShortageCost'].sum(),
            'Transport': results_df['TransportCost'].sum(),
            'Total': results_df['TotalCost'].sum()
        }
        
        # Violations
        violations_df = pd.DataFrame(chromosome.violations) if chromosome.violations else pd.DataFrame()
        
        return {
            'z_values': z_df,
            'stock_targets': results_df,
            'flows': flows_df,
            'cost_breakdown': cost_breakdown,
            'violations': violations_df,
            'total_cost_analytical': analytical['total_cost'],
            'total_cost_simulated': chromosome.simulated_fitness,
            'num_violations': analytical['num_violations']
        }
