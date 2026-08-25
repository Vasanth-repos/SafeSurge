"""
Mass conservation diagnostic and water balance verification.
"""

from typing import Dict, Any, List


class MassBalanceDiagnostic:
    def __init__(self, tolerance_m3: float = 0.05):
        self.tolerance_m3 = tolerance_m3
        self.history: List[Dict[str, Any]] = []
        self.cumulative_input_m3: float = 0.0
        self.cumulative_drained_m3: float = 0.0
        self.cumulative_boundary_outflow_m3: float = 0.0

    def record_step(
        self,
        step_index: int,
        timestep_input_m3: float,
        current_total_storage_m3: float,
        timestep_drained_m3: float,
        timestep_boundary_outflow_m3: float,
    ) -> Dict[str, Any]:
        """
        Calculates cumulative balance error:
        Balance_Error = Total_Input - (Current_Storage + Total_Drained + Total_Boundary_Outflow)
        """
        self.cumulative_input_m3 += timestep_input_m3
        self.cumulative_drained_m3 += timestep_drained_m3
        self.cumulative_boundary_outflow_m3 += timestep_boundary_outflow_m3

        accounted_for_m3 = (
            current_total_storage_m3
            + self.cumulative_drained_m3
            + self.cumulative_boundary_outflow_m3
        )
        balance_error_m3 = self.cumulative_input_m3 - accounted_for_m3

        status = "PASS" if abs(balance_error_m3) <= self.tolerance_m3 else "FAIL"

        entry = {
            "step": step_index,
            "input_total_m3": round(self.cumulative_input_m3, 4),
            "storage_total_m3": round(current_total_storage_m3, 4),
            "drained_total_m3": round(self.cumulative_drained_m3, 4),
            "boundary_outflow_m3": round(self.cumulative_boundary_outflow_m3, 4),
            "balance_error_m3": round(balance_error_m3, 6),
            "status": status,
        }
        self.history.append(entry)
        return entry

    def reset(self):
        self.history.clear()
        self.cumulative_input_m3 = 0.0
        self.cumulative_drained_m3 = 0.0
        self.cumulative_boundary_outflow_m3 = 0.0
