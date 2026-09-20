"""Que hay instalado y que hace falta. El visor no depende de que el equipo
tenga nada: lo comprueba y lo dice, en vez de fallar a medio camino."""

from __future__ import annotations

import importlib
import platform
import shutil
import sys
from pathlib import Path

# (modulo, para que sirve, imprescindible)
PIEZAS = [
    ("flet", "interfaz", True),
    ("pydicom", "lectura DICOM", True),
    ("numpy", "calculo de pixeles", True),
    ("PIL", "render de imagen", True),
    ("gdcm", "descompresion rapida (JPEG sin perdida)", False),
    ("pylibjpeg", "descompresion de respaldo", False),
    ("openjpeg", "descompresion JPEG 2000", False),
    ("imageio", "exportar video", False),
    ("imageio_ffmpeg", "codificador de video", False),
]


def _version(modulo) -> str:
    for atributo in ("__version__", "version", "VERSION"):
        v = getattr(modulo, atributo, None)
        if isinstance(v, str):
            return v
    return "instalado"


def revisar() -> list[dict]:
    """Una fila por pieza: nombre, para que sirve, si esta y con que version."""
    filas = []
    for nombre, para, obligatoria in PIEZAS:
        try:
            mod = importlib.import_module(nombre)
            filas.append({"pieza": nombre, "para": para, "hay": True,
                          "detalle": _version(mod), "obligatoria": obligatoria})
        except Exception:
            filas.append({"pieza": nombre, "para": para, "hay": False,
                          "detalle": "no instalado", "obligatoria": obligatoria})

    filas.append(_ffmpeg())
    filas.append(_decodificadores())
    return filas


def _ffmpeg() -> dict:
    ruta = shutil.which("ffmpeg")
    if not ruta:
        try:
            import imageio_ffmpeg
            exe = imageio_ffmpeg.get_ffmpeg_exe()
            ruta = exe if Path(exe).exists() else None
        except Exception:
            ruta = None
    return {"pieza": "ffmpeg", "para": "exportar MP4", "hay": bool(ruta),
            "detalle": Path(ruta).name if ruta else "no disponible", "obligatoria": False}


def _decodificadores() -> dict:
    """Los que pydicom puede usar de verdad para abrir imagen comprimida."""
    try:
        import pydicom.config
        vivos = [h.__name__.rsplit(".", 1)[-1].replace("_handler", "")
                 for h in pydicom.config.pixel_data_handlers if h.is_available()]
    except Exception:
        vivos = []
    return {"pieza": "decodificadores", "para": "formatos comprimidos",
            "hay": bool(vivos), "detalle": ", ".join(vivos) or "ninguno",
            "obligatoria": True}


def equipo() -> list[tuple[str, str]]:
    return [
        ("Sistema", f"{platform.system()} {platform.release()} ({platform.machine()})"),
        ("Python", sys.version.split()[0]),
        ("Ejecutable", "empaquetado" if getattr(sys, "frozen", False) else sys.executable),
    ]


def resumen(filas) -> tuple[int, int]:
    """(cuantas piezas hay, cuantas faltan de las imprescindibles)."""
    return (sum(1 for f in filas if f["hay"]),
            sum(1 for f in filas if f["obligatoria"] and not f["hay"]))
