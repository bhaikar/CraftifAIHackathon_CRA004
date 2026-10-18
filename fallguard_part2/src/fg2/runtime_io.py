"""File channel between the controller and the dashboard. Only blurred frames are ever written."""
from __future__ import annotations
import json, os, time, uuid
from pathlib import Path
import cv2
from .blur import require_blurred
from .contract import AckMessage, ContractError


def _atomic_write(path: Path, data: bytes) -> bool:
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_bytes(data)
    for _ in range(10):
        try:
            os.replace(tmp, path)
            return True
        except PermissionError:      # Windows: reader has the file open
            time.sleep(0.01)
    return False


def write_status(d, status: dict):
    return _atomic_write(Path(d) / "status.json", json.dumps(status).encode())


def read_status(d):
    try:
        return json.loads((Path(d) / "status.json").read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, PermissionError):
        return None


def write_latest(d, blurred) -> bool:
    require_blurred(blurred)
    ok, buf = cv2.imencode(".jpg", blurred.image, [cv2.IMWRITE_JPEG_QUALITY, 80])
    return bool(ok) and _atomic_write(Path(d) / "latest_blurred.jpg", buf.tobytes())


def clear_latest(d):
    try:
        (Path(d) / "latest_blurred.jpg").unlink(missing_ok=True)
    except PermissionError:
        pass


def read_latest(d):
    try:
        return (Path(d) / "latest_blurred.jpg").read_bytes()
    except (FileNotFoundError, PermissionError):
        return None


def request_ack(d, mqtt_host=None, mqtt_port=1883):
    """Dashboard side: file ack always, MQTT ack too when a broker is configured."""
    from .bus import publish_once
    from .contract import TOPIC_ACK
    ack = AckMessage(time.time())
    payload = json.loads(ack.to_json())
    payload["id"] = uuid.uuid4().hex
    _atomic_write(Path(d) / "ack.json", json.dumps(payload).encode())
    if mqtt_host:
        publish_once(mqtt_host, mqtt_port, TOPIC_ACK, ack.to_json())
    return ack


def poll_ack(d, last_id=None):
    """Controller side. Returns (AckMessage | None, new_last_id)."""
    try:
        raw = (Path(d) / "ack.json").read_text(encoding="utf-8")
        data = json.loads(raw)
        if data.get("id") == last_id:
            return None, last_id
        return AckMessage.from_json(raw), data.get("id")
    except (FileNotFoundError, json.JSONDecodeError, PermissionError, ContractError):
        return None, last_id


STALE_AFTER_S = 3.0


def is_stale(status, now=None, ttl=STALE_AFTER_S):
    """True when there is no status or it is older than ttl. A stale state must never be shown as current."""
    if status is None:
        return True
    return (now if now is not None else time.time()) - status.get("updated_at", 0) > ttl
