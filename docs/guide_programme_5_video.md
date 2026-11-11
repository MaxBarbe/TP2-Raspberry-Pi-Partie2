# Programme 5 — Détection de mouvement dans une vidéo

Le programme compare chaque image à l’image précédente. Pillow calcule la
différence de luminosité pixel par pixel : les changements supérieurs à 25
(sur 255) deviennent blancs, le reste reste noir. Le premier cadre sert de
référence : une vidéo de N images produit N−1 masques. Ce seuil porte sur
l’image, pas sur l’activité CPU.

- **Séquentiel** : les paires sont calculées l’une après l’autre.
- **Parallèle** : le pool de quatre processus reçoit des lots de huit paires.
  Le processus principal préserve la succession des images entre les lots et
  écrit les masques dans le bon ordre. Aucun fichier intermédiaire par image.

FFmpeg lit et réencode la vidéo ; Pillow calcule les masques en Python via
ses fonctions natives. La sortie est en 640 × 360, sans audio, à cadence
constante basée sur la cadence moyenne annoncée par la vidéo d’entrée.
Les mouvements de caméra et les changements d’éclairage peuvent aussi
produire du blanc. Utiliser de préférence une vidéo avec caméra fixe.

## Lancer sur le Raspberry Pi

Pillow doit être installé dans l’interpréteur utilisé. Si FFmpeg manque :

```bash
sudo apt install ffmpeg
```

L’exemple fourni est `IMG_0882.mov`, déjà placé à côté du script. Dans Spyder, lance le script avec F5,
puis change `MODE = "sequentiel"` en `MODE = "parallele"` et relance.
Les deux vidéos et les mesures sont dans `resultats_video/`.

Pour relever la puissance, utilise plutôt le terminal :

```bash
cd /home/pi/Documents/TP2-Raspberry-Pi-Partie2
python3 programme_5_video.py IMG_0882.mov --mode sequentiel --wattmetre
python3 programme_5_video.py IMG_0882.mov --mode parallele --wattmetre
```

Entre DEBUT et FIN, relève la puissance moyenne de la carte et saisis-la
en watts après l’essai. Si le wattmètre affiche V et A, multiplie la tension
par le courant moyen. Utilise une vidéo dont le traitement est assez long
pour relever la puissance de façon représentative.

Le temps inclut le décodage, le calcul des masques, les transferts et
l’encodage, mais exclut la préparation du pool. Énergie par masque en mJ =
puissance moyenne en W × temps moyen en ms. Comparer la même vidéo, le
même seuil, la même résolution et le même governor pour les deux versions.
Le script ne modifie pas le governor.
