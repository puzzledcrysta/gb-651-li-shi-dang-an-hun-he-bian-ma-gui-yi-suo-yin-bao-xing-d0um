from . import core


def execute(payload: dict | None = None, store=None) -> dict:
    payload = payload or {"store": store}
    if "store" not in payload:
        payload = payload | {"store": store}
    return core.run(payload)


def latest(store) -> dict | None:
    return core.latest_reconcile(store)
