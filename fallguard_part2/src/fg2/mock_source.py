"""Stand-in for Part 1: synthetic frames plus contract messages. No real video, no real people."""
from __future__ import annotations
import numpy as np
from .contract import StateMessage

# (seconds, state, reason, score, person_present, camera_ok, posture)
DEFAULT_SCENARIO = [
    (3.0, "normal", "stable upright", 0.05, True, True, "upright"),
    (1.5, "possible_fall", "rapid descent, torso tilting", 0.60, True, True, "falling"),
    (3.0, "confirmed_fall", "sustained low posture, no recovery", 0.90, True, True, "lying"),
    (2.0, "recovering", "upright posture resumed", 0.30, True, True, "upright"),
    (2.0, "normal", "stable upright", 0.05, True, True, "upright"),
    (1.5, "unknown", "camera lost", 0.0, False, False, "none"),
    (1.5, "normal", "no person in view", 0.0, False, True, "none"),
]


def _box(posture, t):
    x = 120 + 60 * np.sin(t)
    if posture == "upright":
        return (x, 100, x + 110, 420)
    if posture == "falling":
        return (x, 220, x + 200, 400)
    if posture == "lying":
        return (x, 340, x + 260, 430)
    return None


class MockSource:
    def __init__(self, fps=15, size=(480, 640), scenario=None, seed=0, start_ts=1_760_800_000.0,
                 hold_until_ack=None, max_hold_s=120):
        self.fps, self.size, self.seed = fps, size, seed
        self.hold_until_ack, self.max_hold_s = hold_until_ack, max_hold_s
        self.scenario = scenario or DEFAULT_SCENARIO
        self.start_ts = start_ts

    def __iter__(self):
        rng = np.random.default_rng(self.seed)
        h, w = self.size
        bg = rng.integers(40, 90, (h, w, 3), dtype=np.uint8)
        fid = 0

        def make(fid, state, reason, score, present, cam_ok, posture):
            ts = self.start_ts + fid / self.fps
            frame = bg.copy()
            box = _box(posture, fid / self.fps) if present else None
            boxes = ()
            if box:
                x1, y1, x2, y2 = (int(v) for v in box)
                x1, x2 = max(0, x1), min(w - 1, x2)
                y1, y2 = max(0, y1), min(h - 1, y2)
                frame[y1:y2, x1:x2] = rng.integers(150, 255, (y2 - y1, x2 - x1, 3), dtype=np.uint8)
                boxes = ((float(x1), float(y1), float(x2), float(y2)),)
            return frame, StateMessage(ts, fid, state, reason, score, 1 if boxes else None, boxes, cam_ok)

        for step in self.scenario:
            secs, state = step[0], step[1]
            for _ in range(int(secs * self.fps)):
                yield make(fid, *step[1:])
                fid += 1
            if state == "confirmed_fall" and self.hold_until_ack:
                extra = 0
                while not self.hold_until_ack() and extra < self.max_hold_s * self.fps:
                    yield make(fid, *step[1:])
                    fid += 1
                    extra += 1
