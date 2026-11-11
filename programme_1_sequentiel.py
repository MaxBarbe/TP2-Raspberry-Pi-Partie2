"""Partie 1 : Niveaux de gris, sans parallélisme."""
from pathlib import Path
from time import perf_counter

from PIL import Image

DUREE_MIN = 15  # Secondes : augmenter si le wattmètre est lent.
LOT = 4  # Même nombre d'images par lot dans les trois essais.
DOSSIER = Path(__file__).resolve().parent
SOURCE = DOSSIER / "image1.jpg"


def gris(image):
    # Pillow fait la conversion en code natif, sans boucle Python par pixel.
    return image.convert("L")


def traiter_lot(image, pool):
    # Chaque conversion se termine avant de commencer la suivante.
    return [gris(image) for _ in range(LOT)]


def mesurer(image, pool=None):
    # Préparer les processus hors chronométrage.
    traiter_lot(image, pool)
    print(f"DÉBUT programme 1 : relève la puissance moyenne au wattmètre.", flush=True)
    nombre = 0
    debut = perf_counter()
    while True:
        resultats = traiter_lot(image, pool)
        nombre += len(resultats)
        duree = perf_counter() - debut
        if duree >= DUREE_MIN:
            break
    print("FIN de la mesure de puissance.", flush=True)
    reference = gris(image).tobytes()
    if any(r.tobytes() != reference for r in resultats):
        raise RuntimeError("Les résultats diffèrent de la conversion séquentielle.")
    sortie = DOSSIER / "resultats"
    sortie.mkdir(exist_ok=True)
    finale = resultats[0]
    finale.save(sortie / "partie_1_gris.png")
    print(f"{nombre} images en {duree:.3f} s | {nombre/duree:.3f} images/s")
    print(f"Temps moyen par image (durée/nombre) : {1000*duree/nombre:.3f} ms")
    print(f"Énergie par image = puissance moyenne (W) × {duree/nombre:.8f} s")
    print("Images identiques à la référence. Résultats :", sortie)


def main():
    if not SOURCE.is_file():
        raise SystemExit(f"Place image1.jpg à côté du script : {SOURCE}")
    with Image.open(SOURCE) as entree:
        image = entree.convert("RGB")
    mesurer(image)

if __name__ == "__main__":
    main()
