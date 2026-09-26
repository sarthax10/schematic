"""Frame-exact renderer: serves runtime/ + a job directory over localhost, opens the
runtime in headless Chromium at exactly 1080×1920, and for every frame n calls
window.seek(n / fps) and screenshots — never records in real time, so a slow machine
produces the same video as a fast one, just more slowly.

The frame range is split across several pages rendering in parallel, each piping JPEG
frames into its own ffmpeg segment; segments are joined losslessly and muxed with the
narration.
"""
from __future__ import annotations

import asyncio
import functools
import http.server
import threading
import time
from pathlib import Path

from playwright.async_api import async_playwright

from . import media

RUNTIME_DIR = Path(__file__).resolve().parent.parent / "runtime"
WIDTH, HEIGHT = 1080, 1920


class _Handler(http.server.SimpleHTTPRequestHandler):
    """Serves runtime/ at / and the job directory at /job/."""

    def __init__(self, *args, job_dir: Path, **kwargs):
        self.job_dir = job_dir
        super().__init__(*args, directory=str(RUNTIME_DIR), **kwargs)

    def translate_path(self, path):
        clean = path.split("?", 1)[0].split("#", 1)[0]
        if clean.startswith("/job/"):
            return str(self.job_dir / clean[len("/job/"):])
        return super().translate_path(path)

    def end_headers(self):
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def log_message(self, *args):
        pass


def serve(job_dir: Path, port: int = 0) -> tuple[http.server.ThreadingHTTPServer, int]:
    handler = functools.partial(_Handler, job_dir=job_dir)
    server = http.server.ThreadingHTTPServer(("127.0.0.1", port), handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server, server.server_address[1]


async def _render_chunk(browser, url: str, frames: range, fps: int, seg: Path, progress: list, slot: int) -> None:
    page = await browser.new_page(viewport={"width": WIDTH, "height": HEIGHT}, device_scale_factor=1)
    errors: list[str] = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    await page.goto(url)
    try:
        await page.wait_for_function("window.__ready === true", timeout=30_000)
    except Exception:
        raise RuntimeError(f"runtime failed to load: {errors or 'timeout'}")

    proc = await asyncio.create_subprocess_exec(
        media.FFMPEG, "-hide_banner", "-loglevel", "error", "-y",
        "-f", "image2pipe", "-framerate", str(fps), "-c:v", "mjpeg", "-i", "-",
        # JPEG frames decode as full-range BT.601; convert explicitly to the limited-range
        # BT.709 that phones and upload pipelines expect, or colours shift on playback.
        "-vf", "scale=in_range=pc:out_range=tv:out_color_matrix=bt709,format=yuv420p",
        "-colorspace", "bt709", "-color_primaries", "bt709", "-color_trc", "bt709", "-color_range", "tv",
        "-c:v", "libx264", "-preset", "medium", "-crf", "17",
        "-r", str(fps), str(seg),
        stdin=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
    )
    for n in frames:
        await page.evaluate("t => window.seek(t)", n / fps)
        buf = await page.screenshot(type="jpeg", quality=94, animations="disabled", caret="hide")
        proc.stdin.write(buf)
        await proc.stdin.drain()
        progress[slot] += 1
    proc.stdin.close()
    _, err = await proc.communicate()
    await page.close()
    if proc.returncode != 0:
        raise RuntimeError(f"ffmpeg segment encode failed: {err.decode(errors='replace')[-2000:]}")
    if errors:
        raise RuntimeError(f"runtime errors during render: {errors[:3]}")


async def _render(job_dir: Path, out: Path, fps: int, duration: float, workers: int) -> None:
    server, port = serve(job_dir)
    url = f"http://127.0.0.1:{port}/index.html?timeline=/job/timeline.json&mode=render"
    total = round(duration * fps)
    size = -(-total // workers)
    chunks = [range(i, min(i + size, total)) for i in range(0, total, size)]
    segs = [job_dir / f"seg_{i:02d}.mp4" for i in range(len(chunks))]
    progress = [0] * len(chunks)
    started = time.time()
    try:
        async with async_playwright() as pw:
            browser = await pw.chromium.launch(args=["--force-color-profile=srgb", "--hide-scrollbars"])
            tasks = [
                asyncio.create_task(_render_chunk(browser, url, ch, fps, seg, progress, i))
                for i, (ch, seg) in enumerate(zip(chunks, segs))
            ]
            while not all(t.done() for t in tasks):
                await asyncio.sleep(1.0)
                done = sum(progress)
                rate = done / max(time.time() - started, 1e-6)
                print(f"\r  frames {done}/{total}  ({rate:.1f} fps)", end="", flush=True)
            for t in tasks:
                t.result()
            await browser.close()
        print()
    finally:
        server.shutdown()

    concat = job_dir / "segments.txt"
    concat.write_text("".join(f"file '{s.name}'\n" for s in segs), encoding="utf-8")
    media.run([
        "-f", "concat", "-safe", "0", "-i", str(concat), "-i", str(job_dir / "narration.m4a"),
        "-map", "0:v", "-map", "1:a", "-c", "copy", "-movflags", "+faststart", str(out),
    ])
    for s in segs:
        s.unlink(missing_ok=True)
    concat.unlink(missing_ok=True)


def render(job_dir: Path, out: Path, fps: int, duration: float, workers: int = 4) -> None:
    asyncio.run(_render(job_dir, out, fps, duration, workers))


async def snapshot(job_dir: Path, times: list[float], out_dir: Path) -> list[Path]:
    """Stills at specific times — for quick visual checks without a full render."""
    server, port = serve(job_dir)
    url = f"http://127.0.0.1:{port}/index.html?timeline=/job/timeline.json&mode=render"
    paths = []
    try:
        async with async_playwright() as pw:
            browser = await pw.chromium.launch()
            page = await browser.new_page(viewport={"width": WIDTH, "height": HEIGHT})
            await page.goto(url)
            await page.wait_for_function("window.__ready === true", timeout=30_000)
            for t in times:
                await page.evaluate("t => window.seek(t)", t)
                p = out_dir / f"still_{t:06.2f}.png"
                await page.screenshot(path=str(p))
                paths.append(p)
            await browser.close()
    finally:
        server.shutdown()
    return paths
