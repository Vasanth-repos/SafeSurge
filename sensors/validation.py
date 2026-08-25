"""
Layer 12 — Sensor Telemetry Validation Engine:
Enforces identity, temporal, physical range, rate-of-rise, and float-switch
consistency checks to produce ACCEPTED/REJECTED verdicts with audit tracking.
"""

from __future__ import annotations

from typing import Dict, List, Optional, Tuple, Any
from sensors.models import (
    SensorState,
    MeasurementStatus,
    RejectionReason,
    SensorEnvelope,
    ValidationResult,
)
from sensors.registry import SensorRegistry, SensorConfig
from sensors.ultrasonic import process_measurement
from sensors.float_switch import validate_float_consistency
from sensors.health import SensorHealthTracker


def validate_rate_of_rise(
    previous_level_cm: float,
    previous_timestamp_seconds: int,
    current_level_cm: float,
    current_timestamp_seconds: int,
    max_rate_cm_per_second: float = 2.0,
    max_gap_seconds: int = 30,
) -> bool:
    """
    Validates rate-of-rise plausibility:
    - dt <= 0: Invalid temporal progression.
    - dt > max_gap_seconds: Time gap too large for strict rate checking -> passes.
    - rate <= 0: Falling/stable water is allowed.
    - rate > 0: Validates rate <= max_rate_cm_per_second.
    """
    dt = current_timestamp_seconds - previous_timestamp_seconds
    if dt <= 0:
        return False

    if dt > max_gap_seconds:
        return True

    rate = (current_level_cm - previous_level_cm) / dt
    if rate <= 0:
        return True

    return rate <= max_rate_cm_per_second


class SensorValidator:
    def __init__(
        self,
        registry: SensorRegistry,
        max_rate_cm_per_second: float = 2.0,
        max_rate_gap_seconds: int = 30,
        stale_after_seconds: int = 30,
        offline_after_seconds: int = 180,
    ):
        self.registry = registry
        self.max_rate_cm_per_second = max_rate_cm_per_second
        self.max_rate_gap_seconds = max_rate_gap_seconds

        self.health_tracker = SensorHealthTracker(
            stale_after_seconds=stale_after_seconds,
            offline_after_seconds=offline_after_seconds,
        )

        # Stateful memory:
        # (sensor_id, boot_id) -> last sequence
        self._last_sequence: Dict[Tuple[str, str], int] = {}

        # sensor_id -> (last_accepted_level_cm, last_accepted_measured_at_seconds)
        self._last_accepted: Dict[str, Tuple[float, int]] = {}

        # Audit history
        self.audit_log: List[ValidationResult] = []

    def reset(self) -> None:
        self._last_sequence.clear()
        self._last_accepted.clear()
        self.health_tracker.reset()
        self.audit_log.clear()

    def validate(self, envelope: SensorEnvelope) -> ValidationResult:
        sid = envelope.sensor_id
        boot_id = envelope.boot_id
        seq = envelope.sequence
        t_meas = envelope.measured_at_seconds
        t_recv = envelope.received_at_seconds

        # 1. Update communication health arrival timestamp
        self.health_tracker.record_heartbeat(sid, t_recv)
        current_health = self.health_tracker.get_state(sid, t_recv)

        # 2. Check Sensor Registry Identity
        config = self.registry.get(sid)
        if config is None:
            return self._reject(
                envelope, RejectionReason.UNKNOWN_SENSOR, current_health, ("UNKNOWN_SENSOR",)
            )

        if not config.enabled:
            return self._reject(
                envelope, RejectionReason.DISABLED_SENSOR, current_health, ("DISABLED_SENSOR",), config.location_id
            )

        # 3. Check Timestamps
        if t_meas < 0 or t_recv < 0 or t_recv < t_meas:
            return self._reject(
                envelope, RejectionReason.INVALID_TIMESTAMP, SensorState.INVALID, ("TIMESTAMP_CLOCK_SKEW",), config.location_id
            )

        # 4. Check Sequence Numbers for same (sensor_id, boot_id)
        seq_key = (sid, boot_id)
        last_seq = self._last_sequence.get(seq_key)
        if last_seq is not None:
            if seq == last_seq:
                return self._reject(
                    envelope, RejectionReason.DUPLICATE, current_health, ("DUPLICATE_SEQUENCE",), config.location_id
                )
            if seq < last_seq:
                return self._reject(
                    envelope, RejectionReason.OUT_OF_ORDER, current_health, ("OUT_OF_ORDER_SEQUENCE",), config.location_id
                )

        # Update last sequence for this session
        self._last_sequence[seq_key] = seq

        # 5. Process Layer 11 Ultrasonic Burst Echoes
        raw_measurement = process_measurement(envelope, config)

        if raw_measurement.distance_cm is None:
            return self._reject(
                envelope, RejectionReason.INSUFFICIENT_SAMPLES, current_health, ("ECHO_BURST_FAILURE",), config.location_id
            )

        dist = raw_measurement.distance_cm
        level = raw_measurement.water_level_cm

        # 6. Validate Distance Range
        if not (config.min_distance_cm <= dist <= config.max_distance_cm):
            return self._reject(
                envelope, RejectionReason.RANGE_ERROR, current_health, ("DISTANCE_OUT_OF_BOUNDS",), config.location_id, dist, level
            )

        # 7. Validate Water Level Range
        if level is None or not (config.min_level_cm <= level <= config.max_level_cm):
            return self._reject(
                envelope, RejectionReason.RANGE_ERROR, current_health, ("LEVEL_OUT_OF_BOUNDS",), config.location_id, dist, level
            )

        # 8. Validate Rate of Rise against previous ACCEPTED reading
        last_acc = self._last_accepted.get(sid)
        if last_acc is not None:
            prev_level, prev_t = last_acc
            valid_rate = validate_rate_of_rise(
                previous_level_cm=prev_level,
                previous_timestamp_seconds=prev_t,
                current_level_cm=level,
                current_timestamp_seconds=t_meas,
                max_rate_cm_per_second=self.max_rate_cm_per_second,
                max_gap_seconds=self.max_rate_gap_seconds,
            )
            if not valid_rate:
                return self._reject(
                    envelope, RejectionReason.RATE_SPIKE, current_health, ("RATE_OF_RISE_ANOMALY",), config.location_id, dist, level
                )

        # 9. Validate Float Switch Consistency
        if config.float_enabled:
            float_ok = validate_float_consistency(
                water_level_cm=level,
                float_triggered=envelope.float_triggered,
                trigger_level_cm=config.float_trigger_level_cm,
                tolerance_cm=config.float_tolerance_cm,
            )
            if not float_ok:
                return self._reject(
                    envelope, RejectionReason.FLOAT_CONFLICT, current_health, ("FLOAT_SWITCH_CONFLICT",), config.location_id, dist, level
                )

        # 10. ACCEPT measurement and update stateful baseline
        self._last_accepted[sid] = (level, t_meas)

        res = ValidationResult(
            sensor_id=sid,
            boot_id=boot_id,
            sequence=seq,
            measured_at_seconds=t_meas,
            received_at_seconds=t_recv,
            distance_cm=dist,
            water_level_cm=level,
            sensor_state=current_health,
            measurement_status=MeasurementStatus.ACCEPTED,
            rejection_reason=RejectionReason.NONE,
            quality_flags=("VALID",),
            location_id=config.location_id,
        )
        self.audit_log.append(res)
        return res

    def _reject(
        self,
        envelope: SensorEnvelope,
        reason: RejectionReason,
        state: SensorState,
        flags: Tuple[str, ...],
        location_id: Optional[str] = None,
        distance_cm: Optional[float] = None,
        water_level_cm: Optional[float] = None,
    ) -> ValidationResult:
        res = ValidationResult(
            sensor_id=envelope.sensor_id,
            boot_id=envelope.boot_id,
            sequence=envelope.sequence,
            measured_at_seconds=envelope.measured_at_seconds,
            received_at_seconds=envelope.received_at_seconds,
            distance_cm=distance_cm,
            water_level_cm=water_level_cm,
            sensor_state=state,
            measurement_status=MeasurementStatus.REJECTED,
            rejection_reason=reason,
            quality_flags=flags,
            location_id=location_id,
        )
        self.audit_log.append(res)
        return res
