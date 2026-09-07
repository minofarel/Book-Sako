"""
Render orchestrator. Streams raw rgb24 frames to ffmpeg via stdin.

Usage:
  python3 src/render.py <fmt> <f0> <f1> <out.mp4>     # chunk render [f0,f1)
  python3 src/render.py grid <fmt> f,f,f,... <out.jpg>  # contact sheet
  python3 src/render.py profile <fmt> <f0> <f1>       # timing only

fmt in {9x16, 16x9, 1x1}.  Segments are aligned to sequence boundaries so the
only sequential accumulator (Seq1 laser trail) always lives in its own chunk.
"""
import os
import sys
import time
import subprocess
import numpy as np
from PIL import Image

sys.path.insert(0, os.path.dirname(__file__))
import context as CTX

FPS = CTX.FPS

# (name, module, class, global_start, global_end)  end exclusive
SEGMENTS = [
    ("s1", "seq1", "Seq1", 0, 120),
    ("s2", "seq2", "Seq2", 120, 270),
    ("s3", "seq3", "Seq3", 270, 570),
    ("s4", "seq4", "Seq4", 570, 870),
]
TOTAL = SEGMENTS[-1][4]


def _seg_for(f):
    for name, mod, cls, a, b in SEGMENTS:
        if a <= f < b:
            return name, mod, cls, a, b
    return SEGMENTS[-1]


def _instance(ctx, cache, name, mod, cls):
    if name not in cache:
        import importlib
        m = importlib.import_module(mod)
        cache[name] = getattr(m, cls)(ctx)
    return cache[name]


def render_frame(ctx, cache, f):
    name, mod, cls, a, b = _seg_for(f)
    seq = _instance(ctx, cache, name, mod, cls)
    frame = seq.render(f - a)
    return frame


def cmd_render(fmt, f0, f1, out):
    ctx = CTX.Context(fmt)
    W, H = ctx.W, ctx.H
    cache = {}
    ff = subprocess.Popen(
        ["ffmpeg", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24",
         "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-",
         "-c:v", "libx264", "-preset", "fast", "-crf", "18",
         "-pix_fmt", "yuv420p", out],
        stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    t0 = time.time()
    for f in range(f0, f1):
        frame = render_frame(ctx, cache, f)
        out8 = CTX.finish(frame, f)
        ff.stdin.write(out8.tobytes())
        if (f - f0) % 30 == 0:
            el = time.time() - t0
            n = f - f0 + 1
            print(f"  frame {f} ({n}/{f1-f0})  {el/n*1000:.0f} ms/frame", flush=True)
    ff.stdin.close()
    ff.wait()
    print(f"done {out}  {time.time()-t0:.1f}s")


def cmd_grid(fmt, frames, out):
    ctx = CTX.Context(fmt)
    cache = {}
    thumbs = []
    tw = 360
    for f in frames:
        frame = render_frame(ctx, cache, f)
        out8 = CTX.finish(frame, f)
        im = Image.fromarray(out8)
        th = int(im.height * tw / im.width)
        im = im.resize((tw, th), Image.LANCZOS)
        thumbs.append((f, im))
    cols = min(4, len(thumbs))
    rows = (len(thumbs) + cols - 1) // cols
    cellh = max(t.height for _, t in thumbs) + 26
    grid = Image.new("RGB", (cols * (tw + 10) + 10, rows * (cellh + 10) + 10),
                     (20, 20, 22))
    from PIL import ImageDraw
    d = ImageDraw.Draw(grid)
    for k, (f, im) in enumerate(thumbs):
        r, c = divmod(k, cols)
        x = 10 + c * (tw + 10)
        y = 10 + r * (cellh + 10)
        grid.paste(im, (x, y + 22))
        d.text((x + 4, y + 4), f"f{f}  t={f/FPS:.2f}s", fill=(230, 230, 230))
    grid.save(out, quality=90)
    print("wrote", out, grid.size)


def cmd_profile(fmt, f0, f1):
    ctx = CTX.Context(fmt)
    cache = {}
    # warm up (precompute)
    render_frame(ctx, cache, f0)
    t0 = time.time()
    for f in range(f0, f1):
        frame = render_frame(ctx, cache, f)
        _ = CTX.finish(frame, f)
    el = time.time() - t0
    n = f1 - f0
    print(f"profile {fmt} [{f0},{f1}): {el:.2f}s total, {el/n*1000:.0f} ms/frame")


if __name__ == "__main__":
    if sys.argv[1] == "grid":
        fmt = sys.argv[2]
        frames = [int(x) for x in sys.argv[3].split(",")]
        cmd_grid(fmt, frames, sys.argv[4])
    elif sys.argv[1] == "profile":
        cmd_profile(sys.argv[2], int(sys.argv[3]), int(sys.argv[4]))
    else:
        fmt = sys.argv[1]
        cmd_render(fmt, int(sys.argv[2]), int(sys.argv[3]), sys.argv[4])
