# Sako — Teasers vidéo de lancement

Teasers vidéo MP4 pour le lancement de la carte **Sako** (fintech pour la
diaspora africaine — comptes, transferts, carte Visa Platinum). Tout est
généré **image par image en Python** (Pillow + numpy), streamé en frames
brutes vers **ffmpeg**, avec une **bande-son originale synthétisée** en numpy.
Aucun logiciel de montage, aucun navigateur, aucune musique préexistante.

## Livrables (`out/`)

| Fichier | Format | Durée | Description |
|---|---|---|---|
| `sako_teaser_9x16.mp4` | 1080×1920 | 29 s | Teaser principal (vertical) |
| `sako_teaser_16x9.mp4` | 1920×1080 | 29 s | Même montage, layouts recalculés (paysage) |
| `sako_teaser_pole_1x1.mp4` | 1080×1080 | 22 s | Déclinaison « pole position » (F1) |
| `sako_music.wav` / `sako_pole_music.wav` | 44.1 kHz stéréo | — | Bandes-son originales |
| `frames_*.jpg` | — | — | Grilles de validation extraites des MP4 livrés |

## Storyboard du teaser principal

1. **0–4 s · Gravure laser** — macro perspective de la carte, métal sombre, un
   stylet lumineux descend le motif (croix d'Agadez), les arêtes scintillent,
   une traînée persiste ; recul sur la carte entière, bande de lumière diagonale.
2. **4–9 s · Révélation par la lumière** — carte dressée dans le noir, une large
   bande diagonale monte et embrase le wordmark « Sako » ; puis macro rasante
   extrême sur les lettres avec glint vertical.
3. **9–19 s · La carte & l'app** — la carte flotte (reflet au sol), titre
   « La carte Sako / VISA PLATINUM », sweep spéculaire, puis elle **se givre**
   derrière la pastille « Bientôt disponible » ; « Connectée à votre app. » avec
   iPhone reconstitué en PIL, 3 écrans (solde 2 480,50 €, liste d'attente,
   transfert Cotonou −200,00 €).
4. **19–29 s · Final** — 5 flashs macro accélérés, « Elle arrive. », logo Sako
   révélé, « BIENTÔT DISPONIBLE · Rejoignez la liste d'attente · sako.app ».

## Bande-son (originale, libre de droits)

Instrumental **desert blues touareg** (~102 BPM, la mineur pentatonique) :
guitare Karplus-Strong, percussions synthétisées (calebasse, djembé, shaker
swingué, claps, basse), et SFX (whoosh, boom, ding cristallin, ticks, laser,
riser). Arc dramaturgique calé sur l'image : mystère → pulsation → groove →
breaks sur les flashs → silence → accord de guitare conclusif.

## Identité respectée

- Palette strictement noir / blanc / gris + un seul accent chaud « champagne »
  (additif, très discret).
- Typographie **Sora** uniquement (titres Bold/ExtraBold, labels capitales
  espacées, tracking manuel caractère par caractère).
- Grain argentique (σ≈6, 4 champs de bruit en rotation) + vignette radiale.
- La carte physique apparaît **floutée** derrière la pastille cadenas
  « Bientôt disponible » dès qu'elle est montrée en produit ; nette seulement
  dans les plans « cinéma » (macro, révélation).

## Structure du code (`src/`)

| Fichier | Rôle |
|---|---|
| `common.py` | Utilitaires : palette, cache de polices, grain, vignette, homographies, sprites de halo, texte tracké, dégradés. |
| `context.py` | Contexte de rendu : chargement des assets, moteur d'éclairage par plaques (`LitCard`), sprites de texte, compositing. |
| `make_assets.py` | **Régénère** `assets/card_sako.png` et `assets/logo_sako_blanc.png` en procédural. |
| `ui.py` | iPhone + écrans d'app (solde, cartes, transfert) + carte à coins arrondis. |
| `seq1..seq4.py` | Les 4 séquences du teaser principal. |
| `render.py` | Orchestrateur : streaming rawvideo → ffmpeg, rendu par chunks, grilles de test. |
| `pole.py` | Le spot 1:1 « pole position » (séquences dédiées + runner). |
| `music.py` | Synthèse des bandes-son (`build`, `build_pole`). |

> **Note sur les assets.** Le prompt fournissait `card_sako.png` et
> `logo_sako_blanc.png`, mais seul le `.md` était présent sur le disque de la
> session (l'image de la carte était visible dans la conversation, pas
> enregistrée en fichier). Les deux assets ont donc été **régénérés en
> procédural** (`make_assets.py`) d'après le visuel de référence : dégradé
> argenté, croix d'Agadez en pointillisme fin, wordmark « Sako », « VISA
> Platinum ». Remplacez-les par les fichiers officiels si disponibles.

## Reproduire

```bash
pip install numpy pillow            # + ffmpeg dans le PATH
# police variable Sora dans assets/Sora.ttf (incluse)
python3 src/make_assets.py          # (ré)génère la carte + le logo
python3 src/music.py out/sako_music.wav 29.1            # bande-son principale
python3 src/music.py out/sako_pole_music.wav 22.0 pole  # bande-son pole
bash scripts_build.sh 9x16 out/sako_teaser_9x16.mp4     # rendu 9:16
bash scripts_build.sh 16x9 out/sako_teaser_16x9.mp4     # rendu 16:9
bash scripts_pole.sh                                    # rendu 1:1

# Grille de frames de test à des instants clés (validation avant rendu complet) :
python3 src/render.py grid 9x16 30,175,300,470,600,865 build/test.jpg
```

Le rendu se fait en **chunks séquentiels** (~300 frames) concaténés puis muxés
(`ffmpeg -c:v ... -c:a aac -shortest`). Les masters sont encodés en CRF 18 puis
ré-encodés en CRF 25 pour des livrables partageables (< 15 Mo).
