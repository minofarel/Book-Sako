# -*- coding: utf-8 -*-
"""
Rendu HTML de la carte Sako. `render_html(payload)` renvoie
{"standalone": <document complet>, "artifact": <contenu seul>}.

Identité respectée : noir / blanc / gris chauds + un seul accent champagne
(réservé au flux vivant), typographie Sora. Carte pré-projetée -> SVG statique,
animation 100 % CSS, entièrement responsive.
"""
from html import escape

FONTS = ("https://fonts.googleapis.com/css2?"
         "family=Sora:wght@400;500;600;700;800&display=swap")


def _origin_label_xy(o):
    x, y, side = o["x"], o["y"], o["side"]
    if side == "t":
        return x, y - 22, "middle"
    if side == "b":
        return x, y + 34, "middle"
    if side == "r":
        return x + 20, y + 7, "start"
    return x - 20, y + 7, "end"          # "l"


def _svg(p):
    W, H = p["viewW"], p["viewH"]
    out = []
    a = out.append
    a(f'<svg class="sako-svg" viewBox="0 0 {W} {H}" '
      f'preserveAspectRatio="xMidYMid meet" role="img" '
      f'aria-label="Carte des transferts Sako : la diaspora (Amérique du Nord, '
      f'Londres, Paris, Bruxelles, Milan, Madrid, Dubaï) envoie de l\'argent vers '
      f'11 pays d\'Afrique de l\'Ouest et centrale, dont le Ghana.">')

    # défs
    a('<defs>'
      '<filter id="sk-glow" x="-40%" y="-40%" width="180%" height="180%">'
      '<feGaussianBlur stdDeviation="4" result="b"/>'
      '<feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge>'
      '</filter>'
      '</defs>')

    # océan / fond
    a(f'<rect class="sk-ocean" x="0" y="0" width="{W}" height="{H}"/>')

    # pays d'arrière-plan
    a('<g class="sk-bg">')
    for d in p["bg"]:
        a(f'<path d="{d}"/>')
    a('</g>')

    # pays desservis (Ghana inclus)
    a('<g class="sk-hi">')
    for iso, c in p["hi"].items():
        a(f'<path class="sk-country sk-{iso}" d="{c["path"]}"/>')
    a('</g>')

    # halo d'apparition du Ghana (accent ponctuel au chargement)
    gha = p["hi"].get("GHA")
    if gha:
        a(f'<path class="sk-ghana-flash" d="{gha["path"]}"/>')

    # arcs : guide permanent + comète (queue + cœur)
    a('<g class="sk-arcs">')
    for arc in p["arcs"]:
        st = f'--dur:{arc["dur"]}s;--delay:{arc["delay"]}s'
        a(f'<path class="sk-guide" d="{arc["d"]}" pathLength="1"/>')
        a(f'<path class="sk-flow sk-flow-tail" d="{arc["d"]}" '
          f'pathLength="1" style="{st}"/>')
        a(f'<path class="sk-flow sk-flow-core" d="{arc["d"]}" '
          f'pathLength="1" style="{st}"/>')
    a('</g>')

    # points de réception (halo d'arrivée + marqueur)
    a('<g class="sk-dests">')
    for iso, dd in p["dests"].items():
        st = f'--dur:{dd["dur"]}s;--delay:{dd["delay"]}s'
        a(f'<circle class="sk-land-pulse" cx="{dd["x"]}" cy="{dd["y"]}" '
          f'r="10" style="{st}"/>')
        a(f'<circle class="sk-dest-ring" cx="{dd["x"]}" cy="{dd["y"]}" r="9"/>')
        a(f'<circle class="sk-dest-dot" cx="{dd["x"]}" cy="{dd["y"]}" r="4.2"/>')
    a('</g>')

    # origines (villes d'envoi)
    a('<g class="sk-origins">')
    origins = list(p["origins"])
    atl = p["atlantic"]
    origins_all = origins + [{"name": atl["label"], "x": atl["ex"],
                              "y": atl["ey"], "side": "r"}]
    for o in origins_all:
        a(f'<circle class="sk-origin-breathe" cx="{o["x"]}" cy="{o["y"]}" '
          f'r="7"/>')
        a(f'<circle class="sk-origin-dot" cx="{o["x"]}" cy="{o["y"]}" r="5"/>')
    a('</g>')

    # libellés des villes
    a('<g class="sk-city-labels">')
    for o in origins_all:
        lx, ly, anchor = _origin_label_xy(o)
        a(f'<text class="sk-city" x="{lx}" y="{ly}" '
          f'text-anchor="{anchor}">{escape(o["name"])}</text>')
    a('</g>')

    # lignes de rappel (petits pays côtiers -> libellé dans le golfe)
    a('<g class="sk-leaders">')
    for iso, c in p["hi"].items():
        if "leader" in c:
            tx, ty = c["leader"]
            a(f'<line class="sk-leader" x1="{c["lx"]}" y1="{c["ly"] - 20}" '
              f'x2="{tx}" y2="{ty}"/>')
            a(f'<circle class="sk-leader-dot" cx="{tx}" cy="{ty}" r="3"/>')
    a('</g>')

    # libellés des pays
    a('<g class="sk-country-labels">')
    for iso, c in p["hi"].items():
        cls = "sk-clabel sk-small" if c.get("small") else "sk-clabel"
        a(f'<text class="{cls} sk-clabel-{iso}" x="{c["lx"]}" y="{c["ly"]}" '
          f'text-anchor="middle">{escape(c["label"])}</text>')
    a('</g>')

    a('</svg>')
    return "".join(out)


CSS = """
@import url('%FONTS%');

.sako-map,.sako-map *,.sako-map *::before,.sako-map *::after{box-sizing:border-box}

/* Composant carte — thème clair unique, pensé pour une landing page.
   Fond transparent : la carte s'intègre dans n'importe quelle section. */
.sako-map{
  --ocean:#E7E4DC; --land:#D7D3CA; --land-line:#EFEDE6;
  --served:#101012; --served-label:#F3F1EA;
  --city:#1A1913; --city-halo:#E7E4DC; --guide:#B7B2A6; --dot-ink:#16150F;
  --champagne:#B48C42; --champagne-soft:#CBAA6B; --champagne-hi:#DEC38A;
  --field-line:#E2DFD5; --vignette:rgba(46,40,28,.12);
  font-family:"Sora",system-ui,-apple-system,Segoe UI,Roboto,sans-serif;
  width:100%;
}

.sako-mapfield{
  position:relative;border-radius:18px;overflow:hidden;background:var(--ocean);
  border:1px solid var(--field-line);
}
.sako-scroll{overflow-x:auto;overflow-y:hidden;-webkit-overflow-scrolling:touch}
.sako-svg{display:block;width:100%;height:auto}
.sako-mapfield::after{                 /* vignette douce */
  content:"";position:absolute;inset:0;pointer-events:none;border-radius:18px;
  box-shadow:0 0 140px 40px var(--vignette) inset;
}
/* dégradé de bord (indice de défilement sur mobile, sans texte) */
.sako-fade{display:none;position:absolute;top:0;right:0;bottom:0;width:44px;
  pointer-events:none;
  background:linear-gradient(90deg,transparent,var(--ocean));}

/* --- géométrie de la carte --- */
.sk-ocean{fill:var(--ocean)}
.sk-bg path{fill:var(--land);stroke:var(--land-line);stroke-width:.9;
  vector-effect:non-scaling-stroke}
.sk-hi .sk-country{fill:var(--served);stroke:var(--ocean);stroke-width:1.4;
  stroke-linejoin:round;vector-effect:non-scaling-stroke}

/* --- arcs / flux --- */
.sk-guide{fill:none;stroke:var(--guide);stroke-width:1.2;opacity:.5;
  vector-effect:non-scaling-stroke;stroke-linecap:round}
.sk-flow{fill:none;vector-effect:non-scaling-stroke;stroke-linecap:round;
  animation:sk-comet var(--dur,4s) linear var(--delay,0s) infinite}
.sk-flow-core{stroke:var(--champagne-hi);stroke-width:2.6;
  stroke-dasharray:.11 1.5;filter:url(#sk-glow)}
.sk-flow-tail{stroke:var(--champagne);stroke-width:6;opacity:.22;
  stroke-dasharray:.24 1.5}
@keyframes sk-comet{from{stroke-dashoffset:0}to{stroke-dashoffset:-1.5}}

/* --- réception --- */
.sk-dest-dot{fill:var(--champagne)}
.sk-dest-ring{fill:none;stroke:var(--champagne);stroke-width:1.4;opacity:.55;
  vector-effect:non-scaling-stroke}
.sk-land-pulse{fill:none;stroke:var(--champagne-hi);stroke-width:2;
  transform-box:fill-box;transform-origin:center;vector-effect:non-scaling-stroke;
  animation:sk-land var(--dur,4s) ease-out var(--delay,0s) infinite}
@keyframes sk-land{
  0%,60%{opacity:0;transform:scale(.35)}
  63%{opacity:.75;transform:scale(.5)}
  100%{opacity:0;transform:scale(2.4)}
}

/* --- origines --- */
.sk-origin-dot{fill:var(--dot-ink)}
.sk-origin-breathe{fill:none;stroke:var(--champagne-soft);stroke-width:1.4;
  transform-box:fill-box;transform-origin:center;vector-effect:non-scaling-stroke;
  animation:sk-breathe 3.4s ease-out infinite}
@keyframes sk-breathe{
  0%{opacity:.6;transform:scale(.6)}
  70%,100%{opacity:0;transform:scale(2.1)}
}

/* --- Ghana : apparition ponctuelle --- */
.sk-ghana-flash{fill:none;stroke:var(--champagne-hi);stroke-width:2.4;
  vector-effect:non-scaling-stroke;opacity:0;
  animation:sk-ghana 3.2s ease-out .3s 1 forwards}
@keyframes sk-ghana{
  0%{opacity:0} 12%{opacity:1} 30%{opacity:.15}
  46%{opacity:.9} 70%{opacity:.1} 100%{opacity:0}
}

/* --- libellés --- */
.sk-clabel{
  fill:var(--served-label);stroke:var(--served);stroke-width:3.4;
  paint-order:stroke;stroke-linejoin:round;
  font-family:"Sora",sans-serif;font-weight:800;font-size:29px;
  letter-spacing:-.01em;
}
.sk-clabel.sk-small{font-size:25px;stroke-width:3}
.sk-clabel-GHA{fill:var(--champagne-hi);stroke:var(--served);stroke-width:3.8}
.sk-leader{stroke:var(--served);stroke-width:1.1;opacity:.42;
  vector-effect:non-scaling-stroke}
.sk-leader-dot{fill:var(--served)}
.sk-city{
  fill:var(--city);stroke:var(--city-halo);stroke-width:3.2;paint-order:stroke;
  stroke-linejoin:round;font-family:"Sora",sans-serif;font-weight:600;
  font-size:20px;letter-spacing:.01em;
}

@media (max-width:680px){
  .sako-scroll{overflow-x:auto}
  .sako-svg{width:640px;max-width:none}
  .sako-fade{display:block}
}

@media (prefers-reduced-motion:reduce){
  .sk-flow,.sk-land-pulse,.sk-origin-breathe,.sk-ghana-flash{animation:none}
  .sk-flow-core{stroke-dasharray:none;opacity:.85}
  .sk-flow-tail{display:none}
  .sk-land-pulse,.sk-ghana-flash{display:none}
}
"""


def render_html(p):
    css = CSS.replace("%FONTS%", FONTS)
    svg = _svg(p)
    title = "Réseau Sako"
    head = (f'<title>{title}</title>\n<style>{css}</style>')
    body = f"""<div class="sako-map">
  <div class="sako-mapfield">
    <div class="sako-scroll">
      {svg}
    </div>
    <div class="sako-fade"></div>
  </div>
</div>"""

    # enveloppe de démonstration (padding facultatif) — le composant à intégrer
    # reste le simple <div class="sako-map">…</div>.
    demo_open = ('<div style="max-width:1160px;margin:0 auto;'
                 'padding:clamp(14px,4vw,52px)">')
    artifact = head + "\n" + demo_open + "\n" + body + "\n</div>\n"
    standalone = (
        "<!doctype html>\n"
        '<html lang="fr">\n<head>\n<meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
        f"{head}\n"
        '<style>html,body{margin:0;background:#EFEDE8}</style>\n'
        "</head>\n<body>\n"
        f"{demo_open}\n{body}\n</div>\n"
        "</body>\n</html>\n"
    )
    return {"standalone": standalone, "artifact": artifact}
