"""Part 2 controller: state message + frame in; blurred output, logs, alerts, status out."""
from __future__ import annotations
import queue, time
from pathlib import Path
from .contract import StateMessage, AckMessage, TOPIC_ACK, ContractError
from .runtime_io import write_status, write_latest, clear_latest, poll_ack

ACTIVE = ("possible_fall", "confirmed_fall", "recovering")


class Part2App:
    def __init__(self, runtime_dir, logger, blurrer, alerts=None, bus=None):
        self.dir = Path(runtime_dir)
        self.dir.mkdir(parents=True, exist_ok=True)
        self.logger, self.blurrer, self.alerts = logger, blurrer, alerts
        self.acked = False
        self._last_ack_id = None
        self._seen_ack_ts: list = []
        self._q: queue.Queue = queue.Queue()
        self._state, self._since = "normal", None
        if bus is not None:
            bus.subscribe(TOPIC_ACK, self._on_bus_ack)

    def _on_bus_ack(self, topic, payload):
        try:
            self._q.put(AckMessage.from_json(payload))
        except ContractError:
            pass

    def _handle_ack(self, ack):
        if ack.ts in self._seen_ack_ts:          # same ack arrived via file and MQTT
            return
        self._seen_ack_ts = (self._seen_ack_ts + [ack.ts])[-20:]
        self.logger.acknowledge(ack)
        self.acked = True

    def _drain_acks(self):
        ack, self._last_ack_id = poll_ack(self.dir, self._last_ack_id)
        if ack:
            self._handle_ack(ack)
        while not self._q.empty():
            self._handle_ack(self._q.get())

    def step(self, frame, msg: StateMessage):
        self._drain_acks()
        before = self.logger.open_incident
        event = self.logger.observe(msg)
        incident = self.logger.open_incident or before
        if event in ("incident_opened",):
            self.acked = False
        if self.alerts:
            self.alerts.observe(msg, incident)
        if msg.state != self._state or self._since is None:
            self._state, self._since = msg.state, msg.ts
        bf = self.blurrer.process_or_drop(frame, msg.frame_id, msg.ts, msg)
        if bf is None:
            clear_latest(self.dir)              # fail closed: no stale or raw image remains
        else:
            write_latest(self.dir, bf)
        write_status(self.dir, {
            "state": msg.state, "reason": msg.reason, "evidence_score": msg.evidence_score,
            "camera_ok": msg.camera_ok, "frame_id": msg.frame_id, "ts": msg.ts,
            "state_elapsed_s": round(msg.ts - self._since, 1),
            "open_incident": self.logger.open_incident,
            "awaiting_ack": msg.state in ACTIVE and not self.acked,
            "video_ok": bf is not None, "blur_mode": bf.mode if bf else "dropped",
            "updated_at": time.time(),
        })
        if msg.state == "normal" and event == "incident_closed":
            self.acked = False
        return bf
