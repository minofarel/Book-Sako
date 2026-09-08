# Carte des flux Sako (web)

Composant web **responsive et animé** représentant le réseau de transferts
Sako : la diaspora (Amérique du Nord, Londres, Paris, Bruxelles, Milan, Madrid,
Dubaï) envoie de l'argent vers **11 pays** d'Afrique de l'Ouest et centrale —
**Sénégal, Mali, Burkina Faso, Côte d'Ivoire, Ghana, Togo, Bénin, Niger,
Nigeria, Tchad, Cameroun**.

Il remplace l'ancien **GIF** statique par un rendu vectoriel :

- le **Ghana** apparaît désormais sur la carte (mis en valeur, accent champagne) ;
- les **lignes de flux** sont reprises en animation — tracé guide permanent +
  comètes champagne qui remontent de la ville d'envoi vers le pays, vitesse
  visuelle homogène, halo d'arrivée sur chaque pays desservi ;
- **responsive** : le SVG s'adapte via `viewBox` ; sur mobile la carte défile
  horizontalement, la légende se replie ; `prefers-reduced-motion` respecté.

Identité respectée : noir / blanc / gris chauds + un seul accent **champagne**
(réservé au flux vivant), typographie **Sora** (Google Fonts, repli système),
thème **clair et sombre** automatique.

## Fichiers

| Fichier | Rôle |
|---|---|
| `diaspora-map.html` | **Livrable** : page HTML autonome (aucune dépendance de carto au runtime, animation 100 % CSS). |
| `diaspora-map.artifact.html` | Même contenu sans l'enveloppe `<html>`/`<head>` — pour publication en Artifact Claude. |
| `build_map.py` | Générateur : projette la géométrie (Web Mercator) en chemins SVG, calcule libellés, origines, arcs. |
| `build_map_html.py` | Gabarit HTML/CSS + assemblage du SVG. |
| `countries.geo.json` | Géométrie source des pays (Natural Earth, domaine public, via `johan/world.geo.json`). |

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
