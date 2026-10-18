"""Pose-derived, torso-normalized temporal features."""
from __future__ import annotations

from dataclasses import dataclass
from math import atan2, degrees, hypot, isfinite
from typing import Optional


# COCO-17 indices
LS, RS, LH, RH = 5, 6, 11, 12
LEFT_KNEE, RIGHT_KNEE = 13, 14


@dataclass(frozen=True)
class PoseFeatures:
    torso_length: float
    trunk_angle_deg: float
    body_aspect_ratio: float
    hip_y: float
    hip_x: float
    confidence: float
    upright: bool
    near_horizontal: bool
    valid: bool


def _point(points: list[list[float]], index: int) -> tuple[float, float, float]:
    x, y, confidence = points[index]
    return float(x), float(y), float(confidence)


def _midpoint(a: tuple[float, float, float], b: tuple[float, float, float]) -> tuple[float, float, float]:
    return ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2, min(a[2], b[2]))


def _distance(a: tuple[float, float, float], b: tuple[float, float, float]) -> float:
    return hypot(a[0] - b[0], a[1] - b[1])


def extract_features(
    keypoints: list[list[float]],
    box: list[float],
    min_keypoint_confidence: float = 0.35,
    horizontal_angle_deg: float = 55.0,
    upright_angle_deg: float = 25.0,
) -> PoseFeatures:
    """Compute stable geometry from a COCO-17 pose.

    All displacement-like quantities are normalized by torso length.  The
    angle is measured between the shoulder-to-hip vector and vertical: 0° is
    upright and 90° is horizontal.
    """
    if len(keypoints) != 17 or len(box) != 4:
        return PoseFeatures(0, 90, 0, 0, 0, 0, False, False, False)

    required = [LS, RS, LH, RH]
    if any(keypoints[index][2] < min_keypoint_confidence for index in required):
        return PoseFeatures(0, 90, 0, 0, 0, 0, False, False, False)

    left_shoulder = _point(keypoints, LS)
    right_shoulder = _point(keypoints, RS)
    left_hip = _point(keypoints, LH)
    right_hip = _point(keypoints, RH)
    shoulders = _midpoint(left_shoulder, right_shoulder)
    hips = _midpoint(left_hip, right_hip)

    torso_left = _distance(left_shoulder, left_hip)
    torso_right = _distance(right_shoulder, right_hip)
    torso_length = (torso_left + torso_right) / 2
    if torso_length <= 1e-6 or not isfinite(torso_length):
        return PoseFeatures(0, 90, 0, hips[1], hips[0], min(shoulders[2], hips[2]), False, False, False)

    dx = hips[0] - shoulders[0]
    dy = hips[1] - shoulders[1]
    trunk_angle = degrees(abs(atan2(dx, dy)))
    x1, y1, x2, y2 = map(float, box)
    width = max(abs(x2 - x1), 1e-6)
    height = max(abs(y2 - y1), 1e-6)
    aspect_ratio = height / width
    confidence = min(left_shoulder[2], right_shoulder[2], left_hip[2], right_hip[2])

    return PoseFeatures(
        torso_length=torso_length,
        trunk_angle_deg=trunk_angle,
        body_aspect_ratio=aspect_ratio,
        hip_y=hips[1],
        hip_x=hips[0],
        confidence=confidence,
        upright=trunk_angle <= upright_angle_deg,
        near_horizontal=trunk_angle >= horizontal_angle_deg,
        valid=True,
    )
