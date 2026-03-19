# Multi-Echelon Inventory Optimization (MEIO)

A sophisticated supply chain optimization system using Genetic Algorithms and Monte Carlo simulation to minimize total costs while meeting service level targets.

## 🎯 Features

- **Multi-Echelon Network**: Optimize across plants, distribution centers, and regional nodes
- **Genetic Algorithm**: Two-stage optimization with analytical evaluation and Monte Carlo validation
- **Advanced Analytics**: 
  - Demand propagation with risk pooling
  - Safety stock optimization
  - Service level guarantees (fill rate)
  - Cost minimization (holding, ordering, transport, shortage)
- **Interactive Dashboard**: Real-time progress tracking and KPI visualization
- **Excel I/O**: Easy data input and comprehensive results export

## 🚀 Quick Start

### Installation

```bash
pip install -r requirements.txt
```

### Running the Application

```bash
streamlit run main.py
```

The application will open in your browser at `http://localhost:8501`

### Using the Sample Data

1. Upload `sample_input.xlsx` (provided)
2. Adjust GA parameters in the sidebar
3. Click "Run Optimization"
4. Download results as Excel

## 📊 Input Data Format

Your Excel file must contain 5 sheets:

### 1. Nodes
| Column | Description |
|--------|-------------|
| NodeID | Unique node identifier |
| NodeType | Plant, DC, or Region |
| Capacity_Units | Maximum inventory capacity |

### 2. Lanes
| Column | Description |
|--------|-------------|
| LaneID | Unique lane identifier |
| FromNode | Source node |
| ToNode | Destination node |
| LeadTime_Weeks | Transportation lead time |
| TransportCost_PerUnit | Variable transport cost |
| FixedCost | Fixed transport cost |
| LaneCapacity_Units | Maximum flow capacity |

### 3. SKUs
| Column | Description |
|--------|-------------|
| SKU | Unique SKU identifier |
| HoldingCost_PerUnit | Annual holding cost per unit |
| OrderingCost | Fixed cost per order |
| ShortageCost_PerUnit | Penalty cost per shortage |

### 4. Demand
| Column | Description |
|--------|-------------|
| NodeID | Node where demand occurs |
| SKU | SKU identifier |
| WeeklyMean | Mean weekly demand |
| WeeklyStdDev | Std deviation of weekly demand |

### 5. Parameters
| Parameter | Description | Typical Value |
|-----------|-------------|---------------|
| reviewperiod | Inventory review period (weeks) | 1 |
| targetfillrate | Target service level | 0.95 |
| simulationweeks | Monte Carlo simulation length | 52 |
| randomseed | Random seed for reproducibility | 42 |

## 🧮 Mathematical Formulations

### Demand Propagation
For each upstream node:
```
μ(node, sku) = Σ(α × μ_downstream)
σ(node, sku) = √(Σ(α × σ_downstream)²)
```

### Effective Lead Time
```
L_eff = Σ(α_i × L_i) / Σ(α_i)
```

### Safety Stock
```
SS = z × σ_weekly × √(L + R)
```
where:
- z = safety factor
- L = lead time
- R = review period

### Fill Rate
```
FR = 1 - (ES / Q)
ES = σ_L × L(z)
L(z) = φ(z) - z(1 - Φ(z))
```

### Total Cost
```
TC = Holding + Ordering + Transport + Shortage

Holding = Σ(h × (SS + CS))
Ordering = Σ(K × λ)
Transport = Σ(c_var × flow + c_fixed)
Shortage = Σ(p × ES × λ)
```

## 🧬 Genetic Algorithm

### Chromosome Encoding
- **Part 1**: Safety factors (z) for each (node, SKU)
- **Part 2**: Sourcing shares (α) for each (lane, SKU)

### Constraints
1. **Sourcing**: Σ(α) = 1 for each node's inbound flows
2. **Node Capacity**: SS + CS ≤ Capacity
3. **Lane Capacity**: Flow ≤ Lane Capacity
4. **Service Level**: Fill Rate ≥ Target

### Two-Stage Evaluation

**Stage A (Analytical)**:
- Fast evaluation using closed-form formulas
- Penalty-based constraint handling
- Applied to all generations

**Stage B (Simulation)**:
- Monte Carlo validation over specified weeks
- Applied to top K candidates in final generation
- Returns realized performance metrics

## 📈 Output Sheets

1. **ResultsZ**: Optimal safety factors by node and SKU
2. **StockTargets**: Inventory targets (SS, CS, base stock, fill rate)
3. **FlowsOptimized**: Sourcing shares and flows by lane
4. **CostBreakdown**: Detailed cost components
5. **Diagnostics**: Performance metrics and validation

## 🎛️ GA Parameters

| Parameter | Description | Recommended Range |
|-----------|-------------|-------------------|
| Population Size | Chromosomes per generation | 50-200 |
| Generations | Evolution iterations | 100-500 |
| Mutation Rate | Gene mutation probability | 0.05-0.2 |
| Crossover Rate | Parent crossover probability | 0.7-0.9 |
| Elite Size | Top solutions preserved | 5-10% of pop |

## 🏗️ Architecture

```
main.py
├── Streamlit UI
├── File I/O (Excel)
├── Progress tracking
└── KPI Dashboard

engine.py
├── InventoryEngine class
├── Demand propagation
├── Analytical metrics
└── Monte Carlo simulation

optimizer.py
├── GeneticOptimizer class
├── Chromosome encoding
├── Two-stage evaluation
└── Genetic operators
```

## 🔬 Example Use Cases

1. **Network Design**: Determine optimal sourcing strategies
2. **Safety Stock Optimization**: Balance costs vs. service levels
3. **Scenario Analysis**: Test different demand patterns
4. **Capacity Planning**: Identify bottlenecks and expansion needs
5. **Cost Reduction**: Minimize total supply chain costs

## 🛠️ Customization

### Modify Cost Functions
Edit `engine.py` → `calculate_costs()` to add custom cost components

### Add Constraints
Edit `optimizer.py` → `_evaluate_fitness_analytical()` to add domain-specific constraints

### Adjust Genetic Operators
Edit `optimizer.py` → `_mutate()` or `_crossover()` for custom evolution strategies

## 📝 Best Practices

1. **Data Quality**: Ensure accurate demand statistics and cost parameters
2. **Parameter Tuning**: Start with default GA settings, then fine-tune
3. **Validation**: Always review simulation results for feasibility
4. **Sensitivity Analysis**: Test with different parameter values
5. **Scalability**: For large networks (>100 nodes), increase population size and generations

## 🐛 Troubleshooting

**Issue**: Optimization returns infeasible solutions
- **Solution**: Check capacity constraints and increase population size

**Issue**: Slow convergence
- **Solution**: Increase mutation rate or decrease population size

**Issue**: Poor fill rates in simulation
- **Solution**: Lower target fill rate or increase safety factors manually

**Issue**: Excel export fails
- **Solution**: Ensure write permissions and close file if open

## 📚 References

- Silver, E. A., Pyke, D. F., & Peterson, R. (1998). *Inventory Management and Production Planning and Scheduling*
- Axsäter, S. (2015). *Inventory Control* (3rd ed.)
- Simchi-Levi, D., Kaminsky, P., & Simchi-Levi, E. (2007). *Designing and Managing the Supply Chain*

## 📄 License

MIT License - Free for educational and commercial use

## 👨‍💻 Author

Senior Supply-Chain Optimization Engineer & Expert Python Developer

---

**Version**: 1.0.0  
**Last Updated**: February 2026
