import logging


# one format for every service: without it warnings print bare, no level or time (live: missed errors)
def setup(level: int = logging.INFO) -> None:
    logging.basicConfig(level=level, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    logging.getLogger("httpx").setLevel(logging.WARNING)  # one INFO line per request drowns the rest
