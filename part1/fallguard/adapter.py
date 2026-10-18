"""Pose model output adapter.

PipeGen's model node is expected to emit COCO-17 keypoints in this order:
0 nose, 1 left eye, 2 right eye, 3 left ear, 4 right ear,
5 left shoulder, 6 right shoulder, 7 left elbow, 8 right elbow,
9 left wrist, 10 right wrist, 11 left hip, 12 right hip,
13 left knee, 14 right knee, 15 left ankle, 16 right ankle.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, Optional


COCO_KEYPOINTS = (
    "nose", "left_eye", "right_eye", "left_ear", "right_ear",
    "left_shoulder", "right_shoulder", "left_elbow", "right_elbow",
    "left_wrist", "right_wrist", "left_hip", "right_hip",
    "left_knee", "right_knee", "left_ankle", "right_ankle",
)


@dataclass(frozen=True)
class Detection:
    """One decoded person returned by the pose parser."""

    box: list[float]
    keypoints: list[list[float]]
    confidence: float

    @property
    def person_count(self) -> int:
        return 1


def _as_float(value: Any) -> float:
    return float(value)


def normalize_keypoints(points: Iterable[Iterable[Any]]) -> list[list[float]]:
    """Convert model output to exactly 17 ``[x, y, confidence]`` rows."""
    normalized: list[list[float]] = []
    for point in points:
        values = list(point)
        if len(values) < 2:
            raise ValueError("each keypoint must contain at least x and y")
        normalized.append([
            _as_float(values[0]),
            _as_float(values[1]),
            _as_float(values[2]) if len(values) > 2 else 1.0,
        ])
    if len(normalized) != len(COCO_KEYPOINTS):
        raise ValueError(
            f"expected {len(COCO_KEYPOINTS)} COCO keypoints, got {len(normalized)}"
        )
    return normalized


def decode_pose_output(raw: dict[str, Any]) -> list[Detection]:
    """Decode a model-independent parser payload.

    PipeGen adapters can map their native parser output into this small shape:
    ``{"detections": [{"box": [...], "keypoints": [...], "confidence": ...}]}``.
    Keeping this boundary explicit makes the fall logic testable without a GPU.
    """
    detections: list[Detection] = []
    for item in raw.get("detections", []):
        box = [_as_float(value) for value in item["box"]]
        if len(box) != 4:
            raise ValueError("person box must be [x1, y1, x2, y2]")
        detections.append(Detection(
            box=box,
            keypoints=normalize_keypoints(item["keypoints"]),
            confidence=max(0.0, min(1.0, _as_float(item.get("confidence", 0.0)))),
        ))
    return detections


def select_single_person(
    detections: list[Detection],
    confidence_threshold: float = 0.45,
) -> tuple[Optional[Detection], str]:
    """Apply the default single-person policy.

    Multiple confident people deliberately produce ``Unknown`` rather than
    guessing which person's posture should drive an alarm.
    """
    confident = [d for d in detections if d.confidence >= confidence_threshold]
    if not confident:
        return None, "no confident person"
    if len(confident) > 1:
        return None, "more than one confident person"
    return confident[0], "ok"
