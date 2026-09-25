"""EpilepticCLI visual identity: black + violet palette."""

from rich.style import Style
from rich.theme import Theme

# Palette
VIOLET = "#a855f7"
VIOLET_DEEP = "#7c3aed"
VIOLET_DARK = "#6d28d9"
VIOLET_DIM = "#4c1d95"
LAVENDER = "#c084fc"
LILAC = "#e9d5ff"
MAGENTA = "#d946ef"
INK = "#0a0a0f"
FAINT = "#71717a"
FAINTER = "#3f3f46"
WHITE = "#fafafa"
GOOD = "#4ade80"
WARN = "#fbbf24"
BAD = "#f87171"

THEME = Theme(
    {
        "epi.primary": Style(color=VIOLET),
        "epi.deep": Style(color=VIOLET_DEEP),
        "epi.dim": Style(color=VIOLET_DIM),
        "epi.lavender": Style(color=LAVENDER),
        "epi.lilac": Style(color=LILAC),
        "epi.magenta": Style(color=MAGENTA),
        "epi.faint": Style(color=FAINT),
        "epi.fainter": Style(color=FAINTER),
        "epi.text": Style(color=WHITE),
        "epi.good": Style(color=GOOD),
        "epi.warn": Style(color=WARN),
        "epi.bad": Style(color=BAD),
        "markdown.code": Style(color=LAVENDER),
        "markdown.code_block": Style(color=LILAC),
        "markdown.h1": Style(color=VIOLET, bold=True),
        "markdown.h2": Style(color=LAVENDER, bold=True),
        "markdown.h3": Style(color=LAVENDER),
        "markdown.link": Style(color=MAGENTA, underline=True),
        "markdown.block_quote": Style(color=FAINT, italic=True),
        "markdown.item.bullet": Style(color=VIOLET),
        "markdown.item.number": Style(color=VIOLET),
        "markdown.hr": Style(color=VIOLET_DIM),
        "markdown.strong": Style(color=LILAC, bold=True),
        "markdown.emph": Style(color=LAVENDER, italic=True),
        "repr.number": Style(color=MAGENTA),
        "repr.str": Style(color=LAVENDER),
    }
)

# Glyphs
GLYPH_ASSISTANT = "⌬"
GLYPH_TOOL = "◈"
GLYPH_USER = "▚"
GLYPH_OK = "◆"
GLYPH_ERR = "⨯"
GLYPH_SPINNER = "dots12"
GLYPH_SEP = "⟢"
