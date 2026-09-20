"""Buscar y aplicar actualizaciones.

Es la UNICA parte del programa que toca la red, y solo cuando el usuario lo
pide: o pulsa "buscar ahora", o deja puesto el aviso al arrancar (que viene
apagado). Sin telemetria: se pide un JSON publico y no se manda nada.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
import tempfile
import urllib.request
from pathlib import Path

REPO = "Losif24/dcm-viewer"
API = f"https://api.github.com/repos/{REPO}/releases/latest"
PAGINA = f"https://github.com/{REPO}/releases/latest"
ESPERA = 6


def _numeros(v: str) -> tuple:
    return tuple(int(n) for n in re.findall(r"\d+", v or "")[:4]) or (0,)


def hay_mas_nueva(instalada: str, publicada: str) -> bool:
    return _numeros(publicada) > _numeros(instalada)


def ultima() -> dict | None:
    """La ultima version publicada, o None si no se pudo preguntar."""
    try:
        pet = urllib.request.Request(API, headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": "DCM-Viewer",          # GitHub exige identificarse
        })
        with urllib.request.urlopen(pet, timeout=ESPERA) as r:
            datos = json.loads(r.read().decode("utf-8"))
    except Exception:
        return None

    instalador = next((a["browser_download_url"] for a in datos.get("assets", [])
                       if a.get("name", "").lower().endswith(".exe")), None)
    return {
        "version": (datos.get("tag_name") or "").lstrip("vV"),
        "notas": (datos.get("body") or "").strip(),
        "pagina": datos.get("html_url") or PAGINA,
        "instalador": instalador,
        "tamanio": next((a.get("size", 0) for a in datos.get("assets", [])
                         if a.get("browser_download_url") == instalador), 0),
    }


def descargar(url: str, avance=None) -> Path:
    """Trae el instalador a la carpeta temporal y devuelve su ruta."""
    destino = Path(tempfile.gettempdir()) / Path(url).name
    pet = urllib.request.Request(url, headers={"User-Agent": "DCM-Viewer"})
    with urllib.request.urlopen(pet, timeout=30) as r, open(destino, "wb") as f:
        total = int(r.headers.get("Content-Length") or 0)
        leido = 0
        while True:
            trozo = r.read(262144)
            if not trozo:
                break
            f.write(trozo)
            leido += len(trozo)
            if avance:
                avance(leido, total)
    return destino


def instalar(ruta: Path) -> None:
    """Lanza el instalador y se quita de en medio: no puede actualizarse a si mismo
    con el programa abierto."""
    subprocess.Popen([str(ruta), "/SILENT", "/NOCANCEL"], close_fds=True)
    sys.exit(0)
