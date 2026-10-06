#!/usr/bin/env python3
"""Render the stadium background (frontend/public/stadium.jpg) procedurally.

No third-party photos are used, so there are no image rights issues. To use your own photo, replace
frontend/public/stadium.jpg (recommended: dark, 2400x1350 or larger).

Requirements (dev only):  pip install numpy pillow
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

W, H = 2400, 1350
ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "frontend/public/stadium.jpg"
rng = np.random.default_rng(2027)


def layer() -> tuple[Image.Image, ImageDraw.ImageDraw]:
    img = Image.new("L", (W, H), 0)
    return img, ImageDraw.Draw(img)


def arr(img: Image.Image) -> np.ndarray:
    return np.asarray(img, dtype=np.float32) / 255.0


def blur(img: Image.Image, radius: float) -> Image.Image:
    return img.filter(ImageFilter.GaussianBlur(radius))


def mix(base: np.ndarray, mask: np.ndarray, color: tuple[float, float, float], alpha: float = 1.0) -> np.ndarray:
    c = np.array(color, dtype=np.float32) / 255.0
    m = (mask * alpha)[..., None]
    return base * (1 - m) + c * m


def add(base: np.ndarray, mask: np.ndarray, color: tuple[float, float, float], strength: float) -> np.ndarray:
    c = np.array(color, dtype=np.float32) / 255.0
    return base + mask[..., None] * c * strength


def main() -> None:
    y = np.linspace(0, 1, H, dtype=np.float32)[:, None]
    x = np.linspace(0, 1, W, dtype=np.float32)[None, :]

    # night sky
    top, horizon = np.array([2, 3, 9]) / 255, np.array([14, 22, 48]) / 255
    t = np.clip(y / 0.5, 0, 1)
    img = (top * (1 - t[..., None]) + horizon * t[..., None]) * np.ones((H, W, 1), dtype=np.float32)

    # stadium bowl: upper ring (stands) between two ellipses
    stands, d = layer()
    d.ellipse([-500, 330, W + 500, 1650], fill=255)
    inner, d2 = layer()
    d2.ellipse([-150, 770, W + 150, 1500], fill=255)
    stands_m = np.clip(arr(stands) - arr(inner), 0, 1)
    img = mix(img, stands_m, (8, 10, 18))
    # crowd texture lit by spill light (brighter towards the field)
    crowd = rng.random((H, W)).astype(np.float32)
    crowd = (crowd > 0.82).astype(np.float32) * rng.uniform(0.15, 0.6, (H, W)).astype(np.float32)
    crowd_img = blur(Image.fromarray((crowd * 255).astype(np.uint8)), 0.8)
    spill = np.clip((y - 0.3) / 0.45, 0, 1) ** 1.5
    tint = np.stack([0.75 + 0.25 * (1 - x), 0.72 * np.ones_like(x), 0.75 + 0.25 * x], -1)
    img = img + (arr(crowd_img) * stands_m * spill)[..., None] * tint * 0.55
    # tier lines
    tiers, d3 = layer()
    for i, top_y in enumerate((420, 520, 610)):
        d3.arc([-480 + i * 60, top_y, W + 480 - i * 60, 1650 - i * 40], 180, 360, fill=150, width=3)
    img = add(img, arr(blur(tiers, 1.5)) * stands_m, (120, 140, 190), 0.25)
    # roof rim
    rim, d4 = layer()
    d4.arc([-500, 330, W + 500, 1650], 180, 360, fill=255, width=5)
    img = add(img, arr(blur(rim, 2)), (170, 190, 255), 0.6)

    # floodlight banks + beams + bloom
    beams, db = layer()
    bulbs, dl = layer()
    banks = [(260, 470), (700, 380), (1200, 345), (1700, 380), (2140, 470)]
    for bx, by in banks:
        for r in range(3):
            for c in range(6):
                lx, ly = bx - 45 + c * 16, by - 22 + r * 12
                dl.rectangle([lx, ly, lx + 10, ly + 7], fill=255)
        db.polygon([(bx - 40, by), (bx + 40, by), (W / 2 + (bx - W / 2) * 0.35 + 420, H), (W / 2 + (bx - W / 2) * 0.35 - 420, H)],
                   fill=60)
    beam_m = arr(blur(beams, 40)) * np.clip(1.2 - y, 0, 1)
    img = add(img, beam_m, (190, 205, 255), 0.35)
    bulb_m = arr(bulbs)
    img = add(img, bulb_m, (255, 255, 255), 2.2)
    img = add(img, arr(blur(bulbs, 12)), (210, 225, 255), 2.6)
    img = add(img, arr(blur(bulbs, 60)), (140, 165, 255), 2.4)
    img = add(img, arr(blur(bulbs, 180)), (90, 110, 200), 1.6)

    # field with perspective
    field, df = layer()
    vp_x, horizon_y = W / 2, 790
    df.polygon([(-900, H), (W + 900, H), (W / 2 + 900, horizon_y), (W / 2 - 900, horizon_y)], fill=255)
    field_m = arr(field)
    depth = np.clip((y - horizon_y / H) / (1 - horizon_y / H), 0, 1)
    turf = np.stack([0.02 + 0.02 * depth, 0.09 + 0.08 * depth, 0.05 + 0.04 * depth], -1)
    # mowing pattern: bands get wider towards the camera
    band = np.floor(np.log1p((y * H - horizon_y).clip(0) / 18) * 4.2)
    stripes = (band % 2 == 0).astype(np.float32) * 0.022
    img = img * (1 - field_m[..., None]) + (turf + stripes[..., None]) * field_m[..., None]
    lines, dlines = layer()
    for side in (-1, 1):  # sidelines converge to the vanishing point
        bottom_x = W / 2 + side * 1750
        dlines.line([(vp_x + (bottom_x - vp_x) * 0.3, horizon_y + 4), (bottom_x, H)], fill=230, width=6)
    for k in range(1, 22):  # yard lines every 5 yards, thicker every 10
        f = k / 22
        yy = horizon_y + (H - horizon_y) * f**1.9
        half = 525 + 1225 * f**1.9
        dlines.line([(W / 2 - half, yy), (W / 2 + half, yy)], fill=230 if k % 2 == 0 else 120,
                    width=max(1, int(1 + 4 * f**1.9)))
        for hx in (-0.18, 0.18):  # hash marks
            cx = W / 2 + hx * half * 2
            dlines.line([(cx - 4 - 10 * f, yy), (cx + 4 + 10 * f, yy)], fill=200, width=max(2, int(2 + 6 * f)))
    img = add(img, arr(blur(lines, 1.0)) * field_m * (0.25 + 0.75 * depth), (230, 240, 235), 0.22)

    # camera flashes in the crowd
    flashes, dfl = layer()
    for _ in range(140):
        fx, fy = rng.uniform(0, W), rng.uniform(380, 760)
        r = rng.uniform(1.2, 2.6)
        dfl.ellipse([fx - r, fy - r, fx + r, fy + r], fill=255)
    flash_m = arr(flashes) * stands_m
    img = add(img, flash_m, (255, 255, 255), 0.9)
    img = add(img, arr(blur(Image.fromarray((flash_m * 255).astype(np.uint8)), 6)), (200, 215, 255), 1.4)

    # haze, conference glows, vignette
    haze = blur(Image.fromarray((rng.random((H // 8, W // 8)) * 255).astype(np.uint8)).resize((W, H)), 60)
    img = add(img, (arr(haze) - 0.5) * np.clip(1.1 - y, 0, 1), (120, 140, 200), 0.12)
    afc = np.exp(-(((x - 0.04) / 0.32) ** 2 + ((y - 0.62) / 0.42) ** 2))
    nfc = np.exp(-(((x - 0.96) / 0.32) ** 2 + ((y - 0.62) / 0.42) ** 2))
    img = add(img, afc, (230, 30, 60), 0.30)
    img = add(img, nfc, (40, 110, 255), 0.30)
    vignette = np.clip(1 - 0.75 * (((x - 0.5) / 0.75) ** 2 + ((y - 0.45) / 0.85) ** 2), 0, 1)
    img = img * (0.35 + 0.65 * vignette[..., None])

    # tone map + grain
    img = 1 - np.exp(-img * 1.35)
    img = img + rng.normal(0, 0.012, img.shape).astype(np.float32)
    out = (np.clip(img, 0, 1) ** (1 / 1.08) * 255).astype(np.uint8)
    Image.fromarray(out).save(OUT, quality=80, optimize=True, progressive=True)
    print(f"wrote {OUT.relative_to(ROOT)} ({OUT.stat().st_size // 1024} KB)")


if __name__ == "__main__":
    main()
