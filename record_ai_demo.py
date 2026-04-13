#!/usr/bin/env python3
"""
Record an automated demo of the Ask AMEND AI feature.

Usage:
    GROQ_API_KEY=sk_... conda run -n amend_playwright python record_ai_demo.py
    OPENAI_API_KEY=sk_... conda run -n amend_playwright python record_ai_demo.py
    GOOGLE_API_KEY=... conda run -n amend_playwright python record_ai_demo.py

Options:
    --question INDEX    Which starter question to use (0-indexed, default: 0)
    --output PATH       Where to save the recording (default: docs/assets/ask-amend-demo.webm)

Prerequisites:
    - Jekyll server running at http://localhost:4000/
    - API key passed via environment variable (GROQ_API_KEY, OPENAI_API_KEY, or GOOGLE_API_KEY)
    - ffmpeg installed (for screen capture)
    - Key is only held in memory during the recording session, not persisted to disk

Examples:
    GROQ_API_KEY=sk_123abc conda run -n amend_playwright python record_ai_demo.py
    GOOGLE_API_KEY=... conda run -n amend_playwright python record_ai_demo.py --question 4
"""

import asyncio
import argparse
import os
import shutil
import signal
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from playwright.async_api import async_playwright

VIEWPORT_W = 1280
VIEWPORT_H = 900
# Extra pixels to trim from left/top of capture to exclude any DE chrome bleed
CAPTURE_TRIM_X = 0
CAPTURE_TRIM_Y = 0


CURSOR_JS = """
(() => {
    if (document.getElementById('_demo_cursor')) return;
    const el = document.createElement('div');
    el.id = '_demo_cursor';
    el.style.cssText = [
        'position:fixed', 'z-index:999999', 'pointer-events:none',
        'width:22px', 'height:22px', 'border-radius:50%',
        'background:rgba(255,50,50,0.75)', 'border:2px solid white',
        'box-shadow:0 0 6px rgba(0,0,0,0.6)',
        'transform:translate(-50%,-50%)',
        'transition:left 0.05s,top 0.05s',
        'left:-50px', 'top:-50px',
    ].join(';');
    document.body.appendChild(el);
    document.addEventListener('mousemove', e => {
        el.style.left = e.clientX + 'px';
        el.style.top  = e.clientY + 'px';
    }, true);
})();
"""


async def inject_cursor(page):
    """Inject a visible red-dot cursor that tracks Playwright mouse events."""
    await page.evaluate(CURSOR_JS)


async def run_demo(page, provider, model, api_key, question_index):
    """Execute the demo interaction on an already-open page."""

    # ── Load page ──────────────────────────────────────────────────────────────
    print("Loading page...")
    await page.goto("http://localhost:4000/ai_analysis.html", wait_until="networkidle")
    await page.wait_for_timeout(2000)

    # Inject API settings and reload
    await page.evaluate(f"""() => {{
        localStorage.setItem('ai_provider', '{provider}');
        localStorage.setItem('ai_model', '{model}');
        localStorage.setItem('ai_api_key', '{api_key}');
    }}""")
    await page.reload(wait_until="networkidle")
    await page.wait_for_timeout(2000)
    await inject_cursor(page)

    # ── Load database ──────────────────────────────────────────────────────────
    db_status = await page.locator("#ai-db-status-text").text_content()
    print(f"DB status: {db_status}")

    load_button = page.locator("#ai-load-db")
    if await load_button.is_visible():
        print("Loading database...")
        await load_button.click()
        await page.wait_for_selector("#ai-submit:not([disabled])", timeout=120000)
        print("  Database loaded!")
        await page.wait_for_timeout(3000)
        await inject_cursor(page)  # Re-inject after DB load updates DOM
    else:
        print("  Database already loaded")

    await page.wait_for_timeout(1000)

    # ── Click starter question ─────────────────────────────────────────────────
    print("Clicking starter question...")
    buttons = page.locator("button.ai-starter-btn")
    btn_count = await buttons.count()
    if question_index >= btn_count:
        raise ValueError(f"Only {btn_count} questions available, requested {question_index}")

    btn = buttons.nth(question_index)
    btn_box = await btn.bounding_box()
    await page.mouse.move(btn_box["x"] + btn_box["width"] / 2, btn_box["y"] + btn_box["height"] / 2)
    await page.wait_for_timeout(300)
    await btn.click()
    await page.wait_for_timeout(500)

    # ── Submit ─────────────────────────────────────────────────────────────────
    print("Submitting question...")
    submit = page.locator("#ai-submit")
    submit_box = await submit.bounding_box()
    await page.mouse.move(submit_box["x"] + submit_box["width"] / 2, submit_box["y"] + submit_box["height"] / 2)
    await page.wait_for_timeout(300)
    await submit.click()

    # ── Wait for chart ─────────────────────────────────────────────────────────
    # The chart renders offscreen then is shown as a PNG thumbnail (.ai-chart-thumb).
    # Wait for the thumbnail img to get a src attribute (i.e. rendering complete).
    print("Waiting for AI response and chart thumbnail...")
    await page.wait_for_selector("#ai-artifact-list .ai-artifact-body", timeout=60000)
    await page.wait_for_selector(".ai-chart-thumb[src]", timeout=30000)
    await page.wait_for_timeout(1500)

    # ── Click thumbnail to open fullscreen interactive chart ───────────────────
    print("Opening fullscreen chart...")
    thumb = page.locator(".ai-chart-thumb").first
    thumb_box = await thumb.bounding_box()
    if thumb_box:
        await page.mouse.move(thumb_box["x"] + thumb_box["width"] / 2, thumb_box["y"] + thumb_box["height"] / 2)
        await page.wait_for_timeout(300)
        await thumb.click()
        await page.wait_for_timeout(1500)

        # Hover over the interactive Plotly chart in the fullscreen overlay
        chart = page.locator("#ai-fullscreen-chart .js-plotly-plot")
        chart_box = await chart.bounding_box()
        if chart_box:
            cy = chart_box["y"] + chart_box["height"] / 2
            for x_frac in [0.3, 0.5, 0.7]:
                await page.mouse.move(chart_box["x"] + chart_box["width"] * x_frac, cy)
                await page.wait_for_timeout(400)

        close_btn = page.locator("#ai-fullscreen-close")
        if await close_btn.is_visible():
            close_box = await close_btn.bounding_box()
            await page.mouse.move(
                close_box["x"] + close_box["width"] / 2,
                close_box["y"] + close_box["height"] / 2
            )
            await page.wait_for_timeout(300)
            await close_btn.click()
            await page.wait_for_timeout(800)

    # ── Show SQL ───────────────────────────────────────────────────────────────
    print("Showing SQL...")
    sql_toggle = page.locator(".ai-sql-toggle").first
    if await sql_toggle.is_visible():
        sql_box = await sql_toggle.bounding_box()
        await page.mouse.move(sql_box["x"] + sql_box["width"] / 2, sql_box["y"] + sql_box["height"] / 2)
        await page.wait_for_timeout(300)
        await sql_toggle.click()
        await page.wait_for_timeout(6000)  # ~2s at 3x

    # ── Show data table ────────────────────────────────────────────────────────
    print("Showing data table...")
    data_toggle = page.locator(".ai-data-toggle").first
    await data_toggle.scroll_into_view_if_needed()
    await page.wait_for_timeout(300)
    if await data_toggle.is_visible():
        data_box = await data_toggle.bounding_box()
        await page.mouse.move(data_box["x"] + data_box["width"] / 2, data_box["y"] + data_box["height"] / 2)
        await page.wait_for_timeout(300)
        await data_toggle.click()
        await page.wait_for_timeout(800)
        # Scroll down to reveal the expanded data table
        await page.evaluate("window.scrollBy(0, 400)")
        await page.wait_for_timeout(9000)  # ~3s at 3x

    print("All interactions complete.")


async def record_demo(question_index: int = 0, output_path: str = None):
    """Record the AI Analysis demo using ffmpeg x11grab for reliable screen capture."""

    if output_path is None:
        output_path = "docs/assets/ask-amend-demo.webm"

    output_path = Path(output_path).resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)

    api_key = os.getenv("GROQ_API_KEY") or os.getenv("OPENAI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    if not api_key:
        print("ERROR: Set one of: GROQ_API_KEY, OPENAI_API_KEY, or GOOGLE_API_KEY")
        return False

    if os.getenv("GROQ_API_KEY"):
        provider, model = "groq", "llama-3.3-70b-versatile"
    elif os.getenv("OPENAI_API_KEY"):
        provider, model = "openai", "gpt-4o-mini"
    else:
        provider, model = "gemini", "gemini-2.5-flash"

    display = os.getenv("DISPLAY", ":1")
    print(f"Provider: {provider}, Model: {model}")
    print(f"Display: {display}, Output: {output_path}")

    tmpdir = tempfile.mkdtemp()
    raw_video = Path(tmpdir) / "raw.mkv"
    ffmpeg_proc = None

    try:
        async with async_playwright() as p:
            context = await p.chromium.launch_persistent_context(
                user_data_dir=tmpdir,
                headless=False,
                args=["--window-position=0,0", f"--window-size={VIEWPORT_W},{VIEWPORT_H}"],
                viewport={"width": VIEWPORT_W, "height": VIEWPORT_H},
            )
            page = await context.new_page()

            # Navigate to a real page so we can measure browser chrome dimensions
            await page.goto("http://localhost:4000/ai_analysis.html", wait_until="domcontentloaded")
            await page.wait_for_timeout(1500)

            # Measure where the viewport content starts on screen
            geom = await page.evaluate("""() => ({
                screenX: window.screenX,
                screenY: window.screenY,
                outerW: window.outerWidth,
                outerH: window.outerHeight,
                innerW: window.innerWidth,
                innerH: window.innerHeight,
            })""")
            h_border = (geom["outerW"] - geom["innerW"]) // 2
            top_chrome = geom["outerH"] - geom["innerH"] - h_border
            cap_x = geom["screenX"] + h_border
            cap_y = geom["screenY"] + top_chrome
            # Clamp to screen origin — never negative
            cap_x = max(0, cap_x) + CAPTURE_TRIM_X
            cap_y = max(0, cap_y) + CAPTURE_TRIM_Y
            cap_w = VIEWPORT_W - CAPTURE_TRIM_X
            cap_h = VIEWPORT_H - CAPTURE_TRIM_Y
            print(f"Viewport on screen: ({cap_x}, {cap_y}) {cap_w}x{cap_h}  chrome: top={top_chrome}px sides={h_border}px")

            screenshot_path = output_path.parent / "debug_screenshot.png"
            await page.screenshot(path=str(screenshot_path))
            print(f"Screenshot: {screenshot_path.stat().st_size} bytes")

            # Start ffmpeg — capture only the browser viewport, no titlebar/panels
            print("Starting screen capture...")
            ffmpeg_cmd = [
                "ffmpeg", "-y",
                "-f", "x11grab",
                "-r", "24",
                "-s", f"{cap_w}x{cap_h}",
                "-i", f"{display}+{cap_x},{cap_y}",
                "-c:v", "libx264",
                "-preset", "fast",
                "-crf", "18",
                str(raw_video)
            ]
            ffmpeg_proc = subprocess.Popen(
                ffmpeg_cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            time.sleep(1)  # Let ffmpeg initialise

            try:
                await run_demo(page, provider, model, api_key, question_index)
            except Exception as e:
                print(f"ERROR during demo: {e}")
                import traceback
                traceback.print_exc()
                return False
            finally:
                await context.close()
                # Stop ffmpeg by sending SIGINT (same as Ctrl+C) — works reliably without a TTY
                print("Stopping capture...")
                ffmpeg_proc.send_signal(signal.SIGINT)
                try:
                    ffmpeg_proc.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    ffmpeg_proc.kill()
                ffmpeg_proc = None

        # Convert to webm with 3x speedup; ensure even dimensions
        out_w = (VIEWPORT_W - CAPTURE_TRIM_X) & ~1
        out_h = (VIEWPORT_H - CAPTURE_TRIM_Y) & ~1
        if raw_video.exists() and raw_video.stat().st_size > 10000:
            print(f"Raw video: {raw_video.stat().st_size:,} bytes — converting to webm (3x speed)...")
            result = subprocess.run([
                "ffmpeg", "-y",
                "-i", str(raw_video),
                "-vf", f"setpts=PTS/3,scale={out_w}:{out_h}",
                "-r", "24",
                "-c:v", "libvpx-vp9",
                "-b:v", "1M",
                str(output_path)
            ], capture_output=True)
            if result.returncode == 0:
                print(f"Video saved to {output_path} ({output_path.stat().st_size:,} bytes)")
                return True
            else:
                print(f"ffmpeg conversion failed:\n{result.stderr.decode()}")
                return False
        else:
            print(f"ERROR: Raw video missing or too small")
            return False

    finally:
        if ffmpeg_proc:
            ffmpeg_proc.kill()
        shutil.rmtree(tmpdir, ignore_errors=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Record Ask AMEND AI demo",
        epilog="API key via env var: GROQ_API_KEY, OPENAI_API_KEY, or GOOGLE_API_KEY"
    )
    parser.add_argument("--question", type=int, default=0,
                        help="Starter question index (0-indexed, default: 0)")
    parser.add_argument("--output", type=str, default="docs/assets/ask-amend-demo.webm",
                        help="Output path (default: docs/assets/ask-amend-demo.webm)")

    args = parser.parse_args()
    success = asyncio.run(record_demo(args.question, args.output))
    sys.exit(0 if success else 1)
