import pandas as pd
import numpy as np


def generate_final_meio_data(filename="MEIO_Synthetic_Data.xlsx"):
    """
    Generates a high-volume synthetic dataset for the MEIO tool.
    Structure: 3 Plants -> 7 DCs -> 15 Regions.
    """
    with pd.ExcelWriter(filename, engine='openpyxl') as writer:

        # 1. Nodes: NodeID, NodeType, Capacity_Units
        nodes_data = {
            "NodeID": ["PLT_01", "PLT_02", "PLT_03"] + [f"DC_{i:02d}" for i in range(1, 8)] + [f"REG_{i:02d}" for i in range(1, 16)],
            "NodeType": ["plant"]*3 + ["dc"]*7 + ["region"]*15,
            "Capacity_Units": [100000]*3 + [25000]*7 + [0]*15
        }
        pd.DataFrame(nodes_data).to_excel(
            writer, sheet_name="Nodes", index=False)

        # 2. Lanes: LaneID, FromNode, ToNode, LeadTime_Weeks, TransportCost_PerUnit, FixedCost, LaneCapacity_Units
        lanes = []
        # Plants to DCs (Multi-sourcing enabled)
        for dc_idx in range(1, 8):
            for plt_idx in range(1, 4):
                lanes.append([
                    f"L_P{plt_idx}_D{dc_idx}", f"PLT_{plt_idx:02d}", f"DC_{dc_idx:02d}",
                    np.random.uniform(1.5, 3.5), np.random.uniform(
                        0.3, 0.6), 500, 10000
                ])
        # DCs to Regions
        for reg_idx in range(1, 16):
            # Assign each region to a primary and secondary DC
            primary_dc = (reg_idx % 7) + 1
            secondary_dc = ((reg_idx + 1) % 7) + 1
            for dc_idx in [primary_dc, secondary_dc]:
                lanes.append([
                    f"L_D{dc_idx}_R{reg_idx}", f"DC_{dc_idx:02d}", f"REG_{reg_idx:02d}",
                    np.random.uniform(0.5, 1.5), np.random.uniform(
                        0.1, 0.3), 150, 5000
                ])

        pd.DataFrame(lanes, columns=[
            "LaneID", "FromNode", "ToNode", "LeadTime_Weeks",
            "TransportCost_PerUnit", "FixedCost", "LaneCapacity_Units"
        ]).to_excel(writer, sheet_name="Lanes", index=False)

        # 3. SKUs: SKU, HoldingCost_PerUnit, OrderingCost, ShortageCost_PerUnit
        skus_data = {
            "SKU": ["SKU_HIGH_VAL", "SKU_VOLUME"],
            "HoldingCost_PerUnit": [3.50, 0.75],
            "OrderingCost": [200, 50],
            "ShortageCost_PerUnit": [100.0, 15.0]
        }
        pd.DataFrame(skus_data).to_excel(
            writer, sheet_name="SKUs", index=False)

        # 4. Demand: NodeID, SKU, WeeklyMean, WeeklyStdDev
        demand = []
        np.random.seed(42)
        for i in range(1, 16):
            node = f"REG_{i:02d}"
            # High Value SKU Demand
            demand.append([node, "SKU_HIGH_VAL", np.random.randint(
                30, 80), np.random.randint(5, 20)])
            # Volume SKU Demand
            demand.append([node, "SKU_VOLUME", np.random.randint(
                300, 600), np.random.randint(40, 100)])

        pd.DataFrame(demand, columns=["NodeID", "SKU", "WeeklyMean", "WeeklyStdDev"]).to_excel(
            writer, sheet_name="Demand", index=False)

        # 5. Parameters: Parameter, Value
        params_data = {
            "Parameter": ["reviewperiod", "targetfillrate", "simulationweeks", "randomseed"],
            "Value": [1, 0.98, 52, 12345]
        }
        pd.DataFrame(params_data).to_excel(
            writer, sheet_name="Parameters", index=False)

    print(f"Successfully generated {filename} with 100+ data rows.")


if __name__ == "__main__":
    generate_final_meio_data()
