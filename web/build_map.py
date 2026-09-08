#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
build_map.py — Génère `web/diaspora-map.html`, une carte SVG responsive et
animée du réseau de transferts Sako (diaspora -> pays d'origine).

Tout est pré-projeté en Python (Web Mercator) vers des chemins SVG statiques :
le HTML livré est autonome (aucune librairie de carto au runtime, animation
100 % CSS). On charge la police Sora depuis Google Fonts avec repli système.

Usage :
    python3 web/build_map.py [chemin_geojson] [chemin_sortie_html]

Source géométrie : web/countries.geo.json (world.geo.json, © Natural Earth,
domaine public, via johan/world.geo.json).
"""
import json
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))

# ---------------------------------------------------------------------------
# Fenêtre géographique (lon/lat) et projection Web Mercator
# ---------------------------------------------------------------------------
LON0, LON1 = -38.0, 60.0        # ouest (Atlantique) -> est (Golfe)
LAT0, LAT1 = -4.0, 54.0         # sud (équateur) -> nord (Europe)
TARGET_W = 1720.0               # largeur du viewBox en unités SVG


def merc_x(lon):
    return math.radians(lon)


def merc_y(lat):
    lat = max(min(lat, 85.0), -85.0)
    return math.log(math.tan(math.pi / 4 + math.radians(lat) / 2))


X0, X1 = merc_x(LON0), merc_x(LON1)
Y0, Y1 = merc_y(LAT0), merc_y(LAT1)
K = TARGET_W / (X1 - X0)                     # échelle unique (conforme)
VIEW_W = round((X1 - X0) * K)
VIEW_H = round((Y1 - Y0) * K)


def project(lon, lat):
    """(lon, lat) degrés -> (x, y) unités SVG (y vers le bas)."""
    x = (merc_x(lon) - X0) * K
    y = (Y1 - merc_y(lat)) * K               # inversion nord/haut
    return x, y


# ---------------------------------------------------------------------------
# Géométrie -> chemins SVG (simplifiés)
# ---------------------------------------------------------------------------
def _iter_polys(geom):
    """Renvoie une liste de polygones ; chaque polygone = liste d'anneaux."""
    t = geom["type"]
    if t == "Polygon":
        return [geom["coordinates"]]
    if t == "MultiPolygon":
        return geom["coordinates"]
    return []


def _rdp(pts, eps):
    """Ramer-Douglas-Peucker sur une polyligne OUVERTE (itératif)."""
    n = len(pts)
    if n < 3:
        return pts[:]
    keep = [False] * n
    keep[0] = keep[-1] = True
    stack = [(0, n - 1)]
    while stack:
        a, b = stack.pop()
        if b <= a + 1:
            continue
        x0, y0 = pts[a]
        x1, y1 = pts[b]
        dx, dy = x1 - x0, y1 - y0
        seg = math.hypot(dx, dy) or 1e-9
        dmax, idx = 0.0, -1
        for i in range(a + 1, b):
            px, py = pts[i]
            d = abs(dy * px - dx * py + x1 * y0 - y1 * x0) / seg
            if d > dmax:
                dmax, idx = d, i
        if dmax > eps and idx != -1:
            keep[idx] = True
            stack.append((a, idx))
            stack.append((idx, b))
    return [pts[i] for i in range(n) if keep[i]]


def _rdp_ring(pts, eps):
    """RDP sur un anneau FERMÉ : coupe au point le plus éloigné du départ
    puis simplifie chaque moitié (évite la dégénérescence départ==fin)."""
    if len(pts) > 1 and pts[0] == pts[-1]:
        pts = pts[:-1]
    n = len(pts)
    if n < 4:
        return pts
    x0, y0 = pts[0]
    far, fd = 0, -1.0
    for i in range(1, n):
        dd = (pts[i][0] - x0) ** 2 + (pts[i][1] - y0) ** 2
        if dd > fd:
            fd, far = dd, i
    a = _rdp(pts[:far + 1], eps)
    b = _rdp(pts[far:] + [pts[0]], eps)
    return a[:-1] + b[:-1]


def ring_to_svg(ring, quant, eps):
    """Anneau [[lon,lat],...] -> segment 'M.. L.. Z' projeté et simplifié."""
    pts = []
    last = None
    for lon, lat in ring:
        x, y = project(lon, lat)
        p = (x, y)
        if last is None or abs(x - last[0]) > 1e-6 or abs(y - last[1]) > 1e-6:
            pts.append(p)
            last = p
    if len(pts) < 4:
        return ""
    if eps > 0:
        pts = _rdp_ring(pts, eps)
        if len(pts) < 4:
            return ""
    fmt = f"%.{quant}f" if quant > 0 else "%.0f"
    d = "M" + " L".join(f"{fmt % x},{fmt % y}" for x, y in pts) + "Z"
    return d


def geom_to_path(geom, quant=1, eps=0.7):
    parts = []
    for poly in _iter_polys(geom):
        for ring in poly:
            seg = ring_to_svg(ring, quant, eps)
            if seg:
                parts.append(seg)
    return "".join(parts)


def feature_bbox(geom):
    xs, ys = [], []
    for poly in _iter_polys(geom):
        for ring in poly:
            for lon, lat in ring:
                xs.append(lon)
                ys.append(lat)
    if not xs:
        return None
    return min(xs), min(ys), max(xs), max(ys)


def largest_ring(geom):
    best, best_area = None, -1.0
    for poly in _iter_polys(geom):
        if not poly:
            continue
        ring = poly[0]
        area = abs(_shoelace(ring))
        if area > best_area:
            best, best_area = ring, area
    return best


def _shoelace(ring):
    s = 0.0
    n = len(ring)
    for i in range(n - 1):
        x1, y1 = ring[i]
        x2, y2 = ring[i + 1]
        s += x1 * y2 - x2 * y1
    return s / 2.0


def centroid_lonlat(ring):
    """Centroïde surfacique d'un anneau (lon/lat)."""
    a = _shoelace(ring)
    if abs(a) < 1e-12:
        lons = [p[0] for p in ring]
        lats = [p[1] for p in ring]
        return sum(lons) / len(lons), sum(lats) / len(lats)
    cx = cy = 0.0
    n = len(ring)
    for i in range(n - 1):
        x1, y1 = ring[i]
        x2, y2 = ring[i + 1]
        cross = x1 * y2 - x2 * y1
        cx += (x1 + x2) * cross
        cy += (y1 + y2) * cross
    cx /= (6 * a)
    cy /= (6 * a)
    return cx, cy


# ---------------------------------------------------------------------------
# Pays mis en avant (marché Sako) — Ghana inclus
# ---------------------------------------------------------------------------
HIGHLIGHT = {
    "SEN": "Sénégal",
    "MLI": "Mali",
    "BFA": "Burkina Faso",
    "CIV": "Côte d'Ivoire",
    "GHA": "Ghana",
    "TGO": "Togo",
    "BEN": "Bénin",
    "NER": "Niger",
    "NGA": "Nigeria",
    "TCD": "Tchad",
    "CMR": "Cameroun",
}

# Ajustements manuels des ancres de label (dx, dy en unités SVG) pour éviter
# les chevauchements dans les pays d'intérieur.
LABEL_NUDGE = {
    "CIV": (-8, -28),    # Côte d'Ivoire : remontée dans le corps du pays
    "BFA": (0, 0),
    "SEN": (-4, 2),
    "NGA": (8, 8),
    "CMR": (12, 6),
    "TCD": (-4, 22),
    "NER": (12, -6),
    "MLI": (-6, -16),
}

# Petits pays côtiers : libellé posé dans le golfe de Guinée + ligne de rappel.
# iso -> (label_x, label_y, attach_x, attach_y)  en unités SVG.
GULF_LABELS = {
    "GHA": (600, 1150, 649, 1016),
    "TGO": (696, 1150, 686, 1004),
    "BEN": (790, 1150, 709, 980),
}

# ---------------------------------------------------------------------------
# Points d'origine (diaspora) et destinations
# ---------------------------------------------------------------------------
# name, lon, lat, label anchor side ("l"/"r"/"t"/"b"), destination ISO3
ORIGINS = [
    ("Londres",     -0.13, 51.51, "t", "GHA"),
    ("Paris",        2.35, 48.86, "t", "MLI"),
    ("Bruxelles",    4.35, 50.85, "r", "CMR"),
    ("Milan",        9.19, 45.46, "r", "NGA"),
    ("Madrid",      -3.70, 40.42, "l", "CIV"),
    ("Dubaï",       55.27, 25.20, "l", "TCD"),
]
# Origine transatlantique : entre par le bord gauche (hors cadre réel).
ATLANTIC = ("Amérique du Nord", -74.0, 40.7, "SEN")

# Point de réception au sein d'un pays (léger décalage vs label si besoin).
DEST_NUDGE = {
    "SEN": (10, 6),
    "MLI": (0, 8),
    "CIV": (0, -2),
    "GHA": (0, -4),
    "NGA": (-6, -6),
    "CMR": (-6, -6),
    "TCD": (-6, 0),
}


def arc_points(x1, y1, x2, y2, bulge=0.22):
    """Points de contrôle d'un cubique bombé vers le haut de l'écran."""
    dx, dy = x2 - x1, y2 - y1
    dist = math.hypot(dx, dy) or 1.0
    mx, my = (x1 + x2) / 2, (y1 + y2) / 2
    nx, ny = -dy / dist, dx / dist                 # normale
    if ny > 0:                                     # vers le haut (y plus petit)
        nx, ny = -nx, -ny
    off = bulge * dist
    cx, cy = mx + nx * off, my + ny * off
    c1 = (x1 + (cx - x1) * 0.55, y1 + (cy - y1) * 0.55)
    c2 = (x2 + (cx - x2) * 0.55, y2 + (cy - y2) * 0.55)
    return (x1, y1), c1, c2, (x2, y2)


def bezier_at(pts, t):
    (x0, y0), (x1, y1), (x2, y2), (x3, y3) = pts
    u = 1 - t
    a, b, c, d = u * u * u, 3 * u * u * t, 3 * u * t * t, t * t * t
    return (a * x0 + b * x1 + c * x2 + d * x3,
            a * y0 + b * y1 + c * y2 + d * y3)


def bezier_len(pts, n=48):
    prev = bezier_at(pts, 0.0)
    total = 0.0
    for i in range(1, n + 1):
        cur = bezier_at(pts, i / n)
        total += math.hypot(cur[0] - prev[0], cur[1] - prev[1])
        prev = cur
    return total


def bezier_entry_x(pts, x_target, n=200):
    """Premier point (en partant de l'origine) où la courbe atteint x_target."""
    prev = bezier_at(pts, 0.0)
    for i in range(1, n + 1):
        cur = bezier_at(pts, i / n)
        if (prev[0] - x_target) * (cur[0] - x_target) <= 0:
            return cur
        prev = cur
    return bezier_at(pts, 0.5)


def arc_d(pts):
    (x0, y0), (x1, y1), (x2, y2), (x3, y3) = pts
    return (f"M{x0:.1f},{y0:.1f} C{x1:.1f},{y1:.1f} "
            f"{x2:.1f},{y2:.1f} {x3:.1f},{y3:.1f}")


def build():
    src = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "countries.geo.json")
    out = sys.argv[2] if len(sys.argv) > 2 else os.path.join(HERE, "diaspora-map.html")
    data = json.load(open(src, encoding="utf-8"))

    # -- fenêtre élargie pour filtrer les pays d'arrière-plan --------------
    pad = 12.0
    wxmin, wxmax = LON0 - pad, LON1 + pad
    wymin, wymax = LAT0 - pad, LAT1 + pad

    bg_paths = []
    hi = {}          # iso -> {path, label, anchor(x,y)}
    for f in data["features"]:
        iso = f.get("id")
        geom = f["geometry"]
        bbox = feature_bbox(geom)
        if not bbox:
            continue
        bxmin, bymin, bxmax, bymax = bbox
        if iso in HIGHLIGHT:
            path = geom_to_path(geom, quant=1, eps=0.6)
            ring = largest_ring(geom)
            clon, clat = centroid_lonlat(ring)
            ax, ay = project(clon, clat)
            entry = {
                "path": path,
                "label": HIGHLIGHT[iso],
                "cx": round(ax, 1),
                "cy": round(ay, 1),
            }
            if iso in GULF_LABELS:
                lx, ly, tx, ty = GULF_LABELS[iso]
                entry.update({"lx": lx, "ly": ly, "small": True,
                              "leader": [tx, ty]})
            else:
                ndx, ndy = LABEL_NUDGE.get(iso, (0, 0))
                entry.update({"lx": round(ax + ndx, 1),
                              "ly": round(ay + ndy, 1)})
            hi[iso] = entry
        else:
            # arrière-plan : seulement si visible dans la fenêtre
            if bxmax < wxmin or bxmin > wxmax or bymax < wymin or bymin > wymax:
                continue
            path = geom_to_path(geom, quant=0, eps=1.3)
            if path:
                bg_paths.append(path)

    # -- réception (destinations) -----------------------------------------
    def dest_point(iso):
        c = hi[iso]
        dx, dy = DEST_NUDGE.get(iso, (0, 0))
        return c["cx"] + dx, c["cy"] + dy

    arcs = []
    origins_render = []
    SPEED = 300.0          # unités SVG / s -> vitesse visuelle homogène
    STAGGER = 0.85         # décalage entre départs de comètes

    # origines terrestres
    for i, (name, lon, lat, side, dest) in enumerate(ORIGINS):
        ox, oy = project(lon, lat)
        dx, dy = dest_point(dest)
        pts = arc_points(ox, oy, dx, dy, bulge=0.26)
        dur = max(2.6, min(6.5, bezier_len(pts) / SPEED))
        arcs.append({
            "d": arc_d(pts),
            "delay": round(i * STAGGER, 2),
            "dur": round(dur, 2),
            "src": name, "dest": dest,
            "ddx": round(dx, 1), "ddy": round(dy, 1),
        })
        origins_render.append({
            "name": name, "x": round(ox, 1), "y": round(oy, 1), "side": side,
        })

    # origine transatlantique : départ hors cadre à gauche, entrée par le bord
    aname, alon, alat, adest = ATLANTIC
    ox, oy = project(alon, alat)          # x très négatif -> hors cadre
    dx, dy = dest_point(adest)
    apts = arc_points(ox, oy, dx, dy, bulge=0.14)
    ex, ey = bezier_entry_x(apts, 40.0)   # point d'entrée visible (x~40)
    adur = max(2.6, min(6.5, bezier_len(apts) / SPEED))
    arcs.append({
        "d": arc_d(apts),
        "delay": round(len(ORIGINS) * STAGGER, 2),
        "dur": round(adur, 2),
        "src": aname, "dest": adest,
        "ddx": round(dx, 1), "ddy": round(dy, 1),
    })
    atlantic = {"label": aname, "ex": round(ex, 1), "ey": round(ey, 1)}

    # point de réception unique par pays (pour les halos)
    dests = {}
    for a in arcs:
        dests[a["dest"]] = {"x": a["ddx"], "y": a["ddy"],
                            "delay": a["delay"], "dur": a["dur"]}

    payload = {
        "viewW": VIEW_W, "viewH": VIEW_H,
        "bg": bg_paths,
        "hi": hi,
        "arcs": arcs,
        "origins": origins_render,
        "atlantic": atlantic,
        "dests": dests,
    }
    rendered = render_html(payload)
    with open(out, "w", encoding="utf-8") as fh:
        fh.write(rendered["standalone"])
    # variante « contenu seul » pour publication en Artifact
    art = os.path.join(HERE, "diaspora-map.artifact.html")
    with open(art, "w", encoding="utf-8") as fh:
        fh.write(rendered["artifact"])

    # export JSON (à consommer dans un composant maison React/JS)
    data = json_payload(payload)
    djson = os.path.join(HERE, "diaspora-map.data.json")
    with open(djson, "w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False, separators=(",", ":"))
    print(f"[ok] {out}  ({len(rendered['standalone'])//1024} KB)  "
          f"viewBox=0 0 {VIEW_W} {VIEW_H}  pays={len(hi)}  "
          f"fond={len(bg_paths)}  arcs={len(arcs)}")
    print(f"[ok] {djson}  ({os.path.getsize(djson)//1024} KB)")


def _origin_label(o):
    """Position/ancrage du libellé d'une ville selon son côté."""
    x, y, side = o["x"], o["y"], o["side"]
    if side == "t":
        return {"x": x, "y": round(y - 22, 1), "anchor": "middle"}
    if side == "b":
        return {"x": x, "y": round(y + 34, 1), "anchor": "middle"}
    if side == "r":
        return {"x": round(x + 20, 1), "y": round(y + 7, 1), "anchor": "start"}
    return {"x": round(x - 20, 1), "y": round(y + 7, 1), "anchor": "end"}


def json_payload(p):
    """Transforme le payload interne en JSON auto-documenté et stable."""
    served = []
    for iso, c in p["hi"].items():
        item = {
            "iso": iso,
            "name": c["label"],
            "path": c["path"],
            "label": {"x": c["lx"], "y": c["ly"], "anchor": "middle",
                      "small": bool(c.get("small"))},
        }
        if "leader" in c:
            tx, ty = c["leader"]
            item["leader"] = {"x1": c["lx"], "y1": round(c["ly"] - 20, 1),
                              "x2": tx, "y2": ty}
        served.append(item)

    origins = []
    for o in p["origins"]:
        origins.append({"name": o["name"], "x": o["x"], "y": o["y"],
                        "offMap": False, "label": _origin_label(o)})
    atl = p["atlantic"]
    origins.append({
        "name": atl["label"], "x": atl["ex"], "y": atl["ey"], "offMap": True,
        "label": {"x": round(atl["ex"] + 20, 1), "y": round(atl["ey"] + 7, 1),
                  "anchor": "start"},
    })

    flows = []
    for a in p["arcs"]:
        flows.append({
            "from": a["src"], "to": a["dest"], "path": a["d"],
            "durationSec": a["dur"], "delaySec": a["delay"],
            "arrival": {"x": a["ddx"], "y": a["ddy"]},
        })

    return {
        "$schema": "sako-diaspora-map/v1",
        "meta": {
            "description": "Carte des flux de transferts Sako : diaspora -> "
                           "pays d'origine. Coordonnées déjà projetées en "
                           "unités du viewBox (Web Mercator).",
            "projection": "web-mercator",
            "window": {"lon": [LON0, LON1], "lat": [LAT0, LAT1]},
            "accent": "#B48C42",
            "servedCount": len(served),
        },
        "viewBox": {"width": VIEW_W, "height": VIEW_H},
        "background": p["bg"],
        "served": served,
        "origins": origins,
        "flows": flows,
    }


# render_html défini dans build_map_html.py (importé) pour garder ce
# fichier lisible ; fallback inline si l'import échoue.
try:
    from build_map_html import render_html          # type: ignore
except Exception:  # pragma: no cover
    sys.path.insert(0, HERE)
    from build_map_html import render_html           # type: ignore


if __name__ == "__main__":
    build()
