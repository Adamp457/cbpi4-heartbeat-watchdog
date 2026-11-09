# AGENTS.md

Instructions for agents working in this repo (Claude Code reads it via the
`CLAUDE.md` symlink). Claude Code owns development of this project.

## What this is

A CBPi 4 extension that publishes `cbpi/heartbeat`, plus a Home Assistant
blueprint that switches MQTT actors off when the heartbeat stops. See
[README.md](README.md). The heartbeat contract in the README is the public
interface: change it only with a version bump and a README update.

- `cbpi4_heartbeat_watchdog/snapshot.py`: pure payload builder (tested).
- `cbpi4_heartbeat_watchdog/extension.py`: CBPi 4.7.7 glue.
- `blueprints/cbpi_heartbeat_watchdog.yaml`: the HA side.

## Process

Code, tests and docs freely. Ask first (one line) before any write to a
production CBPi or anything that switches a real heater or pump. Nothing in a
dev rig talks to the production broker.

Testing:
- **Dev rig:** a dev CBPi 4.7.7 container with its own private broker. Copy the
  wheel into its `cbpi` container, `pip install`, restart the container, then
  `mosquitto_sub -t cbpi/heartbeat`. Switch an actor on with
  `POST /actor/<id>/on` and a `{}` JSON body (without the body it's a no-op).
- **Blueprint:** test on HA against a scratch topic (`claude/tmp/...`) with a
  short timeout, read the automation traces, then delete the test automation
  and clear any retained scratch topics.

## CBPi 4.7.7 facts this relies on

- Pip plugins load if the top-level module name starts with `cbpi`, and
  `importlib.metadata.version(<module>)` must resolve, so the distribution name
  must normalise to the module name. `config.yaml` in the package is only read
  for CBPi's built-in extensions.
- An actor's live state is `actor.instance.get_state()`. `Actor.state` isn't
  kept current.
- A clean CBPi shutdown doesn't switch MQTT actors off; their retained `on`
  stays on the broker.
- HA script templates parse a rendered JSON string into a dict. `mqtt.publish`
  then re-encodes it as JSON, so a templated off payload arrives intact
  (checked on HA 2026.11).
