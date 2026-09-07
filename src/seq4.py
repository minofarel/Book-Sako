"""
Sequence 4 (19-29s, 300 frames) : Final hype.

f 0..95   : 5 accelerating macro flashes of card details, darkened with a baked
            diagonal light band, punch-in 1.10->1.0, boom on each cut.
f 95..103 : black.
f 103..150: "Elle arrive." ExtraBold, punch.
f 150..300: Sako logo deblur/scale-in + light sweep, baseline, "BIENTÔT
            DISPONIBLE", "Rejoignez la liste d'attente · sako.app", fade to black.
"""
import numpy as np
from PIL import Image, ImageFilter

import common as C
import context as CTX

# flash cut starts (local frames); flash k = [CUTS[k], CUTS[k+1])
CUTS = [0, 24, 46, 65, 81, 95]
# card detail crops (box on the 1536x969 card) + band angle
CROPS = [
    ((40, 30, 560, 330), 28),      # wordmark
    ((596, 96, 980, 470), 122),    # croix d'Agadez (ring + wings)
    ((1080, 30, 1500, 250), 20),   # VISA
    ((606, 470, 946, 838), 150),   # motif serré (body + pendant)
    ((648, 690, 900, 946), 68),    # bas du bijou
]


class Seq4:
    def __init__(self, ctx):
        self.ctx = ctx
        self.W, self.H = ctx.W, ctx.H
        W, H = self.W, self.H

        self.plates = [self._make_plate(box, ang) for box, ang in CROPS]

        # "Elle arrive."
        self.elle = ctx.text_block([
            {"text": "Elle arrive.", "size": int(H * 0.072), "weight": "ExtraBold",
             "tracking": -2, "color": (247, 247, 247)}])

        # final lockup pieces
        self.logo_rgb, self.logo_a = self._logo(int(ctx.U * 0.52))
        lh, lw = self.logo_a.shape
        self.logo_cd = C.diag_coord(lh, lw, np.deg2rad(28))
        self.logo_white = np.full((lh, lw, 3), 255.0, dtype=np.float32)

        self.baseline = ctx.text_block([
            {"text": "La finance sans frontières", "size": int(H * 0.024),
             "weight": "Light", "tracking": int(H * 0.004), "color": (196, 196, 199)}])
        self.dispo = ctx.text_block([
            {"text": "BIENTÔT DISPONIBLE", "size": int(H * 0.020), "weight": "SemiBold",
             "tracking": int(H * 0.010), "color": (232, 232, 234)}])
        self.cta = ctx.text_block([
            {"text": "Rejoignez la liste d'attente · sako.app", "size": int(H * 0.022),
             "weight": "Regular", "tracking": int(H * 0.002), "color": (176, 176, 180)}])

    # ----------------------------------------------------------------------
    def _cover(self, box):
        crop = self.ctx.card.convert("RGB").crop(box)
        cw, ch = crop.size
        s = max(self.W / cw, self.H / ch)
        crop = crop.resize((int(cw * s) + 1, int(ch * s) + 1), Image.LANCZOS)
        x = (crop.width - self.W) // 2
        y = (crop.height - self.H) // 2
        crop = crop.crop((x, y, x + self.W, y + self.H))
        return np.asarray(crop, dtype=np.float32)

    def _make_plate(self, box, ang):
        W, H = self.W, self.H
        base = self._cover(box)
        d = C.diag_coord(H, W, np.deg2rad(ang))
        band = C.light_band(d, 0.5, 0.26)
        lum = (0.2126 * base[:, :, 0] + 0.7152 * base[:, :, 1] + 0.0722 * base[:, :, 2]) / 255.0
        spec = np.clip((lum - 0.6) / 0.4, 0, 1) ** 2.2
        plate = base * (0.20 + 0.52 * band)[:, :, None]
        plate += (spec * band)[:, :, None] * 170.0
        return np.clip(plate, 0, 255)

    def _logo(self, width):
        lg = self.ctx.logo
        h = int(width * lg.height / lg.width)
        lg = lg.resize((width, h), Image.LANCZOS)
        arr = np.asarray(lg, dtype=np.float32)
        return arr[:, :, :3].copy(), arr[:, :, 3] / 255.0

    def _punch(self, plate, punch, boost):
        W, H = self.W, self.H
        if punch > 1.003:
            nw, nh = int(W * punch), int(H * punch)
            im = Image.fromarray(C.finalize(plate)).resize((nw, nh), Image.BILINEAR)
            x, y = (nw - W) // 2, (nh - H) // 2
            out = np.asarray(im.crop((x, y, x + W, y + H)), dtype=np.float32)
        else:
            out = plate.copy()
        if boost > 0:
            out = out + boost
        return out

    # ----------------------------------------------------------------------
    def _flashes(self, i):
        # which flash
        k = 0
        for j in range(5):
            if CUTS[j] <= i < CUTS[j + 1]:
                k = j
                break
        lf = i - CUTS[k]
        dur = CUTS[k + 1] - CUTS[k]
        punch = C.lerp(1.10, 1.0, C.ease_out(lf / dur, 2.4))
        boost = max(0.0, (1 - lf / 3.0)) * 46 if lf < 3 else 0.0
        return self._punch(self.plates[k], punch, boost)

    def _elle(self, i):
        frame = self.ctx.black_bg()
        j = i - 103
        n = 150 - 103
        t = j / n
        sc = C.lerp(1.16, 1.0, C.ease_out(np.clip(j / 10.0, 0, 1), 2.5))
        alpha = C.smoothstep(np.clip(j / 6.0, 0, 1)) * (1 - C.smoothstep((j - (n - 8)) / 8.0))
        blur = C.lerp(10, 0, C.ease_out(np.clip(j / 8.0, 0, 1)))
        rgb, a, _ = self.elle
        if blur > 0.5:
            im = Image.fromarray(np.dstack([np.clip(rgb, 0, 255),
                                            np.clip(a * 255, 0, 255)]).astype(np.uint8), "RGBA")
            im = im.filter(ImageFilter.GaussianBlur(float(blur)))
            arr = np.asarray(im, dtype=np.float32)
            rgb, a = arr[:, :, :3], arr[:, :, 3] / 255.0
        # subtle boom flash at entry
        if j < 3:
            frame += (3 - j) / 3.0 * 24
        CTX.paste(frame, rgb, a, self.W * 0.5, self.H * 0.47, scale=float(sc),
                  opacity=float(alpha))
        return frame

    def _final(self, i):
        W, H = self.W, self.H
        frame = self.ctx.black_bg()
        j = i - 150
        # logo deblur/scale-in
        tin = C.ease_out(np.clip(j / 26.0, 0, 1), 2.2)
        sc = C.lerp(0.82, 1.0, tin)
        alpha = C.smoothstep(np.clip(j / 20.0, 0, 1))
        blur = C.lerp(20, 0, tin)
        rgb, a = self.logo_rgb, self.logo_a
        if blur > 0.5:
            im = Image.fromarray(np.dstack([np.clip(rgb, 0, 255),
                                            np.clip(a * 255, 0, 255)]).astype(np.uint8), "RGBA")
            im = im.filter(ImageFilter.GaussianBlur(float(blur)))
            arr = np.asarray(im, dtype=np.float32)
            rgb, a = arr[:, :, :3], arr[:, :, 3] / 255.0
        ly = H * 0.40
        CTX.paste(frame, rgb, a, W * 0.5, ly, scale=float(sc), opacity=float(alpha))

        # light sweep across the logo (one pass)
        sp = (j - 26) / 26.0
        if 0 <= sp <= 1.05:
            stripe = C.light_band(self.logo_cd, C.lerp(-0.1, 1.1, C.smoothstep(sp)), 0.12)
            hi = self.logo_a * stripe
            CTX.paste(frame, self.logo_white, hi, W * 0.5, ly, opacity=1.7, add=True)

        # staggered text
        def show(block, cy, start):
            op = C.smoothstep((j - start) / 12.0)
            if op > 0.01:
                r, aa, _ = block
                CTX.paste(frame, r, aa, W * 0.5, cy, opacity=float(op))
        show(self.baseline, H * 0.505, 30)
        show(self.dispo, H * 0.60, 44)
        show(self.cta, H * 0.655, 54)

        # fade to black at the very end
        fade = C.smoothstep((j - (150 - 14)) / 14.0)
        if fade > 0:
            frame *= (1 - fade)
        return frame

    def render(self, i):
        if i < 95:
            return self._flashes(i)
        if i < 103:
            frame = self.ctx.black_bg()
            if i < 98:                       # residual boom light from last flash
                frame += (98 - i) / 5.0 * 12
            return frame
        if i < 150:
            return self._elle(i)
        return self._final(i)
