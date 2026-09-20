"""Lectura de estudios DICOM: indexado, orden anatomico y render a PNG."""

from __future__ import annotations

import base64
import io
import threading
import xml.etree.ElementTree as ET
from collections import OrderedDict
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pydicom
from PIL import Image

try:
    from pydicom.pixels import apply_modality_lut
except ImportError:                                  # pydicom 2.x
    from pydicom.pixel_data_handlers.util import apply_modality_lut


# (centro, ancho) en Hounsfield: los mismos ajustes que trae cualquier
# estacion de radiologia, para no buscarlos a mano cada vez.
PRESETS = OrderedDict([
    ("Automatico", None),
    ("Cerebro", (40.0, 80.0)),
    ("Subdural", (75.0, 215.0)),
    ("Hueso", (500.0, 2000.0)),
    ("Pulmon", (-600.0, 1500.0)),
    ("Mediastino", (50.0, 350.0)),
    ("Abdomen", (60.0, 400.0)),
    ("Higado", (30.0, 150.0)),
    ("Angio", (300.0, 600.0)),
])

CACHE_MB = 280          # techo de memoria de la cache de cortes decodificados


def _num(v, default=0.0):
    """Los valores DICOM llegan como DSfloat, IS o lista; aplana a float."""
    try:
        if v is None:
            return default
        if hasattr(v, "__len__") and not isinstance(v, str):
            v = v[0]
        return float(v)
    except Exception:
        return default


@dataclass
class Frame:
    path: Path
    frame: int
    order: float


class Series:
    def __init__(self, head: pydicom.Dataset, uid: str):
        self.head = head
        self.uid = uid
        self.frames: list[Frame] = []
        self.ventana_xml = None          # la que dejo guardada el programa del escaner
        self._cache = OrderedDict()
        self._bytes = 0
        self._lock = threading.Lock()

    # --- identidad -------------------------------------------------------
    @property
    def modality(self) -> str:
        return str(self.head.get("Modality", "??"))

    @property
    def description(self) -> str:
        d = self.head.get("SeriesDescription") or self.head.get("StudyDescription")
        return str(d) if d else "sin descripcion"

    @property
    def label(self) -> str:
        return f"{self.modality}   {self.description}   ({len(self.frames)})"

    @property
    def mono1(self) -> bool:
        return str(self.head.get("PhotometricInterpretation", "")).strip() == "MONOCHROME1"

    @property
    def units(self) -> str:
        return "HU" if self.modality == "CT" else ""

    @property
    def spacing(self):
        """(alto, ancho) de pixel normalizado: los pixeles no siempre son cuadrados."""
        ps = self.head.get("PixelSpacing") or self.head.get("ImagerPixelSpacing")
        if not ps:
            return 1.0, 1.0
        sy, sx = _num(ps[0], 1.0), _num(ps[1], 1.0)
        m = min(sy, sx) or 1.0
        return sy / m, sx / m

    # --- pixeles ---------------------------------------------------------
    def en_cache(self, i: int) -> bool:
        f = self.frames[i]
        with self._lock:
            return (str(f.path), f.frame) in self._cache

    def pixels(self, i: int) -> np.ndarray:
        f = self.frames[i]
        key = (str(f.path), f.frame)
        with self._lock:
            hit = self._cache.get(key)
            if hit is not None:
                self._cache.move_to_end(key)
                return hit

        # descomprimir cuesta ~90 ms en un CBCT: se hace FUERA del lock para que
        # la precarga y la interfaz no se esperen la una a la otra
        ds = pydicom.dcmread(f.path)
        arr = ds.pixel_array
        if int(_num(ds.get("NumberOfFrames"), 1)) > 1:
            arr = arr[f.frame]
        out = arr.astype(np.uint8) if arr.ndim == 3 else apply_modality_lut(arr, ds).astype(np.float32)

        with self._lock:
            if key not in self._cache:
                self._cache[key] = out
                self._bytes += out.nbytes
                while self._bytes > CACHE_MB * 1024 * 1024 and len(self._cache) > 4:
                    self._bytes -= self._cache.popitem(last=False)[1].nbytes
        return out

    def suggested_window(self, i: int):
        c, w = self.head.get("WindowCenter"), self.head.get("WindowWidth")
        if c is not None and w is not None and _num(w) > 0:
            return _num(c), _num(w)
        a = self.pixels(i)
        if a.ndim == 3:
            return 128.0, 255.0
        lo, hi = (float(x) for x in np.percentile(a, (0.5, 99.5)))
        if hi <= lo:
            hi = lo + 1.0
        return (lo + hi) / 2.0, hi - lo

    def value_at(self, i: int, px: int, py: int):
        a = self.pixels(i)
        if not (0 <= py < a.shape[0] and 0 <= px < a.shape[1]):
            return None
        v = a[py, px]
        return tuple(int(x) for x in v) if a.ndim == 3 else float(v)

    def shape(self, i: int):
        a = self.pixels(i)
        return a.shape[1], a.shape[0]

    # --- render ----------------------------------------------------------
    def imagen(self, i, wc, ww, invert=False) -> Image.Image:
        """El corte pasado por ventana/nivel, en pixeles crudos y sin escalar."""
        a = self.pixels(i)
        if a.ndim == 3:
            return Image.fromarray(a, "RGB")
        ww = max(float(ww), 1e-3)
        g = np.clip((a - (float(wc) - ww / 2.0)) / ww, 0.0, 1.0)
        if self.mono1 != invert:
            g = 1.0 - g
        return Image.fromarray((g * 255.0).astype(np.uint8), "L")

    def encajar(self, img, box_w, box_h, zoom=1.0, par=False):
        """Escala para caber en la caja respetando PixelSpacing; `par` fuerza lados pares (el video los exige)."""
        sy, sx = self.spacing
        k = min(box_w / (img.width * sx), box_h / (img.height * sy)) * zoom
        w, h = max(1, round(img.width * sx * k)), max(1, round(img.height * sy * k))
        if par:
            w, h = max(2, w - w % 2), max(2, h - h % 2)
        rs = Image.Resampling.LANCZOS if k < 1 else Image.Resampling.NEAREST
        return img.resize((w, h), rs)

    def render(self, i, wc, ww, box_w, box_h, zoom=1.0, invert=False):
        """Devuelve (png_base64, ancho, alto) escalado para caber en la caja."""
        img = self.encajar(self.imagen(i, wc, ww, invert), box_w, box_h, zoom)
        buf = io.BytesIO()
        img.save(buf, "PNG", compress_level=1)      # el 6 por defecto cuesta 21 ms por fotograma
        return base64.b64encode(buf.getvalue()).decode(), img.width, img.height

    # --- cabecera --------------------------------------------------------
    def info(self, i: int, anonimo: bool = True):
        h = self.head
        ds = pydicom.dcmread(self.frames[i].path, stop_before_pixels=True)
        ancho, alto = self.shape(i)
        ps = h.get("PixelSpacing")
        meta = getattr(h, "file_meta", None)
        ts = getattr(meta, "TransferSyntaxUID", None) if meta else None
        oculto = "-- oculto --"

        campos = [
            ("Paciente", oculto if anonimo else str(h.get("PatientName", "-"))),
            ("ID", oculto if anonimo else str(h.get("PatientID", "-"))),
            ("Nacimiento", oculto if anonimo else str(h.get("PatientBirthDate", "-"))),
            ("Sexo", str(h.get("PatientSex", "-"))),
            ("Modalidad", self.modality),
            ("Estudio", str(h.get("StudyDescription", "-"))),
            ("Serie", self.description),
            ("Fecha", str(h.get("StudyDate", "-"))),
            ("Equipo", f"{h.get('Manufacturer', '')} {h.get('ManufacturerModelName', '')}".strip()),
            ("Matriz", f"{ancho} x {alto}"),
            ("Pixel mm", f"{_num(ps[0]):.3f} x {_num(ps[1]):.3f}" if ps else "-"),
            ("Grosor mm", f"{_num(h.get('SliceThickness')):.2f}" if h.get("SliceThickness") is not None else "-"),
            ("Posicion", f"{_num(ds.get('SliceLocation')):.2f}" if ds.get("SliceLocation") is not None else "-"),
            ("Instancia", str(ds.get("InstanceNumber", "-"))),
            ("kVp / mAs", f"{h.get('KVP', '-')} / {h.get('Exposure', '-')}"),
            ("Bits", str(h.get("BitsStored", "-"))),
            ("Fotometria", str(h.get("PhotometricInterpretation", "-"))),
            ("Compresion", ts.name if ts is not None else "-"),
        ]
        return [(k, v if v and v not in ("None", "None None") else "-") for k, v in campos]


def ventana_de_analisis(carpeta: Path):
    """CS 3D Imaging y compania guardan en un XML la ventana con la que se REVISO el
    estudio; vale mas que la de la cabecera, que suele ser el rango entero del equipo."""
    for xml in list(carpeta.glob("Analyses/*.xml")) + list(carpeta.glob("*.xml")):
        try:
            for nodo in ET.parse(xml).iter("Lut2D"):
                wl, ww = _num(nodo.get("windowlevel"), 0), _num(nodo.get("windowwidth"), 0)
                if ww > 0:
                    return wl, ww
        except Exception:
            continue
    return None


def _order_key(ds: pydicom.Dataset, fallback: float) -> float:
    """Proyectar el origen sobre la normal del plano ordena bien hasta en cortes oblicuos."""
    ipp, iop = ds.get("ImagePositionPatient"), ds.get("ImageOrientationPatient")
    if ipp is not None and iop is not None and len(iop) == 6:
        try:
            r = np.array([float(x) for x in iop[:3]])
            c = np.array([float(x) for x in iop[3:]])
            p = np.array([float(x) for x in ipp])
            return float(np.dot(p, np.cross(r, c)))
        except Exception:
            pass
    if ipp is not None:
        return _num(ipp[2], fallback)
    for tag in ("InstanceNumber", "SliceLocation"):
        if ds.get(tag) is not None:
            return _num(ds.get(tag), fallback)
    return fallback


def load_study(root, on_progress=None):
    """Indexa una carpeta (o un archivo) y devuelve sus series ya ordenadas."""
    root = Path(root)
    files = [root] if root.is_file() else sorted(p for p in root.rglob("*") if p.is_file())
    grupos = OrderedDict()

    for n, p in enumerate(files):
        if on_progress and (n % 8 == 0 or n == len(files) - 1):
            on_progress(n + 1, len(files))
        if p.name.upper() == "DICOMDIR":
            continue
        try:
            ds = pydicom.dcmread(p, stop_before_pixels=True, force=False)
        except Exception:
            continue
        if "Rows" not in ds:
            continue

        uid = str(ds.get("SeriesInstanceUID") or p.parent)
        serie = grupos.get(uid)
        if serie is None:
            serie = grupos[uid] = Series(ds, uid)
        base = _order_key(ds, float(n))
        for k in range(max(1, int(_num(ds.get("NumberOfFrames"), 1)))):
            serie.frames.append(Frame(p, k, base + k * 1e-3))

    series = list(grupos.values())
    ventana = ventana_de_analisis(root if root.is_dir() else root.parent)
    for s in series:
        s.frames.sort(key=lambda f: f.order)
        s.ventana_xml = ventana
    series.sort(key=lambda s: len(s.frames), reverse=True)
    return series
