"""Message transports. Alerts and acks carry metadata only, never frames."""
from __future__ import annotations
from .contract import TOPIC_STATUS


class LocalBus:
    """In-process bus for tests and broker-less demos."""
    def __init__(self):
        self.sent = []
        self._subs = {}

    def publish(self, topic, payload, qos=1, retain=False):
        self.sent.append((topic, payload))
        for cb in self._subs.get(topic, []):
            cb(topic, payload)
        return True

    def subscribe(self, topic, cb):
        self._subs.setdefault(topic, []).append(cb)

    def close(self):
        pass


class MqttBus:
    """paho-mqtt wrapper with last-will, retained online status and auto-resubscribe."""
    def __init__(self, host="localhost", port=1883, client_id="fg2-part2", client=None):
        self.host, self.port = host, port
        self.connected = False
        self._subs = {}
        if client is None:
            import paho.mqtt.client as mqtt
            try:
                client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=client_id)
            except AttributeError:
                client = mqtt.Client(client_id=client_id)
        self.c = client
        self.c.will_set(TOPIC_STATUS, "offline", qos=1, retain=True)
        self.c.on_connect = self._on_connect
        self.c.on_disconnect = self._on_disconnect
        self.c.on_message = self._on_message

    def start(self):
        self.c.connect_async(self.host, self.port)
        self.c.loop_start()

    def _on_connect(self, c, userdata, flags, rc=None, props=None):
        self.connected = True
        for t in self._subs:
            c.subscribe(t, qos=1)
        c.publish(TOPIC_STATUS, "online", qos=1, retain=True)

    def _on_disconnect(self, c, userdata, *args):
        self.connected = False

    def _on_message(self, c, userdata, m):
        payload = m.payload.decode("utf-8", "replace")
        for cb in self._subs.get(m.topic, []):
            cb(m.topic, payload)

    def subscribe(self, topic, cb):
        self._subs.setdefault(topic, []).append(cb)
        if self.connected:
            self.c.subscribe(topic, qos=1)

    def publish(self, topic, payload, qos=1, retain=False):
        try:
            return self.c.publish(topic, payload, qos=qos, retain=retain).rc == 0
        except Exception:
            return False

    def close(self):
        try:
            self.c.publish(TOPIC_STATUS, "offline", qos=1, retain=True)
            self.c.loop_stop()
            self.c.disconnect()
        except Exception:
            pass


def publish_once(host, port, topic, payload, qos=1, timeout=3):
    """Fire-and-forget publish for short-lived processes (e.g. the dashboard). Never raises."""
    try:
        import paho.mqtt.publish as pub
        pub.single(topic, payload, qos=qos, hostname=host, port=port, keepalive=timeout)
        return True
    except Exception:
        return False
