# Carte des flux Sako (web)

Composant web **responsive et animé** représentant le réseau de transferts
Sako : la diaspora (Amérique du Nord, Londres, Paris, Bruxelles, Milan, Madrid,
Dubaï) envoie de l'argent vers **11 pays** d'Afrique de l'Ouest et centrale —
**Sénégal, Mali, Burkina Faso, Côte d'Ivoire, Ghana, Togo, Bénin, Niger,
Nigeria, Tchad, Cameroun**.

Il remplace l'ancien **GIF** statique par un rendu vectoriel, pensé pour être
posé **tel quel dans une section de landing page** (carte seule, sans titre ni
légende) :

- le **Ghana** apparaît désormais sur la carte (mis en valeur, accent champagne) ;
- les **lignes de flux** sont reprises en animation — tracé guide permanent +
  comètes champagne qui remontent de la ville d'envoi vers le pays, vitesse
  visuelle homogène, halo d'arrivée sur chaque pays desservi ;
- **responsive** : le SVG s'adapte via `viewBox` ; sur mobile la carte défile
  horizontalement (dégradé de bord comme indice) ; `prefers-reduced-motion`
  respecté.

Identité respectée : noir / blanc / gris chauds + un seul accent **champagne**
(réservé au flux vivant), typographie **Sora** (Google Fonts, repli système),
**thème clair unique** (pas de mode sombre), fond transparent pour s'insérer
dans n'importe quelle section.

## Fichiers

| Fichier | Rôle |
|---|---|
| `diaspora-map.html` | **Livrable** : page HTML autonome (aucune dépendance de carto au runtime, animation 100 % CSS). |
| `diaspora-map.artifact.html` | Même contenu sans l'enveloppe `<html>`/`<head>` — pour publication en Artifact Claude. |
| `diaspora-map.data.json` | **Données de la carte** (déjà projetées) à consommer dans un composant maison. |
| `react/SakoMap.jsx` + `react/sako-map.css` | Composant React prêt à l'emploi qui rend le JSON. |
| `build_map.py` | Générateur : projette la géométrie (Web Mercator) en chemins SVG, calcule libellés, origines, arcs. |
| `build_map_html.py` | Gabarit HTML/CSS + assemblage du SVG. |
| `countries.geo.json` | Géométrie source des pays (Natural Earth, domaine public, via `johan/world.geo.json`). |

## Données JSON (`diaspora-map.data.json`)

Toutes les coordonnées sont **déjà projetées** dans le repère du `viewBox`
(pas de calcul de carto côté client). Schéma :

```jsonc
{
  "viewBox": { "width": 1720, "height": 1201 },
  "meta": { "projection": "web-mercator", "accent": "#B48C42", "servedCount": 11, … },
  "background": [ "M… L… Z", … ],            // pays inactifs (gris) : chemins SVG
  "served": [                                 // 11 pays desservis (noir)
    {
      "iso": "GHA", "name": "Ghana",
      "path": "M… Z",                         // chemin SVG du pays
      "label": { "x": 600, "y": 1150, "anchor": "middle", "small": true },
      "leader": { "x1": 600, "y1": 1130, "x2": 649, "y2": 1016 }  // optionnel
    }, …
  ],
  "origins": [                                // villes d'envoi
    { "name": "Londres", "x": …, "y": …, "offMap": false,
      "label": { "x": …, "y": …, "anchor": "middle" } }, …
  ],
  "flows": [                                  // flux animés origine -> pays
    { "from": "Londres", "to": "GHA", "path": "M… C… ",
      "durationSec": 3.15, "delaySec": 0,
      "arrival": { "x": …, "y": … } }, …
  ]
}
```

Rendu : dessiner `background` (gris) puis `served` (noir), tracer chaque
`flows[].path` avec `pathLength="1"` et une comète animée (voir `react/sako-map.css`,
`@keyframes sk-comet`), en injectant `--dur`/`--delay` depuis
`durationSec`/`delaySec` ; poser un halo sur `flows[].arrival`, les points sur
`origins`, puis les libellés (`served[].label`, `origins[].label`) et les lignes
de rappel (`served[].leader`).

### React

```jsx
import SakoMap from "./react/SakoMap";   // importe le JSON + le CSS
export default () => <SakoMap />;
```

## Régénérer

```bash
python3 web/build_map.py
# -> web/diaspora-map.html  +  web/diaspora-map.artifact.html
```

Pour changer les pays desservis, les villes d'envoi ou leurs destinations,
éditer `HIGHLIGHT`, `ORIGINS` / `ATLANTIC` et `GULF_LABELS` dans
`web/build_map.py`, puis relancer la commande.

## Intégration

`diaspora-map.html` est autonome et peut être servi tel quel ou intégré en
`<iframe>`. Pour l'insérer directement dans une page existante, reprendre le
bloc `<main class="sako-map">…</main>` et le `<style>` associé (voir
`diaspora-map.artifact.html`) ; la seule ressource externe est la police Sora
depuis Google Fonts.
