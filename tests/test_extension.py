"""The CBPi glue: beats keep coming, survive a failed publish, and end with one stopped beat."""
import asyncio
import json
import sys
import types
from pathlib import Path
from types import SimpleNamespace as NS

sys.path.insert(0, str(Path(__file__).parents[1]))
# Stand-in for cbpi.api so the extension imports without CBPi installed.
sys.modules.setdefault('cbpi', types.ModuleType('cbpi'))
sys.modules.setdefault('cbpi.api', types.ModuleType('cbpi.api'))
sys.modules['cbpi.api'].CBPiExtension = object

from cbpi4_heartbeat_watchdog import extension  # noqa: E402


class Satellite:
    def __init__(self, fail_first=0):
        self.beats, self.fail = [], fail_first

    async def publish(self, topic, message, retain=False):
        if self.fail:
            self.fail -= 1
            raise RuntimeError('broker hiccup')
        assert (topic, retain) == ('cbpi/heartbeat', False)
        self.beats.append(json.loads(message))


def fake_cbpi(satellite):
    heater = NS(id='h', name='Heater', instance=NS(get_state=lambda: True, topic='cbpi/actor/h'))
    return NS(satellite=satellite, actor=NS(data=[heater]), app=NS(on_cleanup=[], on_shutdown=[]))


def run(coro):
    return asyncio.run(coro)


def test_beats_survive_a_failed_publish_and_stop_cleanly(monkeypatch):
    monkeypatch.setattr(extension, 'INTERVAL', 0.01)

    async def scenario():
        sat = Satellite(fail_first=1)
        cbpi = fake_cbpi(sat)
        hb = extension.Heartbeat(cbpi)
        await asyncio.sleep(0.1)
        await cbpi.app.on_cleanup[0](cbpi.app)
        n = len(sat.beats)
        await asyncio.sleep(0.05)
        return sat.beats, n

    beats, at_cleanup = run(scenario())
    assert len(beats) == at_cleanup, 'beats kept coming after cleanup'
    assert len(beats) >= 4, 'the failed first publish stopped the loop'
    assert all(b['state'] == 'running' for b in beats[:-1])
    assert beats[-1]['state'] == 'stopped'
    assert beats[-1]['on'][0]['topic'] == 'cbpi/actor/h', 'stopped beat must still list what is on'


def test_mqtt_disabled_does_nothing():
    async def scenario():
        cbpi = fake_cbpi(None)
        extension.Heartbeat(cbpi)
        return cbpi.app.on_cleanup

    assert run(scenario()) == []


def test_websockets_closed_on_shutdown():
    """Open UI WebSockets otherwise hold CBPi's shutdown past systemd's stop timeout."""
    closed = []

    class WS:
        async def close(self, code=None, message=None):
            closed.append(code)

    cbpi = fake_cbpi(None)  # MQTT off: the close is wired up anyway
    cbpi.ws = NS(_clients={WS(), WS()})
    ext = extension.Heartbeat(cbpi)
    run(cbpi.app.on_shutdown[0](None))
    assert len(closed) == 2 and ext.cbpi is cbpi
