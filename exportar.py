"""Sacar la secuencia a imagenes sueltas, GIF animado o video MP4."""

from __future__ import annotations

import re
from pathlib import Path

import numpy as np
from PIL import Image

FORMATOS = ("PNG (imagenes)", "GIF animado", "MP4 (video)")
TAMANIOS = {"Original": 0, "512 px": 512, "768 px": 768, "1024 px": 1024, "1600 px": 1600}


def nombre_limpio(t: str) -> str:
    t = re.sub(r"[^\w\-. ]+", "", str(t)).strip().replace(" ", "_")
    return t[:60] or "serie"


def _cuadros(serie, i0, i1, wc, ww, invert, lado, par, avance=None):
    total = i1 - i0 + 1
    for n, i in enumerate(range(i0, i1 + 1)):
        img = serie.imagen(i, wc, ww, invert)
        # lado 0 = tamanio original: la caja se calcula para que la escala salga 1
        sy, sx = serie.spacing
        caja = (lado, lado) if lado else (img.width * sx, img.height * sy)
        yield serie.encajar(img, caja[0], caja[1], 1.0, par)
        if avance:
            avance(n + 1, total)


def exportar(formato, destino: Path, serie, i0, i1, wc, ww, invert, lado, fps, avance=None) -> Path:
    """Devuelve la ruta creada. `destino` es carpeta para PNG y archivo para GIF/MP4."""
    if formato.startswith("PNG"):
        return _png(destino, serie, i0, i1, wc, ww, invert, lado, avance)
    if formato.startswith("GIF"):
        return _gif(destino, serie, i0, i1, wc, ww, invert, lado, fps, avance)
    return _mp4(destino, serie, i0, i1, wc, ww, invert, lado, fps, avance)


def _png(carpeta: Path, serie, i0, i1, wc, ww, invert, lado, avance):
    carpeta.mkdir(parents=True, exist_ok=True)
    base = nombre_limpio(serie.description)
    for n, img in enumerate(_cuadros(serie, i0, i1, wc, ww, invert, lado, False, avance)):
        img.save(carpeta / f"{base}_{i0 + n + 1:04d}.png")
    return carpeta


def _gif(destino: Path, serie, i0, i1, wc, ww, invert, lado, fps, avance):
    destino.parent.mkdir(parents=True, exist_ok=True)
    cuadros = list(_cuadros(serie, i0, i1, wc, ww, invert, lado, False, avance))
    # en gris el GIF ya sale con paleta de 256; solo el color necesita cuantizar
    cuadros = [c if c.mode == "L" else c.convert("P", palette=Image.Palette.ADAPTIVE, colors=256) for c in cuadros]
    cuadros[0].save(destino, save_all=True, append_images=cuadros[1:],
                    duration=max(20, round(1000 / max(1, fps))), loop=0, optimize=True)
    return destino


def _mp4(destino: Path, serie, i0, i1, wc, ww, invert, lado, fps, avance):
    import imageio.v2 as imageio

    destino.parent.mkdir(parents=True, exist_ok=True)
    escritor = imageio.get_writer(destino, fps=max(1, fps), codec="libx264",
                                  quality=8, macro_block_size=1)
    try:
        for img in _cuadros(serie, i0, i1, wc, ww, invert, lado, True, avance):
            escritor.append_data(np.asarray(img.convert("RGB")))
    finally:
        escritor.close()
    return destino
