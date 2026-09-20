"""Registro local de estudios: la lista de trabajo del visor.

Vive en %APPDATA%\\DCM Viewer\\registro.json. Se escribe entero en cada cambio
porque son unos pocos kilobytes; no merece complicarlo mas.
"""

from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path

CARPETA = Path(os.getenv("APPDATA") or Path.home()) / "DCM Viewer"
FICHERO = CARPETA / "registro.json"
TOPE = 200                      # el registro no crece sin limite

PENDIENTE, REVISADO = "PENDIENTE", "REVISADO"


def cargar() -> list[dict]:
    try:
        datos = json.loads(FICHERO.read_text(encoding="utf-8"))
        return [d for d in datos if isinstance(d, dict) and d.get("ruta")]
    except Exception:
        return []


def guardar(registros: list[dict]) -> None:
    try:
        CARPETA.mkdir(parents=True, exist_ok=True)
        FICHERO.write_text(json.dumps(registros[:TOPE], ensure_ascii=False, indent=1),
                           encoding="utf-8")
    except Exception:
        pass                    # que un registro no escribible no tumbe el visor


def _buscar(registros, ruta):
    ruta = str(ruta)
    return next((r for r in registros if r.get("ruta") == ruta), None)


def anotar(ruta, **datos) -> list[dict]:
    """Apunta el estudio recien abierto (o lo sube al principio si ya estaba)."""
    registros = cargar()
    ficha = _buscar(registros, ruta)
    if ficha is None:
        ficha = {"ruta": str(ruta), "estado": PENDIENTE, "nota": "", "veces": 0}
    else:
        registros.remove(ficha)
    ficha.update({k: v for k, v in datos.items() if v is not None})
    ficha["veces"] = int(ficha.get("veces", 0)) + 1
    ficha["abierto"] = datetime.now().strftime("%Y-%m-%d %H:%M")
    registros.insert(0, ficha)
    guardar(registros)
    return registros


def actualizar(ruta, **campos) -> list[dict]:
    registros = cargar()
    ficha = _buscar(registros, ruta)
    if ficha:
        ficha.update(campos)
        guardar(registros)
    return registros


def quitar(ruta) -> list[dict]:
    registros = [r for r in cargar() if r.get("ruta") != str(ruta)]
    guardar(registros)
    return registros


def existe(ruta) -> bool:
    try:
        return Path(ruta).exists()
    except Exception:
        return False


def filtrar(registros, texto):
    texto = (texto or "").strip().lower()
    if not texto:
        return registros
    def casa(r):
        campos = (r.get("serie", ""), r.get("modalidad", ""), r.get("nota", ""),
                  r.get("paciente", ""), r.get("ruta", ""), r.get("estado", ""))
        return any(texto in str(c).lower() for c in campos)
    return [r for r in registros if casa(r)]
