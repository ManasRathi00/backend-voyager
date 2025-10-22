import sys
import logging
import json
import traceback


class AutomaticExceptionLogger(logging.Logger):
    def error(self, msg, *args, **kwargs):
        kwargs.setdefault("exc_info", True)
        super().error(msg, *args, **kwargs)


def setup_logger():
    logging.setLoggerClass(AutomaticExceptionLogger)


    logger = logging.getLogger("transcriber_application") 
    logger.setLevel(logging.INFO)


    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_formatter = logging.Formatter(
        "%(asctime)s - %(filename)s - line %(lineno)d - %(levelname)s - %(message)s"
    )
    console_handler.setFormatter(console_formatter)
    logger.addHandler(console_handler)

    return logger

logger = setup_logger()