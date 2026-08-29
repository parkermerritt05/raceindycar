import logging

LOGGER = logging.getLogger("fastindycar")
LEVELS = {
    "DEBUG": logging.DEBUG,
    "INFO": logging.INFO,
    "WARNING": logging.WARNING,
    "ERROR": logging.ERROR,
    "CRITICAL": logging.CRITICAL,
}


def set_log_level(level):
    if isinstance(level, str):
        level = LEVELS[level.upper()]
    LOGGER.setLevel(level)
    if not LOGGER.handlers:
        LOGGER.addHandler(logging.StreamHandler())
