"""Metadata-only incident log (JSON lines). Rejects anything that is not a small scalar."""
from __future__ import annotations
import json, os, time
from pathlib import Path
from .contract import StateMessage, AckMessage
from .blur import PrivacyError

ALLOWED = {"event", "incident_id", "ts", "ts_iso", "state", "reason", "evidence_score",
           "track_id", "frame_id", "model", "runtime", "operator_action"}
OPEN_STATES = {"possible_fall", "confirmed_fall", "recovering"}


def sanitize(rec: dict) -> dict:
    for k, v in rec.items():
        if k not in ALLOWED:
            raise PrivacyError(f"field not allowed in incident log: {k}")
        if v is not None and not isinstance(v, (str, int, float, bool)):
            raise PrivacyError(f"non-scalar value for {k}")
        if isinstance(v, str) and len(v) > 200:
            raise PrivacyError(f"string too long for {k}")
    return rec


class IncidentLogger:
    def __init__(self, directory="incidents", model="unknown", runtime="unknown"):
        self.dir = Path(directory)
        self.dir.mkdir(parents=True, exist_ok=True)
        self.path = self.dir / "incidents.jsonl"
        self.model, self.runtime = model, runtime
        self._state = "normal"
        self._open_id: str | None = None
        self._count = 0

    @property
    def open_incident(self):
        return self._open_id

    def _write(self, rec):
        rec.update(model=self.model, runtime=self.runtime)
        sanitize(rec)
        with open(self.path, "a", encoding="utf-8") as f:
            f.write(json.dumps(rec) + "\n")
            f.flush()
            os.fsync(f.fileno())

    def _iso(self, ts):
        return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(ts))

    def observe(self, msg: StateMessage):
        """Call for every state message; logs only on state changes."""
        if msg.state == self._state:
            return None
        prev, self._state = self._state, msg.state
        base = {"ts": msg.ts, "ts_iso": self._iso(msg.ts), "state": msg.state, "reason": msg.reason,
                "evidence_score": msg.evidence_score, "track_id": msg.track_id, "frame_id": msg.frame_id}
        if self._open_id is None and msg.state == "possible_fall":
            self._count += 1
            self._open_id = f"inc-{int(msg.ts)}-{self._count}"
            event = "incident_opened"
        elif self._open_id and msg.state == "normal" and prev in OPEN_STATES:
            event = "incident_closed"
        else:
            event = "state_change"
        rec = {"event": event, "incident_id": self._open_id, **base}
        self._write(rec)
        if event == "incident_closed":
            self._open_id = None
        return event

    def acknowledge(self, ack: AckMessage):
        self._write({"event": "acknowledged", "incident_id": self._open_id, "ts": ack.ts,
                     "ts_iso": self._iso(ack.ts), "operator_action": "ack"})

    def read_all(self):
        if not self.path.exists():
            return []
        return [json.loads(l) for l in self.path.read_text(encoding="utf-8").splitlines() if l.strip()]
