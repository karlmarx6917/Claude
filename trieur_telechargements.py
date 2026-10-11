#!/usr/bin/env python3
"""Range automatiquement un dossier (par défaut Téléchargements) par type de fichier.

Usage:
    python trieur_telechargements.py                # trie ~/Downloads
    python trieur_telechargements.py C:\\Dossier     # trie un autre dossier
    python trieur_telechargements.py --simulation   # montre ce qui serait fait
    python trieur_telechargements.py --surveiller   # trie en continu (toutes les 30 s)
"""
import argparse
import shutil
import time
from pathlib import Path

CATEGORIES = {
    "Images": {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp", ".svg", ".heic"},
    "Videos": {".mp4", ".mkv", ".avi", ".mov", ".wmv", ".webm"},
    "Musique": {".mp3", ".wav", ".flac", ".aac", ".ogg", ".m4a"},
    "Documents": {".pdf", ".doc", ".docx", ".txt", ".odt", ".xls", ".xlsx", ".ppt", ".pptx", ".csv", ".md"},
    "Archives": {".zip", ".rar", ".7z", ".tar", ".gz"},
    "Programmes": {".exe", ".msi", ".dmg", ".deb", ".appimage", ".apk"},
    "Code": {".py", ".js", ".html", ".css", ".json", ".sh", ".bat", ".ps1"},
}
EN_COURS = {".crdownload", ".part", ".tmp", ".download"}


def categorie(ext: str) -> str:
    for nom, exts in CATEGORIES.items():
        if ext in exts:
            return nom
    return "Autres"


def destination_libre(dest: Path) -> Path:
    """Évite d'écraser un fichier existant : photo.png -> photo (1).png"""
    if not dest.exists():
        return dest
    i = 1
    while True:
        essai = dest.with_name(f"{dest.stem} ({i}){dest.suffix}")
        if not essai.exists():
            return essai
        i += 1


def trier(dossier: Path, simulation: bool = False) -> int:
    deplaces = 0
    for f in dossier.iterdir():
        if not f.is_file() or f.name.startswith(".") or f.suffix.lower() in EN_COURS:
            continue
        if f.resolve() == Path(__file__).resolve():
            continue
        cible = destination_libre(dossier / categorie(f.suffix.lower()) / f.name)
        print(f"{'[simulation] ' if simulation else ''}{f.name} -> {cible.parent.name}/{cible.name}")
        if not simulation:
            cible.parent.mkdir(exist_ok=True)
            shutil.move(str(f), str(cible))
        deplaces += 1
    return deplaces


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("dossier", nargs="?", default=str(Path.home() / "Downloads"))
    p.add_argument("--simulation", action="store_true", help="n'effectue aucun déplacement")
    p.add_argument("--surveiller", action="store_true", help="trie en boucle toutes les 30 s")
    a = p.parse_args()

    dossier = Path(a.dossier).expanduser()
    if not dossier.is_dir():
        raise SystemExit(f"Dossier introuvable : {dossier}")

    if a.surveiller:
        print(f"Surveillance de {dossier} (Ctrl+C pour arrêter)")
        try:
            while True:
                trier(dossier, a.simulation)
                time.sleep(30)
        except KeyboardInterrupt:
            print("\nArrêté.")
    else:
        n = trier(dossier, a.simulation)
        print(f"\n{n} fichier(s) {'à déplacer' if a.simulation else 'déplacé(s)'}.")


if __name__ == "__main__":
    main()
