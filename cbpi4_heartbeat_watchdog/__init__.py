def setup(cbpi):
    # Imported here so the pure snapshot logic can be tested without CBPi.
    from .extension import Heartbeat
    cbpi.plugin.register('HeartbeatWatchdog', Heartbeat)
