import os
import sys


def _enableWindowsANSI() -> None:
    """Turn on ANSI escape code support in older Windows consoles (no effect elsewhere)."""
    try:
        import ctypes

        kernel32 = ctypes.windll.kernel32
        handle = kernel32.GetStdHandle(-11)  # STD_OUTPUT_HANDLE
        mode = ctypes.c_uint32()
        if kernel32.GetConsoleMode(handle, ctypes.byref(mode)):
            kernel32.SetConsoleMode(handle, mode.value | 0x0004)  # ENABLE_VIRTUAL_TERMINAL_PROCESSING
    except Exception:
        pass


if os.name == "nt":
    _enableWindowsANSI()


class ChatColor:

    """
    A class that defines ANSI escape codes for various text colors and formatting in the terminal.

    Use ChatColor.paint(text, *styles) to color text. Colors are skipped automatically when
    output is not a terminal (e.g. redirected to a file or captured by tests) or when the
    NO_COLOR environment variable is set.
    """

    # Dark colors
    DARK_BLACK = "\033[30m"
    DARK_RED = "\033[31m"
    DARK_ORANGE = "\033[38;5;208m"
    DARK_YELLOW = "\033[33m"
    DARK_GREEN = "\033[32m"
    DARK_BLUE = "\033[34m"
    DARK_VIOLET = "\033[35m"
    DARK_GRAY = "\033[90m"
    AQUA = "\033[36m"

    # Bright colors
    BLACK = "\033[90m"
    RED = "\033[91m"
    ORANGE = "\033[38;5;214m"
    YELLOW = "\033[93m"
    GREEN = "\033[92m"
    BLUE = "\033[94m"
    VIOLET = "\033[95m"
    CYAN = "\033[96m"
    LIGHT_GRAY = "\033[37m"
    WHITE = "\033[97m"

    # Dark background colors
    BG_DARK_BLACK = "\033[40m"
    BG_DARK_RED = "\033[41m"
    BG_DARK_ORANGE = "\033[48;5;208m"
    BG_DARK_YELLOW = "\033[43m"
    BG_DARK_GREEN = "\033[42m"
    BG_DARK_BLUE = "\033[44m"
    BG_DARK_VIOLET = "\033[45m"
    BG_DARK_GRAY = "\033[100m"

    # Bright background colors
    BG_BRIGHT_BLACK = "\033[100m"
    BG_BRIGHT_RED = "\033[101m"
    BG_BRIGHT_ORANGE = "\033[48;5;214m"
    BG_BRIGHT_YELLOW = "\033[103m"
    BG_BRIGHT_GREEN = "\033[102m"
    BG_BRIGHT_BLUE = "\033[104m"
    BG_BRIGHT_VIOLET = "\033[105m"
    BG_BRIGHT_CYAN = "\033[106m"
    BG_BRIGHT_WHITE = "\033[107m"
    BG_BRIGHT_GRAY = "\033[47m"

    # Special formatting
    RESET = "\33[0m"
    BOLD = "\33[1m"
    UNDERLINE = "\33[4m"
    REVERSED = "\33[7m"

    @staticmethod
    def isEnabled() -> bool:
        """Return True when colors should be printed."""
        if os.environ.get("NO_COLOR"):
            return False
        isatty = getattr(sys.stdout, "isatty", None)
        return bool(isatty and isatty())

    @classmethod
    def paint(cls, text: object, *styles: str) -> str:
        """
        Wrap text in the given styles and reset afterwards.
        Example: ChatColor.paint("Done!", ChatColor.BOLD, ChatColor.GREEN)
        """
        if not styles or not cls.isEnabled():
            return str(text)
        return "".join(styles) + str(text) + cls.RESET