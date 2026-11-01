"""Build GitHub-compatible, finite motion from original art and public stories.

Run from any directory: python scripts/build-profile-motion.py
Requires fonttools, Pillow and Playwright (with Microsoft Edge on Windows).
The bundled Lora fonts retain their existing SIL Open Font License.
No analytical pipelines or customer data are used.
"""

import re
from io import BytesIO
from pathlib import Path

from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.ttLib import TTFont
from PIL import Image
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "assets"
FRAME_MS = 100
DURATION_MS = 4800


def outlined_text(text, font_name, x, y, size):
    with TTFont(ROOT / "scripts" / "fonts" / font_name) as font:
        glyphs = font.getGlyphSet()
        cmap = font.getBestCmap()
        cursor = 0
        paths = []
        for character in text:
            name = cmap[ord(character)]
            pen = SVGPathPen(glyphs)
            glyphs[name].draw(pen)
            paths.append(
                f'<path transform="translate({cursor} 0)" d="{pen.getCommands()}"/>'
            )
            cursor += font["hmtx"][name][0]
        scale = size / font["head"].unitsPerEm
        return (
            f'<g transform="translate({x} {y}) scale({scale} {-scale})">'
            + "".join(paths)
            + "</g>"
        )


def build_banner():
    template = (ROOT / "scripts" / "profile-banner.svg").read_text(encoding="utf-8")
    banner = template.replace(
        "__FIRST_LINE__",
        outlined_text("Good questions.", "Lora-Regular.ttf", 56, 135, 58),
    ).replace(
        "__SECOND_LINE__",
        outlined_text("Clearer connections.", "Lora-Italic.ttf", 56, 215, 58),
    )
    (ASSETS / "profile-banner.svg").write_text(banner, encoding="utf-8")
    still = re.sub(
        r"/\* MOTION_START \*/.*?/\* MOTION_END \*/", "", banner, flags=re.DOTALL
    )
    (ASSETS / "profile-banner-static.svg").write_text(still, encoding="utf-8")


def capture_preview(browser, name, url, viewport=(1440, 900)):
    width, height = viewport
    page = browser.new_page(
        viewport={"width": width, "height": height},
        device_scale_factor=1,
        color_scheme="light",
        reduced_motion="no-preference",
    )
    try:
        page.goto(url, wait_until="networkidle")
        page.evaluate("document.fonts.ready")
        page.evaluate(
            """() => {
                window.previewAnimations = document.getAnimations();
                window.previewAnimations.forEach(animation => animation.pause());
            }"""
        )
        frames = []
        for time in range(0, DURATION_MS + 1, FRAME_MS):
            page.evaluate(
                """time => window.previewAnimations.forEach(animation => {
                    animation.currentTime = time;
                })""",
                time,
            )
            image = Image.open(BytesIO(page.screenshot())).convert("RGB")
            frames.append(
                image.resize(
                    (960, round(height * 960 / width)), Image.Resampling.LANCZOS
                )
            )
        # A shared palette avoids colour shimmer as details move between frames.
        palette = frames[-1].quantize(colors=128)
        frames[-1].save(ASSETS / f"{name}-still.png", optimize=True)
        indexed = [
            frame.quantize(palette=palette, dither=Image.Dither.NONE)
            for frame in frames
        ]
        # Omit GIF's loop extension: play once, then leave the complete story visible.
        indexed[0].save(
            ASSETS / f"{name}-motion.gif",
            save_all=True,
            append_images=indexed[1:],
            duration=FRAME_MS,
            optimize=True,
            disposal=1,
        )
        print(f"Built {name}: {len(frames)} frames; one finite introduction.")
    finally:
        page.close()


def main():
    ASSETS.mkdir(exist_ok=True)
    build_banner()
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(channel="msedge")
        try:
            capture_preview(
                browser,
                "engagement-atlas",
                "https://mberca.github.io/engagement-atlas/?scoutTheme=light",
            )
            capture_preview(
                browser,
                "wonderland",
                "https://mberca.github.io/alice-in-wonderland-analysis/?scoutTheme=light",
            )
            capture_preview(
                browser,
                "titanic",
                "https://mberca.github.io/titanic-patterns/?scoutTheme=light",
                viewport=(1600, 1400),
            )
        finally:
            browser.close()


if __name__ == "__main__":
    main()
