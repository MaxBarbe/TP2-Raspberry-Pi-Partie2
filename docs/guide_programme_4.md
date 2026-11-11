# Programme 4 — Application de traitement d’un dossier de photos

Le programme applique Pillow à plusieurs photos. Un pool utilise autant de
processus que le système expose de CPU utilisables. Chaque tâche ouvre sa
photo, la convertit avec `convert("L")` et enregistre un PNG en gris. Seuls les
chemins sont envoyés aux processus : les gros buffers d’image ne transitent
pas par le pool. C’est une nouvelle implémentation, donc elle se mesure à part
des programmes 1 à 3.

| Profil applicatif | Governor Linux | Fréquence | Processus |
|---|---|---|---|
| ÉCO | `conservative` | Plafond bas : minimum autorisé par défaut, ou valeur disponible sous le plafond choisi | Tous les CPU utilisables |
| MAX | `performance` | Fréquence maximale autorisée par le système demandée | Même nombre |

MAX demande la fréquence maximale. La charge CPU effective dépend du nombre
de photos, du décodage, des écritures sur disque et des limites thermiques.
À plafond égal au minimum, ÉCO n’a qu’une fréquence autorisée ; pour garder
plusieurs fréquences basses, choisir un plafond intermédiaire, par exemple
`--plafond-eco 1000` sur le Raspberry du TP si cette fréquence est disponible.

## Exécution dans le terminal du Raspberry Pi

Place plusieurs vraies photos dans `photos/` à côté du script. Depuis le
dossier partie2 :

```bash
sudo python3 programme_4_application.py photos --mode comparer --tours 5
```

Adapte `--tours` pour obtenir une fenêtre de mesure assez longue. Le programme
attend ton signal, affiche DÉBUT, traite le lot, puis affiche FIN et demande le
**courant moyen en ampères**. La tension utilisée est 5 V par défaut. Les deux
modes travaillent sur les mêmes photos et font le même nombre de tours.
Avec plusieurs tours, les sorties PNG du même essai sont réécrites ; le nombre
d’images indiqué compte toutes les conversions réalisées. Les PNG finaux et
les mesures JSON sont sauvegardés dans `resultats_programme4/`.

Le temps inclut ouverture, décodage, conversion, transferts de tâches et
écriture des PNG. Il exclut le démarrage du pool, l’inventaire et la saisie.
Le governor précédent et son plafond sont restaurés à la fin de chaque essai.
Le test passe par ÉCO puis MAX ; répéter aussi les modes séparément dans
l’ordre inverse pour limiter l’effet de la chauffe et des caches disque.

Si le TP demande une règle de choix, ajoute par exemple `--debit-min 10` :
parmi les modes qui atteignent 10 images/s, l’application recommande celui
qui a la plus petite énergie mesurée par image. 10 est un exemple à adapter.
La décision ne dépend d’aucun pourcentage de charge CPU.

Pour vérifier uniquement la conversion sans sudo ni changement CPU :

```bash
python3 programme_4_application.py photos --sans-cpufreq --sans-saisie
```

## Activité des cœurs et puissance de la carte

Le programme compare les compteurs Linux de chaque CPU au début et à la fin.
Il affiche l'activité moyenne des cœurs, y compris les autres tâches du
système, et l'enregistre dans `comparaison.json`. C'est un pourcentage de
temps actif, pas des watts par cœur. Les cœurs partagent la politique de
fréquence sur le Raspberry Pi du TP.

Pour étudier l'effet du nombre de cœurs sollicités, garder le même mode et
les mêmes photos, puis refaire l'essai avec `--processus 1`, `--processus 2`
et `--processus 4`. Sous Linux, les travailleurs sont limités à autant de
CPU autorisés ; les autres CPU restent disponibles pour le système.

```bash
sudo python3 programme_4_application.py photos --mode eco --processus 1 --tours 5 --mesurer-repos
```

Avec `--mesurer-repos`, attendre que la lecture du wattmètre se stabilise
après l'application du profil, puis saisir le courant au repos. Le programme
calcule le surplus de puissance de la **carte** : puissance en traitement
moins puissance au repos du même profil. Le wattmètre à l'entrée ne permet
pas d'isoler la puissance individuelle de chaque cœur.
