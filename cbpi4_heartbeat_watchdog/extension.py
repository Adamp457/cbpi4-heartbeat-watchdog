"""CBPi 4.7.7 extension: publish the heartbeat every second, and a final one on clean shutdown.

It also makes the clean shutdown happen: CBPi 4.7.7 never closes its WebSocket clients, so
with any UI tab open aiohttp's graceful shutdown waits on them (60 s), systemd's 30 s stop
timeout SIGKILLs CBPi, and nothing on on_cleanup runs: no kettle stop, no save, no stopped
beat. Closing them on on_shutdown lets the shutdown finish in about a second.
"""
import asyncio
import json
import logging

from cbpi.api import CBPiExtension

from .snapshot import INTERVAL, TOPIC, snapshot

log = logging.getLogger(__name__)


class Heartbeat(CBPiExtension):

    def __init__(self, cbpi):
        self.cbpi = cbpi
        cbpi.app.on_shutdown.append(self._close_websockets)
        if cbpi.satellite is None:
            log.warning('Heartbeat watchdog: MQTT is disabled in CBPi config; nothing will be published')
            return
        cbpi.app.on_cleanup.append(self._stopped)
        self._task = asyncio.create_task(self._run())

    async def _publish(self, state):
        await self.cbpi.satellite.publish(TOPIC, json.dumps(snapshot(self.cbpi.actor.data, state)), False)

    async def _run(self):
        while True:
            try:
                await self._publish('running')
            except asyncio.CancelledError:
                raise
            except Exception:
                # Keep beating; a silent heartbeat is what makes the watchdog act.
                log.exception('Heartbeat watchdog: publish failed')
            await asyncio.sleep(INTERVAL)

    async def _stopped(self, app):
        self._task.cancel()
        # Lists anything still on: a clean CBPi stop leaves MQTT actors' retained "on" in place.
        try:
            await self._publish('stopped')
        except Exception:
            log.warning('Heartbeat watchdog: could not publish stopped heartbeat')

    async def _close_websockets(self, app):
        clients = list(getattr(getattr(self.cbpi, 'ws', None), '_clients', ()))  # CBPi 4.7.7 internals
        for ws in clients:
            try:
                await ws.close(code=1001, message=b'CBPi shutting down')  # 1001 = going away
            except Exception:
                log.warning('Heartbeat watchdog: could not close a WebSocket client at shutdown')
        if clients:
            log.info('Heartbeat watchdog: closed %d WebSocket client(s) for a clean shutdown', len(clients))
