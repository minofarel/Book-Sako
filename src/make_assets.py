"""
Regenerate the two image assets procedurally, matching the reference:
  assets/card_sako.png       1536x969  silver, pointillist Agadez cross,
                             "Sako" wordmark top-left, "VISA Platinum" top-right
  assets/logo_sako_blanc.png white "Sako" wordmark (+ mark) on transparent

Pure Pillow + numpy. Run:  python3 src/make_assets.py
"""
import os
import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

import sys
sys.path.insert(0, os.path.dirname(__file__))
from common import font, draw_tracked, text_width

CARD_W, CARD_H = 1536, 969
S = 2                       # supersample for the vector line-art
CX = CARD_W // 2            # cross vertical axis


# --------------------------------------------------------------------------
# Agadez cross line-art -> a grayscale "structure" map (0..255 = dot density)
# --------------------------------------------------------------------------
def build_cross_structure():
    W, H = CARD_W * S, CARD_H * S
    im = Image.new("L", (W, H), 0)
    d = ImageDraw.Draw(im)
    cx = CX * S

    def sc(v):            # scale a card-space length to supersample space
        return v * S

    lw = max(2, int(2.4 * S))     # main stroke
    lwt = max(1, int(1.4 * S))    # thin hatch

    def line(p0, p1, w=lw, f=255):
        d.line([(cx + sc(p0[0]), sc(p0[1])), (cx + sc(p1[0]), sc(p1[1]))],
               fill=f, width=w)

    def poly(pts, w=lw, f=255):
        pp = [(cx + sc(x), sc(y)) for x, y in pts]
        d.line(pp + [pp[0]], fill=f, width=w)

    def ring(cyv, r, w=lw, f=255):
        d.ellipse([cx - sc(r), sc(cyv) - sc(r), cx + sc(r), sc(cyv) + sc(r)],
                  outline=f, width=w)

    def dot(x, y, r=3, f=255):
        d.ellipse([cx + sc(x) - sc(r), sc(y) - sc(r),
                   cx + sc(x) + sc(r), sc(y) + sc(r)], fill=f)

    # ---- 1. apex triangle + beads (top) -----------------------------------
    poly([(-34, 96), (34, 96), (0, 40)])
    line((-20, 78), (20, 78), lwt)
    dot(0, 62, 4); dot(-9, 84, 3); dot(9, 84, 3)
    dot(0, 30, 4)

    # ---- 2. ring ----------------------------------------------------------
    ring(232, 96)
    ring(232, 64, lwt)
    line((0, 96), (0, 136), lwt)          # ring -> neck stem

    # ---- 3. wings / bowtie arms at ring height ----------------------------
    for s in (-1, 1):
        # horizontal diamond (bowtie)
        poly([(s * 96, 232), (s * 210, 196), (s * 300, 232), (s * 210, 268)])
        line((s * 132, 232), (s * 300, 232), lwt)   # spine
        d.ellipse([cx + sc(s * 300) - sc(14), sc(232) - sc(14),
                   cx + sc(s * 300) + sc(14), sc(232) + sc(14)],
                  outline=255, width=lwt)            # tip knob
        dot(s * 210, 214, 3); dot(s * 210, 250, 3)

    # ---- 4. neck bar with hatch ------------------------------------------
    d.rounded_rectangle([cx - sc(78), sc(356), cx + sc(78), sc(404)],
                        radius=sc(10), outline=255, width=lw)
    for i in range(-6, 7):
        line((i * 11, 358), (i * 11, 402), lwt)      # vertical hatch

    # ---- 5. body pyramid (apex up) with chevron hatching ------------------
    poly([(-150, 560), (150, 560), (0, 410)])
    poly([(-104, 560), (104, 560), (0, 452)], lwt)
    # chevron / herringbone inner lines
    for k in range(1, 6):
        yv = 452 + k * 20
        wv = (yv - 410) / 150.0 * 150 * 0.86
        line((-wv, yv), (0, yv - 20), lwt)
        line((wv, yv), (0, yv - 20), lwt)
    dot(0, 500, 5); dot(-34, 545, 3); dot(34, 545, 3)

    # ---- 6. side nubs -----------------------------------------------------
    for s in (-1, 1):
        d.rounded_rectangle(
            [cx + sc(s * 150) - (sc(70) if s > 0 else 0),
             sc(536), cx + sc(s * 150) + (sc(70) if s < 0 else 0), sc(566)],
            radius=sc(6), outline=255, width=lwt)
        d.ellipse([cx + sc(s * 224) - sc(11), sc(551) - sc(11),
                   cx + sc(s * 224) + sc(11), sc(551) + sc(11)],
                  outline=255, width=lwt)

    # ---- 7. lower band + triangular fringe + dangles ----------------------
    d.rounded_rectangle([cx - sc(150), sc(576), cx + sc(150), sc(612)],
                        radius=sc(8), outline=255, width=lw)
    for i in range(-13, 14):
        line((i * 11, 578), (i * 11, 610), lwt)
    nteeth = 9
    for i in range(nteeth):
        x0 = -140 + i * (280 / (nteeth - 1))
        step = 280 / (nteeth - 1)
        poly([(x0, 612), (x0 + step, 612), (x0 + step / 2, 656)], lwt)
    # dangles
    for i in range(7):
        xd = -120 + i * 40
        line((xd, 612), (xd, 640 + (i % 2) * 16), lwt)
        dot(xd, 640 + (i % 2) * 16 + 6, 3)

    # ---- 8. pendant / shield (teardrop tapering to a point) ---------------
    left = []
    right = []
    N = 60
    for i in range(N + 1):
        t = i / N
        yv = 640 + t * 268                 # 640 -> 908
        # width profile: bulge then taper to a point
        wv = 118 * (1 - t) ** 0.65 * (0.35 + 0.65 * np.sin(np.pi * min(t * 1.15, 1))) + 6 * (1 - t)
        wv = max(wv, 0.0)
        left.append((-wv, yv))
        right.append((wv, yv))
    contour = left + right[::-1]
    pp = [(cx + sc(x), sc(y)) for x, y in contour]
    d.line(pp + [pp[0]], fill=255, width=lw)
    # inner echo line
    pp2 = [(cx + sc(x * 0.72), sc(640 + (y - 640) * 0.9)) for x, y in contour]
    d.line(pp2 + [pp2[0]], fill=255, width=lwt)

    # ---- 9. bottom diamond (4-directions motif) ---------------------------
    poly([(0, 742), (26, 770), (0, 798), (-26, 770)], lwt)
    dot(0, 770, 4)
    dot(0, 752, 2); dot(0, 788, 2); dot(-16, 770, 2); dot(16, 770, 2)
    dot(0, 900, 3)

    im = im.filter(ImageFilter.GaussianBlur(S * 0.5))
    im = im.resize((CARD_W, CARD_H), Image.LANCZOS)
    return np.asarray(im, dtype=np.float32)


# --------------------------------------------------------------------------
# Stipple : turn a structure map into pointillist dots on a jittered grid
# --------------------------------------------------------------------------
def stipple_layer(structure, step=3, jitter=1.3, gain=1.0, thr=0.16, seed=3):
    rng = np.random.default_rng(seed)
    h, w = structure.shape
    ys = np.arange(step // 2, h - 1, step)
    xs = np.arange(step // 2, w - 1, step)
    gx, gy = np.meshgrid(xs.astype(np.float32), ys.astype(np.float32))
    gx = np.clip(gx + rng.uniform(-jitter, jitter, gx.shape), 0, w - 1)
    gy = np.clip(gy + rng.uniform(-jitter, jitter, gy.shape), 0, h - 1)
    ix = gx.astype(np.int32).ravel()
    iy = gy.astype(np.int32).ravel()
    val = structure[iy, ix] / 255.0
    keep = rng.random(val.shape) < (val * gain)
    keep &= val > thr
    ix, iy, val = ix[keep], iy[keep], val[keep]
    layer = np.zeros((h, w), dtype=np.float32)
    bright = val * (0.75 + 0.25 * rng.random(val.shape))
    np.add.at(layer, (iy, ix), bright)
    return np.clip(layer, 0, 1)


# --------------------------------------------------------------------------
# Silver background
# --------------------------------------------------------------------------
def build_background():
    h, w = CARD_H, CARD_W
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    nx, ny = xx / w, yy / h
    # diagonal gradient: dark bottom-left -> bright top-right
    g = 0.62 * (nx) + 0.55 * (1 - ny)
    base = 92 + g * 112
    # bright hotspot upper-right (kept off the vertical centre so the cross reads)
    hot = np.exp(-(((nx - 0.74) / 0.34) ** 2 + ((ny - 0.24) / 0.34) ** 2))
    base = base + hot * 26
    # gentle darkening lower-left corner
    base = base - np.exp(-(((nx - 0.05) / 0.5) ** 2 + ((ny - 0.98) / 0.5) ** 2)) * 26
    img = np.repeat(base[:, :, None], 3, axis=2)
    # very slight cool cast (neutral silver leans a touch blue)
    img[:, :, 2] += 3.0
    img[:, :, 0] -= 2.0
    return img


def main():
    os.makedirs("assets", exist_ok=True)
    rng = np.random.default_rng(11)

    img = build_background()
    h, w = CARD_H, CARD_W

    # global metallic pointillism: signed fine specks everywhere
    speck = rng.normal(0, 1, (h, w)).astype(np.float32)
    speck_mask = (rng.random((h, w)) < 0.22).astype(np.float32)
    img += (speck * speck_mask)[:, :, None] * 7.0
    # a sparse brighter dust
    dust = (rng.random((h, w)) < 0.03).astype(np.float32) * rng.random((h, w))
    img += dust[:, :, None] * 26.0

    # Agadez cross (faint, lighter than ground)
    structure = build_cross_structure()
    cross = stipple_layer(structure, step=3, jitter=1.3, gain=1.25, thr=0.10, seed=5)
    cross = np.asarray(Image.fromarray((cross * 255).astype(np.uint8))
                       .filter(ImageFilter.GaussianBlur(0.4)), np.float32) / 255.0
    # engraved relief: bright light on the up-left facet, dark on the down-right
    img += cross[:, :, None] * 96.0
    sh = np.zeros_like(cross)
    sh[3:, 3:] = cross[:-3, :-3]
    img -= (np.clip(sh - cross, 0, 1))[:, :, None] * 34.0

    img = np.clip(img, 0, 255)

    # ---- wordmarks (drawn on top, crisp) ---------------------------------
    pim = Image.fromarray(img.astype(np.uint8)).convert("RGB")
    draw = ImageDraw.Draw(pim)

    # Sako logo mark : ring + "S" + satellite node (top-left)
    lx, ly = 74, 74
    R = 46
    draw.ellipse([lx, ly, lx + 2 * R, ly + 2 * R], outline=(248, 248, 248), width=6)
    sfnt = font(70, "ExtraBold")
    bb = draw.textbbox((0, 0), "S", font=sfnt)
    draw.text((lx + R - (bb[2] - bb[0]) / 2 - bb[0],
               ly + R - (bb[3] - bb[1]) / 2 - bb[1]), "S",
              font=sfnt, fill=(250, 250, 250))
    # satellite node (transfer motif)
    nx0, ny0 = lx + 2 * R - 6, ly + 10
    draw.line([lx + 2 * R - 22, ly + 22, nx0, ny0], fill=(240, 240, 240), width=4)
    draw.ellipse([nx0 - 8, ny0 - 8, nx0 + 8, ny0 + 8], fill=(252, 252, 252))

    # "Sako" wordmark
    wfnt = font(96, "Bold")
    draw.text((lx + 2 * R + 30, ly + R - 60), "Sako", font=wfnt, fill=(250, 250, 250))

    # VISA (top-right) : bold, slightly sheared to evoke the logo
    visa = font(104, "ExtraBold")
    vtxt = Image.new("RGBA", (460, 150), (0, 0, 0, 0))
    vd = ImageDraw.Draw(vtxt)
    vd.text((6, 6), "VISA", font=visa, fill=(255, 255, 255, 255))
    vtxt = vtxt.transform(vtxt.size, Image.AFFINE, (1, -0.18, 22, 0, 1, 0),
                          Image.BICUBIC)
    vb = vtxt.getbbox()
    vtxt = vtxt.crop(vb)
    pim.paste(vtxt, (CARD_W - vtxt.size[0] - 70, 62), vtxt)

    # "Platinum" under VISA, right aligned
    pfnt = font(52, "Regular")
    ptxt = "Platinum"
    pw = draw.textlength(ptxt, font=pfnt)
    draw.text((CARD_W - 70 - pw, 182), ptxt, font=pfnt, fill=(250, 250, 250))

    pim.save("assets/card_sako.png")
    print("wrote assets/card_sako.png", pim.size)

    # ---- logo_sako_blanc.png : white mark + wordmark on transparent -------
    LW, LH = 720, 220
    lim = Image.new("RGBA", (LW, LH), (0, 0, 0, 0))
    ld = ImageDraw.Draw(lim)
    R2 = 62
    ox, oy = 8, (LH - 2 * R2) // 2
    ld.ellipse([ox, oy, ox + 2 * R2, oy + 2 * R2], outline=(255, 255, 255, 255), width=8)
    s2 = font(96, "ExtraBold")
    bb = ld.textbbox((0, 0), "S", font=s2)
    ld.text((ox + R2 - (bb[2] - bb[0]) / 2 - bb[0],
             oy + R2 - (bb[3] - bb[1]) / 2 - bb[1]), "S",
            font=s2, fill=(255, 255, 255, 255))
    nx0, ny0 = ox + 2 * R2 - 8, oy + 14
    ld.line([ox + 2 * R2 - 30, oy + 30, nx0, ny0], fill=(255, 255, 255, 255), width=5)
    ld.ellipse([nx0 - 11, ny0 - 11, nx0 + 11, ny0 + 11], fill=(255, 255, 255, 255))
    w2 = font(132, "Bold")
    ld.text((ox + 2 * R2 + 40, LH / 2 - 82), "Sako", font=w2, fill=(255, 255, 255, 255))
    lim = lim.crop(lim.getbbox())
    lim.save("assets/logo_sako_blanc.png")
    print("wrote assets/logo_sako_blanc.png", lim.size)


if __name__ == "__main__":
    main()
