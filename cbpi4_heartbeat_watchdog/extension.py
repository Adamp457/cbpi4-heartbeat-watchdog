"""CBPi 4.7.7 extension: publish the heartbeat every second, and a final one on clean shutdown."""
import asyncio
import json
import logging

from cbpi.api import CBPiExtension

from .snapshot import INTERVAL, TOPIC, snapshot

log = logging.getLogger(__name__)


class Heartbeat(CBPiExtension):

    def __init__(self, cbpi):
        self.cbpi = cbpi
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
