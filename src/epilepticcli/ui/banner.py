"""EpilepticCLI banner and identity marks."""

from epilepticcli import APP_NAME, __author__, __version__
from epilepticcli.ui.theme import (
    FAINT,
    LAVENDER,
    LILAC,
    MAGENTA,
    VIOLET,
    VIOLET_DEEP,
    VIOLET_DIM,
)

# Half-block wordmark built from geometric glyphs.
WORDMARK = [
    "█▀▀ █▀█ █ █   █▀▀ █▀█ ▀█▀ █ █▀▀",
    "█▀  █▀▀ █ █   █▀  █▀▀  █  █ █  ",
    "▀▀▀ ▀   ▀ ▀▀▀ ▀▀▀ ▀    ▀  ▀ ▀▀▀",
]

RULE = "▞" + "▚▞" * 20 + "▚"

GRADIENT = [VIOLET_DIM, VIOLET_DEEP, VIOLET, LAVENDER, LILAC]


def render(console) -> None:
    from rich.text import Text

    console.print()
    console.print(Text(RULE, style=f"{VIOLET_DIM}"))
    for i, line in enumerate(WORDMARK):
        style = f"bold {GRADIENT[min(i + 1, len(GRADIENT) - 1)]}"
        console.print(Text("  " + line, style=style))
    console.print(Text("   ▸▸ C L I ◂◂", style=f"bold {MAGENTA}"))
    console.print(Text(RULE, style=f"{VIOLET_DIM}"))
    tag = Text()
    tag.append("  multi-provider AI terminal", style=f"{FAINT}")
    tag.append("  ⟢  ", style=f"{VIOLET_DEEP}")
    tag.append(f"v{__version__}", style=f"{LAVENDER}")
    tag.append("  ⟢  ", style=f"{VIOLET_DEEP}")
    tag.append(f"by {__author__}", style=f"italic {FAINT}")
    console.print(tag)
    console.print()


def compact_tag() -> str:
    return f"{APP_NAME} v{__version__} by {__author__}"
