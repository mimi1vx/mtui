#
# implementation of a logging.Formatter to enable color output
#

import inspect
import logging

(BLACK, RED, GREEN, YELLOW, BLUE, MAGENTA, CYAN, WHITE) = list(range(8))

RESET_SEQ = "\033[0m"
COLOR_SEQ = "\033[1;{}m"

COLORS = {
    "WARNING": YELLOW,
    "INFO": GREEN,
    "DEBUG": BLUE,
    "CRITICAL": RED,
    "ERROR": RED,
}


class ColorFormatter(logging.Formatter):
    def __init__(self, msg) -> None:
        logging.Formatter.__init__(self, msg)

    def formatColor(self, levelname: str) -> str:
        if levelname == "DEBUG":
            caller = inspect.currentframe()
            frame, _, _, function, _, _ = inspect.getouterframes(caller)[9]
            if mo := inspect.getmodule(frame):
                module = mo.__name__
            else:
                module = "unknown"
            return (
                "\033[2K"
                + COLOR_SEQ.format(30 + COLORS[levelname])
                + levelname.lower()
                + RESET_SEQ
                + " [{!s}:{!s}]".format(module, function)
                + RESET_SEQ
            )
        else:
            return (
                "\033[2K"
                + COLOR_SEQ.format(30 + COLORS[levelname])
                + levelname.lower()
                + RESET_SEQ
            )

    def format(self, record: logging.LogRecord) -> str:
        record.message = record.getMessage()
        if self._fmt and self._fmt.find("%(levelname)") >= 0:
            record.levelname = self.formatColor(record.levelname)

        return logging.Formatter.format(self, record)


def create_logger(name: str, level: str = "INFO") -> logging.Logger:
    out = logging.getLogger(name) if name else logging.getLogger()
    out.setLevel(level)
    handler = logging.StreamHandler()
    formatter = ColorFormatter("%(levelname)s: %(message)s")
    handler.setFormatter(formatter)
    out.addHandler(handler)
    return out
