"""Part 1 -> Part 2 contract types.

The runtime emits one ``FrameStatus`` for every processed frame.  Part 2 may
use ``person_box`` to apply privacy blur without receiving the raw frame here.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, Optional
import json


class FallState(str, Enum):
    NORMAL = "Normal"
    POSSIBLE_FALL = "Possible Fall"
    CONFIRMED_FALL = "Confirmed Fall"
    RECOVERING = "Recovering"
    UNKNOWN = "Unknown"


@dataclass(frozen=True)
class FrameStatus:
    frame_id: int
    timestamp_ms: int
    state: FallState
    reason: str
    confidence: float
    person_box: Optional[list[float]] = None
    keypoints: Optional[list[list[float]]] = None
    person_count: int = 0
    metrics: dict[str, float] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["state"] = self.state.value
        return data

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), separators=(",", ":"))


VALID_STATES = {state.value for state in FallState}
