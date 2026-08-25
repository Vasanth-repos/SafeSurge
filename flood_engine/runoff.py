"""
Runoff estimation using SCS-CN (Soil Conservation Service Curve Number)
with cumulative-P / incremental-Q method.
"""

from typing import Dict
import numpy as np


class CellRunoffState:
    def __init__(self, cn_value: float, area_m2: float = 100.0):
        self.cn_value = float(np.clip(cn_value, 30.0, 98.0))
        self.area_m2 = area_m2
        # Max potential retention S (mm)
        self.S = (25400.0 / self.cn_value) - 254.0
        self.Ia = 0.2 * self.S
        self.cumulative_P_mm: float = 0.0
        self.cumulative_Q_mm: float = 0.0

    def compute_incremental_runoff(self, delta_rainfall_mm: float) -> float:
        """
        Takes rainfall received during the current timestep (in mm),
        updates cumulative P and Q, and returns incremental runoff in m^3.
        """
        self.cumulative_P_mm += max(0.0, delta_rainfall_mm)
        P = self.cumulative_P_mm

        if P <= self.Ia:
            Q_cum = 0.0
        else:
            Q_cum = ((P - self.Ia) ** 2) / (P - self.Ia + self.S)

        delta_Q_mm = max(0.0, Q_cum - self.cumulative_Q_mm)
        self.cumulative_Q_mm = Q_cum

        # Convert mm over cell area to m^3
        # 1 mm = 0.001 m -> m^3 = delta_Q_mm * 0.001 * area_m2
        delta_Q_m3 = (delta_Q_mm / 1000.0) * self.area_m2
        return delta_Q_m3

    def reset(self):
        self.cumulative_P_mm = 0.0
        self.cumulative_Q_mm = 0.0
