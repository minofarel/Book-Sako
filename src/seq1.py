"""
Sequence 1 (0-4s, 120 frames) : Laser engraving — mystery.

Shot A (f 0..89):  tight macro of the card, dark grainy metal, a dark stylus
descends the motif; its luminous tip reveals the engraving locally, ciselated
edges shimmer, a faint light trail lingers.  Push-in crop window on a big warp.
Shot B (f 90..119): pull back to the whole card floating on black, slight 3D
tilt, a diagonal light band sweeps across.  No text.
"""
import numpy as np
from PIL import Image, ImageDraw, ImageFilter

import common as C
import context as CTX

CUT = 90  # local frame of the cut


def _rotate_quad(quad, deg, cx, cy):
    a = np.deg2rad(deg)
    ca, sa = np.cos(a), np.sin(a)
    out = []
    for x, y in quad:
        dx, dy = x - cx, y - cy
        out.append((cx + dx * ca - dy * sa, cy + dx * sa + dy * ca))
    return out


class Seq1:
    def __init__(self, ctx):
        self.ctx = ctx
        self.W, self.H = ctx.W, ctx.H
        W, H = self.W, self.H

        # ---- Shot A : big warped macro (card overflows the frame) --------
        MW, MH = int(W * 1.7), int(H * 1.7)
        self.MW, self.MH = MW, MH
        cardW, cardH = ctx.card.size
        scale = (MH / cardH) * 1.25
        w, h = cardW * scale, cardH * scale
        cx, cy = MW / 2, MH / 2
        key = 0.10 * w
        quad = [(cx - w / 2 + key, cy - h / 2), (cx + w / 2 - key, cy - h / 2),
                (cx + w / 2, cy + h / 2), (cx - w / 2, cy + h / 2)]
        quad = _rotate_quad(quad, -7.0, cx, cy)
        warped = C.warp_card(ctx.card, (MW, MH), quad).convert("RGBA")
        arr = np.asarray(warped, dtype=np.float32)
        rgb = arr[:, :, :3]
        self.macro_dark = rgb * 0.17            # dark metal, motif barely visible
        lit = np.clip((rgb - 128) * 1.12 + 128, 0, 255)
        self.macro_lit = lit
        # engraved edges for shimmer
        edg = warped.convert("L").filter(ImageFilter.FIND_EDGES)
        edg = edg.filter(ImageFilter.GaussianBlur(0.6))
        e = np.asarray(edg, dtype=np.float32)
        self.macro_edge = np.clip(e / (e.max() + 1e-6), 0, 1)

        # ---- Shot B : full card floating, lit by a moving band -----------
        cw = int(W * 0.82)
        ch = int(cw * cardH / cardW)
        bx, by = W / 2, H / 2
        bquad = [(bx - cw / 2, by - ch / 2), (bx + cw / 2, by - ch / 2),
                 (bx + cw / 2, by + ch / 2), (bx - cw / 2, by + ch / 2)]
        bquad = _rotate_quad(bquad, -4.0, bx, by)
        # subtle keystone for 3D
        bquad[0] = (bquad[0][0] + 0.03 * cw, bquad[0][1])
        bquad[1] = (bquad[1][0] - 0.01 * cw, bquad[1][1])
        self.litB = CTX.LitCard(ctx.card, (W, H), bquad, theta=np.deg2rad(58),
                                dark_b=0.10, lit_b=1.0, lit_contrast=1.24,
                                spec_thr=0.55, spec_pow=2.3)

        # ---- sprites / accumulators --------------------------------------
        self.tip_glow = C.glow_sprite(int(H * 0.11), power=2.1)
        self.trail_glow = C.glow_sprite(int(H * 0.075), power=2.4)
        self.spark_glow = C.glow_sprite(max(6, int(H * 0.012)), power=1.8)
        self.acc = np.zeros((H, W), dtype=np.float32)  # sequential trail
        self.sparks = []
        self.rng = np.random.default_rng(1)
        self.warm = np.array([1.0, 0.92, 0.78], dtype=np.float32)  # tip light hue

    # ----------------------------------------------------------------------
    def _tip_path(self, i):
        W, H = self.W, self.H
        t = i / (CUT - 1)
        ts = C.smoothstep(t)
        x = W * (0.68 - 0.20 * ts)
        y = H * (-0.04 + 0.94 * t)
        x += 3.2 * np.sin(2 * np.pi * 22 * i / CTX.FPS)
        y += 3.0 * np.sin(2 * np.pi * 19 * i / CTX.FPS)
        return x, y

    def _crop_macro(self, i):
        """Push-in crop window (z 1.05 -> 0.85 + slow drift). Returns floats."""
        W, H = self.W, self.H
        t = i / (CUT - 1)
        z = 1.05 - 0.20 * C.smoothstep(t)
        cw, ch = W * z, H * z
        # drift: follow the descent a little
        ccx = self.MW / 2 + (0.06 * self.MW) * (t - 0.5) * 2
        ccy = self.MH / 2 + (0.10 * self.MH) * (t - 0.5) * 2
        x0 = int(ccx - cw / 2); y0 = int(ccy - ch / 2)
        x0 = max(0, min(self.MW - int(cw), x0))
        y0 = max(0, min(self.MH - int(ch), y0))
        box = (x0, y0, x0 + int(cw), y0 + int(ch))

        def crop_resize(a, mode):
            im = Image.fromarray(np.clip(a, 0, 255).astype(np.uint8), mode)
            im = im.crop(box).resize((W, H), Image.BILINEAR)
            return np.asarray(im, dtype=np.float32)

        dark = crop_resize(self.macro_dark, "RGB")
        lit = crop_resize(self.macro_lit, "RGB")
        edge = crop_resize((self.macro_edge * 255), "L")
        return dark, lit, edge / 255.0

    def _shotA(self, i):
        W, H = self.W, self.H
        dark, lit, edge = self._crop_macro(i)
        tip = self._tip_path(i)

        # local illumination mask from tip + lingering trail
        L = np.zeros((H, W), dtype=np.float32)
        C.add_mask(L, self.tip_glow, tip[0], tip[1], 1.0)  # tip local light
        # decay + add to trail accumulator (shorter, softer tail)
        self.acc *= 0.90
        C.add_mask(self.acc, self.trail_glow, tip[0], tip[1], 0.45)
        illum = np.clip(0.055 + L * 1.1 + np.clip(self.acc, 0, 1) * 0.4, 0, 1)

        frame = dark + (lit - dark) * illum[:, :, None]
        # ciselated edges flare only in the immediate tip light (no lingering orbs)
        flick = 0.72 + 0.28 * np.sin(2 * np.pi * 5.5 * i / CTX.FPS)
        sparkcol = np.array([1.0, 0.97, 0.9], dtype=np.float32)
        sparkle = (edge * np.clip(L, 0, 1) * flick)[:, :, None] * sparkcol[None, None, :] * 105
        frame += sparkle

        # stylus needle (dark, tapered) coming from top-right
        frame = self._draw_needle(frame, tip)

        # bright tip core + halo
        frame = C.add_sprite(frame, self.tip_glow, tip[0], tip[1],
                             self.warm * 60, 0.9)
        core = C.glow_sprite(int(H * 0.02), 2.0)
        frame = C.add_sprite(frame, core, tip[0], tip[1],
                             np.array([255, 250, 240], np.float32), 1.4)

        # sparks
        self._update_sparks(i, tip)
        for s in self.sparks:
            frame = C.add_sprite(frame, self.spark_glow, s[0], s[1],
                                 self.warm * 255, s[4])
        return frame

    def _draw_needle(self, frame, tip):
        W, H = self.W, self.H
        ov = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        d = ImageDraw.Draw(ov)
        base = (W * 1.02, -0.08 * H)
        # tapered dark body
        ang = np.arctan2(tip[1] - base[1], tip[0] - base[0])
        perp = ang + np.pi / 2
        bw = H * 0.028
        p1 = (base[0] + np.cos(perp) * bw, base[1] + np.sin(perp) * bw)
        p2 = (base[0] - np.cos(perp) * bw, base[1] - np.sin(perp) * bw)
        d.polygon([p1, p2, tip], fill=(9, 9, 11, 255))
        # rim highlight along one edge
        d.line([p1, tip], fill=(120, 118, 112, 180), width=2)
        arr = np.asarray(ov, dtype=np.float32)
        a = (arr[:, :, 3] / 255.0)[:, :, None]
        return frame * (1 - a) + arr[:, :, :3] * a

    def _update_sparks(self, i, tip):
        alive = []
        for s in self.sparks:
            s[0] += s[2]; s[1] += s[3]; s[3] += 0.6  # gravity
            s[4] *= 0.80
            if s[4] > 0.06:
                alive.append(s)
        self.sparks = alive
        if i < CUT:
            for _ in range(self.rng.integers(0, 2)):
                a = self.rng.uniform(0, 2 * np.pi)
                sp = self.rng.uniform(2, 8)
                self.sparks.append([tip[0], tip[1],
                                    np.cos(a) * sp, np.sin(a) * sp - 2, 1.0])

    def _shotB(self, i):
        W, H = self.W, self.H
        j = i - CUT
        n = 120 - CUT
        t = j / (n - 1)
        bg = self.ctx.black_bg()
        # diagonal band sweep across the card
        center = C.lerp(-0.15, 1.15, C.smoothstep(t))
        width = 0.15
        frame = self.litB.compose(bg, center, width, spec_gain=1.5,
                                  ambient=0.07, warm=0.5)
        # cut flash on the first frames (the boom)
        if j < 5:
            frame += (1 - j / 5.0) * 42
        return frame

    def render(self, i):
        if i < CUT:
            return self._shotA(i)
        return self._shotB(i)
