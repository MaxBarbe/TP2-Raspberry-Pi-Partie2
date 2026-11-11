# Programme 5 — Résultats sur le Raspberry Pi

Vidéo d’entrée : IMG_0882.mov. Les deux essais ont produit 349 masques de
mouvement en 640 × 360, avec le même seuil de différence (25 sur 255).
Les fichiers MP4 de sortie ont la même empreinte SHA-256.

| Mesure | Séquentiel | Parallèle (4 processus) |
|---|---:|---:|
| Durée du traitement | 115,125 s | 116,547 s |
| Débit | 3,031 images/s | 2,995 images/s |
| Temps moyen par masque | 329,870 ms | 333,945 ms |
| Puissance de la carte | 4,35 W | 4,60 W |
| Énergie estimée par masque | 1,435 J | 1,536 J |

Énergie par masque = puissance moyenne × durée totale / nombre de masques.
La mesure inclut le décodage, le calcul, les transferts et l’encodage. La
version parallèle a pris 1,2 % de temps en plus et environ 7 % d’énergie
en plus par masque sur cet essai. Le test ne sépare pas le coût des
transferts du coût du décodage et de l’encodage.

Les deux essais ont été réalisés avec le governor `conservative`, d’après
le relevé de l’expérimentateur. Ce réglage n’a pas été enregistré par le script
dans les fichiers JSON. Ces essais comparent donc les deux versions du
traitement sous le même governor.
