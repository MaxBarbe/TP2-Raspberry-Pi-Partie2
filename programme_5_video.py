"""Détection de mouvement sur une vidéo : séquentiel ou quatre processus."""
import argparse
from contextlib import nullcontext
from fractions import Fraction
import json
import math
import multiprocessing as mp
from pathlib import Path
import shutil
import subprocess
import sys
from time import perf_counter

from PIL import Image, ImageChops

DOSSIER = Path(__file__).resolve().parent
VIDEO = DOSSIER / "IMG_0882.mov"
MODE = "sequentiel"  # Dans Spyder, mettre "parallele" pour le second essai.
PROCESSUS = 4
LOT = 8  # Nombre de comparaisons envoyées ensemble ; mémoire bornée.
TAILLE = (640, 360)
SEUIL = 25  # Différence de luminosité (0-255), pas un seuil de charge CPU.
TABLE = [0 if i <= SEUIL else 255 for i in range(256)]


def mouvement(couple):
    """Comparer deux images grises : blanc = changement, noir = stable."""
    avant, apres = couple
    a = Image.frombytes("L", TAILLE, avant)
    b = Image.frombytes("L", TAILLE, apres)
    return ImageChops.difference(a, b).point(TABLE).tobytes()


def cadence(source):
    commande = ["ffprobe", "-v", "error", "-select_streams", "v:0",
                "-show_entries", "stream=avg_frame_rate", "-of", "json", str(source)]
    info = json.loads(subprocess.check_output(commande, text=True))
    try:
        fps = Fraction(info["streams"][0]["avg_frame_rate"])
    except (IndexError, KeyError, ValueError, ZeroDivisionError) as exc:
        raise ValueError("Impossible de déterminer la cadence de la vidéo.") from exc
    if fps <= 0:
        raise ValueError("Cadence vidéo invalide.")
    return str(fps)


def traiter(source, temporaire, fps, pool):
    w, h = TAILLE
    dimension = f"{w}x{h}"
    # Même décodage et même résolution dans les deux modes.
    filtre = (f"scale={w}:{h}:force_original_aspect_ratio=decrease,"
              f"pad={w}:{h}:(ow-iw)/2:(oh-ih)/2,setsar=1")
    lecture = ["ffmpeg", "-nostdin", "-v", "error", "-threads", "1",
               "-i", str(source), "-map", "0:v:0", "-an", "-filter_threads", "1",
               "-vf", filtre, "-vsync", "0", "-c:v", "rawvideo", "-threads", "1",
               "-pix_fmt", "gray", "-f", "rawvideo", "pipe:1"]
    ecriture = ["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "gray",
                "-video_size", dimension, "-framerate", fps, "-i", "pipe:0",
                "-an", "-filter_threads", "1", "-c:v", "mpeg4", "-threads", "1",
                "-pix_fmt", "yuv420p", str(temporaire)]
    compte = 0
    precedente = None
    lot = []

    # FFmpeg lit la vidéo et écrit la sortie. Python traite les images en flux.
    with subprocess.Popen(lecture, stdout=subprocess.PIPE) as lecteur:
        try:
            with subprocess.Popen(ecriture, stdin=subprocess.PIPE) as ecrivain:
                try:
                    while True:
                        image = lecteur.stdout.read(w * h)
                        if not image:
                            break
                        if len(image) != w * h:
                            raise RuntimeError("Image vidéo incomplète.")
                        if precedente is not None:
                            lot.append((precedente, image))
                        # Conserver l'image précédente même entre deux lots.
                        precedente = image
                        if len(lot) == LOT:
                            compte += ecrire_lot(lot, pool, ecrivain.stdin)
                            lot.clear()
                    if lot:
                        compte += ecrire_lot(lot, pool, ecrivain.stdin)
                    ecrivain.stdin.close()
                    if ecrivain.wait() != 0:
                        raise RuntimeError("Échec de l'encodage vidéo.")
                finally:
                    if ecrivain.poll() is None:
                        ecrivain.terminate()
            if lecteur.wait() != 0:
                raise RuntimeError("Échec du décodage vidéo.")
        finally:
            if lecteur.poll() is None:
                lecteur.terminate()
    if compte == 0:
        raise ValueError("Il faut au moins deux images dans la vidéo.")
    return compte


def ecrire_lot(lot, pool, sortie):
    # map attend les résultats et conserve l'ordre des paires de la vidéo.
    masques = map(mouvement, lot) if pool is None else pool.map(mouvement, lot, chunksize=1)
    for masque in masques:
        sortie.write(masque)
    return len(lot)


def puissance():
    while True:
        valeur = input("Puissance moyenne pendant l'essai (W), vide si inconnue : ").strip()
        if not valeur:
            return None
        try:
            watts = float(valeur.replace(",", "."))
            if math.isfinite(watts) and watts > 0:
                return watts
        except ValueError:
            pass
        print("Entre une puissance positive, en watts.")


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("video", nargs="?", type=Path, default=VIDEO)
    cli.add_argument("--mode", choices=("sequentiel", "parallele"), default=MODE)
    cli.add_argument("--wattmetre", action="store_true")
    cli.add_argument("--interne", action="store_true", help=argparse.SUPPRESS)
    args = cli.parse_args()
    if not args.interne:
        # Exécuter hors du noyau Spyder pour que multiprocessing puisse démarrer.
        commande = [sys.executable, "-u", str(Path(__file__).resolve()), str(args.video.resolve()),
                    "--mode", args.mode, "--interne"]
        if args.wattmetre:
            commande.append("--wattmetre")
        subprocess.run(commande, check=True)
        return
    if not all(shutil.which(programme) for programme in ("ffmpeg", "ffprobe")):
        raise RuntimeError("FFmpeg est absent. Sur le Raspberry : sudo apt install ffmpeg")
    source = args.video.resolve()
    if not source.is_file():
        raise FileNotFoundError(f"Vidéo introuvable : {source}")
    fps = cadence(source)
    dossier = DOSSIER / "resultats_video"
    dossier.mkdir(exist_ok=True)
    finale = dossier / f"mouvement_{args.mode}.mp4"
    temporaire = dossier / f"mouvement_{args.mode}.tmp.mp4"
    contexte = mp.get_context("spawn").Pool(PROCESSUS) if args.mode == "parallele" else nullcontext()
    try:
        with contexte as pool:
            if pool is not None:
                pool.map(abs, [0] * PROCESSUS, chunksize=1)
            if args.wattmetre:
                input("Prépare le wattmètre et appuie sur Entrée.")
            print(f"DEBUT {args.mode} : relève la puissance moyenne.", flush=True)
            debut = perf_counter()
            nombre = traiter(source, temporaire, fps, pool)
            duree = perf_counter() - debut
            print("FIN de la mesure.", flush=True)
        temporaire.replace(finale)
    finally:
        temporaire.unlink(missing_ok=True)
    watts = puissance() if args.wattmetre else None
    mesure = dict(mode=args.mode, processus=PROCESSUS if args.mode == "parallele" else 1,
                  masques=nombre, secondes=duree, debit_images_s=nombre/duree,
                  ms_image=1000*duree/nombre, puissance_W=watts,
                  mJ_image=None if watts is None else 1000*watts*duree/nombre,
                  resolution=list(TAILLE), seuil=SEUIL, video_source=str(source))
    (dossier / f"mesure_{args.mode}.json").write_text(json.dumps(mesure, indent=2) + "\n", encoding="utf-8")
    print(f"{nombre} masques | {duree:.3f} s | {nombre/duree:.2f} images/s")
    print(f"Temps moyen : {1000*duree/nombre:.3f} ms/image")
    if watts is not None:
        print(f"Énergie estimée : {1000*watts*duree/nombre:.2f} mJ/image")
    print("Vidéo produite :", finale)


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, RuntimeError, subprocess.CalledProcessError) as erreur:
        raise SystemExit(f"Erreur : {erreur}")
