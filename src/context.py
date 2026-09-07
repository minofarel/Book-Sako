"""
Shared render context: assets, the plate-based lit-card engine, text sprites,
compositing helpers, backgrounds. Sequences build on this.
"""
import functools
import numpy as np
from PIL import Image, ImageDraw, ImageFilter

import common as C

FPS = 30
SIZES = {
    "9x16": (1080, 1920),
    "16x9": (1920, 1080),
    "1x1":  (1080, 1080),
}


def _lum(rgb):
    return 0.2126 * rgb[:, :, 0] + 0.7152 * rgb[:, :, 1] + 0.0722 * rgb[:, :, 2]


class LitCard:
    """
    A warped card lit by a moving diagonal light band, built from precomputed
    dark / lit plates + a specular mask. Compose is a cheap per-frame blend.
    """
    def __init__(self, card_pil, size, dst_quad, theta,
                 dark_b=0.13, lit_b=1.0, lit_contrast=1.2,
                 spec_thr=0.58, spec_pow=2.3, blur_dof=None):
        W, H = size
        warped = C.warp_card(card_pil, size, dst_quad).convert("RGBA")
        arr = np.asarray(warped, dtype=np.float32)
        self.size = size
        self.alpha = (arr[:, :, 3] / 255.0)[:, :, None]
        base = arr[:, :, :3]
        self.dark = base * dark_b
        lit = (base - 128.0) * lit_contrast + 128.0
        lit = np.clip(lit * lit_b, 0, 255)
        self.lit = lit
        lum = _lum(lit) / 255.0
        self.spec = (np.clip((lum - spec_thr) / (1 - spec_thr + 1e-6), 0, 1) ** spec_pow)
        self.dcoord = C.diag_coord(H, W, theta)
        self.bbox = warped.getbbox()  # (l,t,r,b) or None
        if blur_dof is not None:
            self.lit_blur = C.pil_blur(lit, blur_dof)
            self.dark_blur = C.pil_blur(self.dark, blur_dof)

    def compose(self, bg, center, width, spec_gain=1.7, ambient=0.0,
                warm=0.0, extra_alpha=1.0):
        band = C.light_band(self.dcoord, center, width)
        lit_amt = np.clip(ambient + band, 0, 1)[:, :, None]
        card = self.dark + (self.lit - self.dark) * lit_amt
        blow = (self.spec * band)[:, :, None]
        card = card + blow * spec_gain * 210.0
        if warm > 0:
            card = card + blow * warm * C.CHAMPAGNE[None, None, :]
        a = self.alpha * extra_alpha
        return bg * (1 - a) + card * a

    def compose_dof(self, bg, focus_center, focus_width, light_center, light_width,
                    spec_gain=1.4, ambient=0.35):
        """Depth of field: sharp in a band perpendicular to the focal plane."""
        band = C.light_band(self.dcoord, light_center, light_width)
        lit_amt = np.clip(ambient + band, 0, 1)[:, :, None]
        sharp = self.dark + (self.lit - self.dark) * lit_amt
        blurry = self.dark_blur + (self.lit_blur - self.dark_blur) * lit_amt
        fmask = C.light_band(self.dcoord, focus_center, focus_width)[:, :, None]
        card = blurry + (sharp - blurry) * fmask
        card = card + (self.spec * band)[:, :, None] * spec_gain * 210.0
        return bg * (1 - self.alpha) + card * self.alpha


class Context:
    def __init__(self, fmt):
        self.fmt = fmt
        self.W, self.H = SIZES[fmt]
        self.card = Image.open("assets/card_sako.png").convert("RGBA")
        self.logo = Image.open("assets/logo_sako_blanc.png").convert("RGBA")
        self.cache = {}

    # ---- backgrounds -----------------------------------------------------
    @functools.lru_cache(maxsize=4)
    def _dark_base(self):
        h, w = self.H, self.W
        yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
        nx, ny = xx / w, yy / h
        r = np.sqrt((nx - 0.5) ** 2 + (ny - 0.42) ** 2)
        base = 15 - r * 16
        img = np.repeat(np.clip(base, 3, 15)[:, :, None], 3, axis=2)
        img[:, :, 2] += 2.0
        return img

    def black_bg(self):
        return self._dark_base().copy()

    # ---- text sprites ----------------------------------------------------
    def text_block(self, lines, pad=40, line_gap=1.28, align="c"):
        """
        lines: list of dict(text, size, weight, tracking, color, caps=False).
        Returns (rgb float HxWx3, alpha float HxW01, (w,h)).
        Rendered on transparent, cropped tight + pad.
        """
        # measure
        tmp = Image.new("RGBA", (10, 10))
        td = ImageDraw.Draw(tmp)
        widths, heights, fonts, texts = [], [], [], []
        for ln in lines:
            fnt = C.font(ln["size"], ln.get("weight", "Bold"))
            txt = ln["text"].upper() if ln.get("caps") else ln["text"]
            trk = ln.get("tracking", 0)
            w = C.text_width(td, txt, fnt, trk)
            widths.append(w)
            heights.append(ln["size"] * line_gap)
            fonts.append((fnt, trk))
            texts.append(txt)
        W = int(max(widths) + 2 * pad)
        Htot = int(sum(heights) + 2 * pad)
        im = Image.new("RGBA", (W, Htot), (0, 0, 0, 0))
        d = ImageDraw.Draw(im)
        y = pad
        for ln, (fnt, trk), txt, hh in zip(lines, fonts, texts, heights):
            col = ln.get("color", (255, 255, 255))
            fill = (col[0], col[1], col[2], 255)
            if align == "c":
                C.draw_tracked(d, (W / 2, y), txt, fnt, fill, trk, anchor="c")
            elif align == "l":
                C.draw_tracked(d, (pad, y), txt, fnt, fill, trk, anchor="l")
            else:
                C.draw_tracked(d, (W - pad, y), txt, fnt, fill, trk, anchor="r")
            y += hh
        arr = np.asarray(im, dtype=np.float32)
        rgb = arr[:, :, :3].copy()
        alpha = arr[:, :, 3] / 255.0
        return rgb, alpha, (W, Htot)

    # ---- lock pill "Bientot disponible" ----------------------------------
    def lock_pill(self, text="Bientôt disponible", scale=1.0):
        fs = int(40 * scale)
        fnt = C.font(fs, "SemiBold")
        pad_x, pad_y = int(34 * scale), int(22 * scale)
        icon = int(fs * 1.05)
        gap = int(18 * scale)
        tmp = ImageDraw.Draw(Image.new("RGBA", (10, 10)))
        tw = tmp.textlength(text, font=fnt)
        W = int(pad_x * 2 + icon + gap + tw)
        H = int(pad_y * 2 + fs * 1.25)
        im = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        d = ImageDraw.Draw(im)
        d.rounded_rectangle([0, 0, W - 1, H - 1], radius=H // 2,
                            fill=(10, 10, 12, 205), outline=(150, 150, 155, 150),
                            width=max(1, int(2 * scale)))
        # padlock icon (vector)
        ix, iy = pad_x, H // 2
        bw = int(icon * 0.62)
        bh = int(icon * 0.5)
        d.rounded_rectangle([ix, iy - bh // 2 + int(4 * scale),
                             ix + bw, iy + bh // 2 + int(6 * scale)],
                            radius=int(5 * scale), fill=(240, 240, 242, 255))
        sh = int(bw * 0.34)
        d.arc([ix + bw // 2 - sh, iy - bh // 2 - sh + int(2 * scale),
               ix + bw // 2 + sh, iy - bh // 2 + sh + int(4 * scale)],
              180, 360, fill=(240, 240, 242, 255), width=max(2, int(4 * scale)))
        d.text((ix + icon + gap, H / 2 - fs * 0.66), text, font=fnt,
               fill=(238, 238, 240, 255))
        arr = np.asarray(im, dtype=np.float32)
        return arr[:, :, :3].copy(), arr[:, :, 3] / 255.0, (W, H)


# ==========================================================================
# compositing helpers (module-level, operate on float frames)
# ==========================================================================
def paste(frame, rgb, alpha, cx, cy, scale=1.0, opacity=1.0, add=False,
          rot=0.0):
    """Composite sprite (float rgb 0..255, alpha 0..1) centred at (cx,cy)."""
    if scale != 1.0 or rot != 0.0:
        h0, w0 = rgb.shape[:2]
        im = Image.fromarray(np.dstack([np.clip(rgb, 0, 255),
                                        np.clip(alpha * 255, 0, 255)]
                                       ).astype(np.uint8), "RGBA")
        if scale != 1.0:
            im = im.resize((max(1, int(w0 * scale)), max(1, int(h0 * scale))),
                           Image.BICUBIC)
        if rot != 0.0:
            im = im.rotate(rot, expand=True, resample=Image.BICUBIC)
        arr = np.asarray(im, dtype=np.float32)
        rgb = arr[:, :, :3]
        alpha = arr[:, :, 3] / 255.0
    sh, sw = rgb.shape[:2]
    x0 = int(round(cx - sw / 2)); y0 = int(round(cy - sh / 2))
    return _blend(frame, rgb, alpha * opacity, x0, y0, add)


def _blend(frame, rgb, alpha, x0, y0, add=False):
    H, W = frame.shape[:2]
    sh, sw = rgb.shape[:2]
    x1, y1 = x0 + sw, y0 + sh
    ix0, iy0, ix1, iy1 = max(0, x0), max(0, y0), min(W, x1), min(H, y1)
    if ix0 >= ix1 or iy0 >= iy1:
        return frame
    sx0, sy0 = ix0 - x0, iy0 - y0
    r = rgb[sy0:sy0 + (iy1 - iy0), sx0:sx0 + (ix1 - ix0)]
    a = alpha[sy0:sy0 + (iy1 - iy0), sx0:sx0 + (ix1 - ix0)]
    if a.ndim == 2:
        a = a[:, :, None]
    reg = frame[iy0:iy1, ix0:ix1]
    if add:
        frame[iy0:iy1, ix0:ix1] = reg + r * a
    else:
        frame[iy0:iy1, ix0:ix1] = reg * (1 - a) + r * a
    return frame


def finish(frame, f, vignette=0.42, grain=6.0):
    """Grain + vignette, then clip to uint8. Call once per frame at the end."""
    frame = C.apply_vignette(frame, vignette)
    frame = C.add_grain(frame, f, sigma=grain)
    return C.finalize(frame)
