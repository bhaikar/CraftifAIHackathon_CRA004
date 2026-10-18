"""MQTT alert publisher. Metadata-only payloads on care/room1/fall."""
from __future__ import annotations
import json
from .contract import StateMessage, TOPIC_FALL
from .incident_log import sanitize


class AlertPublisher:
    def __init__(self, bus, topic=TOPIC_FALL):
        self.bus, self.topic = bus, topic
        self._prev = "normal"
        self._had_alert = False
        self.failed = 0

    def _send(self, event, msg, incident_id):
        rec = {"event": event, "incident_id": incident_id, "ts": msg.ts, "state": msg.state,
               "reason": msg.reason, "evidence_score": msg.evidence_score, "track_id": msg.track_id}
        sanitize(rec)
        ok = self.bus.publish(self.topic, json.dumps(rec), qos=1, retain=False)
        if not ok:
            self.failed += 1
        return event

    def observe(self, msg: StateMessage, incident_id=None):
        """Publish on state transitions only. Returns the event name or None."""
        if msg.state == self._prev:
            return None
        prev, self._prev = self._prev, msg.state
        if msg.state in ("possible_fall", "confirmed_fall"):
            self._had_alert = True
            return self._send("fall_alert", msg, incident_id)
        if msg.state == "normal" and self._had_alert and prev in ("recovering", "possible_fall"):
            self._had_alert = False
            return self._send("alert_cleared", msg, incident_id)
        return None
