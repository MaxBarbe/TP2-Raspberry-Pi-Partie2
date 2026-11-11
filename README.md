# TP2 - Raspberry Pi : traitement d’images et consommation

**Auteur : Maxime Barbe**

Partie 2 du TP2 Architecture multicores et consommation : convertir des images avec Pillow, comparer le séquentiel et le parallèle par processus, puis étudier le compromis entre débit et énergie. Les cinq programmes sont les versions utilisées pour les essais. Les numéros 1, 2 et 3 désignent trois variantes au sein de cette partie 2.

## Programmes

| Fichier | Fonctionnement |
|---|---|
| `programme_1_sequentiel.py` | Convertit une image entière en niveaux de gris, sans parallélisme |
| `programme_2_images_paralleles.py` | Répartit des conversions d’images entières entre quatre processus |
| `programme_3_quadrants_paralleles.py` | Découpe une image en quatre quadrants, les convertit avec quatre processus puis les réassemble |
| `programme_4_application.py` | Traite un dossier de photos avec des profils ÉCO et MAX, suit la fréquence et l’activité des cœurs |
| `programme_5_video.py` | Compare deux images consécutives d’une vidéo, en séquentiel ou avec quatre processus |

`image1.jpg` sert aux programmes 1 à 3, `photos/` contient les cinq entrées du programme 4 et `IMG_0882.mov` est la vidéo du programme 5. Les explications et la synthèse PDF sont dans [`docs/`](docs/). Les JSON des essais retenus sont conservés dans [`mesures/`](mesures/), séparément des résultats générés lors d’une nouvelle exécution.

## Installation sur Raspberry Pi OS

```bash
sudo apt update
sudo apt install git python3 python3-pil ffmpeg
```

Pour un environnement Python personnel, installer aussi la dépendance avec l’interpréteur concerné : `python3 -m pip install -r requirements.txt`. FFmpeg et ffprobe sont des exécutables système, pas des dépendances Python.

```bash
git clone https://github.com/MaxBarbe/TP2-Raspberry-Pi-Partie2.git
cd TP2-Raspberry-Pi-Partie2
```

Le dépôt est privé : GitHub demande une authentification autorisée lors du clonage.

## 1. Comparer les trois conversions d’image

```bash
python3 programme_1_sequentiel.py
python3 programme_2_images_paralleles.py
python3 programme_3_quadrants_paralleles.py
```

Les trois scripts utilisent `image1.jpg` à côté du code. Ils répètent la même image par lots de quatre pendant au moins 15 secondes. Lire la puissance moyenne au wattmètre entre DÉBUT et FIN. Ils affichent le débit et le temps moyen par image, vérifient les pixels contre la référence Pillow et enregistrent les PNG dans `resultats/`. Le programme 3 produit aussi les quatre morceaux.

Le chronométrage exclut la lecture initiale, la sauvegarde et la création du pool. Il inclut les transferts entre processus et, pour le programme 3, le découpage et le réassemblage. Le temps durée/nombre est l’inverse du débit, pas la latence individuelle d’une tâche parallèle.

Dans Spyder, ouvrir le fichier enregistré puis appuyer sur F5. Les programmes 2 et 3 lancent un interpréteur indépendant pour démarrer les processus hors du noyau Spyder. Le terminal reste préférable pour les mesures et les programmes interactifs.

## 2. Traiter plusieurs photos avec ÉCO et MAX

Essai sans modification du CPU, sans saisie et sans sudo :

```bash
python3 programme_4_application.py photos --sans-cpufreq --sans-saisie --processus 1
```

Comparaison sur Raspberry Pi, avec les mêmes réglages que les mesures disponibles :

```bash
sudo python3 programme_4_application.py photos --mode comparer --processus 1 --tours 5 --mesurer-repos
```

- ÉCO utilise `conservative` et limite la fréquence au minimum autorisé par défaut (600 MHz sur la carte du TP).
- MAX utilise `performance` et le plafond maximal configuré au lancement (1 800 MHz lors du TP).
- Le script applique les profils temporairement et restaure le governor et son plafond en sortie normale ou lors d’une exception gérée.
- Il demande le **courant en ampères**. La tension vaut 5 V par défaut et se règle avec `--volts`.
- Les réglages CPU demandent sudo. Si Pillow est installé uniquement dans un environnement virtuel, utiliser son interpréteur plutôt que celui du système.

Le temps inclut ouverture, décodage, conversion et écriture des photos. Les sorties PNG et JSON sont dans `resultats_programme4/`. Pour étudier le parallélisme, répéter avec `--processus 2`, puis `--processus 4`, sur le même corpus. Sans cette option, le programme utilise tous les CPU autorisés. Les mesures publiées ici utilisent **un seul processus**, dans les deux profils.

Le profil applicatif pilote des governors Linux existants. Il ne crée pas un nouveau governor noyau. L’activité par cœur est un pourcentage calculé depuis `/proc/stat`, tandis que le wattmètre donne la puissance de toute la carte.

Guide détaillé : [`docs/guide_programme_4.md`](docs/guide_programme_4.md).

## 3. Comparer les images d’une vidéo

```bash
python3 programme_5_video.py IMG_0882.mov --mode sequentiel --wattmetre
python3 programme_5_video.py IMG_0882.mov --mode parallele --wattmetre
```

Le programme demande une **puissance en watts** après l’essai. Si le wattmètre indique V et A, calculer P = U × I. Il ne change pas le governor. Pour vérifier uniquement le traitement, omettre `--wattmetre`.

Pillow calcule la différence absolue de luminosité entre deux images grises. Un changement supérieur à 25 sur 255 devient blanc, sinon le pixel est noir. Ce calcul détecte des changements, sans identifier les objets. FFmpeg décode et réencode la vidéo en 640 × 360, sans audio. Le temps mesuré inclut décodage, calcul, transferts et encodage, mais pas la création du pool.

Les résultats sont dans `resultats_video/`. N images sources donnent N−1 masques, soit 349 dans cet exemple. Guide : [`docs/guide_programme_5_video.md`](docs/guide_programme_5_video.md). Dans Spyder, le chemin par défaut est déjà `IMG_0882.mov` et la variable `MODE` choisit l’exécution.

## Résultats mesurés

Les puissances concernent toute la carte. L’énergie estimée par image vaut **P × durée / nombre d’images** et suppose une puissance représentative pendant la fenêtre de traitement.

| Variante | Governor | Temps/image | Puissance en charge | Énergie/image |
|---|---|---:|---:|---:|
| Programme 1 | ondemand | 7,236 ms | 3,50 W | 25,3 mJ |
| Programme 1 | conservative | 5,545 ms | 3,45 W | 19,1 mJ |
| Programme 2 | ondemand | 98,590 ms | 3,70 W | 364,8 mJ |
| Programme 2 | conservative | 98,580 ms | 3,60 W | 354,9 mJ |
| Programme 3 | ondemand | 118,571 ms | 3,60 W | 426,9 mJ |
| Programme 3 | conservative | 118,760 ms | 3,50 W | 415,7 mJ |

Sur cette image, la conversion séquentielle Pillow est la plus efficace. Les valeurs viennent des relevés transmis pendant le TP, également repris dans le [PDF de synthèse](docs/TP2_Resultats_Partie2.pdf). Les différences entre governors restent à confirmer avec des répétitions et un suivi de fréquence et de température.

| Programme 4, 25 images, un processus | Durée | Puissance | Énergie/image |
|---|---:|---:|---:|
| ÉCO, conservative, plafond 600 MHz | 40,998 s | 2,10 W | 3,444 J |
| MAX, performance, 1 800 MHz | 13,610 s | 3,35 W | 1,824 J |

MAX est environ trois fois plus rapide et demande 47 % d’énergie en moins par image sur cet essai. La puissance au repos ÉCO (2,15 W) dépassait légèrement celle en charge (2,10 W), ce qui demande une nouvelle mesure. Seuls les essais retenus `20261103_191354_773239` et `20261103_191508_412920` sont archivés ici.

| Programme 5, conservative | Masques | Durée | Puissance | Énergie/masque |
|---|---:|---:|---:|---:|
| Séquentiel | 349 | 115,125 s | 4,35 W | 1,435 J |
| Quatre processus | 349 | 116,547 s | 4,60 W | 1,536 J |

La même vidéo de sortie a été obtenue. Le parallèle demande environ 7 % d’énergie supplémentaire sur cet essai. Le governor conservative a été confirmé lors du TP, mais n’est pas enregistré par le programme 5. Son débit mesuré est d’environ trois masques par seconde, sans traitement en temps réel à la cadence nominale du fichier.

Les programmes 1 à 3, 4 et 5 n’utilisent pas le même corpus ni la même fenêtre de mesure. Leurs valeurs absolues ne doivent donc pas être comparées comme s’il s’agissait d’une seule expérience.
