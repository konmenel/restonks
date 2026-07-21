"""Color themes for the restonks GUI.

Each `Theme` maps directly onto Quasar's own color/dark-mode system via
`apply_theme` (`ui.dark_mode` + `ui.colors`), so switching themes doesn't
require any custom CSS, Quasar's native components (cards, tables,
inputs) already re-theme themselves.
"""

from dataclasses import dataclass

from nicegui import ui


@dataclass(frozen=True)
class Theme:
    name: str
    dark: bool
    primary: str
    secondary: str
    background: str
    accent: str


THEMES: dict[str, Theme] = {
    theme.name: theme
    for theme in [
        # --- Dark themes ---------------------------------------------------
        Theme(
            name="DarkMidnight",
            dark=True,
            primary="#4f8cff",
            secondary="#2b3040",
            background="#0b0d12",
            accent="#34d399",
        ),
        Theme(
            name="DarkDracula",
            dark=True,
            primary="#bd93f9",
            secondary="#44475a",
            background="#1e1f29",
            accent="#50fa7b",
        ),
        Theme(
            name="DarkEmerald",
            dark=True,
            primary="#10b981",
            secondary="#1f2e2a",
            background="#0a1210",
            accent="#34d399",
        ),
        # --- Light themes ----------------------------------------------------
        Theme(
            name="LightArctic",
            dark=False,
            primary="#2563eb",
            secondary="#e2e8f0",
            background="#f8fafc",
            accent="#0d9488",
        ),
        Theme(
            name="LightSandstone",
            dark=False,
            primary="#b45309",
            secondary="#f1e4d2",
            background="#fdf8f0",
            accent="#c2410c",
        ),
        Theme(
            name="LightMint",
            dark=False,
            primary="#0d9488",
            secondary="#d9f2ec",
            background="#f4fbf9",
            accent="#059669",
        ),
    ]
}

DEFAULT_THEME = "DarkMidnight"
THEME_NAMES = list(THEMES.keys())


def apply_theme(theme_name: str, dark_mode: ui.dark_mode) -> None:
    theme = THEMES[theme_name]
    dark_mode.value = theme.dark
    ui.colors(
        primary=theme.primary,
        secondary=theme.secondary,
        accent=theme.accent,
        dark=theme.background,
    )
    ui.query("body").style(f"background-color: {theme.background}")
