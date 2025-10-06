import logging, sys

def setup_logging() -> None:
    fmt = "%(asctime)s %(levelname)s %(name)s: %(message)s"
    handler = logging.StreamHandler(sys.stdout)
    logging.basicConfig(level=logging.INFO, format=fmt, handlers=[handler])
