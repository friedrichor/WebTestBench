import textwrap


# ANSI color codes for terminal output formatting
GREEN = '\033[92m'
RED = '\033[91m'
ORANGE = '\033[38;5;214m'
RESET = '\033[0m'


def print_green(*args):
    print(GREEN, *args, RESET)

def print_red(*args):
    print(RED, *args, RESET)

def print_orange(*args):
    print(ORANGE, *args, RESET)


def print_boxed(text: str, padding: int = 1, max_width: int = 150) -> str:
    """
    Return text wrapped in a Unicode box, preserving newlines.
    
    Args:
        text: Input text (may contain newlines).
        padding: Horizontal padding inside the box.
        max_width: Maximum content width (excluding padding and borders).
                   If None, no width limit is applied.
    """
    raw_lines = text.splitlines() or [""]

    # Step 1: apply max_width wrapping if needed
    lines = []
    for line in raw_lines:
        if max_width is not None and max_width > 0:
            wrapped = textwrap.wrap(
                line,
                width=max_width,
                replace_whitespace=False,
                drop_whitespace=False,
            )
            lines.extend(wrapped if wrapped else [""])
        else:
            lines.append(line)

    # Step 2: compute box width
    content_width = max(len(line) for line in lines)
    pad = " " * padding
    box_width = content_width + padding * 2

    # Step 3: render box
    top = "┌" + "─" * box_width + "┐"
    bottom = "└" + "─" * box_width + "┘"
    body = "\n".join(
        "│" + pad + line.ljust(content_width) + pad + "│"
        for line in lines
    )

    boxed_context = f"{top}\n{body}\n{bottom}"
    print(boxed_context)


class Tee:
    """Mirror writes to multiple text streams."""
    def __init__(self, *streams):
        self.streams = streams

    def write(self, data):
        for stream in self.streams:
            try:
                stream.write(data)
                stream.flush()
            except ValueError:
                # Ignore writes to closed streams to avoid crashing background threads.
                continue
        return len(data)

    def flush(self):
        for stream in self.streams:
            try:
                stream.flush()
            except ValueError:
                # Ignore flushes on closed streams to avoid crashing background threads.
                continue
