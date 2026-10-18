"""Temporal fall state machine.

The state machine is intentionally independent of DeepStream/PipeGen so it can
be replayed against recorded keypoint traces and validated on hard negatives.
"""
from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from typing import Optional

from contract import FallState
from .features import PoseFeatures


@dataclass(frozen=True)
class StateUpdate:
    state: FallState
    reason: str
    confidence: float


class FallStateMachine:
    def __init__(
        self,
        confirmation_window_seconds: float = 3.0,
        upright_recovery_seconds: float = 1.0,
        cooldown_seconds: float = 2.0,
        descent_velocity_threshold: float = 0.9,
        min_confidence: float = 0.45,
        history_seconds: float = 4.0,
    ) -> None:
        self.confirmation_window_seconds = confirmation_window_seconds
        self.upright_recovery_seconds = upright_recovery_seconds
        self.cooldown_seconds = cooldown_seconds
        self.descent_velocity_threshold = descent_velocity_threshold
        self.min_confidence = min_confidence
        self.history_seconds = history_seconds
        self.state = FallState.NORMAL
        self._possible_since: Optional[int] = None
        self._upright_since: Optional[int] = None
        self._cooldown_until: Optional[int] = None
        self._history: deque[tuple[int, PoseFeatures]] = deque()
        self._pending_unknown_return = FallState.NORMAL

    def _trim(self, timestamp_ms: int) -> None:
        cutoff = timestamp_ms - int(self.history_seconds * 1000)
        while self._history and self._history[0][0] < cutoff:
            self._history.popleft()

    def _hip_velocity(self, timestamp_ms: int, features: PoseFeatures) -> float:
        if not self._history:
            return 0.0
        prior_ts, prior = self._history[-1]
        dt = (timestamp_ms - prior_ts) / 1000.0
        if dt <= 0 or not prior.valid:
            return 0.0
        return (features.hip_y - prior.hip_y) / max(features.torso_length, 1e-6) / dt

    def _set_unknown(self, reason: str, confidence: float) -> StateUpdate:
        if self.state is not FallState.UNKNOWN:
            self._pending_unknown_return = self.state
        self.state = FallState.UNKNOWN
        return StateUpdate(self.state, reason, confidence)

    def update(
        self,
        timestamp_ms: int,
        features: Optional[PoseFeatures],
        *,
        reliable: bool = True,
        person_count: int = 1,
        stale: bool = False,
    ) -> StateUpdate:
        """Advance the machine with one time-stamped pose observation."""
        if stale:
            return self._set_unknown("stale feed", 0.0)
        if person_count != 1:
            return self._set_unknown("expected exactly one person", 0.0)
        if not reliable or features is None or not features.valid or features.confidence < self.min_confidence:
            return self._set_unknown("pose confidence below threshold", 0.0 if features is None else features.confidence)

        self._trim(timestamp_ms)
        if self.state is FallState.UNKNOWN:
            self.state = self._pending_unknown_return if self._pending_unknown_return is not FallState.UNKNOWN else FallState.NORMAL

        velocity = self._hip_velocity(timestamp_ms, features)
        self._history.append((timestamp_ms, features))

        if self.state is FallState.NORMAL:
            if velocity >= self.descent_velocity_threshold or features.near_horizontal:
                self.state = FallState.POSSIBLE_FALL
                self._possible_since = timestamp_ms
                return StateUpdate(self.state, "rapid descent or horizontal posture", features.confidence)
            return StateUpdate(self.state, "upright monitoring", features.confidence)

        if self.state is FallState.POSSIBLE_FALL:
            if features.upright:
                self.state = FallState.NORMAL
                self._possible_since = None
                return StateUpdate(self.state, "quick recovery before confirmation", features.confidence)
            if self._possible_since is None:
                self._possible_since = timestamp_ms
            elapsed = (timestamp_ms - self._possible_since) / 1000.0
            if elapsed >= self.confirmation_window_seconds and features.near_horizontal:
                self.state = FallState.CONFIRMED_FALL
                self._upright_since = None
                return StateUpdate(self.state, "low or horizontal posture persisted", features.confidence)
            return StateUpdate(self.state, "fall candidate within confirmation window", features.confidence)

        if self.state is FallState.CONFIRMED_FALL:
            if features.upright:
                if self._upright_since is None:
                    self._upright_since = timestamp_ms
                elapsed = (timestamp_ms - self._upright_since) / 1000.0
                if elapsed >= self.upright_recovery_seconds:
                    self.state = FallState.RECOVERING
                    return StateUpdate(self.state, "upright posture sustained", features.confidence)
            else:
                self._upright_since = None
            return StateUpdate(self.state, "fall alarm latched", features.confidence)

        if self.state is FallState.RECOVERING:
            if not features.upright:
                self.state = FallState.CONFIRMED_FALL
                self._upright_since = None
                return StateUpdate(self.state, "upright posture lost during recovery", features.confidence)
            return StateUpdate(self.state, "awaiting operator acknowledgement", features.confidence)

        return StateUpdate(self.state, "monitoring", features.confidence)

    def acknowledge(self, timestamp_ms: int) -> StateUpdate:
        """Acknowledge a recovered alarm and start cooldown/re-arm."""
        if self.state is not FallState.RECOVERING:
            return StateUpdate(self.state, "acknowledgement ignored outside recovery", 0.0)
        self.state = FallState.NORMAL
        self._possible_since = None
        self._upright_since = None
        self._cooldown_until = timestamp_ms + int(self.cooldown_seconds * 1000)
        return StateUpdate(self.state, "operator acknowledged; cooldown started", 1.0)

    def is_armed(self, timestamp_ms: int) -> bool:
        return self._cooldown_until is None or timestamp_ms >= self._cooldown_until
