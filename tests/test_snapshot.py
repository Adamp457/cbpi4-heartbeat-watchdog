import json
import sys
from pathlib import Path
from types import SimpleNamespace as NS

sys.path.insert(0, str(Path(__file__).parents[1]))

from cbpi4_heartbeat_watchdog.snapshot import snapshot  # noqa: E402


def actor(id, on, **instance):
    # Actor.state is deliberately the opposite: CBPi doesn't keep it current.
    return NS(id=id, name=id.title(), state=not on, instance=NS(get_state=lambda: on, **instance))


def test_lists_only_on_actors_with_their_off_payloads():
    beat = snapshot([
        actor('heater', True, topic='brew/heater'),                                 # MQTTActor
        actor('plug', True, topic='tasmota/cmnd/POWER', payload='{switch_onoff}'),  # Generic/Tasmota
        actor('pump', False, topic='brew/pump'),
        actor('gpio', True),                                                        # not MQTT
    ])
    assert beat['state'] == 'running'
    assert beat['on'] == [
        dict(id='heater', name='Heater', topic='brew/heater', off='{"state": "off", "power": 0}'),
        dict(id='plug', name='Plug', topic='tasmota/cmnd/POWER', off='off'),
        dict(id='gpio', name='Gpio', topic=None, off=None),
    ]
    json.dumps(beat)


def test_actor_without_instance_is_skipped():
    assert snapshot([NS(id='x', name='X', state=True, instance=None)])['on'] == []


def test_stopped_and_empty():
    assert snapshot([], 'stopped') == dict(state='stopped', interval=1., on=[])
