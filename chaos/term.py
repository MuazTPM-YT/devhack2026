import os
import sys
from typing import TextIO

# the UI palette (ui/app/globals.css); oxblood is lifted so it reads on dark terminals too
PAPER = (243, 240, 233)
ROSE_SOFT = (241, 228, 225)
ROSE = (185, 143, 134)
OXBLOOD = (192, 86, 75)
MUTE = (185, 177, 162)
INK = (28, 26, 23)
OK = (47, 107, 59)
WARN = (217, 154, 30)
BAD = (180, 35, 24)

TONES = {"ok": OK, "warn": WARN, "bad": BAD, "idle": (107, 101, 91), "accent": (91, 29, 24)}

RGB = tuple[int, int, int]


def color_on(stream: TextIO | None = None) -> bool:
    s = stream or sys.stdout
    return s.isatty() and "NO_COLOR" not in os.environ


def paint(text: str, fg: RGB | None = None, bold: bool = False, bg: RGB | None = None,
          stream: TextIO | None = None) -> str:
    if not color_on(stream):
        return text
    codes = []
    if bold:
        codes.append("1")
    if fg:
        codes.append("38;2;{};{};{}".format(*fg))
    if bg:
        codes.append("48;2;{};{};{}".format(*bg))
    return f"\x1b[{';'.join(codes)}m{text}\x1b[0m" if codes else text


# status chip like the UI's tags: tone background, paper text; plain [TEXT] without colour
def tag(text: str, tone: str, stream: TextIO | None = None) -> str:
    if not color_on(stream):
        return f"[{text.upper()}]"
    return paint(f" {text.upper()} ", fg=PAPER, bg=TONES.get(tone, TONES["idle"]), bold=True, stream=stream)


def blend(a: RGB, b: RGB, f: float) -> RGB:
    return (round(a[0] + (b[0] - a[0]) * f), round(a[1] + (b[1] - a[1]) * f), round(a[2] + (b[2] - a[2]) * f))


# colour at position f (0..1) along rose-soft -> rose -> oxblood
def gradient(f: float) -> RGB:
    return blend(ROSE_SOFT, ROSE, f * 2) if f < 0.5 else blend(ROSE, OXBLOOD, (f - 0.5) * 2)
