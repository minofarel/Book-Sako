"""
"Pole position" declination — 1:1, 1080x1080, ~22s (660 frames @30fps).
A distinct spot (F1-inspired), built on the same toolkit.

Beats:
  0-90   lockup "Sako | La finance sans frontières" + countdown 0:02->DÉPART
  90-180 card on procedural asphalt, silver sweep
  180-330 card opens like a trapdoor -> light burst -> comet flies right
  330-420 tagline typed letter by letter "La finance sans frontières"
  420-540 card returns as a diamond, sweep + champagne pass, BIENTÔT DISPONIBLE
  540-660 outro: logo revealed by metallic reflection + CTA + legal line

Usage:
  python3 src/pole.py <f0> <f1> <out.mp4>
  python3 src/pole.py grid f,f,f <out.jpg>
"""
import sys
import subprocess
import numpy as np
from PIL import Image, ImageDraw, ImageFilter

import common as C
import context as CTX

FPS = 30
TOTAL = 660


def _rot_quad(quad, deg, cx, cy):
    a = np.deg2rad(deg)
    ca, sa = np.cos(a), np.sin(a)
    return [(cx + (x - cx) * ca - (y - cy) * sa,
             cy + (x - cx) * sa + (y - cy) * ca) for x, y in quad]


class Pole:
    def __init__(self):
        self.ctx = CTX.Context("1x1")
        self.W = self.H = 1080
        W = H = 1080
        self.card = self.ctx.card

        # ---- procedural asphalt ----------------------------------------
        rng = np.random.default_rng(7)
        base = np.zeros((H, W), np.float32)
        for scale, amp in [(6, 1.0), (12, 0.6), (28, 0.4), (64, 0.25), (140, 0.16)]:
            g = rng.random((scale, scale)).astype(np.float32)
            up = np.asarray(Image.fromarray((g * 255).astype(np.uint8)).resize((W, H), Image.BILINEAR),
                            np.float32) / 255.0
            base += up * amp
        base = (base - base.min()) / (np.ptp(base) + 1e-6)
        asph = 26 + base * 40
        # speckle grit
        asph += (rng.random((H, W)) < 0.05) * rng.random((H, W)) * 40
        self.asphalt = np.repeat(asph[:, :, None], 3, axis=2).astype(np.float32)
        yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
        self.diag = (xx + yy) / (W + H)          # for drifting shadow bands

        # ---- card sprite (rounded) for diamond -------------------------
        self.card_spr, self.spec = None, None
        import ui
        self.ui = ui
        self.card_spr, self.spec = ui.rounded_card(self.card, int(0.62 * W))

        # ---- logo ------------------------------------------------------
        lg = self.ctx.logo
        lw = int(W * 0.5)
        lg = lg.resize((lw, int(lw * lg.height / lg.width)), Image.LANCZOS)
        a = np.asarray(lg, np.float32)
        self.logo_rgb, self.logo_a = a[:, :, :3].copy(), a[:, :, 3] / 255.0

        # ---- text blocks ----------------------------------------------
        self.lockup = self.ctx.text_block([
            {"text": "Sako", "size": int(H * 0.05), "weight": "ExtraBold",
             "tracking": -1, "color": (247, 247, 247)}])
        self.baseline_lock = self.ctx.text_block([
            {"text": "LA FINANCE SANS FRONTIÈRES", "size": int(H * 0.018),
             "weight": "SemiBold", "tracking": int(H * 0.006), "color": (188, 188, 190)}])
        self.dispo = self.ctx.text_block([
            {"text": "BIENTÔT DISPONIBLE", "size": int(H * 0.024), "weight": "SemiBold",
             "tracking": int(H * 0.012), "color": (236, 236, 238)}])
        self.cta = self.ctx.text_block([
            {"text": "BIENTÔT DISPONIBLE · SAKO.APP", "size": int(H * 0.022),
             "weight": "SemiBold", "tracking": int(H * 0.010), "color": (232, 232, 234)}])
        self.legal = self.ctx.text_block([
            {"text": "La carte Sako Visa Platinum arrive bientôt · Rejoignez la liste d'attente sur sako.app",
             "size": int(H * 0.0145), "weight": "Light", "tracking": 1, "color": (150, 150, 154)}])
        self.baseline_font = C.font(int(H * 0.036), "Bold")

        self.comet_glow = C.glow_sprite(int(H * 0.05), 2.2)
        self.comet_core = C.glow_sprite(int(H * 0.016), 2.0)
        self.spark = C.glow_sprite(max(5, int(H * 0.01)), 1.8)
        self.warm = C.CHAMPAGNE
        self.rng = np.random.default_rng(3)
        self._cache = {}

    # ---- helpers -------------------------------------------------------
    def _flat_quad(self, open_amt):
        """Card lying flat (open=0) -> far edge lifts up like a hatch (open=1),
        hinged at the near (bottom) edge, revealing light behind it."""
        W, H = self.W, self.H
        cx = W / 2
        bot_y, bot_hw = 0.72 * H, 0.38 * W               # hinge (near edge, fixed)
        top_y = C.lerp(0.44 * H, 0.17 * H, open_amt)     # far edge lifts up
        top_hw = C.lerp(0.24 * W, 0.31 * W, open_amt)    # ...and toward camera
        return [(cx - top_hw, top_y), (cx + top_hw, top_y),
                (cx + bot_hw, bot_y), (cx - bot_hw, bot_y)]

    def _warp_lit(self, quad, light=0.6, rim=False):
        W, H = self.W, self.H
        warped = C.warp_card(self.card, (W, H), quad).convert("RGBA")
        arr = np.asarray(warped, np.float32)
        rgb, alpha = arr[:, :, :3], (arr[:, :, 3] / 255.0)[:, :, None]
        rgb = np.clip((rgb - 128) * 1.12 + 128, 0, 255) * light
        return rgb, alpha, warped

    # ---- beats ---------------------------------------------------------
    def _lockup(self, i):
        W, H = self.W, self.H
        frame = self.ctx.black_bg()
        t = i / 90.0
        # lockup fades in
        op = C.smoothstep(np.clip(i / 12.0, 0, 1))
        r, a, (lw, lh) = self.lockup
        CTX.paste(frame, r, a, W * 0.5, H * 0.40, opacity=float(op))
        r2, a2, _ = self.baseline_lock
        CTX.paste(frame, r2, a2, W * 0.5, H * 0.47, opacity=float(op))
        # divider
        dl = int(W * 0.16 * op)
        d = ImageDraw.Draw(Image.new("RGB", (1, 1)))
        # countdown
        if i < 30:
            num = "0:02"
        elif i < 60:
            num = "0:01"
        elif i < 78:
            num = "0:00"
        else:
            num = "DÉPART"
        blk = self._cache.get(("cd", num))
        if blk is None:
            sz = int(H * 0.11) if num != "DÉPART" else int(H * 0.075)
            blk = self.ctx.text_block([{"text": num, "size": sz, "weight": "ExtraBold",
                                        "tracking": (int(H*0.01) if num=="DÉPART" else -1),
                                        "color": (247, 247, 247)}])
            self._cache[("cd", num)] = blk
        # pulse on each tick
        loc = i % 30
        pop = 1.0 + 0.10 * max(0, 1 - loc / 6.0)
        r3, a3, _ = blk
        CTX.paste(frame, r3, a3, W * 0.5, H * 0.60, scale=float(pop),
                  opacity=float(op))
        if num == "DÉPART":
            g = C.glow_sprite(int(H * 0.09), 2.0)
            frame = C.add_sprite(frame, g, W * 0.5, H * 0.60,
                                 self.warm, 0.5 * (1 - (i - 78) / 12.0))
        return frame

    def _asphalt_scene(self, i, open_amt=0.0, sweep=None, burst=0.0):
        W, H = self.W, self.H
        j = i
        frame = self.asphalt.copy()
        # drifting diagonal shadow bands
        drift = (i / FPS) * 0.05
        shad = 0.72 + 0.28 * np.sin(2 * np.pi * (self.diag * 3 - drift))
        frame = frame * shad[:, :, None]
        # vignetted ground darkening toward top (distance)
        yy = np.linspace(0.5, 1.05, H)[:, None]
        frame = frame * yy[:, :, None] if False else frame  # keep simple
        # the card
        quad = self._flat_quad(open_amt)
        rgb, alpha, warped = self._warp_lit(quad, light=0.62)
        # contact shadow under near edge
        if open_amt < 0.6:
            sh = np.asarray(warped.split()[3], np.float32) / 255.0
            sh = np.asarray(Image.fromarray((sh * 255).astype(np.uint8)).filter(
                ImageFilter.GaussianBlur(18)), np.float32) / 255.0
            frame *= (1 - 0.5 * sh[:, :, None] * (1 - open_amt))
        # baked sheen sweep on the card
        if sweep is not None:
            cd = C.diag_coord(H, W, np.deg2rad(35))
            band = C.light_band(cd, sweep, 0.12)
            lum = (0.2126*rgb[:,:,0]+0.7152*rgb[:,:,1]+0.0722*rgb[:,:,2]) / 255.0
            spec = np.clip((lum - 0.5) / 0.5, 0, 1) ** 2.0
            rgb = rgb + (spec * band)[:, :, None] * 220
            rgb = rgb + band[:, :, None] * 40
        frame = frame * (1 - alpha) + rgb * alpha
        # light burst escaping from behind the lifting far edge
        if burst > 0:
            q = quad
            gx = (q[0][0] + q[1][0]) / 2
            gy = (q[0][1] + q[1][1]) / 2 - H * 0.02
            g = C.glow_sprite(int(H * (0.12 + 0.26 * burst)), 1.7)
            frame = C.add_sprite(frame, g, gx, gy,
                                 np.array([255, 250, 240], np.float32), 1.7 * burst)
            # luminous rim on the lifted far edge
            ov = Image.new("RGBA", (W, H), (0, 0, 0, 0))
            dd = ImageDraw.Draw(ov)
            dd.line([q[0], q[1]], fill=(255, 250, 240, int(235 * burst)), width=5)
            arr = np.asarray(ov, np.float32)
            frame += arr[:, :, :3] * (arr[:, :, 3] / 255.0)[:, :, None]
        return frame

    def _trapdoor(self, i):
        W, H = self.W, self.H
        j = i - 180
        n = 150
        t = j / n
        # phase 1 (0-0.5): open ; phase 2 (0.4-1): burst + comet exit
        open_amt = C.ease_out(np.clip(t / 0.5, 0, 1), 2.2)
        burst = C.smoothstep(np.clip((t - 0.42) / 0.18, 0, 1)) * (1 - C.smoothstep((t - 0.62) / 0.25))
        frame = self._asphalt_scene(i, open_amt=open_amt, burst=burst)
        # comet: launches ~t=0.5 from the gap, flies to the right
        if t > 0.5:
            ct = (t - 0.5) / 0.5
            cx = C.lerp(W * 0.5, W * 1.2, C.ease_in(ct, 1.8))
            cy = C.lerp(H * 0.24, H * 0.32, ct)
            # trail
            for k in range(14):
                tx = cx - k * (0.03 * W) * (0.6 + ct)
                ty = cy + k * (0.006 * H)
                frame = C.add_sprite(frame, self.comet_glow, tx, ty,
                                     np.array([255, 250, 242], np.float32),
                                     0.5 * (1 - k / 14))
            frame = C.add_sprite(frame, self.comet_glow, cx, cy,
                                 np.array([255, 252, 245], np.float32), 1.6)
            frame = C.add_sprite(frame, self.comet_core, cx, cy,
                                 np.array([255, 255, 255], np.float32), 1.8)
            # speed lines
            ov = Image.new("RGBA", (W, H), (0, 0, 0, 0))
            dd = ImageDraw.Draw(ov)
            for _ in range(10):
                ly = self.rng.uniform(0.2, 0.6) * H
                lx = self.rng.uniform(0, cx)
                dd.line([lx, ly, lx + self.rng.uniform(60, 180), ly],
                        fill=(230, 230, 235, 120), width=1)
            arr = np.asarray(ov, np.float32)
            frame += arr[:, :, :3] * (arr[:, :, 3] / 255.0)[:, :, None] * ct
            # particle sparks near gap early
            if ct < 0.45:
                for _ in range(14):
                    px = W * 0.5 + self.rng.uniform(-0.18, 0.18) * W
                    py = 0.26 * H - self.rng.uniform(0, 0.14) * H
                    frame = C.add_sprite(frame, self.spark, px, py, self.warm, 0.8)
        return frame

    def _typed(self, i):
        W, H = self.W, self.H
        j = i - 330
        n = 90
        frame = self.ctx.black_bg()
        text = "La finance sans frontières"
        nch = int(np.clip(j / (n * 0.72), 0, 1) * len(text))
        s = text[:nch]
        im = Image.fromarray(C.finalize(frame))
        d = ImageDraw.Draw(im)
        # centered, measure full to keep anchored left of centre
        fw = d.textlength(text, font=self.baseline_font)
        x0 = W / 2 - fw / 2
        d.text((x0, H * 0.47), s, font=self.baseline_font, fill=(245, 245, 245))
        # cursor
        if j < n - 6 and (j // 4) % 2 == 0:
            cw = d.textlength(s, font=self.baseline_font)
            d.line([x0 + cw + 4, H * 0.47 + 4, x0 + cw + 4, H * 0.47 + H * 0.038],
                   fill=(245, 245, 245), width=3)
        frame = np.asarray(im, np.float32)
        return frame

    def _diamond(self, i):
        W, H = self.W, self.H
        j = i - 420
        n = 120
        t = j / n
        frame = self.ctx.black_bg()
        # diamond card (rotated 45)
        cw = int(0.5 * W)
        ch = int(cw * self.card.height / self.card.width)
        cx, cy = W * 0.5, H * 0.44
        quad = [(cx - cw / 2, cy - ch / 2), (cx + cw / 2, cy - ch / 2),
                (cx + cw / 2, cy + ch / 2), (cx - cw / 2, cy + ch / 2)]
        quad = _rot_quad(quad, 45, cx, cy)
        scin = C.ease_out(np.clip(j / 16.0, 0, 1))
        quad = _rot_quad(quad, (1 - scin) * 40, cx, cy)   # spin into place
        rgb, alpha, warped = self._warp_lit(quad, light=0.5)
        # sweep + champagne
        cd = C.diag_coord(H, W, np.deg2rad(60))
        sweep = C.lerp(-0.1, 1.1, C.smoothstep(np.clip((t - 0.15) / 0.6, 0, 1)))
        band = C.light_band(cd, sweep, 0.13)
        lum = (0.2126*rgb[:,:,0]+0.7152*rgb[:,:,1]+0.0722*rgb[:,:,2]) / 255.0
        spec = np.clip((lum - 0.5) / 0.5, 0, 1) ** 2.1
        rgb = rgb + band[:, :, None] * 55 + (spec * band)[:, :, None] * 230
        rgb = rgb + (spec * band)[:, :, None] * 0.6 * self.warm[None, None, :]
        frame = frame * (1 - alpha) + rgb * alpha * float(C.smoothstep(np.clip(j/12.,0,1)))
        # BIENTÔT DISPONIBLE
        op = C.smoothstep((j - 40) / 16.0)
        if op > 0.01:
            r, a, _ = self.dispo
            CTX.paste(frame, r, a, W * 0.5, H * 0.80, opacity=float(op))
        return frame

    def _outro(self, i):
        W, H = self.W, self.H
        j = i - 540
        n = 120
        t = j / n
        frame = self.ctx.black_bg()
        # logo revealed by a metallic reflection wipe
        rgb, a = self.logo_rgb, self.logo_a
        lh, lw = a.shape
        reveal = C.ease_out(np.clip(j / 34.0, 0, 1))
        xnorm = np.linspace(0, 1, lw)[None, :]
        wipe = np.clip((reveal - xnorm) / 0.12 + 0.5, 0, 1)   # left-to-right reveal
        amask = a * wipe
        ly = H * 0.44
        CTX.paste(frame, rgb, amask, W * 0.5, ly)
        # bright reflection streak at the wipe edge
        edge = np.clip(1 - np.abs(xnorm - reveal) / 0.05, 0, 1)
        streak = a * edge
        CTX.paste(frame, np.full((lh, lw, 3), 255.0), streak, W * 0.5, ly,
                  opacity=1.6, add=True)
        # CTA + legal
        op = C.smoothstep((j - 40) / 16.0)
        if op > 0.01:
            r, aa, _ = self.cta
            CTX.paste(frame, r, aa, W * 0.5, H * 0.60, opacity=float(op))
        opl = C.smoothstep((j - 54) / 16.0)
        if opl > 0.01:
            r, aa, _ = self.legal
            CTX.paste(frame, r, aa, W * 0.5, H * 0.92, opacity=float(opl))
        # fade out
        fade = C.smoothstep((j - (n - 14)) / 14.0)
        if fade > 0:
            frame *= (1 - fade)
        return frame

    # ---- dispatch ------------------------------------------------------
    def render(self, i):
        if i < 90:
            return self._lockup(i)
        if i < 180:
            j = i - 90
            sweep = C.lerp(-0.1, 1.1, C.smoothstep(np.clip((j - 15) / 55.0, 0, 1)))
            return self._asphalt_scene(i, open_amt=0.0,
                                       sweep=sweep if j > 10 else None)
        if i < 330:
            return self._trapdoor(i)
        if i < 420:
            return self._typed(i)
        if i < 540:
            return self._diamond(i)
        return self._outro(i)


# --------------------------------------------------------------------------
def cmd_render(f0, f1, out):
    p = Pole()
    W, H = p.W, p.H
    ff = subprocess.Popen(
        ["ffmpeg", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}",
         "-r", str(FPS), "-i", "-", "-c:v", "libx264", "-preset", "fast",
         "-crf", "18", "-pix_fmt", "yuv420p", out],
        stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    for f in range(f0, f1):
        frame = p.render(f)
        ff.stdin.write(CTX.finish(frame, f).tobytes())
    ff.stdin.close(); ff.wait()
    print("done", out)


def cmd_grid(frames, out):
    p = Pole()
    tw = 300
    ims = []
    for f in frames:
        im = Image.fromarray(CTX.finish(p.render(f), f)).resize((tw, tw), Image.LANCZOS)
        ims.append((f, im))
    cols = min(4, len(ims))
    rows = (len(ims) + cols - 1) // cols
    grid = Image.new("RGB", (cols * (tw + 8) + 8, rows * (tw + 24) + 8), (20, 20, 22))
    d = ImageDraw.Draw(grid)
    for k, (f, im) in enumerate(ims):
        r, c = divmod(k, cols)
        x, y = 8 + c * (tw + 8), 8 + r * (tw + 24)
        grid.paste(im, (x, y + 20)); d.text((x + 3, y + 3), f"f{f} {f/FPS:.2f}s", fill=(230,230,230))
    grid.save(out, quality=90); print("wrote", out)


if __name__ == "__main__":
    if sys.argv[1] == "grid":
        cmd_grid([int(x) for x in sys.argv[2].split(",")], sys.argv[3])
    else:
        cmd_render(int(sys.argv[1]), int(sys.argv[2]), sys.argv[3])
