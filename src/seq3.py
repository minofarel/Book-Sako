"""
Sequence 3 (9-19s, 300 frames) : The card and the app — desire.

A (f 0..90):   card floats in with a floor reflection, title "La carte Sako. /
               VISA PLATINUM", specular sweep.
B (f 90..150): the card frosts over (sharp->blur, ~1s) as the "Bientôt
               disponible" pill appears (ding).
C (f 150..299):"Connectée à votre app. / Chaque euro, en temps réel." — blurred
               card + iPhone, a connection pulse, three screens in rhythmic
               cuts (balance €, cards/waitlist, Cotonou transfer + toast).
"""
import numpy as np
from PIL import Image, ImageFilter

import common as C
import context as CTX
import ui


class Seq3:
    def __init__(self, ctx):
        self.ctx = ctx
        self.W, self.H = ctx.W, ctx.H
        W, H = self.W, self.H

        self.card_spr, self.spec = ui.rounded_card(ctx.card, int(ctx.U * 0.72))
        wc, hc = self.card_spr.size
        self.cd = C.diag_coord(hc, wc, np.deg2rad(32))
        self.white_base = np.full((hc, wc, 3), 255.0, dtype=np.float32)

        pr, pa, _ = ctx.lock_pill("Bientôt disponible", scale=ctx.U / 1080 * 1.15)
        self.pill_rgb, self.pill_a = pr, pa

        # titles
        self.titleA = ctx.text_block([
            {"text": "La carte Sako.", "size": int(H * 0.040), "weight": "Bold",
             "tracking": -1, "color": (246, 246, 246)},
            {"text": "VISA PLATINUM", "size": int(H * 0.019), "weight": "SemiBold",
             "tracking": int(H * 0.006), "caps": True, "color": (188, 188, 190)}],
            line_gap=1.7)
        self.titleC = ctx.text_block([
            {"text": "Connectée à votre app.", "size": int(H * 0.036), "weight": "Bold",
             "tracking": -1, "color": (246, 246, 246)},
            {"text": "Chaque euro, en temps réel.", "size": int(H * 0.021),
             "weight": "Light", "tracking": 1, "color": (186, 186, 189)}],
            line_gap=1.6)

        # phone + screens
        self.pw = int(ctx.U * 0.345)
        SCR = (480, int(480 * 2.02))
        self.scr1 = ui.screen_balance(SCR)
        self.scr2 = ui.screen_cards(SCR, self.card_spr)
        self.SCR = SCR
        self.phone1 = ui.phone(self.scr1, self.pw)
        self.phone2 = ui.phone(self.scr2, self.pw)
        self._scr3_cache = {}

        yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
        self.xn = xx / W

    # ----------------------------------------------------------------------
    def _place_card(self, frame, cx, cy, scale, blur, alpha,
                    sweep_pos=None, sweep_i=1.4, pill_alpha=0.0, pill_scale=1.0,
                    reflect=True):
        spr = self.card_spr
        sw, sh = max(2, int(spr.width * scale)), max(2, int(spr.height * scale))
        cim = spr.resize((sw, sh), Image.BICUBIC)
        if blur > 0.4:
            cim = cim.filter(ImageFilter.GaussianBlur(float(blur)))
        arr = np.asarray(cim, dtype=np.float32)
        rgb, a = arr[:, :, :3], arr[:, :, 3] / 255.0

        if reflect:
            refl = np.asarray(cim.transpose(Image.FLIP_TOP_BOTTOM), dtype=np.float32)
            grad = (1 - np.linspace(0, 1, sh) ** 0.9)[:, None] * 0.42
            ra = refl[:, :, 3] / 255.0 * grad * alpha
            CTX.paste(frame, refl[:, :, :3] * 0.5, ra, cx, cy + sh + int(sh * 0.03))

        CTX.paste(frame, rgb, a * alpha, cx, cy)

        if sweep_pos is not None:
            stripe = C.light_band(self.cd, sweep_pos, 0.12)
            hi = (self.spec * stripe)
            CTX.paste(frame, self.white_base, hi, cx, cy, scale=scale,
                      opacity=sweep_i * alpha, add=True)
        if pill_alpha > 0.01:
            CTX.paste(frame, self.pill_rgb, self.pill_a, cx, cy,
                      scale=pill_scale, opacity=pill_alpha)

    def _phone3(self, toast_t):
        key = round(toast_t, 2)
        if key not in self._scr3_cache:
            s = ui.screen_transfer(self.SCR, toast_t=toast_t)
            self._scr3_cache[key] = ui.phone(s, self.pw)
            if len(self._scr3_cache) > 40:
                self._scr3_cache.clear()
        return self._scr3_cache[key]

    def _paste_pil(self, frame, pim, cx, cy, opacity=1.0):
        arr = np.asarray(pim, dtype=np.float32)
        CTX.paste(frame, arr[:, :, :3], arr[:, :, 3] / 255.0 * opacity, cx, cy)

    def _title(self, frame, block, cx, cy, opacity):
        rgb, a, (w, h) = block
        CTX.paste(frame, rgb, a, cx, cy, opacity=opacity)

    # ----------------------------------------------------------------------
    def render(self, i):
        W, H = self.W, self.H
        frame = self.ctx.black_bg()

        # ---- card transform across the timeline --------------------------
        # entrance
        tin = C.ease_out(np.clip(i / 18.0, 0, 1))
        # frost
        frost = C.smoothstep((i - 90) / 30.0)
        # A/B -> C transition (card moves left + shrinks)
        tc = C.smoothstep((i - 148) / 26.0)

        cx = C.lerp(W * 0.5, W * 0.29, tc)
        cy = C.lerp(H * 0.5 + (1 - tin) * H * 0.03, H * 0.52, tc)
        scale = C.lerp(1.0, 0.60, tc) * C.lerp(0.9, 1.0, tin)
        bob = np.sin(2 * np.pi * 0.22 * i / CTX.FPS) * H * 0.004 * (1 - tc)
        blur = frost * 13.0 * C.lerp(1.0, 0.6, tc)
        calpha = C.smoothstep(np.clip(i / 16.0, 0, 1))

        # sweep only in beat A
        sweep = None
        if i < 92:
            sp = (i - 20) / 55.0
            if 0 <= sp <= 1.05:
                sweep = C.lerp(-0.1, 1.1, C.smoothstep(sp))
        # pill
        pill_alpha = C.smoothstep((i - 104) / 12.0)
        pill_scale = C.lerp(1.12, 1.0, C.smoothstep((i - 104) / 14.0)) * \
            C.lerp(1.0, 0.62, tc)

        self._place_card(frame, cx, cy + bob, scale, blur, calpha,
                         sweep_pos=sweep, pill_alpha=pill_alpha,
                         pill_scale=pill_scale, reflect=(tc < 0.5))

        # ---- phone + screens (beat C) ------------------------------------
        if i > 150:
            pslide = C.ease_out(np.clip((i - 150) / 22.0, 0, 1))
            pcx = C.lerp(W * 1.2, W * 0.72, pslide)
            pcy = H * 0.53
            if i < 208:
                phone = self.phone1
            elif i < 251:
                phone = self.phone2
            else:
                toast_t = C.smoothstep((i - 264) / 12.0)
                phone = self._phone3(toast_t)
            # tiny cut punch on screen changes
            punch = 1.0
            for cutf in (208, 251):
                if 0 <= i - cutf < 4:
                    punch = 1.0 + 0.02 * (4 - (i - cutf))
            self._paste_pil(frame, phone, pcx, pcy, opacity=pslide)

            # connection pulse between card and phone
            if pslide > 0.5:
                x0, x1 = cx + W * 0.14, pcx - self.pw * 0.5
                yline = pcy
                for k in range(6):
                    fx = x0 + (x1 - x0) * k / 5.0
                    CTX.paste(frame, np.full((3, 3, 3), 255.0),
                              np.ones((3, 3)) * 0.5, fx, yline, scale=3, add=True)
                pph = (i % 22) / 22.0
                px = C.lerp(x0, x1, pph)
                g = C.glow_sprite(int(H * 0.02), 2.2)
                frame = C.add_sprite(frame, g, px, yline,
                                     np.array([255, 250, 240], np.float32), 1.3)

        # ---- titles ------------------------------------------------------
        aA = C.smoothstep(np.clip((i - 16) / 14.0, 0, 1)) * (1 - C.smoothstep((i - 140) / 16.0))
        aC = C.smoothstep((i - 150) / 16.0)
        if aA > 0.01:
            self._title(frame, self.titleA, W * 0.5, H * 0.135, aA)
        if aC > 0.01:
            self._title(frame, self.titleC, W * 0.5, H * 0.135, aC)

        # ding flash cues (visual sparkle) at pill + toast
        if 104 <= i < 110:
            g = C.glow_sprite(int(H * 0.05), 2.0)
            frame = C.add_sprite(frame, g, cx, cy, np.array([255, 250, 242], np.float32),
                                 (110 - i) / 6.0 * 0.6)
        return frame
