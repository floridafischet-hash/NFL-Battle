#!/usr/bin/env python3
"""Generate the default team crests (frontend/public/logos/<ABBR>.svg).

The crests are neutral placeholders in the team colors – no trademarked NFL artwork. Replace any
file with an official logo (same file name) or upload a logo per team in the admin area.

Requirements (dev only):  pip install fonttools
Font: Oswald Bold from the frontend dependency @fontsource/oswald (SIL Open Font License).

    python scripts/generate_team_logos.py
"""

from __future__ import annotations

import colorsys
import importlib.util
from pathlib import Path

from fontTools.pens.boundsPen import BoundsPen
from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.ttLib import TTFont

ROOT = Path(__file__).resolve().parents[1]
FONT = ROOT / "frontend/node_modules/@fontsource/oswald/files/oswald-latin-700-normal.woff"
OUT = ROOT / "frontend/public/logos"

SHIELD = "M64 5 L116 21 V60 C116 92 94 113 64 123 C34 113 12 92 12 60 V21 Z"
SHIELD_INNER = "M64 13 L108 27 V60 C108 87 89 105 64 114 C39 105 20 87 20 60 V27 Z"


def load_teams() -> list[tuple]:
    spec = importlib.util.spec_from_file_location("teams", ROOT / "backend/app/seed/teams.py")
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module.NFL_TEAMS


def shade(hex_color: str, factor: float) -> str:
    r, g, b = (int(hex_color[i : i + 2], 16) / 255 for i in (1, 3, 5))
    h, lightness, s = colorsys.rgb_to_hls(r, g, b)
    lightness = max(0.0, min(1.0, lightness * factor))
    r, g, b = colorsys.hls_to_rgb(h, lightness, s)
    return "#%02x%02x%02x" % (round(r * 255), round(g * 255), round(b * 255))


def luminance(hex_color: str) -> float:
    r, g, b = (int(hex_color[i : i + 2], 16) / 255 for i in (1, 3, 5))
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


class TextRenderer:
    def __init__(self, font_path: Path):
        self.font = TTFont(str(font_path))
        self.glyphs = self.font.getGlyphSet()
        self.cmap = self.font.getBestCmap()
        self.upm = self.font["head"].unitsPerEm

    def path(self, text: str, center_x: float, baseline: float, max_width: float, cap_height: float) -> str:
        names = [self.cmap[ord(ch)] for ch in text]
        advance = sum(self.glyphs[n].width for n in names)
        bounds = BoundsPen(self.glyphs)
        self.glyphs[self.cmap[ord("H")]].draw(bounds)
        cap = bounds.bounds[3]
        scale = min(cap_height / cap, max_width / advance)
        x = center_x - advance * scale / 2
        parts = []
        for name in names:
            pen = SVGPathPen(self.glyphs)
            self.glyphs[name].draw(pen)
            d = pen.getCommands()
            if d:
                parts.append(f'<path transform="translate({x:.2f} {baseline:.2f}) scale({scale:.5f} {-scale:.5f})" d="{d}"/>')
            x += self.glyphs[name].width * scale
        return "".join(parts)


def crest(abbr: str, primary: str, secondary: str, text: TextRenderer) -> str:
    top, bottom = shade(primary, 1.35), shade(primary, 0.7)
    if luminance(primary) < 0.04:  # near-black teams get a lighter body
        top, bottom = "#3a3f4b", "#0b0d12"
    stripe = secondary if abs(luminance(secondary) - luminance(primary)) > 0.12 else "#ffffff"
    rim = secondary if abs(luminance(secondary) - luminance(primary)) > 0.12 else shade(primary, 1.8)
    if luminance(rim) < 0.06:  # black rims disappear on the dark UI
        rim = shade(primary, 1.7) if luminance(primary) > 0.04 else "#9ca3af"
    if luminance(stripe) < 0.06:
        stripe = "#1f2430"
    max_width = 78 if len(abbr) <= 2 else 88
    cap = 40 if len(abbr) <= 2 else 34
    letters = text.path(abbr, 64, 78, max_width, cap)
    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 128 128" role="img" aria-label="{abbr}">
<defs>
<linearGradient id="body" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="{top}"/><stop offset="1" stop-color="{bottom}"/></linearGradient>
<linearGradient id="shine" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#fff" stop-opacity=".38"/><stop offset=".5" stop-color="#fff" stop-opacity="0"/></linearGradient>
<clipPath id="clip"><path d="{SHIELD}"/></clipPath>
</defs>
<path d="{SHIELD}" fill="url(#body)"/>
<g clip-path="url(#clip)">
<rect x="55" y="0" width="18" height="128" fill="{stripe}" opacity=".9"/>
<rect x="52" y="0" width="2.5" height="128" fill="#fff" opacity=".55"/>
<rect x="73.5" y="0" width="2.5" height="128" fill="#fff" opacity=".55"/>
<path d="M0 0 H128 V58 C96 46 32 46 0 58 Z" fill="url(#shine)"/>
<path d="M30 98 H98" stroke="#000" stroke-opacity=".25" stroke-width="10"/>
</g>
<path d="{SHIELD}" fill="none" stroke="{rim}" stroke-width="6" stroke-linejoin="round"/>
<path d="{SHIELD_INNER}" fill="none" stroke="#fff" stroke-opacity=".28" stroke-width="1.5"/>
<g fill="#ffffff" stroke="#0a0d14" stroke-width="5" stroke-linejoin="round" paint-order="stroke">{letters}</g>
<g fill="#fff" opacity=".9"><circle cx="50" cy="98" r="2.2"/><circle cx="64" cy="98" r="2.2"/><circle cx="78" cy="98" r="2.2"/></g>
</svg>
"""


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    text = TextRenderer(FONT)
    teams = load_teams()
    for abbr, _city, _short, _conf, _div, primary, secondary in teams:
        (OUT / f"{abbr}.svg").write_text(crest(abbr, primary, secondary, text))
    (OUT / "TBD.svg").write_text(crest("TBD", "#475569", "#94a3b8", text))
    print(f"wrote {len(teams) + 1} crests to {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
