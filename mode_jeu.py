#!/usr/bin/env python3
"""Mode jeu pour Windows : deux raccourcis globaux.

  Ctrl+Alt+F9  -> ACTIVER : ferme Edge, jeu en priorité haute, Discord en priorité basse,
                  mode d'alimentation Performances, affiche les processus les plus gourmands.
  Ctrl+Alt+F10 -> RESTAURER : remet les priorités et le mode d'alimentation d'avant.
  Ctrl+C dans la console -> quitter.

Le « jeu » est la fenêtre au premier plan au moment où tu appuies sur Ctrl+Alt+F9.
Installation : pip install psutil
"""
import ctypes
import ctypes.wintypes as wt
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

import psutil

ETAT = Path(os.environ.get("LOCALAPPDATA", Path.home())) / "mode_jeu_etat.json"
GUID_PERFORMANCES = "8c5e7fda-e8bf-4a96-9a85-a6e23a8c635c"
NOMS_EDGE = "msedge.exe"
# Fenêtres qu'on ne considère jamais comme « le jeu »
IGNORES = {"explorer.exe", "cmd.exe", "powershell.exe", "pwsh.exe", "python.exe", "pythonw.exe",
           "windowsterminal.exe", "conhost.exe", "discord.exe", "msedge.exe", "searchhost.exe"}
NIVEAUX = {
    "haute": psutil.HIGH_PRIORITY_CLASS if sys.platform == "win32" else 0,
    "basse": psutil.BELOW_NORMAL_PRIORITY_CLASS if sys.platform == "win32" else 0,
}

MOD_ALT, MOD_CONTROL, MOD_NOREPEAT = 0x1, 0x2, 0x4000
VK_F9, VK_F10 = 0x78, 0x79
WM_HOTKEY = 0x0312


def processus_au_premier_plan():
    user32 = ctypes.windll.user32
    hwnd = user32.GetForegroundWindow()
    pid = wt.DWORD()
    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    try:
        return psutil.Process(pid.value)
    except psutil.Error:
        return None


def lire_plan_actif():
    sortie = subprocess.run(["powercfg", "/getactivescheme"], capture_output=True, text=True).stdout
    m = re.search(r"([0-9a-fA-F]{8}(?:-[0-9a-fA-F]{4}){3}-[0-9a-fA-F]{12})", sortie)
    return m.group(1).lower() if m else None


def activer_performances():
    """Active le plan Performances ; le crée s'il est masqué (cas fréquent sur portables)."""
    if subprocess.run(["powercfg", "/setactive", GUID_PERFORMANCES], capture_output=True).returncode == 0:
        return True
    dup = subprocess.run(["powercfg", "/duplicatescheme", GUID_PERFORMANCES], capture_output=True, text=True)
    m = re.search(r"([0-9a-fA-F]{8}(?:-[0-9a-fA-F]{4}){3}-[0-9a-fA-F]{12})", dup.stdout)
    return bool(m) and subprocess.run(["powercfg", "/setactive", m.group(1)], capture_output=True).returncode == 0


def fermer_edge():
    """Fermeture propre d'abord (laisse Edge sauvegarder), puis forcée pour les restes."""
    if not any(p.name().lower() == NOMS_EDGE for p in psutil.process_iter()):
        return False
    subprocess.run(["taskkill", "/IM", NOMS_EDGE], capture_output=True)
    time.sleep(3)
    subprocess.run(["taskkill", "/F", "/IM", NOMS_EDGE], capture_output=True)
    return True


def changer_priorite(proc, niveau):
    """Renvoie l'ancienne priorité, ou None si Windows refuse (anti-cheat, droits...)."""
    try:
        ancienne = proc.nice()
        proc.nice(NIVEAUX[niveau])
        return ancienne
    except psutil.Error:
        return None


def top_cpu(n=8, duree=2.0):
    procs = list(psutil.process_iter(["name"]))
    for p in procs:
        try:
            p.cpu_percent(None)
        except psutil.Error:
            pass
    time.sleep(duree)
    mesures = []
    for p in procs:
        try:
            mesures.append((p.cpu_percent(None) / psutil.cpu_count(), p.info["name"], p.pid))
        except psutil.Error:
            pass
    print(f"\nTop {n} CPU (sur {duree:.0f} s, % du CPU total) :")
    for cpu, nom, pid in sorted(mesures, reverse=True)[:n]:
        print(f"  {cpu:5.1f} %  {nom} (pid {pid})")


def activer():
    if ETAT.exists():
        print("Mode jeu déjà actif. Ctrl+Alt+F10 pour restaurer d'abord.")
        return
    etat = {"plan": lire_plan_actif(), "priorites": {}, "edge_ferme": False}

    jeu = processus_au_premier_plan()
    if jeu is None or jeu.name().lower() in IGNORES:
        print("Aucun jeu détecté au premier plan : lance le raccourci DEPUIS le jeu.")
    else:
        ancienne = changer_priorite(jeu, "haute")
        if ancienne is None:
            print(f"Impossible de changer la priorité de {jeu.name()} (essaie en administrateur).")
        else:
            etat["priorites"][str(jeu.pid)] = [jeu.name(), ancienne]
            print(f"Jeu : {jeu.name()} -> priorité haute")

    n = 0
    for p in psutil.process_iter(["name"]):
        if p.info["name"] and p.info["name"].lower() == "discord.exe":
            ancienne = changer_priorite(p, "basse")
            if ancienne is not None:
                etat["priorites"][str(p.pid)] = ["discord.exe", ancienne]
                n += 1
    print(f"Discord : {n} processus -> priorité basse" if n else "Discord non trouvé.")

    etat["edge_ferme"] = fermer_edge()
    print("Edge fermé." if etat["edge_ferme"] else "Edge n'était pas ouvert.")

    print("Mode Performances activé." if activer_performances() else "Échec du changement de mode d'alimentation.")
    ETAT.write_text(json.dumps(etat), encoding="utf-8")
    top_cpu()


def restaurer():
    if not ETAT.exists():
        print("Rien à restaurer (mode jeu pas activé).")
        return
    etat = json.loads(ETAT.read_text(encoding="utf-8"))
    for pid, (nom, ancienne) in etat["priorites"].items():
        try:
            p = psutil.Process(int(pid))
            if p.name().lower() == nom.lower():  # évite de toucher un pid réutilisé
                p.nice(ancienne)
                print(f"{nom} (pid {pid}) : priorité d'origine remise")
        except psutil.Error:
            print(f"{nom} (pid {pid}) : fermé entre-temps, ignoré")
    if etat.get("plan"):
        subprocess.run(["powercfg", "/setactive", etat["plan"]], capture_output=True)
        print("Mode d'alimentation d'origine remis.")
    if etat.get("edge_ferme"):
        print("Edge a été fermé : rouvre-le toi-même (Ctrl+Maj+T récupère les onglets).")
    ETAT.unlink()


def main():
    if sys.platform != "win32":
        raise SystemExit("Ce script ne fonctionne que sous Windows.")
    user32 = ctypes.windll.user32
    for ident, vk in ((1, VK_F9), (2, VK_F10)):
        if not user32.RegisterHotKey(None, ident, MOD_CONTROL | MOD_ALT | MOD_NOREPEAT, vk):
            raise SystemExit("Raccourci déjà pris par un autre programme.")
    print("Prêt. Ctrl+Alt+F9 = activer | Ctrl+Alt+F10 = restaurer | Ctrl+C = quitter")
    msg = wt.MSG()
    try:
        while user32.GetMessageW(ctypes.byref(msg), None, 0, 0) != 0:
            if msg.message == WM_HOTKEY:
                activer() if msg.wParam == 1 else restaurer()
    except KeyboardInterrupt:
        pass
    finally:
        user32.UnregisterHotKey(None, 1)
        user32.UnregisterHotKey(None, 2)


if __name__ == "__main__":
    main()
