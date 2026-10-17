"""Scheduled refresh: `python -m lifeline_data.worker [--once]`.

Refreshes all sources every DATA_REFRESH_INTERVAL_SECONDS (default 6 h). Keeps running with no
network: failed sources fall back to cached or mock data, and the loop continues.
"""

from __future__ import annotations

import argparse
import asyncio
import contextlib
import logging
from collections import Counter

from lifeline_data.hub import DataHub
from lifeline_data.logsafe import quiet_http_loggers
from lifeline_data.settings import DataSettings

log = logging.getLogger("lifeline_data.worker")


async def refresh_once(hub: DataHub) -> dict[str, str]:
    try:
        statuses = await hub.refresh_all()
    except Exception:  # the hub never raises, but the worker must never die
        log.exception("refresh failed")
        return {}
    summary: dict[str, str] = {s.id: s.status for s in statuses}
    log.info("refresh done: %s", dict(Counter(summary.values())))
    for s in statuses:
        if s.last_error and s.status != "live":
            log.info("source %s: %s (%s)", s.id, s.status, s.last_error)
    return summary


async def run(once: bool = False, settings: DataSettings | None = None) -> None:
    settings = settings or DataSettings()
    hub = DataHub(settings)
    try:
        while True:
            await refresh_once(hub)
            if once:
                return
            await asyncio.sleep(settings.data_refresh_interval_seconds)
    finally:
        await hub.aclose()


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Lifeline data refresh worker")
    parser.add_argument("--once", action="store_true", help="refresh one time and exit")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    quiet_http_loggers()
    with contextlib.suppress(KeyboardInterrupt):
        asyncio.run(run(once=args.once))


if __name__ == "__main__":
    main()
