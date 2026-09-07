"""
Common rendering utilities for the Sako teaser pipeline.

Everything image-space is numpy float32 (H, W, 3) in 0..255 until the very
last step (finalize -> uint8). Per-pixel work is vectorised; Python loops are
only tolerated per-note (audio) or per-particle.
"""
import functools
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter

# --------------------------------------------------------------------------
# Palette (strict black / white / grey, one discreet warm "champagne" accent)
# --------------------------------------------------------------------------
BLACK      = (5, 5, 5)
NEAR_BLACK = (17, 17, 17)
WHITE      = (255, 255, 255)
CHAMPAGNE  = np.array([88, 78, 62], dtype=np.float32)   # additive warm pass only

FONT_PATH = "assets/Sora.ttf"


# --------------------------------------------------------------------------
# Fonts : one cached instance per (size, weight) of the Sora variable font.
# --------------------------------------------------------------------------
@functools.lru_cache(maxsize=256)
def font(size, weight="Bold"):
    f = ImageFont.truetype(FONT_PATH, int(size))
    try:
        f.set_variation_by_name(weight)
    except Exception:
        pass
    return f


def text_width(draw, s, fnt, tracking=0):
    """Total advance width of a string drawn char-by-char with `tracking` px."""
    w = 0
    for ch in s:
        bb = draw.textbbox((0, 0), ch, font=fnt)
        w += (bb[2] - bb[0]) if ch != " " else fnt.getlength(" ")
        w += tracking
    if s:
        w -= tracking
    return w


def draw_tracked(draw, xy, s, fnt, fill, tracking=0, anchor="l"):
    """
    Draw a string char-by-char with manual letter tracking.
    anchor: 'l' left, 'r' right (x is right edge -> x = x - total_width),
            'c' centre (x is centre).
    Uses advance widths so spacing stays even. Returns (x0, x1).
    """
    x, y = xy
    total = text_width(draw, s, fnt, tracking)
    if anchor == "r":
        x = x - total
    elif anchor == "c":
        x = x - total / 2.0
    x0 = x
    for ch in s:
        if ch == " ":
            x += fnt.getlength(" ") + tracking
            continue
        # anchor each glyph at its left side bearing so kerning stays even
        bb = draw.textbbox((0, 0), ch, font=fnt)
        draw.text((x - bb[0], y), ch, font=fnt, fill=fill)
        x += (bb[2] - bb[0]) + tracking
    return x0, x0 + total


# --------------------------------------------------------------------------
# Grain (silver-halide) : 4 precomputed gaussian noise fields, rotated per frame
# --------------------------------------------------------------------------
@functools.lru_cache(maxsize=8)
def _grain_bank(h, w, sigma=6.0, seed=7):
    rng = np.random.default_rng(seed)
    return [rng.normal(0.0, sigma, (h, w, 1)).astype(np.float32) for _ in range(4)]


def add_grain(img, frame_idx, sigma=6.0, amount=1.0):
    h, w = img.shape[:2]
    bank = _grain_bank(h, w, sigma)
    return img + bank[frame_idx & 3] * amount


# --------------------------------------------------------------------------
# Vignette : soft radial multiplier (0.5 .. 1.0)
# --------------------------------------------------------------------------
@functools.lru_cache(maxsize=8)
def vignette_mask(h, w, strength=0.5, radius=0.95):
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    cx, cy = w / 2.0, h / 2.0
    d = np.sqrt(((xx - cx) / (w / 2.0)) ** 2 + ((yy - cy) / (h / 2.0)) ** 2)
    m = 1.0 - strength * np.clip((d - radius * 0.35) / (1.25 - radius * 0.35), 0, 1) ** 1.6
    return np.clip(m, 1.0 - strength, 1.0)[:, :, None].astype(np.float32)


def apply_vignette(img, strength=0.42):
    h, w = img.shape[:2]
    return img * vignette_mask(h, w, strength)


# --------------------------------------------------------------------------
# Frame finalisation : clip -> uint8 (call once, at the very end)
# --------------------------------------------------------------------------
def finalize(img):
    return np.clip(img, 0, 255).astype(np.uint8)


# --------------------------------------------------------------------------
# Homography helpers
# --------------------------------------------------------------------------
def perspective_coeffs(src_quad, dst_quad):
    """
    8 coeffs for Image.transform(size, Image.PERSPECTIVE, coeffs): the source
    quad ends up at the destination quad in the OUTPUT image. PIL maps output
    -> input, so we solve find_coeffs(dst, src).
    Quads: list of 4 (x, y) as TL, TR, BR, BL.
    """
    matrix = []
    for (dx, dy), (sx, sy) in zip(dst_quad, src_quad):
        matrix.append([dx, dy, 1, 0, 0, 0, -sx * dx, -sx * dy])
        matrix.append([0, 0, 0, dx, dy, 1, -sy * dx, -sy * dy])
    A = np.array(matrix, dtype=np.float64)
    B = np.array(src_quad, dtype=np.float64).reshape(8)
    res = np.linalg.solve(A, B)
    return res.reshape(8)


def homography_matrix(src_quad, dst_quad):
    """3x3 forward matrix mapping src -> dst, for projecting points."""
    A = []
    B = []
    for (sx, sy), (dx, dy) in zip(src_quad, dst_quad):
        A.append([sx, sy, 1, 0, 0, 0, -dx * sx, -dx * sy])
        B.append(dx)
        A.append([0, 0, 0, sx, sy, 1, -dy * sx, -dy * sy])
        B.append(dy)
    A = np.array(A, dtype=np.float64)
    B = np.array(B, dtype=np.float64)
    h = np.linalg.solve(A, B)
    return np.array([[h[0], h[1], h[2]],
                     [h[3], h[4], h[5]],
                     [h[6], h[7], 1.0]], dtype=np.float64)


def project(H, pts):
    """Project Nx2 points through 3x3 homography H. Returns Nx2."""
    pts = np.asarray(pts, dtype=np.float64)
    ones = np.ones((pts.shape[0], 1))
    P = np.hstack([pts, ones]) @ H.T
    return P[:, :2] / P[:, 2:3]


def warp_card(card_img, size, dst_quad, resample=Image.BICUBIC):
    """
    Warp a PIL card so its (0,0)-(W,0)-(W,H)-(0,H) corners land on dst_quad
    inside an output canvas of `size`. Returns RGBA PIL image.
    """
    W, H = card_img.size
    src_quad = [(0, 0), (W, 0), (W, H), (0, H)]
    coeffs = perspective_coeffs(src_quad, dst_quad)
    if card_img.mode != "RGBA":
        card_img = card_img.convert("RGBA")
    return card_img.transform(size, Image.PERSPECTIVE, coeffs, resample)


# --------------------------------------------------------------------------
# Glow sprite : radial falloff, additive. Cached by (radius, power).
# --------------------------------------------------------------------------
@functools.lru_cache(maxsize=64)
def glow_sprite(radius, power=2.0):
    r = int(radius)
    size = 2 * r + 1
    yy, xx = np.mgrid[0:size, 0:size].astype(np.float32)
    d = np.sqrt((xx - r) ** 2 + (yy - r) ** 2) / r
    g = np.clip(1.0 - d, 0.0, 1.0) ** power
    return g.astype(np.float32)


def add_mask(mask, sprite, cx, cy, intensity=1.0):
    """Additively stamp a single-channel sprite into a 2D float mask."""
    h, w = mask.shape
    sh, sw = sprite.shape
    r = sh // 2
    x0, y0 = int(round(cx)) - r, int(round(cy)) - r
    ix0, iy0 = max(0, x0), max(0, y0)
    ix1, iy1 = min(w, x0 + sw), min(h, y0 + sh)
    if ix0 >= ix1 or iy0 >= iy1:
        return mask
    sx0, sy0 = ix0 - x0, iy0 - y0
    mask[iy0:iy1, ix0:ix1] += sprite[sy0:sy0 + (iy1 - iy0),
                                     sx0:sx0 + (ix1 - ix0)] * intensity
    return mask


def add_sprite(img, sprite, cx, cy, color, intensity=1.0):
    """Additively blend a single-channel sprite tinted `color` at (cx, cy)."""
    h, w = img.shape[:2]
    sh, sw = sprite.shape
    r = sh // 2
    x0, y0 = int(round(cx)) - r, int(round(cy)) - r
    x1, y1 = x0 + sw, y0 + sh
    ix0, iy0 = max(0, x0), max(0, y0)
    ix1, iy1 = min(w, x1), min(h, y1)
    if ix0 >= ix1 or iy0 >= iy1:
        return img
    sx0, sy0 = ix0 - x0, iy0 - y0
    sub = sprite[sy0:sy0 + (iy1 - iy0), sx0:sx0 + (ix1 - ix0), None]
    col = np.asarray(color, dtype=np.float32)
    img[iy0:iy1, ix0:ix1] += sub * col * intensity
    return img


# --------------------------------------------------------------------------
# Gradients
# --------------------------------------------------------------------------
def linear_gradient(h, w, c0, c1, angle_deg=90.0):
    """Linear gradient across the frame at `angle_deg` (0 = left->right)."""
    ang = np.deg2rad(angle_deg)
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    t = xx * np.cos(ang) + yy * np.sin(ang)
    t = (t - t.min()) / (np.ptp(t) + 1e-6)
    c0 = np.asarray(c0, np.float32)
    c1 = np.asarray(c1, np.float32)
    return (c0[None, None, :] * (1 - t[:, :, None]) + c1[None, None, :] * t[:, :, None])


def diag_coord(h, w, theta):
    """Precomputed diagonal coordinate d = x cos + y sin, normalised to 0..1."""
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    d = xx * np.cos(theta) + yy * np.sin(theta)
    return (d - d.min()) / (np.ptp(d) + 1e-6)


def light_band(dcoord, center, width):
    """Gaussian light band exp(-((d-c)/w)^2) over a diagonal coord map."""
    return np.exp(-(((dcoord - center) / max(width, 1e-4)) ** 2)).astype(np.float32)


# --------------------------------------------------------------------------
# small helpers
# --------------------------------------------------------------------------
def smoothstep(t):
    t = np.clip(t, 0.0, 1.0)
    return t * t * (3 - 2 * t)


def ease_out(t, p=3.0):
    return 1.0 - (1.0 - np.clip(t, 0, 1)) ** p


def ease_in(t, p=3.0):
    return np.clip(t, 0, 1) ** p


def lerp(a, b, t):
    return a + (b - a) * t


def pil_blur(np_img, radius):
    """GaussianBlur via PIL on a float image (returns float32)."""
    im = Image.fromarray(finalize(np_img))
    im = im.filter(ImageFilter.GaussianBlur(radius))
    return np.asarray(im, dtype=np.float32)
