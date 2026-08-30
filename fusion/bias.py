"""
Layer 13 — Exponentially Weighted Moving Average (EWMA) Bias Estimator:
Estimates smoothed local sensor residual bias (B_t = alpha*q*e + (1-alpha*q)*B_{t-1})
with minimum observation warm-up, large-residual protection, and bounded clamping.
"""

from __future__ import annotations

from fusion.history import SensorHistoryTracker
from fusion.models import SensorBiasState, SensorObservation


def calculate_residual(observed_depth_cm: float, model_depth_cm: float) -> float:
    """e = H_obs - H_model"""
    return float(observed_depth_cm) - float(model_depth_cm)


def update_ewma_bias(
    current_bias_cm: float,
    residual_cm: float,
    alpha: float = 0.3,
    quality: float = 1.0,
    max_bias_cm: float = 50.0,
) -> float:
    """
    Computes quality-weighted EWMA bias update:
    effective_alpha = alpha * quality
    B_t = effective_alpha * e + (1 - effective_alpha) * B_{t-1}
    B_t = clip(B_t, -max_bias_cm, max_bias_cm)
    """
    eff_alpha = max(0.0, min(1.0, float(alpha) * float(quality)))
    new_bias = eff_alpha * float(residual_cm) + (1.0 - eff_alpha) * float(current_bias_cm)
    return max(-max_bias_cm, min(max_bias_cm, new_bias))


class SensorBiasEstimator:
    def __init__(
        self,
        bias_alpha: float = 0.3,
        minimum_bias_observations: int = 3,
        max_residual_for_bias_update_cm: float = 20.0,
        max_bias_cm: float = 50.0,
    ):
        self.bias_alpha = float(bias_alpha)
        self.minimum_bias_observations = int(minimum_bias_observations)
        self.max_residual_for_bias_update_cm = float(max_residual_for_bias_update_cm)
        self.max_bias_cm = float(max_bias_cm)

        self._states: dict[str, SensorBiasState] = {}

    def get_state(self, sensor_id: str) -> SensorBiasState:
        if sensor_id not in self._states:
            self._states[sensor_id] = SensorBiasState(sensor_id=sensor_id)
        return self._states[sensor_id]

    def update_observation(
        self,
        observation: SensorObservation,
        model_depth_cm: float,
        history_tracker: SensorHistoryTracker | None = None,
    ) -> SensorBiasState:
        """
        Updates sensor bias state:
        1. Checks observation validity (ACCEPTED + ONLINE).
        2. Calculates residual.
        3. Records in history tracker.
        4. Checks large-residual threshold (|e| <= max_residual).
        5. Evaluates minimum observation warm-up threshold.
        6. Updates EWMA bias and clamps.
        """
        state = self.get_state(observation.sensor_id)
        residual = calculate_residual(observation.observed_depth_cm, model_depth_cm)

        state.last_residual_cm = residual
        state.last_updated_seconds = observation.timestamp_seconds

        # Record in history tracker for confidence evaluation
        if history_tracker is not None:
            history_tracker.record_observation(
                sensor_id=observation.sensor_id,
                timestamp_seconds=observation.timestamp_seconds,
                model_depth_cm=model_depth_cm,
                observed_depth_cm=observation.observed_depth_cm,
                residual_cm=residual,
            )

        # Gate 1: Check observation status & health
        if observation.measurement_status != "ACCEPTED" or observation.sensor_state != "ONLINE":
            return state

        # Gate 2: Large-residual protection
        if abs(residual) > self.max_residual_for_bias_update_cm:
            # Do NOT update persistent bias with anomalous single-step discrepancy
            return state

        # Increment observation counter
        state.observation_count += 1

        # Gate 3: Minimum observation warm-up
        if state.observation_count >= self.minimum_bias_observations:
            state.is_eligible = True
            state.bias_cm = update_ewma_bias(
                current_bias_cm=state.bias_cm,
                residual_cm=residual,
                alpha=self.bias_alpha,
                quality=observation.quality,
                max_bias_cm=self.max_bias_cm,
            )

        return state

    def reset(self) -> None:
        self._states.clear()
