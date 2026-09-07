"""
Sequence 2 (4-9s, 150 frames) : Reveal by light (Revolut style).

Plan 1 (f 0..105):  card standing in pure black, macro on its top; a wide
diagonal band rises slowly, the "Sako" wordmark ignites, the motif appears,
then the scene falls back to shadow.
Plan 2 (f 106..149): extreme raking macro on the letters (wordmark region
pre-cropped, upscaled x3, THEN warped), short DOF, a vertical glint crosses
"Sako".
"""
import numpy as np
from PIL import Image

import common as C
import context as CTX

CUT = 106


class Seq2:
    def __init__(self, ctx):
        self.ctx = ctx
        self.W, self.H = ctx.W, ctx.H
        W, H = self.W, self.H
        cardW, cardH = ctx.card.size

        # ---- Plan 1 : big upright card, top prominent --------------------
        cw = ctx.U * 1.55
        ch = cw * cardH / cardW
        cx = W * 0.5
        ty = H * 0.30
        quad = [(cx - cw / 2, ty), (cx + cw / 2, ty),
                (cx + cw / 2, ty + ch), (cx - cw / 2, ty + ch)]
        # gentle keystone (top edge a touch further)
        quad[0] = (quad[0][0] + 0.05 * cw, quad[0][1] + 0.015 * ch)
        quad[1] = (quad[1][0] - 0.05 * cw, quad[1][1] + 0.015 * ch)
        self.p1 = CTX.LitCard(ctx.card, (W, H), quad, theta=np.deg2rad(245),
                              dark_b=0.03, lit_b=0.94, lit_contrast=1.3,
                              spec_thr=0.52, spec_pow=2.2)

        # ---- Plan 2 : wordmark crop -> upscale x3 -> warp ----------------
        wm = ctx.card.crop((58, 40, 476, 214))          # "Sako" region
        wm = wm.resize((wm.width * 3, wm.height * 3), Image.LANCZOS)
        WW, WH = wm.size
        # raking keystone: bottom near/large, top recedes
        m = W * 0.10
        dq = [(m + 0.20 * W, H * 0.30), (W - m - 0.20 * W, H * 0.30),
              (W - m, H * 0.86), (m, H * 0.86)]
        self.p2 = CTX.LitCard(wm, (W, H), dq, theta=np.deg2rad(2),
                              dark_b=0.07, lit_b=1.0, lit_contrast=1.3,
                              spec_thr=0.42, spec_pow=1.8, blur_dof=11)
        # vertical glint coordinate (screen x, normalised)
        yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
        self.xn = (xx / W)

    # ----------------------------------------------------------------------
    def _plan1(self, i):
        t = i / (CUT - 1)
        bg = self.ctx.black_bg()
        center = C.lerp(-0.28, 1.35, C.ease_out(t, 1.7))
        width = C.lerp(0.10, 0.34, t)
        frame = self.p1.compose(bg, center, width, spec_gain=1.55,
                                ambient=0.005, warm=0.7)
        if i < 8:                       # ease in from black
            frame *= C.smoothstep(i / 8.0)
        return frame

    def _plan2(self, i):
        W, H = self.W, self.H
        j = i - CUT
        n = 150 - CUT
        t = j / (n - 1)
        bg = self.ctx.black_bg()
        # raking light rakes across, focus band tracks slightly behind
        light_c = C.lerp(0.15, 0.9, C.smoothstep(t))
        frame = self.p2.compose_dof(bg, focus_center=0.5, focus_width=0.42,
                                    light_center=light_c, light_width=0.34,
                                    spec_gain=1.5, ambient=0.28)
        # vertical glint sweeping across the letters ("shing")
        gx = C.lerp(-0.1, 1.1, C.smoothstep(np.clip((t - 0.15) / 0.7, 0, 1)))
        gw = 0.05
        gl = np.exp(-(((self.xn - gx) / gw) ** 2))
        glint = (self.p2.spec * gl)[:, :, None] * np.array([255, 252, 245], np.float32)
        frame += glint * 1.9
        if j < 4:                       # cut flash
            frame += (1 - j / 4.0) * 34
        return frame

    def render(self, i):
        if i < CUT:
            return self._plan1(i)
        return self._plan2(i)
