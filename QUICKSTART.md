# 🚀 Quick Start Guide

Get up and running with the MEIO system in 5 minutes!

## ⚡ Super Quick Start

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Verify installation
python test_installation.py

# 3. Run the application
streamlit run main.py
```

That's it! The application will open in your browser at http://localhost:8501

## 📝 Step-by-Step Guide

### 1️⃣ Install Python Dependencies

Make sure you have Python 3.8+ installed, then run:

```bash
pip install -r requirements.txt
```

This installs:
- Streamlit (web UI)
- Pandas (data processing)
- NumPy (numerical computing)
- SciPy (statistical functions)
- OpenPyXL (Excel I/O)
- Matplotlib & Seaborn (visualization)

### 2️⃣ Verify Installation

Run the test script to ensure everything is working:

```bash
python test_installation.py
```

You should see:
```
✓ Streamlit
✓ Pandas
✓ NumPy
✓ SciPy
✓ OpenPyXL
✓ Matplotlib
✓ Seaborn

✅ All packages installed successfully!
```

### 3️⃣ Launch the Application

Start the Streamlit app:

```bash
streamlit run main.py
```

Your browser will automatically open to http://localhost:8501

### 4️⃣ Download the Template

In the app:
1. Look for the sidebar on the left
2. Click "📥 Download Excel Template"
3. Save the file as `MEIO_Template.xlsx`

### 5️⃣ Configure Your Network

Open the downloaded template in Excel and fill in your data:

**Required Sheets:**
1. **Nodes** - Your supply chain network (Plants, DCs, Regions)
2. **SKUs** - Product identifiers
3. **Demand** - Regional demand statistics
4. **LeadTimes** - Transportation times
5. **Transport** - Shipping costs
6. **Costs** - Inventory holding, ordering, and shortage costs
7. **Policies** - Review periods
8. **ServiceTargets** - Target fill rates
9. **InitialInventory** - Starting stock levels
10. **SimulationParams** - Simulation settings

💡 **Tip**: The template includes sample data - you can use it as-is for testing!

### 6️⃣ Upload and Optimize

Back in the app:
1. Click "Choose Excel file" in the sidebar
2. Upload your configured template
3. Adjust optimization settings if desired:
   - Population Size: 50 (default)
   - Generations: 100 (default)
   - Mutation Rate: 0.15 (default)
   - Top K for Simulation: 5 (default)
4. Click "🚀 Run Optimization"

### 7️⃣ Review Results

Watch the real-time progress bar as the GA optimizes your network!

When complete, you'll see:
- **Total Cost**: Analytical and simulated weekly costs
- **Violations**: Number of constraint violations
- **Fill Rate**: Average service level across the network
- **Visualizations**: Cost breakdown, service levels, convergence

### 8️⃣ Download Results

Click "📥 Download Optimization Results (Excel)" to get:
- Optimized safety factors (Z-values)
- Stock targets (safety stock, cycle stock, base stock)
- Sourcing flows (allocation decisions)
- Cost breakdown
- Diagnostics (any constraint violations)
- Convergence history

## 🎯 Try the Programmatic Example

Want to use the system without the UI? Run the example script:

```bash
python example_usage.py
```

This demonstrates how to:
- Create network data programmatically
- Run optimization in a script
- Extract and save results
- Perfect for batch processing or integration

## 🔧 Troubleshooting

### Port Already in Use

If you see "Address already in use":

```bash
streamlit run main.py --server.port 8502
```

### Module Not Found

If you see "ModuleNotFoundError":

```bash
pip install -r requirements.txt --upgrade
```

### Excel File Won't Upload

- Ensure the file is .xlsx format (not .xls)
- Check that all 10 required sheets are present
- Verify column names match exactly (case-sensitive)

### Slow Performance

For large networks:
- Reduce population size (e.g., 30)
- Reduce generations (e.g., 50)
- Reduce simulation weeks in SimulationParams

## 📊 Understanding the Output

### Cost Components

- **Holding Cost**: Storage costs (h × inventory)
- **Ordering Cost**: Fixed costs per order (K × frequency)
- **Shortage Cost**: Penalties for stockouts (p × expected shortage)
- **Transport Cost**: Fixed + variable shipping costs

### Constraint Violations

The optimizer tries to satisfy:
- **Node Capacity**: Total stock ≤ warehouse capacity
- **Service Targets**: Fill rate ≥ target fill rate

Violations are penalized heavily to guide the GA toward feasible solutions.

### Convergence Chart

Shows how the best solution improves over generations:
- **Steep drop**: GA finding better solutions quickly
- **Plateau**: GA converging to optimal
- **Final spike**: Monte Carlo simulation of top candidates

## 🎓 Next Steps

1. **Experiment**: Try different GA parameters
2. **Scale Up**: Add more nodes, SKUs, or links
3. **Customize**: Modify cost parameters, service targets
4. **Integrate**: Use `example_usage.py` as a template for automation

## 📚 Need Help?

- Check the full [README.md](README.md) for detailed documentation
- Review the mathematical formulations in the README
- Examine the sample data in the template

## 💡 Pro Tips

1. **Start Simple**: Begin with the sample network, then gradually add complexity
2. **Seed Consistency**: Use the same RandomSeed for reproducible results
3. **Service vs Cost**: Higher service targets = higher costs (trade-off!)
4. **Constraint Tuning**: Adjust capacity and targets to ensure feasible solutions
5. **Simulation Validation**: Stage B simulation provides realistic cost estimates

---

**Ready to optimize your supply chain? Let's go! 🚀**
