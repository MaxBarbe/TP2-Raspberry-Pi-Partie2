"""Application terminal : conversion d'un dossier de photos avec deux profils CPU."""
import argparse
from contextlib import contextmanager
from datetime import datetime
import hashlib
import json
import math
import multiprocessing as mp
import os
from pathlib import Path
import statistics
import sys
import threading
from time import perf_counter

from PIL import Image

EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".tif", ".tiff", ".webp"}
CPUFREQ = Path("/sys/devices/system/cpu/cpufreq")


def limiter_travailleur(cpus):
    if cpus is not None:
        os.sched_setaffinity(0, cpus)


def compteurs_cpu(chemin=Path("/proc/stat")):
    """Lire les compteurs cumulés de chaque CPU logique, pas de la ligne globale."""
    try:
        lignes = chemin.read_text().splitlines()
    except OSError:
        return {}
    resultat = {}
    for ligne in lignes:
        champs = ligne.split()
        if len(champs) >= 9 and champs[0].startswith("cpu") and champs[0][3:].isdigit():
            # Les huit premiers champs évitent de compter guest deux fois.
            resultat[champs[0]] = tuple(map(int, champs[1:9]))
    return resultat


def activite_cpu(avant, apres):
    resultat = {}
    for cpu in sorted(avant.keys() & apres.keys(), key=lambda nom: int(nom[3:])):
        delta = [b - a for a, b in zip(avant[cpu], apres[cpu])]
        total = sum(delta)
        if total > 0 and all(d >= 0 for d in delta):
            # Exclure l'inactivité, l'attente d'E/S et le temps volé de l'activité.
            actif = sum(delta[i] for i in (0, 1, 2, 5, 6))
            resultat[cpu] = round(100 * actif / total, 1)
    return resultat


def convertir(tache):
    """Un processus lit et traite une photo entière ; il ne reçoit que ses chemins."""
    source, sortie = tache
    with Image.open(source) as image:
        image.convert("RGB").convert("L").save(sortie, format="PNG")


def lire(politique, nom):
    return (politique / nom).read_text().strip()


def ecrire(politique, nom, valeur):
    (politique / nom).write_text(f"{valeur}\n")


def profils_cpu(politique, plafond_mhz):
    """ÉCO garde seulement les fréquences sous un plafond ; MAX garde toute la plage."""
    bas = int(lire(politique, "scaling_min_freq"))
    haut = int(lire(politique, "scaling_max_freq"))
    liste = politique / "scaling_available_frequencies"
    frequences = sorted({f for f in map(int, liste.read_text().split()) if bas <= f <= haut}
                        if liste.exists() else {bas, haut})
    limite = plafond_mhz * 1000 if plafond_mhz is not None else bas
    possibles = [f for f in frequences if f <= limite and f < haut]
    if not possibles:
        raise ValueError("Aucune fréquence ÉCO sous le plafond demandé et strictement sous MAX.")
    return {"eco": ("conservative", max(possibles)),
            "max": ("performance", haut)}


@contextmanager
def appliquer(politique, profil):
    """Appliquer un profil pour cet essai, puis revenir aux réglages de départ."""
    if politique is None:
        yield
        return

    governor, plafond = profil
    ancien = lire(politique, "scaling_governor")
    ancien_max = lire(politique, "scaling_max_freq")
    ancienne_consigne = lire(politique, "scaling_setspeed") if ancien == "userspace" else None
    disponibles = lire(politique, "scaling_available_governors").split()
    if governor not in disponibles:
        raise ValueError(f"Governor {governor!r} indisponible : {', '.join(disponibles)}.")
    try:
        ecrire(politique, "scaling_max_freq", plafond)
        ecrire(politique, "scaling_governor", governor)
        if (lire(politique, "scaling_governor") != governor
                or int(lire(politique, "scaling_max_freq")) != plafond):
            raise RuntimeError("Le noyau n'a pas appliqué le profil demandé.")
        yield
    finally:
        try:
            ecrire(politique, "scaling_max_freq", ancien_max)
        finally:
            ecrire(politique, "scaling_governor", ancien)
            if ancienne_consigne and ancienne_consigne.isdigit():
                ecrire(politique, "scaling_setspeed", ancienne_consigne)


def relever_frequences(politique, arret, valeurs):
    """Échantillonnage indicatif de la fréquence pendant le traitement."""
    while not arret.is_set():
        try:
            valeurs.append(int(lire(politique, "scaling_cur_freq")) / 1000)
        except (OSError, ValueError):
            pass
        arret.wait(0.2)


def courant(situation):
    while True:
        try:
            saisie = input(f"Courant moyen {situation} (A), Entrée si inconnu : ").strip()
            if not saisie:
                return None
            amp = float(saisie.replace(",", "."))
            if math.isfinite(amp) and amp > 0:
                return amp
        except ValueError:
            pass
        print("Entre une valeur positive en ampères.")


def lancer(mode, profil, politique, images, dossier, pool, args, nb_processus, cpus):
    destination = dossier / mode
    destination.mkdir()
    # Un numéro évite d'écraser photo.jpg et photo.png, par exemple.
    taches = [(source, destination / f"{i:04d}_{source.stem}_gris.png")
              for i, source in enumerate(images, 1)]
    if not args.sans_saisie:
        input(f"Mode {mode.upper()} : prépare le wattmètre et appuie sur Entrée.")
    freq = []
    arret = threading.Event()
    sonde = None
    with appliquer(politique, profil):
        repos = courant("au repos, avec ce profil actif") if args.mesurer_repos else None
        avant = compteurs_cpu()
        print(f"DÉBUT {mode.upper()} | {profil[0]} | {nb_processus} processus", flush=True)
        debut = perf_counter()
        if politique is not None:
            sonde = threading.Thread(target=relever_frequences, args=(politique, arret, freq))
            sonde.start()
        try:
            for _ in range(args.tours):
                pool.map(convertir, taches, chunksize=1)
        finally:
            duree = perf_counter() - debut
            apres = compteurs_cpu()
            arret.set()
            if sonde is not None:
                sonde.join()
    nombre = len(images) * args.tours
    print(f"FIN {mode.upper()} : {nombre} images en {duree:.3f} s.")
    amps = None if args.sans_saisie else courant("en traitement")
    watts = None if amps is None else args.volts * amps
    watts_repos = None if repos is None else args.volts * repos
    charges = activite_cpu(avant, apres)
    mesure = {
        "mode": mode, "governor_linux": profil[0], "plafond_kHz": profil[1],
        "processus": nb_processus, "tours": args.tours, "images": nombre,
        "secondes": duree, "images_s": nombre / duree, "ms_image": 1000 * duree / nombre,
        "tension_V": args.volts, "courant_A": amps, "puissance_W": watts,
        "puissance_repos_W": watts_repos,
        "surplus_puissance_carte_W": watts - watts_repos if watts is not None and watts_repos is not None else None,
        "cpu_autorises_aux_travailleurs": list(cpus) if cpus is not None else None,
        "activite_cpu_pourcent": charges,
        "mJ_image": None if watts is None else 1000 * watts * duree / nombre,
        "frequence_MHz_min_mediane_max": [min(freq), statistics.median(freq), max(freq)] if freq else None,
    }
    (destination / "mesure.json").write_text(json.dumps(mesure, indent=2) + "\n")
    print(f"Débit : {mesure['images_s']:.2f} images/s ; temps moyen : {mesure['ms_image']:.2f} ms/image")
    if freq:
        print(f"Fréquence observée min / médiane / max : {min(freq):g} / {statistics.median(freq):g} / {max(freq):g} MHz")
    if watts is not None:
        print(f"Puissance : {watts:.2f} W ; énergie : {mesure['mJ_image']:.2f} mJ/image")
    if charges:
        print("Activité moyenne des coeurs :", " | ".join(f"{cpu} : {pct:g} %" for cpu, pct in charges.items()))
    return mesure


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("photos", type=Path, help="Dossier d'au moins deux photos.")
    cli.add_argument("--mode", choices=("eco", "max", "comparer"), default="comparer")
    cli.add_argument("--plafond-eco", type=int, metavar="MHz", help="Par défaut, fréquence minimale autorisée.")
    cli.add_argument("--tours", type=int, default=1, help="Nombre de passages sur le même dossier.")
    cli.add_argument("--volts", type=float, default=5.0)
    cli.add_argument("--debit-min", type=float, help="Débit minimum (images/s) pour recommander un profil.")
    cli.add_argument("--sans-saisie", action="store_true", help="Chronométrer sans saisir de courant.")
    cli.add_argument("--processus", type=int, help="Nombre de processus ; tous les CPU utilisables par défaut.")
    cli.add_argument("--mesurer-repos", action="store_true", help="Saisir aussi le courant au repos pour chaque profil.")
    cli.add_argument("--sans-cpufreq", action="store_true", help="Tester le traitement, sans changer la fréquence.")
    args = cli.parse_args()
    if (args.tours < 1 or not math.isfinite(args.volts) or args.volts <= 0
            or (args.debit_min is not None and
                (not math.isfinite(args.debit_min) or args.debit_min <= 0))):
        cli.error("Nombre de tours, tension et débit minimum doivent être positifs.")
    photos = args.photos.resolve()
    images = sorted(p for p in photos.iterdir() if p.is_file() and p.suffix.lower() in EXTENSIONS)
    if len(images) < 2:
        cli.error("Mets au moins deux fichiers image dans le dossier.")
    if args.sans_saisie and args.mesurer_repos:
        cli.error("--mesurer-repos et --sans-saisie sont incompatibles.")
    autorises = sorted(os.sched_getaffinity(0)) if hasattr(os, "sched_getaffinity") else None
    disponibles = len(autorises) if autorises is not None else (os.cpu_count() or 1)
    n = disponibles if args.processus is None else args.processus
    if not 1 <= n <= disponibles:
        cli.error(f"Choisis entre 1 et {disponibles} processus.")
    cpus = autorises[:n] if autorises is not None else None
    p = None
    if args.sans_cpufreq:
        # Un seul essai de vérification : aucun faux comparatif ÉCO / MAX.
        configurations = {"test": ("inchangé", None)}
        modes = ("test",)
    else:
        if not hasattr(os, "geteuid") or os.geteuid() != 0:
            cli.error("Lance avec sudo sur le Raspberry Pi, ou utilise --sans-cpufreq pour un test.")
        politiques = sorted(CPUFREQ.glob("policy*"))
        if len(politiques) != 1:
            cli.error("Le programme attend la politique CPU commune du Raspberry Pi du TP.")
        p = politiques[0]
        configurations = profils_cpu(p, args.plafond_eco)
        modes = ("eco", "max") if args.mode == "comparer" else (args.mode,)

    dossier = Path(__file__).resolve().parent / "resultats_programme4" / datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    dossier.mkdir(parents=True)
    # Inventaire identique pour les deux modes, enregistré à part du chronométrage.
    inventaire = [{"fichier": image.name, "sha256": hashlib.sha256(image.read_bytes()).hexdigest()}
                  for image in images]
    (dossier / "photos.json").write_text(json.dumps(inventaire, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    with mp.get_context("spawn").Pool(n, initializer=limiter_travailleur, initargs=(cpus,)) as pool:
        pool.map(abs, [0] * n, chunksize=1)
        mesures = [lancer(mode, configurations[mode], p, images, dossier, pool, args, n, cpus)
                   for mode in modes]
    (dossier / "comparaison.json").write_text(json.dumps(mesures, indent=2) + "\n")
    if args.debit_min is not None and len(mesures) == 2:
        valides = [m for m in mesures if m["images_s"] >= args.debit_min and m["mJ_image"] is not None]
        if valides:
            meilleur = min(valides, key=lambda m: (m["mJ_image"], -m["images_s"]))
            print(f"Profil recommandé à {args.debit_min:g} images/s : {meilleur['mode'].upper()}")
            if any(m["mJ_image"] is None for m in mesures):
                print("Recommandation limitée aux profils dont le courant a été mesuré.")
        else:
            print("Aucun profil avec une énergie mesurée ne satisfait le débit demandé.")
    print("Photos converties et mesures :", dossier)


if __name__ == "__main__":
    # Un terminal ancien peut être en Latin-1 (notamment après sudo).
    for flux in (sys.stdout, sys.stderr):
        if hasattr(flux, "reconfigure"):
            flux.reconfigure(errors="backslashreplace")
    try:
        main()
    except (OSError, RuntimeError, ValueError, EOFError) as erreur:
        raise SystemExit(f"Erreur : {erreur}")
    except KeyboardInterrupt:
        raise SystemExit("\nEssai interrompu.")
