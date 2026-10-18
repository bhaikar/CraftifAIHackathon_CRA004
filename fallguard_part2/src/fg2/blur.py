"""Fail-closed privacy blur.

Guarantees:
- Output is always a new array; the raw input frame is never returned.
- Sinks accept only BlurredFrame objects, which only this module can create.
- Any doubt (no boxes, stale/mismatched boxes, camera fault, exception)
  results in a full-frame blur or, on error, no output at all.
"""
from __future__ import annotations
from dataclasses import dataclass
import numpy as np
import cv2
from .contract import StateMessage


class PrivacyError(RuntimeError):
    pass


_TOKEN = object()


class BlurredFrame:
    __slots__ = ("image", "mode", "reason", "frame_id", "ts")

    def __init__(self, image, mode, reason, frame_id, ts, _token=None):
        if _token is not _TOKEN:
            raise PrivacyError("BlurredFrame can only be created by FailClosedBlurrer")
        self.image, self.mode, self.reason = image, mode, reason
        self.frame_id, self.ts = frame_id, ts


def require_blurred(obj):
    """Call at the top of every sink (file, clip, stream)."""
    if not isinstance(obj, BlurredFrame):
        raise PrivacyError(f"sink refused non-blurred input: {type(obj).__name__}")
    return obj


@dataclass
class BlurConfig:
    pad_ratio: float = 0.25
    hold_frames: int = 0   # 0 = strict. Holding old boxes can leak when posture changes fast (see privacy audit)
    person_recent_s: float = 2.0
    empty_scene_policy: str = "full_blur"  # or "passthrough_when_healthy"


def _pixelate(roi, cell):
    h, w = roi.shape[:2]
    small = cv2.resize(roi, (max(1, w // cell), max(1, h // cell)), interpolation=cv2.INTER_AREA)
    return cv2.resize(small, (w, h), interpolation=cv2.INTER_NEAREST)


class FailClosedBlurrer:
    def __init__(self, cfg: BlurConfig | None = None):
        self.cfg = cfg or BlurConfig()
        self._last_boxes: tuple = ()
        self._last_person_ts: float | None = None
        self._held = 0
        self.errors = 0

    def _full(self, frame, reason, fid, ts):
        out = _pixelate(frame.copy(), max(16, frame.shape[1] // 12))
        return BlurredFrame(out, "full", reason, fid, ts, _token=_TOKEN)

    def _region(self, frame, boxes, mode, fid, ts):
        h, w = frame.shape[:2]
        out = frame.copy()
        done = 0
        for x1, y1, x2, y2 in boxes:
            px, py = (x2 - x1) * self.cfg.pad_ratio, (y2 - y1) * self.cfg.pad_ratio
            a, b = max(0, int(x1 - px)), max(0, int(y1 - py))
            c, d = min(w, int(x2 + px)), min(h, int(y2 + py))
            if c - a < 2 or d - b < 2:
                continue
            out[b:d, a:c] = _pixelate(out[b:d, a:c], max(12, (c - a) // 6))
            done += 1
        if done == 0:
            return None
        return BlurredFrame(out, mode, "person regions blurred", fid, ts, _token=_TOKEN)

    def _recent(self, ts):
        return self._last_person_ts is not None and 0 <= ts - self._last_person_ts <= self.cfg.person_recent_s

    def _hold_or_full(self, frame, reason, fid, ts):
        if self._last_boxes and self._recent(ts) and self._held < self.cfg.hold_frames:
            self._held += 1
            res = self._region(frame, self._last_boxes, "held", fid, ts)
            if res:
                return res
        return self._full(frame, reason, fid, ts)

    def process(self, frame, frame_id: int, frame_ts: float, msg: StateMessage | None):
        if not isinstance(frame, np.ndarray) or frame.ndim != 3 or frame.dtype != np.uint8:
            raise PrivacyError("frame must be an HxWx3 uint8 array")
        if msg is None:
            return self._hold_or_full(frame, "no detector message", frame_id, frame_ts)
        if msg.frame_id != frame_id:
            return self._hold_or_full(frame, "boxes not tied to this frame", frame_id, frame_ts)
        if not msg.camera_ok:
            return self._full(frame, "camera fault", frame_id, frame_ts)
        if msg.boxes:
            res = self._region(frame, msg.boxes, "region", frame_id, frame_ts)
            if res is None:
                return self._full(frame, "boxes outside frame", frame_id, frame_ts)
            self._last_boxes, self._last_person_ts, self._held = msg.boxes, frame_ts, 0
            return res
        if self._recent(frame_ts):
            return self._hold_or_full(frame, "person recently seen, no boxes", frame_id, frame_ts)
        if self.cfg.empty_scene_policy == "passthrough_when_healthy":
            return BlurredFrame(frame.copy(), "empty_scene", "healthy detector, no person", frame_id, frame_ts, _token=_TOKEN)
        return self._full(frame, "empty-scene policy: full blur", frame_id, frame_ts)

    def process_or_drop(self, frame, frame_id, frame_ts, msg):
        """Never raises. Returns None (emit nothing) if anything goes wrong."""
        try:
            return self.process(frame, frame_id, frame_ts, msg)
        except Exception:
            self.errors += 1
            return None
