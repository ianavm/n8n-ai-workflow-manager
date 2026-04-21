"""Generate the ``5 Biggest Pain Points of AI`` carousel slides.

Produces 8 slides at 1080x1350 (4:5, Instagram / LinkedIn carousel spec)
matching the AnyVision Media dark + orange editorial brand system.

Why HTML+Playwright rather than Gemini Nano Banana / any image model?
    Image models reliably misspell text and mis-align typography on
    editorial slides. For production carousels we need pixel-perfect
    headlines in Inter Tight, exact brand colors, and consistent layout
    across all 8 slides. HTML templates + a headless browser guarantee
    all of that deterministically.

Output:
    .tmp/carousels/ai-pain-points-2026-04-21/slide{1-8}.html
    .tmp/carousels/ai-pain-points-2026-04-21/slide{1-8}.png   (if --render)

Usage::

    python tools/generate_ai_pain_points_carousel.py           # HTML only
    python tools/generate_ai_pain_points_carousel.py --render  # HTML + PNG

``--render`` requires ``playwright`` + Chromium::

    pip install playwright
    playwright install chromium

Reuse for future carousels:
    Copy this file, swap ``CAROUSEL_ID`` and the ``SLIDES`` list contents.
    The template + render pipeline stays identical.
"""

from __future__ import annotations

import argparse
import logging
import sys
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(message)s")


CAROUSEL_ID = "ai-pain-points-2026-04-21"
OUTPUT_DIR = (
    Path(__file__).parent.parent / ".tmp" / "carousels" / CAROUSEL_ID
)
SLIDE_W = 1080
SLIDE_H = 1350


# =========================================================================
# BRAND SYSTEM
# =========================================================================

COLOR_BG_DARK = "#0B0D10"
COLOR_BG_LIGHT = "#F4F4F2"
COLOR_TEXT_DARK = "#0B0D10"
COLOR_TEXT_LIGHT = "#F4F4F2"
COLOR_ACCENT = "#FF6D5A"
COLOR_SECONDARY = "#8B93A0"

BRAND_HANDLE = "@anyvisionmedia"
BRAND_NAME = "ANYVISION MEDIA"


# =========================================================================
# CONTENT
# =========================================================================

@dataclass(frozen=True)
class Slide:
    number: int
    variant: str  # "dark" or "light"
    eyebrow: str
    headline_html: str  # may contain <u class="accent"> for the orange underline
    body: str
    punchy: str = ""  # optional standout line (large, below body)
    footer_cta: str = ""
    show_swipe_arrow: bool = False


SLIDES: tuple[Slide, ...] = (
    Slide(
        number=1,
        variant="dark",
        eyebrow="AI \u2260 MAGIC",
        headline_html="AI is powerful.<br>Here's where it<br>still <u class='accent'>fails</u>.",
        body="The 5 pain points most businesses only discover <i>after</i> they've wasted time, money, and trust on AI that wasn't ready.",
        punchy="",
        footer_cta="Swipe \u2192",
        show_swipe_arrow=True,
    ),
    Slide(
        number=2,
        variant="dark",
        eyebrow="PAIN POINT 01",
        headline_html="AI doesn't know<br>your <u class='accent'>business</u>.",
        body="Out-of-the-box, it has zero context on your customers, your offer, your tone, or your data. Feed it generic prompts and you'll get generic output.",
        punchy="No context in. No value out.",
    ),
    Slide(
        number=3,
        variant="dark",
        eyebrow="PAIN POINT 02",
        headline_html="It sounds <u class='accent'>confident</u><br>when it's wrong.",
        body="AI hallucinates \u2014 inventing facts, citations, numbers, policies \u2014 and delivers them with the same tone as the truth. Without checks, one confident error can reach a customer.",
        punchy="Confidence is not accuracy.",
    ),
    Slide(
        number=4,
        variant="dark",
        eyebrow="PAIN POINT 03",
        headline_html="AI is only as good<br>as the <u class='accent'>system</u><br>around it.",
        body="A smart model plugged into broken workflows still produces broken outcomes. Without triggers, routing, logging, and review, AI is just an expensive demo.",
        punchy="The model is 10%. The system is 90%.",
    ),
    Slide(
        number=5,
        variant="dark",
        eyebrow="PAIN POINT 04",
        headline_html="Messy data in.<br><u class='accent'>Messy</u> decisions out.",
        body="Duplicate records, stale CRMs, inconsistent labels, half-finished spreadsheets \u2014 AI amplifies whatever you feed it, including the mess.",
        punchy="Garbage in. Garbage \u2014 at scale \u2014 out.",
    ),
    Slide(
        number=6,
        variant="dark",
        eyebrow="PAIN POINT 05",
        headline_html="No human in<br>the loop =<br><u class='accent'>real risk</u>.",
        body="Fully-autonomous AI sending emails, posting content, or making financial calls without review is how brands damage trust overnight. Oversight isn't a bottleneck \u2014 it's the feature.",
        punchy="Automate the work. Supervise the judgment.",
    ),
    Slide(
        number=7,
        variant="light",
        eyebrow="THE TAKEAWAY",
        headline_html="AI isn't the answer.<br>AI with <u class='accent'>structure</u><br>is.",
        body="Context. Guardrails. Clean data. Real workflows. Human oversight. Get these right and AI stops being a toy and starts being leverage.",
        punchy="Model + system + oversight = outcome.",
    ),
    Slide(
        number=8,
        variant="dark",
        eyebrow="YOUR MOVE",
        headline_html="Want AI that<br>actually <u class='accent'>works</u><br>in your business?",
        body="We build the context, systems, data layers, and oversight that turn AI from \"interesting demo\" into real operational leverage.",
        punchy="",
        footer_cta="DM us \u201cAI\u201d \u00b7 " + BRAND_HANDLE,
    ),
)


# =========================================================================
# HTML TEMPLATE
# =========================================================================

CSS_TEMPLATE = """
@import url('https://fonts.googleapis.com/css2?family=Inter+Tight:wght@500;600;700;800&family=Inter:wght@400;500;600&display=swap');

* { box-sizing: border-box; margin: 0; padding: 0; }

html, body {
    width: __W__px;
    height: __H__px;
    overflow: hidden;
    font-family: 'Inter', system-ui, sans-serif;
    -webkit-font-smoothing: antialiased;
    text-rendering: optimizeLegibility;
}

.slide {
    width: __W__px;
    height: __H__px;
    padding: 80px;
    position: relative;
    display: flex;
    flex-direction: column;
    justify-content: space-between;
}

.slide.dark  { background: __BG_DARK__;  color: __TEXT_LIGHT__; }
.slide.light { background: __BG_LIGHT__; color: __TEXT_DARK__; }

.header-row {
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
    font-family: 'Inter', sans-serif;
    font-weight: 500;
    font-size: 18px;
    letter-spacing: 0.12em;
    text-transform: uppercase;
}

.eyebrow {
    color: __ACCENT__;
}

.slide-number {
    opacity: 0.6;
}

.body-wrap {
    flex: 1;
    display: flex;
    flex-direction: column;
    justify-content: center;
    max-width: 860px;
}

.headline {
    font-family: 'Inter Tight', 'Inter', sans-serif;
    font-weight: 800;
    font-size: 96px;
    line-height: 0.98;
    letter-spacing: -0.02em;
    margin-bottom: 40px;
}

.slide.slide-1 .headline,
.slide.slide-7 .headline {
    font-size: 104px;
}

.headline u.accent {
    text-decoration: none;
    color: __ACCENT__;
    position: relative;
}

.body {
    font-family: 'Inter', sans-serif;
    font-weight: 400;
    font-size: 30px;
    line-height: 1.45;
    max-width: 780px;
    opacity: 0.92;
}

.punchy {
    margin-top: 48px;
    font-family: 'Inter Tight', 'Inter', sans-serif;
    font-weight: 700;
    font-size: 38px;
    line-height: 1.2;
    letter-spacing: -0.01em;
    color: __ACCENT__;
    max-width: 780px;
}

.footer-row {
    display: flex;
    justify-content: space-between;
    align-items: flex-end;
    font-family: 'Inter', sans-serif;
    font-size: 18px;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    opacity: 0.7;
}

.footer-cta {
    font-size: 22px;
    font-weight: 600;
    letter-spacing: 0.04em;
    text-transform: none;
    opacity: 1;
    color: __ACCENT__;
}

.progress-bar {
    position: absolute;
    left: 80px;
    right: 80px;
    bottom: 60px;
    height: 3px;
    background: rgba(139, 147, 160, 0.2);
    z-index: 1;
}
.slide.light .progress-bar { background: rgba(11, 13, 16, 0.12); }

.progress-bar .fill {
    height: 100%;
    background: __ACCENT__;
    width: var(--progress, 0%);
}

.cta-bubble {
    display: inline-block;
    margin-top: 32px;
    padding: 20px 36px;
    border: 2px solid __ACCENT__;
    border-radius: 999px;
    font-family: 'Inter Tight', sans-serif;
    font-weight: 700;
    font-size: 32px;
    color: __ACCENT__;
}
"""


HTML_TEMPLATE = """<!doctype html>
<html>
<head>
<meta charset="utf-8"/>
<style>__CSS__</style>
</head>
<body>
  <div class="slide slide-__NUMBER__ __VARIANT__">
    <div class="header-row">
      <span class="eyebrow">__EYEBROW__</span>
      <span class="slide-number">__NUMBER_PADDED__ / 08</span>
    </div>

    <div class="body-wrap">
      <h1 class="headline">__HEADLINE__</h1>
      <p class="body">__BODY__</p>
      __PUNCHY_BLOCK__
      __CTA_BUBBLE__
    </div>

    <div class="footer-row">
      <span>__BRAND_NAME__</span>
      <span>__BRAND_HANDLE__</span>
    </div>

    <div class="progress-bar" style="--progress: __PROGRESS__%;">
      <div class="fill"></div>
    </div>
  </div>
</body>
</html>
"""


# =========================================================================
# RENDER HELPERS
# =========================================================================

def _render_css() -> str:
    return (
        CSS_TEMPLATE
        .replace("__W__", str(SLIDE_W))
        .replace("__H__", str(SLIDE_H))
        .replace("__BG_DARK__", COLOR_BG_DARK)
        .replace("__BG_LIGHT__", COLOR_BG_LIGHT)
        .replace("__TEXT_DARK__", COLOR_TEXT_DARK)
        .replace("__TEXT_LIGHT__", COLOR_TEXT_LIGHT)
        .replace("__ACCENT__", COLOR_ACCENT)
    )


def _build_html(slide: Slide) -> str:
    total = len(SLIDES)
    progress_pct = int(round(100 * slide.number / total))
    punchy_block = (
        f'<p class="punchy">{slide.punchy}</p>'
        if slide.punchy
        else ""
    )
    cta_bubble = (
        f'<div class="cta-bubble">{slide.footer_cta}</div>'
        if slide.number == 8 and slide.footer_cta
        else ""
    )
    footer_cta_text = (
        slide.footer_cta if slide.number != 8 else ""
    )
    # For slides with a plain footer CTA (e.g. "Swipe ->")
    header_and_footer_html = (
        HTML_TEMPLATE
        .replace("__CSS__", _render_css())
        .replace("__NUMBER__", str(slide.number))
        .replace("__NUMBER_PADDED__", f"{slide.number:02d}")
        .replace("__VARIANT__", slide.variant)
        .replace("__EYEBROW__", slide.eyebrow)
        .replace("__HEADLINE__", slide.headline_html)
        .replace("__BODY__", slide.body)
        .replace("__PUNCHY_BLOCK__", punchy_block)
        .replace("__CTA_BUBBLE__", cta_bubble)
        .replace("__BRAND_NAME__", BRAND_NAME)
        .replace("__BRAND_HANDLE__", footer_cta_text or BRAND_HANDLE)
        .replace("__PROGRESS__", str(progress_pct))
    )
    return header_and_footer_html


def _write_html(output_dir: Path, slide: Slide) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / f"slide{slide.number}.html"
    path.write_text(_build_html(slide), encoding="utf-8")
    return path


def _render_png(html_path: Path, png_path: Path) -> None:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        raise SystemExit(
            "Rendering requires playwright. Install with:\n"
            "  pip install playwright\n"
            "  playwright install chromium"
        ) from exc

    url = html_path.resolve().as_uri()
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        ctx = browser.new_context(
            viewport={"width": SLIDE_W, "height": SLIDE_H},
            device_scale_factor=2,  # retina output
        )
        page = ctx.new_page()
        page.goto(url, wait_until="networkidle")
        # Small settle for web-font paint
        page.wait_for_timeout(400)
        page.screenshot(
            path=str(png_path),
            clip={"x": 0, "y": 0, "width": SLIDE_W, "height": SLIDE_H},
            type="png",
        )
        browser.close()


# =========================================================================
# MAIN
# =========================================================================

def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--render",
        action="store_true",
        help="Render each slide HTML to PNG via headless Chromium",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=OUTPUT_DIR,
        help=f"Output directory (default: {OUTPUT_DIR})",
    )
    args = parser.parse_args()

    out: Path = args.out
    logger.info("Output: %s", out)

    for slide in SLIDES:
        html_path = _write_html(out, slide)
        logger.info("  [html] %s", html_path.name)
        if args.render:
            png_path = out / f"slide{slide.number}.png"
            _render_png(html_path, png_path)
            logger.info("  [png ] %s", png_path.name)

    logger.info("\nDone. %d slides in %s", len(SLIDES), out)
    if not args.render:
        logger.info("Run with --render to produce PNG files.")
    else:
        logger.info("\nNext: upload to Supabase:")
        logger.info(
            "  python tools/upload_to_supabase_storage.py "
            "--bucket avm-public --prefix carousels/%s %s/*.png",
            CAROUSEL_ID,
            out,
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
