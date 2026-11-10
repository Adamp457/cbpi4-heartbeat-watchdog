# cbpi4-heartbeat-watchdog

A heartbeat for CraftBeerPi 4, so that something outside CBPi can switch its
MQTT actors off if CBPi dies, hangs or stops with them still on.

It works with any kettle or fermenter logic, because it watches CBPi itself
rather than one plugin.

**This is not a safety system.** It's a convenience fallback for software
failure. Fit hardwired over-temperature and dry-fire cutouts on every
element, independent of CBPi, MQTT and your controller board.

## Why

MQTT-driven panels (MQTTDevice32 and similar) act on CBPi's **retained**
actor commands. If CBPi crashes or hangs while a heater is on, the panel keeps
the last `on` and the broker keeps serving it. A clean CBPi stop doesn't help
either: CBPi 4.7.7 doesn't switch MQTT actors off on shutdown.

CBPi does set an MQTT Last Will (`cbpi/disconnect`), but the broker only sends
it after about 1.5× the keepalive (60 s by default), and it doesn't say which
actors were on.

## What it does

Two parts that share one contract:

1. **CBPi plugin** (this package). It publishes `cbpi/heartbeat` once a second,
   listing every actor that is on and the exact MQTT payload that switches it
   off. On a clean shutdown it publishes a final `stopped` beat that still lists
   whatever is on.
2. **Home Assistant blueprint**
   ([blueprints/cbpi_heartbeat_watchdog.yaml](blueprints/cbpi_heartbeat_watchdog.yaml)).
   If the heartbeat goes silent for the timeout while actors are on, or a
   `stopped` beat lists actors, it publishes each one's off payload (retained,
   like CBPi does) and runs your alert actions.

Anything that can subscribe and publish over MQTT can do the job of part 2:
Node-RED, a script, another controller. The
[MQTTDevice32pIO fork](https://github.com/Adamp457/MQTTDevice32pIO) does it on
the device itself, with no Home Assistant (see its `docs/heartbeat.md`). It
only reads `state` and switches off its own actors, so the allowlists below
don't apply to it.

## Heartbeat contract (v1)

Topic `cbpi/heartbeat`, not retained, every `interval` seconds:

```json
{
  "state": "running",
  "interval": 1.0,
  "on": [
    {"id": "mreWEX...", "name": "HLT Heater", "topic": "cbpi/actor/HLTHeater",
     "off": "{\"state\": \"off\", \"power\": 0}"},
    {"id": "abc123", "name": "GPIO Pump", "topic": null, "off": null}
  ]
}
```

- `state`: `running`, or `stopped` once, on a clean CBPi shutdown.
- `on`: actors that are on. `topic`/`off` are the MQTT topic and the payload
  CBPi itself would publish to switch that actor off. They're `null` for actors
  that aren't MQTT actors (GPIO, relay boards). Those can't be switched off from
  outside CBPi, only reported.
- Off payloads: `MQTTActor` and `OutputMQTTActor` use
  `{"state": "off", "power": 0}`; `GenericMqttActor` and `TasmotaMqttActor`
  use their configured payload template rendered for off.
- A watchdog should act when no beat arrives for a few intervals while the last
  beat's `on` was non-empty, or when a `stopped` beat has a non-empty `on`. It
  should publish each `off` to its `topic` **retained**.

## Install

On the CBPi host, in CBPi's environment, install the wheel from the
[latest release](https://github.com/Adamp457/cbpi4-heartbeat-watchdog/releases/latest).
It isn't on PyPI.

```sh
pipx runpip cbpi4 install https://github.com/Adamp457/cbpi4-heartbeat-watchdog/releases/download/v0.1.0/cbpi4_heartbeat_watchdog-0.1.0-py3-none-any.whl
# or: <cbpi venv>/bin/pip install <that URL or a downloaded wheel>
sudo systemctl restart craftbeerpi   # the unit may be called cbpi on your host
```

MQTT must be enabled in CBPi's `config.yaml` (`mqtt: true`). There are no
settings. The plugin logs a warning and does nothing if MQTT is off.

Then in Home Assistant, import the blueprint from its GitHub URL, and create an
automation from it. Set the timeout (default 15 s) and at least one alert
action, e.g. a mobile notification using `{{ message }}`.

## Security

The heartbeat tells the watchdog what to publish, retained, with the
watchdog's broker credentials. Unchecked, anyone who can publish to
`cbpi/heartbeat` could make it publish anything anywhere, including an
"off" that actually switches a heater **on**. So the blueprint publishes only
when **both** of these hold:

- the topic starts with an **allowed prefix** (default `cbpi/actor/`), and has
  no MQTT wildcards;
- the payload exactly matches an **allowed off payload** (defaults:
  `{"state": "off", "power": 0}`, `OFF`, `off`).

Anything else is refused and named in the alert. Set the prefixes to where
your actor topics actually live. If you use `GenericMqttActor`, add its
rendered off payload.

Also restrict who can publish to `cbpi/heartbeat` with broker ACLs. The
allowlist stops a forged beat switching things on, but a forged beat
saying `on: []` can still hide a real failure from the watchdog.

## Limits

- **One CBPi per broker.** The topic is fixed.
- **A hung kettle logic inside a healthy CBPi** keeps the heartbeat going, so
  this can't detect it. That's the logic's own job.
- **If the broker or the watchdog host is down,** nothing here runs. Your panel's
  own MQTT-loss behaviour and the hardwired cutouts are what's left.

## Development

```sh
python3 -m pytest tests -q
python3 -m pip wheel --no-deps --wheel-dir dist .
```

## Verification

- **Plugin, end to end** (2026-11-10): the 0.1.0 wheel in CBPi 4.7.7
  (Python 3.13) in a dev rig, against a private broker,
  recorded with `mosquitto_sub`.
  - With nothing on, beats arrive once a second.
  - Switching an `MQTTActor` on lists it within a beat, with the topic and
    `{"state": "off", "power": 0}`.
  - A clean stop (`SIGTERM`) sends one `stopped` beat that still lists the
    actor.
  - After a restart, beats resume with `on: []`, but the broker still holds
    the retained `on`. That's the case the watchdog exists for.
  - After a hard kill (`SIGKILL`), beats stop and no `stopped` beat is sent.
- **Unit tests:** the payload builder, plus the CBPi glue with a fake
  CBPi. The glue tests check that beats keep coming after a failed publish,
  that one final `stopped` beat follows cleanup, and that nothing happens
  with MQTT off.
- **Blueprint** (HA 2026.11, 2026-11-10): tested with a forged `stopped` beat on
  a scratch topic when the allowlists were added (commit `db590be`). It hasn't
  been re-run since, and the blueprint is unchanged.
- **Production install** (2026-11-10): v0.1.0 installed on a production CBPi
  4.7.7 from the release URL above, using `--no-deps`. It loaded cleanly, and
  beats arrived once a second on the production broker, with nothing on.
- **Not yet tested:** a production CBPi driving a real kettle with the
  blueprint or the MQTTDevice firmware acting on it.

## Licence

GPL-3.0-or-later, matching CraftBeerPi 4.
