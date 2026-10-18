"""Adapter from Part 1 ``FrameStatus`` objects to Part 2 ``StateMessage``s."""
from __future__ import annotations

from collections.abc import Sequence
from typing import TYPE_CHECKING

from .contract import ContractError, StateMessage

if TYPE_CHECKING:
    from part1.contract import FrameStatus


_STATE_BY_VALUE = {
    "Normal": "normal",
    "Possible Fall": "possible_fall",
    "Confirmed Fall": "confirmed_fall",
    "Recovering": "recovering",
    "Unknown": "unknown",
}


def _part1_state_value(state: object) -> str:
    return str(getattr(state, "value", state))


def _box_tuple(person_box: object) -> tuple[tuple[float, float, float, float], ...]:
    if person_box is None:
        return ()
    if not isinstance(person_box, Sequence) or isinstance(person_box, (str, bytes)) or len(person_box) != 4:
        raise ContractError("Part 1 person_box must contain [x1, y1, x2, y2]")
    x1, y1, x2, y2 = (float(value) for value in person_box)
    if x2 <= x1 or y2 <= y1:
        raise ContractError("Part 1 person_box must have x2 > x1 and y2 > y1")
    return ((x1, y1, x2, y2),)


def convert_part1_status(
    status: FrameStatus,
    *,
    camera_ok: bool = True,
    track_id: int | None = 1,
) -> StateMessage:
    """Translate a validated Part 1 status without transporting raw imagery.

    Part 1 timestamps are integer milliseconds; Part 2 uses seconds. An
    unavailable person box becomes an empty tuple so Part 2's fail-closed
    blurrer can select its full-frame protection path.
    """
    state = _STATE_BY_VALUE.get(_part1_state_value(status.state))
    if state is None:
        raise ContractError(f"unsupported Part 1 fall state: {status.state!r}")

    boxes = _box_tuple(status.person_box)
    if state == "unknown" and "camera" in status.reason.lower():
        camera_ok = False
    confidence = float(status.confidence)
    if not 0.0 <= confidence <= 1.0:
        raise ContractError("Part 1 confidence must be in [0, 1]")

    return StateMessage.from_dict({
        "ts": float(status.timestamp_ms) / 1000.0,
        "frame_id": status.frame_id,
        "state": state,
        "reason": status.reason,
        "evidence_score": confidence,
        "track_id": track_id if boxes else None,
        "boxes": boxes,
        "camera_ok": camera_ok,
    })
