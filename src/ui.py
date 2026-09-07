"""
UI toolkit for Seq 3 : rounded card sprite, iPhone frame, and the three app
screens (balance, cards/waitlist, Cotonou transfer). Everything drawn in PIL,
light neutral aesthetic (#f4f4f2) to match the brand.
"""
import numpy as np
from PIL import Image, ImageDraw, ImageFilter

import common as C

SCREEN_BG = (244, 244, 242)
INK = (24, 24, 26)
GREY = (120, 122, 126)
LINE = (223, 223, 221)


def _rounded_mask(w, h, r):
    m = Image.new("L", (w, h), 0)
    ImageDraw.Draw(m).rounded_rectangle([0, 0, w - 1, h - 1], radius=r, fill=255)
    return m


def rounded_card(card_pil, width, radius_frac=0.055, bake_sheen=True):
    """Return (RGBA sprite, spec_mask 2D 0..1) : the card with rounded corners
    and a soft baked sheen, ready to be scaled / moved / blurred."""
    cw, ch = card_pil.size
    h = int(round(width * ch / cw))
    im = card_pil.convert("RGB").resize((width, h), Image.LANCZOS)
    arr = np.asarray(im, dtype=np.float32)
    if bake_sheen:
        yy, xx = np.mgrid[0:h, 0:width].astype(np.float32)
        nx, ny = xx / width, yy / h
        sheen = 1.0 + 0.16 * (0.5 - ny) + 0.10 * (nx - 0.5)
        arr = np.clip(arr * sheen[:, :, None], 0, 255)
    r = int(h * radius_frac)
    mask = _rounded_mask(width, h, r)
    rgba = np.dstack([arr, np.asarray(mask, np.float32)[:, :, None]]).astype(np.uint8)
    sprite = Image.fromarray(rgba, "RGBA")
    lum = (0.2126 * arr[:, :, 0] + 0.7152 * arr[:, :, 1] + 0.0722 * arr[:, :, 2]) / 255.0
    spec = np.clip((lum - 0.62) / 0.38, 0, 1) ** 2.2 * (np.asarray(mask, np.float32) / 255)
    return sprite, spec


# --------------------------------------------------------------------------
# iPhone frame
# --------------------------------------------------------------------------
def phone(screen_rgba, width):
    """Wrap a screen image in an iPhone body. `width` = body width."""
    ar = 2.06                                  # body aspect (h/w)
    h = int(width * ar)
    bezel = max(6, int(width * 0.035))
    im = Image.new("RGBA", (width, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    r = int(width * 0.16)
    # outer titanium rim + black body
    d.rounded_rectangle([0, 0, width - 1, h - 1], radius=r, fill=(20, 20, 22, 255),
                        outline=(90, 92, 96, 255), width=max(2, int(width * 0.012)))
    # screen
    sx, sy = bezel, bezel
    sw, sh = width - 2 * bezel, h - 2 * bezel
    sr = int(r * 0.82)
    scr = screen_rgba.resize((sw, sh), Image.LANCZOS)
    smask = _rounded_mask(sw, sh, sr)
    im.paste(scr, (sx, sy), smask)
    # dynamic-island notch
    nw, nh = int(width * 0.34), int(width * 0.085)
    nx = (width - nw) // 2
    ny = bezel + int(width * 0.045)
    d.rounded_rectangle([nx, ny, nx + nw, ny + nh], radius=nh // 2, fill=(10, 10, 12, 255))
    return im


# --------------------------------------------------------------------------
# screen helpers
# --------------------------------------------------------------------------
def _base_screen(sz):
    im = Image.new("RGBA", sz, SCREEN_BG + (255,))
    d = ImageDraw.Draw(im)
    w, h = sz
    # status bar
    d.text((int(w * 0.08), int(h * 0.028)), "9:41", font=C.font(int(h * 0.026), "SemiBold"),
           fill=INK)
    # battery + signal (simple)
    bx = int(w * 0.86)
    by = int(h * 0.032)
    d.rounded_rectangle([bx, by, bx + int(w * 0.06), by + int(h * 0.013)],
                        radius=2, outline=INK, width=2)
    d.rectangle([bx + 1, by + 1, bx + int(w * 0.045), by + int(h * 0.013) - 1], fill=INK)
    return im, d


def _mark(d, x, y, r):
    """little Sako ring mark."""
    d.ellipse([x, y, x + 2 * r, y + 2 * r], outline=INK, width=max(2, r // 6))
    f = C.font(int(r * 1.5), "ExtraBold")
    bb = d.textbbox((0, 0), "S", font=f)
    d.text((x + r - (bb[2] - bb[0]) / 2 - bb[0], y + r - (bb[3] - bb[1]) / 2 - bb[1]),
           "S", font=f, fill=INK)


def screen_balance(sz):
    im, d = _base_screen(sz)
    w, h = sz
    _mark(d, int(w * 0.08), int(h * 0.075), int(h * 0.022))
    d.text((int(w * 0.20), int(h * 0.082), ), "Sako", font=C.font(int(h * 0.030), "Bold"), fill=INK)
    d.text((int(w * 0.08), int(h * 0.15)), "Solde disponible",
           font=C.font(int(h * 0.026), "Regular"), fill=GREY)
    d.text((int(w * 0.08), int(h * 0.185)), "2 480,50 €",
           font=C.font(int(h * 0.075), "ExtraBold"), fill=INK)
    # mini chip row
    d.text((int(w * 0.08), int(h * 0.285)), "Compte courant · Sako",
           font=C.font(int(h * 0.024), "Regular"), fill=GREY)
    # section
    d.text((int(w * 0.08), int(h * 0.355)), "Transactions",
           font=C.font(int(h * 0.028), "SemiBold"), fill=INK)
    rows = [("Carrefour", "Aujourd'hui", "−38,20 €"),
            ("Salaire", "Hier", "+2 400,00 €"),
            ("Spotify", "2 sept.", "−11,99 €"),
            ("Retrait DAB", "1er sept.", "−60,00 €")]
    y = int(h * 0.41)
    rh = int(h * 0.085)
    for name, when, amt in rows:
        d.ellipse([int(w * 0.08), y, int(w * 0.08) + rh * 0.62, y + rh * 0.62],
                  fill=(232, 232, 230))
        d.text((int(w * 0.23), y + int(rh * 0.06)), name,
               font=C.font(int(h * 0.025), "SemiBold"), fill=INK)
        d.text((int(w * 0.23), y + int(rh * 0.36)), when,
               font=C.font(int(h * 0.020), "Regular"), fill=GREY)
        af = C.font(int(h * 0.027), "SemiBold")
        aw = d.textlength(amt, font=af)
        d.text((int(w * 0.92) - aw, y + int(rh * 0.20)), amt, font=af, fill=INK)
        y += rh
        d.line([int(w * 0.08), y - int(rh * 0.12), int(w * 0.92), y - int(rh * 0.12)],
               fill=LINE, width=1)
    _tabbar(d, sz, 0)
    return im


def screen_cards(sz, card_sprite):
    im, d = _base_screen(sz)
    w, h = sz
    d.text((int(w * 0.08), int(h * 0.075)), "Vos cartes",
           font=C.font(int(h * 0.040), "Bold"), fill=INK)
    # blurred mini card
    mcw = int(w * 0.84)
    mini = card_sprite.resize((mcw, int(mcw * card_sprite.height / card_sprite.width)),
                              Image.LANCZOS).filter(ImageFilter.GaussianBlur(6))
    mx, my = int(w * 0.08), int(h * 0.17)
    im.paste(mini, (mx, my), mini)
    # lock pill over the card
    _pill(d, im, int(w * 0.5), my + mini.height // 2, int(h * 0.018))
    # waitlist text
    d.text((int(w * 0.5), int(h * 0.6)), "Vous êtes sur la liste d'attente",
           font=C.font(int(h * 0.028), "SemiBold"), fill=INK, anchor="ma")
    d.text((int(w * 0.5), int(h * 0.645)), "Votre carte Visa Platinum arrive bientôt.",
           font=C.font(int(h * 0.023), "Regular"), fill=GREY, anchor="ma")
    # progress-ish bar
    bx0, bx1, by = int(w * 0.14), int(w * 0.86), int(h * 0.72)
    d.rounded_rectangle([bx0, by, bx1, by + int(h * 0.012)], radius=6, fill=(228, 228, 226))
    d.rounded_rectangle([bx0, by, int(bx0 + (bx1 - bx0) * 0.72), by + int(h * 0.012)],
                        radius=6, fill=INK)
    _tabbar(d, sz, 2)
    return im


def screen_transfer(sz, toast_t=1.0):
    im, d = _base_screen(sz)
    w, h = sz
    d.text((int(w * 0.08), int(h * 0.075)), "Transfert",
           font=C.font(int(h * 0.040), "Bold"), fill=INK)
    # big check
    ccx, ccy, cr = int(w * 0.5), int(h * 0.34), int(h * 0.075)
    d.ellipse([ccx - cr, ccy - cr, ccx + cr, ccy + cr], outline=INK, width=max(3, cr // 10))
    d.line([ccx - cr * 0.42, ccy + cr * 0.02, ccx - cr * 0.08, ccy + cr * 0.36],
           fill=INK, width=max(3, cr // 8))
    d.line([ccx - cr * 0.08, ccy + cr * 0.36, ccx + cr * 0.5, ccy - cr * 0.34],
           fill=INK, width=max(3, cr // 8))
    d.text((int(w * 0.5), int(h * 0.46)), "Transfert envoyé",
           font=C.font(int(h * 0.032), "Bold"), fill=INK, anchor="ma")
    d.text((int(w * 0.5), int(h * 0.505)), "vers Cotonou · Bénin",
           font=C.font(int(h * 0.026), "Regular"), fill=GREY, anchor="ma")
    d.text((int(w * 0.5), int(h * 0.57)), "−200,00 €",
           font=C.font(int(h * 0.06), "ExtraBold"), fill=INK, anchor="ma")
    # toast dropping from the top
    if toast_t > 0.01:
        tw, th = int(w * 0.86), int(h * 0.10)
        tx = (w - tw) // 2
        drop = int(C.ease_out(toast_t, 3) * (h * 0.045 + th)) - th
        ty = int(h * 0.02) + drop
        toast = Image.new("RGBA", (tw, th), (0, 0, 0, 0))
        td = ImageDraw.Draw(toast)
        td.rounded_rectangle([0, 0, tw - 1, th - 1], radius=int(th * 0.28),
                             fill=(18, 18, 20, 245))
        cr2 = int(th * 0.24)
        cx2, cy2 = int(th * 0.5), th // 2
        td.ellipse([cx2 - cr2, cy2 - cr2, cx2 + cr2, cy2 + cr2], outline=(240, 240, 242),
                   width=3)
        td.line([cx2 - cr2 * 0.4, cy2, cx2 - cr2 * 0.05, cy2 + cr2 * 0.4],
                fill=(240, 240, 242), width=3)
        td.line([cx2 - cr2 * 0.05, cy2 + cr2 * 0.4, cx2 + cr2 * 0.55, cy2 - cr2 * 0.4],
                fill=(240, 240, 242), width=3)
        td.text((int(th * 0.95), int(th * 0.2)), "Reçu en 28 secondes",
                font=C.font(int(h * 0.023), "SemiBold"), fill=(245, 245, 247))
        td.text((int(th * 0.95), int(th * 0.55)), "Cotonou · −200,00 €",
                font=C.font(int(h * 0.020), "Regular"), fill=(190, 190, 194))
        toast.putalpha(toast.getchannel("A").point(lambda a: int(a * min(1, toast_t * 1.4))))
        im.paste(toast, (tx, ty), toast)
    _tabbar(d, sz, 1)
    return im


def _pill(d, im, cx, cy, fs):
    text = "Bientôt disponible"
    fnt = C.font(fs, "SemiBold")
    tw = d.textlength(text, font=fnt)
    icon = int(fs * 1.1)
    padx, pady, gap = int(fs * 0.8), int(fs * 0.55), int(fs * 0.45)
    W = int(padx * 2 + icon + gap + tw)
    Hh = int(pady * 2 + fs * 1.2)
    pill = Image.new("RGBA", (W, Hh), (0, 0, 0, 0))
    pd = ImageDraw.Draw(pill)
    pd.rounded_rectangle([0, 0, W - 1, Hh - 1], radius=Hh // 2, fill=(12, 12, 14, 220))
    ix, iy = padx, Hh // 2
    bw, bh = int(icon * 0.62), int(icon * 0.5)
    pd.rounded_rectangle([ix, iy - bh // 2 + 3, ix + bw, iy + bh // 2 + 4], radius=4,
                         fill=(240, 240, 242))
    sh = int(bw * 0.34)
    pd.arc([ix + bw // 2 - sh, iy - bh // 2 - sh + 2, ix + bw // 2 + sh, iy - bh // 2 + sh + 3],
           180, 360, fill=(240, 240, 242), width=3)
    pd.text((ix + icon + gap, Hh / 2 - fs * 0.62), text, font=fnt, fill=(238, 238, 240))
    im.paste(pill, (int(cx - W / 2), int(cy - Hh / 2)), pill)


def _tabbar(d, sz, active):
    w, h = sz
    y = int(h * 0.93)
    d.line([0, y - int(h * 0.006), w, y - int(h * 0.006)], fill=LINE, width=1)
    labels = ["Accueil", "Transferts", "Cartes"]
    for i, lab in enumerate(labels):
        x = int(w * (0.22 + i * 0.28))
        col = INK if i == active else GREY
        d.ellipse([x - int(w * 0.014), y, x + int(w * 0.014), y + int(w * 0.028)],
                  outline=col, width=2)
        aw = d.textlength(lab, font=C.font(int(h * 0.018), "Regular"))
        d.text((x - aw / 2, y + int(w * 0.05)), lab,
               font=C.font(int(h * 0.018), "Regular"), fill=col)
