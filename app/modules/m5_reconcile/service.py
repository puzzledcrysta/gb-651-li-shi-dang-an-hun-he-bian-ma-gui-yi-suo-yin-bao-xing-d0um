from . import core


def execute(payload: dict | None = None, store=None) -> dict:
    return core.run(payload or core.SAMPLE, store=store)
