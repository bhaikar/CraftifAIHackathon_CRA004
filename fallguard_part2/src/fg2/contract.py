"""Shared message contract between Part 1 (pipeline) and Part 2 (privacy/app)."""
from __future__ import annotations
import json, math
from dataclasses import dataclass

STATES = ("normal", "possible_fall", "confirmed_fall", "recovering", "unknown")
TOPIC_STATE = "care/room1/state"
TOPIC_FALL = "care/room1/fall"
TOPIC_ACK = "care/room1/ack"
TOPIC_STATUS = "care/room1/status"


class ContractError(ValueError):
    pass


def _num(v, name):
    if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v):
        raise ContractError(f"{name} must be a finite number")
    return float(v)


@dataclass(frozen=True)
class StateMessage:
    ts: float
    frame_id: int
    state: str
    reason: str
    evidence_score: float
    track_id: int | None
    boxes: tuple
    camera_ok: bool

    @classmethod
    def from_dict(cls, d):
        if not isinstance(d, dict):
            raise ContractError("message must be an object")
        for k in ("ts", "frame_id", "state", "reason", "evidence_score", "track_id", "boxes", "camera_ok"):
            if k not in d:
                raise ContractError(f"missing field: {k}")
        ts = _num(d["ts"], "ts")
        fid = d["frame_id"]
        if isinstance(fid, bool) or not isinstance(fid, int) or fid < 0:
            raise ContractError("frame_id must be a non-negative int")
        if d["state"] not in STATES:
            raise ContractError(f"bad state: {d['state']!r}")
        if not isinstance(d["reason"], str) or len(d["reason"]) > 200:
            raise ContractError("reason must be a string up to 200 chars")
        score = _num(d["evidence_score"], "evidence_score")
        if not 0.0 <= score <= 1.0:
            raise ContractError("evidence_score must be in [0, 1]")
        tid = d["track_id"]
        if tid is not None and (isinstance(tid, bool) or not isinstance(tid, int)):
            raise ContractError("track_id must be int or null")
        if not isinstance(d["camera_ok"], bool):
            raise ContractError("camera_ok must be bool")
        if not isinstance(d["boxes"], (list, tuple)):
            raise ContractError("boxes must be a list")
        boxes = []
        for b in d["boxes"]:
            if not isinstance(b, (list, tuple)) or len(b) != 4:
                raise ContractError("each box must be [x1, y1, x2, y2]")
            x1, y1, x2, y2 = (_num(v, "box") for v in b)
            if x2 <= x1 or y2 <= y1:
                raise ContractError("box must have x2 > x1 and y2 > y1")
            boxes.append((x1, y1, x2, y2))
        return cls(ts, fid, d["state"], d["reason"], score, tid, tuple(boxes), d["camera_ok"])

    @classmethod
    def from_json(cls, s):
        try:
            return cls.from_dict(json.loads(s))
        except json.JSONDecodeError as e:
            raise ContractError(f"invalid JSON: {e}") from e

    def to_dict(self):
        return {"ts": self.ts, "frame_id": self.frame_id, "state": self.state,
                "reason": self.reason, "evidence_score": self.evidence_score,
                "track_id": self.track_id, "boxes": [list(b) for b in self.boxes],
                "camera_ok": self.camera_ok}

    def to_json(self):
        return json.dumps(self.to_dict())


@dataclass(frozen=True)
class AckMessage:
    ts: float
    cmd: str = "ack"

    @classmethod
    def from_json(cls, s):
        try:
            d = json.loads(s)
        except json.JSONDecodeError as e:
            raise ContractError(f"invalid JSON: {e}") from e
        if not isinstance(d, dict) or d.get("cmd") != "ack":
            raise ContractError("expected {'cmd': 'ack', 'ts': ...}")
        return cls(_num(d.get("ts"), "ts"))

    def to_json(self):
        return json.dumps({"cmd": self.cmd, "ts": self.ts})
