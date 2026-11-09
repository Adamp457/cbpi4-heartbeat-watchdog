"""Heartbeat payload: which actors are on, and how to switch each one off over MQTT."""
import json

TOPIC = 'cbpi/heartbeat'  # ponytail: fixed; make it a CBPi config value if two CBPis share a broker
INTERVAL = 1.  # s


def off_payload(instance):
    """The payload CBPi's own MQTT actor would publish to switch off, or None if not an MQTT actor."""
    if not getattr(instance, 'topic', None):
        return None
    template = getattr(instance, 'payload', None)  # GenericMqttActor / TasmotaMqttActor
    if isinstance(template, str) and template:
        return template.format(switch_onoff='off', switch_10=0, power=0)
    return json.dumps({'state': 'off', 'power': 0})  # MQTTActor / OutputMQTTActor


def snapshot(actors, state='running'):
    on = []
    for a in actors:
        # Live state is on the instance; Actor.state is a stale dataclass default (CBPi 4.7.7).
        if a.instance is None or not a.instance.get_state():
            continue
        off = off_payload(a.instance)
        on.append(dict(id=a.id, name=a.name,
                       topic=a.instance.topic if off is not None else None, off=off))
    return dict(state=state, interval=INTERVAL, on=on)
