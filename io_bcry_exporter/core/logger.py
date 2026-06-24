# ------------------------------------------------------------------------------
# Name:        core/logger.py
# Purpose:     Pipeline for console logging and stdout messages
# ------------------------------------------------------------------------------

from . import exceptions


class OutPipe:
    """Formats and prints messages to the console based on level classification."""

    def pump(self, message, message_type="info", newline=False):
        if newline:
            print()

        if message_type == "info":
            print(f"[Info] BCry: {message!r}")

        elif message_type == "debug":
            print(f"[Debug] BCry: {message!r}")

        elif message_type == "warning":
            print(f"[Warning] BCry: {message!r}")

        elif message_type == "error":
            print(f"[Error] BCry: {message!r}")

        else:
            raise exceptions.BCryException(f"No such message type {message_type!r}")


# Instantiate the logger locally for direct internal module use
op = OutPipe()


def bcPrint(msg, message_type="info", newline=False):
    """Primary logging function used globally across modules."""
    op.pump(msg, message_type, newline)
