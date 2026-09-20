"""DCM Viewer - visor de series DICOM."""

import os
import sys
import threading
import time
from collections import deque
from pathlib import Path

import flet as ft

import dicomio as dio
import entorno
import exportar as expo
import registro as reg

# Escala de negros: cada superficie un peldanio por encima de la de abajo.
# El lienzo se queda en negro puro a proposito: el negro del DICOM tambien es #000000
# y si el fondo esta un pelo mas claro se ve el recuadro donde acaba la imagen.
BG, CHROME, PANEL, ELEV = "#000000", "#181818", "#1E1E1E", "#262626"
LINE, TXT, DIM, TINTA, ACC = "#333333", "#FFFFFF", "#9A9A9A", "#000000", "#FFFFFF"
MONO = "Consolas"
VERSION = "1.0.0"

TOPBAR, BOTBAR, ALTO = 36, 54, 26          # ALTO: todo lo interactivo de la barra mide igual
ASIDE_MIN, ASIDE_MAX, ASIDE_DEF, DIVISOR = 160, 520, 232, 6


def area_util():
    """El escritorio SIN la barra de tareas: si la ventana no cabe, Windows la deja coja."""
    try:
        import ctypes
        from ctypes import wintypes
        r = wintypes.RECT()
        if ctypes.windll.user32.SystemParametersInfoW(0x0030, 0, ctypes.byref(r), 0):
            if r.right > r.left and r.bottom > r.top:
                return r.left, r.top, r.right - r.left, r.bottom - r.top
    except Exception:
        pass
    return 0, 0, 1280, 720


def ventana_app(titulo):
    """La ventana de la app buscada por titulo Y por clase de Flutter: una carpeta del
    explorador que se llame igual no es nuestra ventana y no hay que tocarla."""
    try:
        import ctypes
        from ctypes import wintypes
        u = ctypes.windll.user32
        halladas = []

        def visita(hwnd, _):
            largo = u.GetWindowTextLengthW(hwnd)
            if largo:
                texto = ctypes.create_unicode_buffer(largo + 1)
                u.GetWindowTextW(hwnd, texto, largo + 1)
                if texto.value == titulo:
                    clase = ctypes.create_unicode_buffer(128)
                    u.GetClassNameW(hwnd, clase, 128)
                    if "FLUTTER" in clase.value.upper():
                        halladas.append(hwnd)
                        return False
            return True

        u.EnumWindows(ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)(visita), 0)
        return halladas[0] if halladas else 0
    except Exception:
        return 0


def quitar_barra_windows(titulo, intentos=40):
    """Flet dice quitar la barra de titulo, pero en Windows llega tarde y la deja puesta:
    se comprueba el estilo real de la ventana y, si sigue el WS_CAPTION, se le quita.
    Se conserva WS_THICKFRAME, asi que los bordes siguen redimensionando."""
    GWL_STYLE, WS_CAPTION = -16, 0x00C00000
    REDIBUJA_MARCO = 0x0027          # SWP_FRAMECHANGED | NOMOVE | NOSIZE | NOZORDER
    BORDE, CAPTION = 34, 35          # atributos DWM de color de marco
    try:
        import ctypes
        u, dwm = ctypes.windll.user32, ctypes.windll.dwmapi
        r, g, b = (int(CHROME[i:i + 2], 16) for i in (1, 3, 5))
        color = ctypes.c_uint((b << 16) | (g << 8) | r)      # COLORREF 0x00BBGGRR
        for _ in range(intentos):
            hwnd = ventana_app(titulo)
            if hwnd:
                estilo = u.GetWindowLongW(hwnd, GWL_STYLE)
                if estilo & WS_CAPTION:
                    u.SetWindowLongW(hwnd, GWL_STYLE, estilo & ~WS_CAPTION)
                    u.SetWindowPos(hwnd, 0, 0, 0, 0, 0, REDIBUJA_MARCO)
                # sin caption queda una franja gris del borde de redimensionar: se tinta
                for attr in (BORDE, CAPTION):
                    dwm.DwmSetWindowAttribute(hwnd, attr, ctypes.byref(color), 4)
                return True
            time.sleep(0.1)
    except Exception:
        pass
    return False


def cerrar_ventana(titulo):
    """El `windowClose` de Flet no hace nada en este cliente de Windows: se manda un
    WM_CLOSE a la ventana y, si aun asi sigue viva, se corta el proceso."""
    try:
        import ctypes
        hwnd = ventana_app(titulo)
        if hwnd:
            ctypes.windll.user32.PostMessageW(hwnd, 0x0010, 0, 0)      # WM_CLOSE
    except Exception:
        pass
    time.sleep(0.8)
    os._exit(0)


def rotulo(t, size=9, color=DIM, mono=False, **kw):
    return ft.Text(t, size=size, color=color, font_family=MONO if mono else None, **kw)


class Visor:
    def __init__(self, page: ft.Page):
        self.page = page
        self.series, self.s, self.i = [], None, 0
        self.wc = self.ww = 0.0
        self.zoom, self.pan = 1.0, [0.0, 0.0]
        self.invert, self.anonimo = False, True
        self.modo = "wl"
        self.cine, self.fps = False, 12
        self.maximizada = False
        self.escribiendo = False
        self.ruta_estudio = None
        self.aside_w, self.aside_abierto, self.aside_auto = ASIDE_DEF, True, False
        self.ancho, self.alto = 1280.0, 800.0
        self.box = [1280.0 - ASIDE_DEF, 600.0]
        self.geo = (0.0, 0.0, 1.0, 1.0)
        self.construir()

    # ------------------------------------------------------------------ UI
    def construir(self):
        p = self.page
        p.title = "DCM Viewer"
        p.bgcolor = BG
        p.padding = 0
        p.theme_mode = ft.ThemeMode.DARK
        if not p.web:                                # en navegador manda la pestania
            x, y, aw, ah = area_util()
            ancho, alto = min(1320, aw - 24), min(880, ah - 40)
            p.window.width, p.window.height = ancho, alto
            p.window.left, p.window.top = x + max(0, (aw - ancho) // 2), y + 8
            p.window.min_width, p.window.min_height = 680, 420
            p.window.resizable = p.window.movable = p.window.maximizable = True
            # una sola cabecera: se quita la de Windows y la barra de la app hace de titulo
            p.window.title_bar_hidden = True
            p.window.title_bar_buttons_hidden = True
            p.window.on_event = self.evento_ventana
            threading.Thread(target=quitar_barra_windows, args=(p.title,), daemon=True).start()
        p.on_keyboard_event = self.tecla
        p.on_resized = self.redimensionar

        self.picker = ft.FilePicker(on_result=self.elegido)
        self.picker_dest = ft.FilePicker(on_result=self.elegido_destino)
        p.overlay.extend([self.picker, self.picker_dest])

        # --- barra superior ---
        self.ruta = ft.TextField(
            hint_text="ruta de la carpeta o del archivo .dcm",
            dense=True, filled=True, fill_color=ELEV, border=ft.InputBorder.NONE,
            border_radius=3, color=TXT, hint_style=ft.TextStyle(color="#6E6E6E", size=9),
            text_size=9, content_padding=ft.padding.symmetric(10, 8), expand=3,
            on_change=self.tecleo, on_submit=lambda e: self.abrir(self.ruta.value),
            on_focus=lambda e: setattr(self, "escribiendo", True),
            on_blur=lambda e: setattr(self, "escribiendo", False),
        )
        self.btn_abrir = ft.TextButton(
            "ABRIR", on_click=lambda e: self.abrir(self.ruta.value), height=ALTO,
            style=ft.ButtonStyle(color=TINTA, bgcolor=ACC, padding=ft.padding.symmetric(0, 10),
                                 shape=ft.RoundedRectangleBorder(radius=3),
                                 text_style=ft.TextStyle(size=9, weight=ft.FontWeight.W_700)),
        )
        self.dd_serie = self.selector("serie", expand=2)
        self.dd_preset = self.selector("Automatico", ancho=118)
        self.dd_preset.items = [self.opcion(k, lambda e, k=k: self.poner_preset(k))
                                for k in dio.PRESETS]
        self.btn_max = self.boton(ft.Icons.CROP_SQUARE, "Maximizar",
                                  lambda e: self.ventana("max"), 11, 30)
        # el sobrante de la fila es zona de agarre: sin barra de Windows, de aqui se arrastra
        self.hueco = ft.WindowDragArea(maximizable=True, expand=1,
                                       content=ft.Container(height=TOPBAR))
        logo = ft.WindowDragArea(maximizable=True, content=ft.Container(
            padding=ft.padding.only(2, 0, 10, 0), height=TOPBAR,
            alignment=ft.alignment.center_left,
            content=ft.Row(spacing=3, tight=True, controls=[
                ft.Text("DCM", size=11, weight=ft.FontWeight.W_700, color=TXT),
                ft.Text("VIEWER", size=11, weight=ft.FontWeight.W_300, color=DIM),
            ])))
        barra = ft.Container(
            height=TOPBAR, bgcolor=CHROME, padding=ft.padding.only(8, 0, 2, 0),
            border=ft.border.only(bottom=ft.BorderSide(1, LINE)),
            content=ft.Row(
                spacing=4, vertical_alignment=ft.CrossAxisAlignment.CENTER,
                controls=[
                    logo,
                    self.boton(ft.Icons.FOLDER_OPEN_OUTLINED, "Abrir carpeta",
                               lambda e: self.picker.get_directory_path("Carpeta del estudio")),
                    self.boton(ft.Icons.DESCRIPTION_OUTLINED, "Abrir un archivo",
                               lambda e: self.picker.pick_files("Archivo DICOM", allow_multiple=False)),
                    self.ruta,
                    self.btn_abrir,
                    self.raya(),
                    self.dd_serie,
                    self.dd_preset,
                    self.hueco,
                    self.boton(ft.Icons.FORMAT_LIST_BULLETED, "Registro de estudios (Ctrl+L)",
                               self.dialogo_registro),
                    self.boton(ft.Icons.INFO_OUTLINE, "Estado del sistema (Ctrl+D)",
                               self.dialogo_entorno),
                    self.boton(ft.Icons.FILE_DOWNLOAD_OUTLINED, "Exportar secuencia (Ctrl+E)",
                               self.dialogo_exportar),
                    self.boton(ft.Icons.VIEW_SIDEBAR_OUTLINED, "Mostrar / ocultar el panel (P)",
                               self.alternar_aside),
                    self.raya(),
                    self.boton(ft.Icons.HORIZONTAL_RULE, "Minimizar",
                               lambda e: self.ventana("min"), 11, 30),
                    self.btn_max,
                    self.boton(ft.Icons.CLOSE, "Cerrar", lambda e: self.ventana("cerrar"), 12, 30),
                ],
            ),
        )

        # --- lienzo ---
        self.img = ft.Image(fit=ft.ImageFit.NONE, left=0, top=0, visible=False)
        self.vacio = ft.Container(
            alignment=ft.alignment.center,
            content=ft.Column(
                horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=8,
                controls=[
                    ft.Icon(ft.Icons.IMAGE_SEARCH, size=38, color="#3A3A3A"),
                    rotulo("Abre la carpeta del estudio", 12, "#6E6E6E"),
                    rotulo("rueda = corte     arrastrar = brillo/contraste     espacio = cine",
                           9, "#4E4E4E"),
                ],
            ),
        )
        self.ov_ti, self.ov_td = rotulo("", 9, DIM, True), rotulo("", 9, DIM, True)
        self.ov_ii, self.ov_id = rotulo("", 9, DIM, True), rotulo("", 9, ACC, True)
        self.lienzo = ft.Stack(controls=[
            self.vacio, self.img,
            ft.Container(self.ov_ti, left=10, top=8),
            ft.Container(self.ov_td, right=10, top=8),
            ft.Container(self.ov_ii, left=10, bottom=8),
            ft.Container(self.ov_id, right=10, bottom=8),
        ])
        gestos = ft.GestureDetector(
            content=ft.Container(self.lienzo, bgcolor=BG, expand=True,
                                 clip_behavior=ft.ClipBehavior.HARD_EDGE),
            on_scroll=self.rueda, on_pan_update=self.arrastre, on_hover=self.cursor,
            mouse_cursor=ft.MouseCursor.PRECISE, expand=True,
        )

        # --- divisor arrastrable ---
        self.divisor = ft.GestureDetector(
            content=ft.Container(width=DIVISOR, bgcolor=LINE),
            mouse_cursor=ft.MouseCursor.RESIZE_LEFT_RIGHT,
            on_pan_update=self.mover_divisor, on_double_tap=self.alternar_aside,
        )

        # --- panel derecho ---
        self.sl_wc = self.regla("Nivel", self.mover_wc)
        self.sl_ww = self.regla("Ancho", self.mover_ww)
        self.tabla = ft.Column(spacing=1, scroll=ft.ScrollMode.AUTO, expand=True)
        self.ch_inv = self.chip(ft.Icons.INVERT_COLORS, "Invertir", self.alternar_invertir)
        self.ch_mov = self.chip(ft.Icons.OPEN_WITH, "Mover", self.alternar_modo)
        self.sw_anon = ft.Switch(value=True, scale=0.55, active_color=ACC,
                                 on_change=self.cambiar_anonimo)
        self.aside = ft.Container(
            width=self.aside_w, bgcolor=PANEL, padding=ft.padding.symmetric(8, 10),
            content=ft.Column(
                spacing=6, expand=True,
                controls=[
                    self.titulo("VENTANA"),
                    self.sl_wc, self.sl_ww,
                    ft.Row(spacing=4, wrap=True, controls=[
                        self.ch_inv, self.ch_mov,
                        self.chip(ft.Icons.FIT_SCREEN, "Ajustar", self.ajustar),
                    ]),
                    ft.Divider(height=1, color=LINE),
                    ft.Row([self.titulo("CABECERA"),
                            ft.Row([rotulo("anonimo", 8.5), self.sw_anon], spacing=0)],
                           alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                    self.tabla,
                ],
            ),
        )

        # --- barra inferior ---
        self.slider = ft.Slider(min=0, max=0, value=0, expand=True, height=20,
                                active_color=ACC, inactive_color=ELEV,
                                on_change=self.mover_corte)
        self.btn_cine = self.boton(ft.Icons.PLAY_ARROW_ROUNDED, "Cine (espacio)", self.alternar_cine)
        self.sel_fps = self.selector(f"{self.fps} fps", ancho=74)
        self.sel_fps.items = [self.opcion(f"{v} fps", lambda e, v=v: self.poner_fps(v))
                              for v in (4, 8, 12, 15, 20, 24, 30)]
        self.lbl_estado = rotulo("sin estudio", 9, DIM, expand=True, no_wrap=True,
                                 overflow=ft.TextOverflow.ELLIPSIS)
        self.lbl_px = rotulo("", 9, ACC, True)
        self.progreso = ft.ProgressBar(height=2, color=ACC, bgcolor=ELEV, visible=False)
        pie = ft.Container(
            height=BOTBAR, bgcolor=CHROME, padding=ft.padding.only(8, 3, 6, 3),
            border=ft.border.only(top=ft.BorderSide(1, LINE)),
            content=ft.Column(spacing=0, controls=[
                self.progreso,
                ft.Row(spacing=1, vertical_alignment=ft.CrossAxisAlignment.CENTER, controls=[
                    self.boton(ft.Icons.CHEVRON_LEFT, "Anterior", lambda e: self.paso(-1)),
                    self.slider,
                    self.boton(ft.Icons.CHEVRON_RIGHT, "Siguiente", lambda e: self.paso(1)),
                    self.btn_cine, self.sel_fps, self.raya(),
                    self.boton(ft.Icons.ZOOM_OUT, "Alejar", lambda e: self.escalar(1 / 1.25)),
                    self.boton(ft.Icons.ZOOM_IN, "Acercar", lambda e: self.escalar(1.25)),
                ]),
                ft.Row([self.lbl_estado, self.lbl_px],
                       alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
            ]),
        )

        p.add(ft.Column(spacing=0, expand=True, controls=[
            barra,
            ft.Row([gestos, self.divisor, self.aside], spacing=0, expand=True,
                   vertical_alignment=ft.CrossAxisAlignment.STRETCH),
            pie,
        ]))
        threading.Thread(target=self.medir_tarde, daemon=True).start()
        threading.Thread(target=self.calentador, daemon=True).start()
        if len(sys.argv) > 1:                # se puede arrastrar la carpeta sobre el .bat
            self.abrir(sys.argv[1])

    # --- piezas sueltas ---
    def titulo(self, t):
        return ft.Text(t, size=8, color=DIM, weight=ft.FontWeight.W_600,
                       style=ft.TextStyle(letter_spacing=1.4))

    def boton(self, icono, ayuda, accion, tam=13, ancho=26):
        return ft.IconButton(icon=icono, tooltip=ayuda, on_click=accion, icon_color=DIM,
                             icon_size=tam, width=ancho, height=26,
                             style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=2)))

    def selector(self, texto, ancho=None, expand=None):
        """Desplegable propio: el de Flet mide 46 px hagas lo que hagas y rompia la fila."""
        etq = ft.Text(texto, size=9, color=TXT, no_wrap=True, expand=True,
                      overflow=ft.TextOverflow.ELLIPSIS)
        b = ft.PopupMenuButton(
            items=[], padding=0, bgcolor=PANEL, expand=expand,
            menu_position=ft.PopupMenuPosition.UNDER,
            shape=ft.RoundedRectangleBorder(radius=3),
            content=ft.Container(
                height=ALTO, width=ancho, bgcolor=ELEV, border_radius=3,
                padding=ft.padding.only(8, 0, 4, 0), alignment=ft.alignment.center_left,
                content=ft.Row(spacing=2, vertical_alignment=ft.CrossAxisAlignment.CENTER,
                               controls=[etq, ft.Icon(ft.Icons.EXPAND_MORE, size=13, color=DIM)]),
            ))
        b.etq = etq
        return b

    def opcion(self, texto, accion):
        return ft.PopupMenuItem(height=26, on_click=accion,
                                content=ft.Text(texto, size=9, color=TXT))

    def raya(self):
        """Separador de grupos: la barra se lee por bloques, no como una fila de cosas."""
        return ft.Container(width=1, height=14, bgcolor=LINE,
                            margin=ft.margin.symmetric(0, 3))

    def chip(self, icono, texto, accion):
        return ft.TextButton(
            content=ft.Row([ft.Icon(icono, size=10), ft.Text(texto, size=8.5)], spacing=3, tight=True),
            on_click=accion, height=22,
            style=ft.ButtonStyle(color=DIM, bgcolor=ELEV, padding=ft.padding.symmetric(0, 6),
                                 shape=ft.RoundedRectangleBorder(radius=3)),
        )

    def pintar_chip(self, chip, activo):
        chip.style.color = TINTA if activo else DIM
        chip.style.bgcolor = ACC if activo else ELEV
        chip.update()

    def regla(self, nombre, accion):
        etq, val = rotulo(nombre, 8.5, DIM), rotulo("-", 8.5, TXT, True)
        sl = ft.Slider(min=0, max=1, value=0, height=18, active_color=ACC,
                       inactive_color=ELEV, on_change=accion, expand=True)
        col = ft.Column([ft.Row([etq, val], alignment=ft.MainAxisAlignment.SPACE_BETWEEN), sl],
                        spacing=0)
        col.valor, col.slider = val, sl
        return col

    # -------------------------------------------------------------- cargar
    def elegido(self, e: ft.FilePickerResultEvent):
        if e.path:
            self.abrir(e.path)
        elif e.files:
            self.abrir(e.files[0].path)

    def tecleo(self, e):
        self.ruta.value = e.control.value       # sin esto el valor no sube al servidor

    def abrir(self, ruta):
        if not ruta:
            return self.estado("escribe o elige una ruta")
        p = Path(str(ruta).strip().strip('"'))
        if not p.exists():
            return self.estado(f"no existe: {p}")
        self.ruta.value = str(p)
        self.progreso.visible = True
        self.estado("leyendo cabeceras...")
        threading.Thread(target=self._cargar, args=(p,), daemon=True).start()

    def _cargar(self, p):
        def avance(n, total):
            self.progreso.value = n / max(1, total)
            self.lbl_estado.value = f"{n}/{total} archivos"
            self.page.update()

        try:
            series = dio.load_study(p, avance)
        except Exception as ex:
            self.progreso.visible = False
            return self.estado(f"error: {ex}")

        self.progreso.visible = False
        if not series:
            self.dd_serie.items = []
            self.dd_serie.etq.value = "serie"
            return self.estado("ahi no hay imagenes DICOM")

        self.series = series
        self.dd_serie.items = [self.opcion(s.label, lambda e, k=n: self.usar_serie(k))
                               for n, s in enumerate(series)]
        self.usar_serie(0)
        self.ruta_estudio = str(p)
        s0 = series[0]
        reg.anotar(p, modalidad=s0.modality, serie=s0.description,
                   cortes=sum(len(x.frames) for x in series), series=len(series),
                   paciente=str(s0.head.get("PatientName", "")) or "-")

    def usar_serie(self, n):
        self.s, self.i = self.series[n], 0
        self.dd_serie.etq.value = self.s.label
        self.zoom, self.pan = 1.0, [0.0, 0.0]
        n = len(self.s.frames)
        self.slider.max = max(0, n - 1)
        # con 356 cortes las marcas del deslizador son ruido: solo en series cortas
        self.slider.divisions = (n - 1) if 1 < n <= 60 else None
        self.dd_preset.items = ([self.opcion("Analisis", lambda e: self.poner_preset("Analisis"))]
                                if self.s.ventana_xml else []) +                                [self.opcion(k, lambda e, k=k: self.poner_preset(k)) for k in dio.PRESETS]
        self.dd_preset.etq.value = "Analisis" if self.s.ventana_xml else "Automatico"
        self.calibrar_reglas()
        self.img.visible, self.vacio.visible = True, False
        self.estado(f"{len(self.s.frames)} cortes")
        self.pintar_info()
        self.pintar()

    def calibrar_reglas(self):
        """Los rangos de los deslizadores salen de los datos: un TAC y una resonancia no comparten escala."""
        self.wc, self.ww = self.s.ventana_xml or self.s.suggested_window(self.i)
        a = self.s.pixels(self.i)
        lo, hi = (0.0, 255.0) if a.ndim == 3 else (float(a.min()), float(a.max()))
        if hi <= lo:
            hi = lo + 1.0
        pad = (hi - lo) * 0.25
        self.sl_wc.slider.min, self.sl_wc.slider.max = lo - pad, hi + pad
        self.sl_ww.slider.min, self.sl_ww.slider.max = 1.0, (hi - lo) * 2.0 + 1.0
        self.sincronizar_reglas()

    def sincronizar_reglas(self):
        for col, v in ((self.sl_wc, self.wc), (self.sl_ww, self.ww)):
            col.slider.value = min(max(v, col.slider.min), col.slider.max)
            col.valor.value = f"{v:,.0f}"

    # -------------------------------------------------------------- pintar
    def pintar(self):
        if not self.s:
            return
        b64, w, h = self.s.render(self.i, self.wc, self.ww, self.box[0], self.box[1],
                                  self.zoom, self.invert)
        self.img.src_base64, self.img.width, self.img.height = b64, w, h
        self.img.left = (self.box[0] - w) / 2 + self.pan[0]
        self.img.top = (self.box[1] - h) / 2 + self.pan[1]
        self.geo = (self.img.left, self.img.top, w, h)

        ancho, alto = self.s.shape(self.i)
        self.ov_ti.value = f"{self.s.modality}  {self.s.description}"
        self.ov_td.value = f"{ancho} x {alto}      {self.zoom * 100:.0f}%"
        self.ov_ii.value = f"W {self.ww:,.0f}   L {self.wc:,.0f}{'   INV' if self.invert else ''}"
        self.ov_id.value = f"{self.i + 1} / {len(self.s.frames)}"
        self.slider.value = self.i
        self.page.update()

    def pintar_info(self):
        if not self.s:
            return
        filas = []
        for k, v in self.s.info(self.i, self.anonimo):
            filas.append(ft.Row(spacing=6, controls=[
                rotulo(k, 8.5, DIM),
                ft.Text(v, size=8.5, color=TXT, font_family=MONO, expand=True,
                        text_align=ft.TextAlign.RIGHT, no_wrap=True,
                        overflow=ft.TextOverflow.ELLIPSIS, tooltip=v),
            ]))
        self.tabla.controls = filas
        self.tabla.update()

    def estado(self, t):
        self.lbl_estado.value = t
        self.page.update()

    # -------------------------------------------------------------- mandos
    def paso(self, d):
        if self.s:
            self.ir(self.i + d)

    def ir(self, n):
        self.i = min(max(0, n), len(self.s.frames) - 1)
        self.pintar()
        self.pintar_info()

    def mover_corte(self, e):
        if self.s:
            self.ir(int(e.control.value))

    def mover_wc(self, e):
        self.wc = float(e.control.value)
        self.sl_wc.valor.value = f"{self.wc:,.0f}"
        self.dd_preset.etq.value = "Manual"
        self.pintar()

    def mover_ww(self, e):
        self.ww = max(1.0, float(e.control.value))
        self.sl_ww.valor.value = f"{self.ww:,.0f}"
        self.dd_preset.etq.value = "Manual"
        self.pintar()

    def poner_fps(self, v):
        self.fps = v
        self.marcar_fps(None)
        self.page.update()

    def marcar_fps(self, gasto):
        """La pastilla dice los fps pedidos y, si el equipo no llega, tambien los reales."""
        texto = f"{self.fps} fps"
        if gasto:
            real = 1.0 / max(gasto, 1e-3)
            if real < self.fps * 0.85:
                texto = f"{real:.0f}/{self.fps} fps"
        if self.sel_fps.etq.value != texto:
            self.sel_fps.etq.value = texto
            try:
                self.sel_fps.etq.update()
            except Exception:
                pass

    def cambiar_anonimo(self, e):
        self.anonimo = e.control.value
        self.pintar_info()

    def poner_preset(self, nombre):
        if not self.s:
            return
        self.dd_preset.etq.value = nombre
        if nombre == "Analisis" and self.s.ventana_xml:
            self.wc, self.ww = self.s.ventana_xml
        else:
            par = dio.PRESETS.get(nombre)
            self.wc, self.ww = par if par else self.s.suggested_window(self.i)
        self.sincronizar_reglas()
        self.pintar()

    def alternar_invertir(self, e=None):
        self.invert = not self.invert
        self.pintar_chip(self.ch_inv, self.invert)
        self.pintar()

    def alternar_modo(self, e=None):
        self.modo = "mover" if self.modo == "wl" else "wl"
        self.pintar_chip(self.ch_mov, self.modo == "mover")
        self.estado("arrastrar: mueve la imagen" if self.modo == "mover"
                    else "arrastrar: brillo y contraste")

    def ajustar(self, e=None):
        self.zoom, self.pan = 1.0, [0.0, 0.0]
        self.pintar()

    def escalar(self, k):
        self.zoom = min(max(0.25, self.zoom * k), 12.0)
        self.pintar()

    def alternar_cine(self, e=None):
        if not self.s:
            return
        self.cine = not self.cine
        self.btn_cine.icon = ft.Icons.PAUSE_ROUNDED if self.cine else ft.Icons.PLAY_ARROW_ROUNDED
        self.btn_cine.icon_color = ACC if self.cine else DIM
        self.page.update()
        if self.cine:
            threading.Thread(target=self.rodar, daemon=True).start()
        else:
            self.pintar_info()           # el cine no refresca la cabecera: al parar, ponerla al dia

    def rodar(self):
        """Mide lo que cuesta cada fotograma y espera solo el resto: si el equipo no da
        para los fps pedidos no se encolan fotogramas, que era lo que colgaba la pausa."""
        muestras = deque(maxlen=8)
        while self.cine and self.s:
            t0 = time.perf_counter()
            self.i = (self.i + 1) % len(self.s.frames)
            try:
                self.pintar()
            except Exception:
                break
            gasto = time.perf_counter() - t0
            muestras.append(gasto)
            self.marcar_fps(sum(muestras) / len(muestras))
            resto = 1.0 / max(1, self.fps) - gasto
            if resto > 0:
                time.sleep(resto)
        self.marcar_fps(None)

    # -------------------------------------------------------------- raton
    def rueda(self, e: ft.ScrollEvent):
        if self.s:
            self.paso(1 if (e.scroll_delta_y or 0) > 0 else -1)

    def arrastre(self, e: ft.DragUpdateEvent):
        if not self.s:
            return
        if self.modo == "mover":
            self.pan[0] += e.delta_x
            self.pan[1] += e.delta_y
        else:
            paso = max(1.0, self.ww / 200.0)
            self.ww = max(1.0, self.ww + e.delta_x * paso)
            self.wc = self.wc - e.delta_y * paso
            self.sincronizar_reglas()
            self.dd_preset.etq.value = "Manual"
        self.pintar()

    def cursor(self, e: ft.HoverEvent):
        if not self.s:
            return
        l, t, w, h = self.geo
        ancho, alto = self.s.shape(self.i)
        px, py = int((e.local_x - l) / w * ancho), int((e.local_y - t) / h * alto)
        v = self.s.value_at(self.i, px, py)
        if v is None:
            self.lbl_px.value = ""
        elif isinstance(v, tuple):
            self.lbl_px.value = f"x{px} y{py}   RGB {v[0]} {v[1]} {v[2]}"
        else:
            self.lbl_px.value = f"x{px} y{py}   {v:,.0f} {self.s.units}"
        self.lbl_px.update()

    # ------------------------------------------------------------- paneles
    def mover_divisor(self, e: ft.DragUpdateEvent):
        if not self.aside_abierto:                    # tirar del borde lo saca de nuevo
            self.aside_abierto = self.aside.visible = True
        self.aside_w = min(max(ASIDE_MIN, self.aside_w - e.delta_x), ASIDE_MAX)
        self.aside.width = self.aside_w
        self.medir(self.ancho, self.alto)

    def ventana(self, que):
        """Los tres botones de la derecha: la barra de arriba hace de barra de titulo."""
        w = self.page.window
        try:
            if que == "min":
                w.minimized = True
            elif que == "max":
                self.maximizada = w.maximized = not self.maximizada
                self.pintar_max()
            else:
                w.destroy()                              # close() no cierra nada aqui
                threading.Thread(target=cerrar_ventana, args=(self.page.title,),
                                 daemon=True).start()
                return
        except Exception:
            pass
        self.page.update()

    def pintar_max(self):
        self.btn_max.icon = ft.Icons.FILTER_NONE if self.maximizada else ft.Icons.CROP_SQUARE
        self.btn_max.tooltip = "Restaurar" if self.maximizada else "Maximizar"

    def evento_ventana(self, e):
        """El doble clic en la barra tambien maximiza: el icono tiene que enterarse."""
        if e.type in (ft.WindowEventType.MAXIMIZE, ft.WindowEventType.UNMAXIMIZE):
            self.maximizada = e.type == ft.WindowEventType.MAXIMIZE
            self.pintar_max()
            self.btn_max.update()

    def alternar_aside(self, e=None):
        self.aside_abierto, self.aside_auto = not self.aside_abierto, False
        self.aside.visible = self.aside_abierto
        self.medir(self.ancho, self.alto)

    # ------------------------------------------------------------- teclado
    def tecla(self, e: ft.KeyboardEvent):
        # Flet nombra las flechas con espacio: 'Arrow Right'. Y ojo, el evento llega
        # tambien mientras se escribe en el campo de ruta.
        k = e.key.replace(" ", "").lower()
        if e.ctrl and k == "e":
            return self.dialogo_exportar()
        if e.ctrl and k == "l":
            return self.dialogo_registro()
        if e.ctrl and k == "d":
            return self.dialogo_entorno()
        if not self.s or self.escribiendo:
            return
        if k in ("arrowdown", "down", "arrowright", "right", "pagedown"):
            self.paso(1)
        elif k in ("arrowup", "up", "arrowleft", "left", "pageup"):
            self.paso(-1)
        elif k == "home":
            self.ir(0)
        elif k == "end":
            self.ir(len(self.s.frames) - 1)
        elif e.key == " " or k == "space":     # solo el espacio de verdad
            self.alternar_cine()
        elif k == "i":
            self.alternar_invertir()
        elif k == "r":
            self.ajustar()
        elif k == "m":
            self.alternar_modo()
        elif k == "p":
            self.alternar_aside()
        elif k in ("+", "="):
            self.escalar(1.25)
        elif k == "-":
            self.escalar(1 / 1.25)

    # ------------------------------------------------------------- tamanio
    def redimensionar(self, e):
        self.medir(e.width, e.height)

    def medir(self, ancho, alto):
        if not ancho or not alto:
            return
        # las reglas de estrechez solo actuan cuando la ventana CAMBIA de tamanio; si no,
        # abrir el panel a mano se deshacia solo al recalcular con el mismo ancho
        redimensiono = ancho != self.ancho or alto != self.alto
        self.ancho, self.alto = ancho, alto
        lado = (self.aside_w if self.aside_abierto else 0) + DIVISOR
        self.box = [max(160.0, ancho - lado), max(160.0, alto - TOPBAR - BOTBAR)]

        # lo que no cabe se va: primero el campo de ruta, luego el panel y los fps
        cabe_ruta = ancho >= 960
        cabe_fps = ancho >= 620          # la pastilla ocupa 74 px: el deslizador cede ese hueco
        if self.ruta.visible != cabe_ruta or self.sel_fps.visible != cabe_fps:
            self.ruta.visible = self.btn_abrir.visible = cabe_ruta
            self.sel_fps.visible = cabe_fps
        if redimensiono and ancho < 820 and self.aside_abierto:
            self.aside_abierto = self.aside.visible = False
            self.aside_auto = True
            self.box[0] = max(160.0, ancho - DIVISOR)
        elif redimensiono and ancho >= 880 and self.aside_auto:   # lo plego la estrechez
            self.aside_abierto = self.aside.visible = True
            self.aside_auto = False
            self.box[0] = max(160.0, ancho - self.aside_w - DIVISOR)
        if self.s:
            self.pintar()
        else:
            self.page.update()

    def calentador(self):
        """Va descomprimiendo por delante del corte actual. Un corte de CBCT cuesta unos
        90 ms en salir del JPEG sin perdidas; sin esto la rueda y el cine van a tirones."""
        while True:
            s, i = self.s, self.i
            if not s:
                time.sleep(0.3)
                continue
            n, hubo = len(s.frames), False
            for d in list(range(1, 26)) + [-1, -2, -3]:
                if self.s is not s or self.i != i:
                    break                               # se movio: recalcular por donde va
                j = (i + d) % n
                if not s.en_cache(j):
                    try:
                        s.pixels(j)
                    except Exception:
                        pass
                    hubo = True
            if not hubo:
                time.sleep(0.25)

    def medir_tarde(self):
        """page.width vale 0 hasta el primer fotograma y a veces tarda: reintentar un rato.
        Con una sola lectura la ventana arrancaba con el panel plegado sin motivo."""
        ultimo = None
        for _ in range(14):
            time.sleep(0.25)
            w, h = self.page.width, self.page.height
            if w and h and (w, h) != ultimo:
                ultimo = (w, h)
                self.medir(w, h)

    # ------------------------------------------------------------ sistema
    def dialogo_entorno(self, e=None):
        """Lo que hay en la maquina y lo que hace falta: sin sorpresas a media faena."""
        filas = entorno.revisar()
        hay, faltan = entorno.resumen(filas)

        def linea(f):
            marca = "OK" if f["hay"] else ("FALTA" if f["obligatoria"] else "OPCIONAL")
            fondo = ACC if f["hay"] else (ELEV if not f["obligatoria"] else "#4A1F1F")
            return ft.Row(spacing=8, vertical_alignment=ft.CrossAxisAlignment.CENTER, controls=[
                ft.Container(width=62, height=17, bgcolor=fondo,
                             border_radius=2, alignment=ft.alignment.center,
                             content=ft.Text(marca, size=7.5,
                                             color=TINTA if f["hay"] else DIM)),
                ft.Container(width=104, content=rotulo(f["pieza"], 8.5, TXT, True)),
                ft.Container(width=210, content=ft.Text(f["detalle"], size=8.5, color=DIM,
                                                        font_family=MONO, no_wrap=True,
                                                        overflow=ft.TextOverflow.ELLIPSIS)),
                ft.Container(expand=True, content=rotulo(f["para"], 8.5, DIM)),
            ])

        equipo = [ft.Row([ft.Container(width=104, content=rotulo(k, 8.5, DIM)),
                          ft.Text(v, size=8.5, color=TXT, font_family=MONO, expand=True,
                                  no_wrap=True, overflow=ft.TextOverflow.ELLIPSIS)],
                         spacing=8)
                  for k, v in entorno.equipo()]

        veredicto = ("todo lo necesario esta en su sitio" if not faltan
                     else f"faltan {faltan} piezas imprescindibles")
        self.dlg_ent = ft.AlertDialog(
            modal=True, bgcolor=PANEL, shape=ft.RoundedRectangleBorder(radius=4),
            title=ft.Row(alignment=ft.MainAxisAlignment.SPACE_BETWEEN, controls=[
                ft.Text("ESTADO DEL SISTEMA", size=11, color=TXT, weight=ft.FontWeight.W_600,
                        style=ft.TextStyle(letter_spacing=1.2)),
                rotulo(f"DCM Viewer {VERSION}", 9, DIM, True)]),
            title_padding=ft.padding.only(20, 14, 20, 6),
            content_padding=ft.padding.symmetric(6, 20),
            actions_padding=ft.padding.only(20, 0, 14, 10),
            content=ft.Container(width=640, content=ft.Column(spacing=5, tight=True, controls=[
                *equipo,
                ft.Divider(height=9, color=LINE),
                *[linea(f) for f in filas],
                ft.Divider(height=9, color=LINE),
                rotulo(f"{hay} de {len(filas)} componentes disponibles  ·  {veredicto}", 8.5),
            ])),
            actions=[ft.TextButton("Cerrar", on_click=lambda ev: self.page.close(self.dlg_ent),
                                   style=ft.ButtonStyle(color=DIM,
                                                        text_style=ft.TextStyle(size=10)))],
        )
        self.page.open(self.dlg_ent)

    # ----------------------------------------------------------- registro
    def dialogo_registro(self, e=None):
        """La lista de trabajo: lo que se ha abierto, en que estado esta y con que nota."""
        self.reg_busca = ft.TextField(
            hint_text="buscar por paciente, serie, nota o estado",
            dense=True, filled=True, fill_color=ELEV, border=ft.InputBorder.NONE,
            border_radius=3, color=TXT, hint_style=ft.TextStyle(color="#6E6E6E", size=9),
            text_size=9, content_padding=ft.padding.symmetric(6, 8), expand=True,
            on_change=lambda ev: self.pintar_registro(),
            on_focus=lambda ev: setattr(self, "escribiendo", True),
            on_blur=lambda ev: setattr(self, "escribiendo", False))
        self.reg_lista = ft.Column(spacing=0, scroll=ft.ScrollMode.AUTO, height=300)
        self.reg_pie = rotulo("", 8.5)
        self.dlg_reg = ft.AlertDialog(
            modal=True, bgcolor=PANEL, shape=ft.RoundedRectangleBorder(radius=4),
            title=ft.Row(alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                         vertical_alignment=ft.CrossAxisAlignment.CENTER, controls=[
                ft.Text("REGISTRO DE ESTUDIOS", size=11, color=TXT,
                        weight=ft.FontWeight.W_600, style=ft.TextStyle(letter_spacing=1.2)),
                ft.Container(self.reg_busca, width=300, height=26),
            ]),
            title_padding=ft.padding.only(20, 14, 20, 6),
            content_padding=ft.padding.symmetric(6, 20),
            actions_padding=ft.padding.only(20, 0, 14, 10),
            content=ft.Container(width=820, content=ft.Column(
                spacing=6, tight=True, alignment=ft.MainAxisAlignment.START, controls=[
                    self.cabecera_registro(),
                    ft.Container(self.reg_lista, alignment=ft.alignment.top_left,
                                 border=ft.border.only(top=ft.BorderSide(1, LINE))),
                    self.reg_pie,
                ])),
            actions=[ft.TextButton("Cerrar", on_click=lambda ev: self.page.close(self.dlg_reg),
                                   style=ft.ButtonStyle(color=DIM,
                                                        text_style=ft.TextStyle(size=10)))],
        )
        self.pintar_registro()
        self.page.open(self.dlg_reg)

    def cabecera_registro(self):
        def col(txt, ancho=None, expand=None, derecha=False):
            return ft.Container(width=ancho, expand=expand, content=rotulo(
                txt, 8, DIM,
                text_align=ft.TextAlign.RIGHT if derecha else ft.TextAlign.LEFT))
        return ft.Row(spacing=6, controls=[
            col("ESTADO", 74), col("ABIERTO", 76), col("MOD", 26),
            col("PACIENTE / SERIE", expand=True), col("CORTES", 42, derecha=True),
            col("NOTA", 150), ft.Container(width=56)])

    def pintar_registro(self):
        todos = reg.cargar()
        vistos = reg.filtrar(todos, self.reg_busca.value)
        self.reg_lista.controls = [self.fila_registro(r) for r in vistos] or [
            ft.Container(rotulo("no hay estudios en el registro", 9, DIM),
                         padding=16, alignment=ft.alignment.center)]
        pendientes = sum(1 for r in todos if r.get("estado") != reg.REVISADO)
        self.reg_pie.value = (f"{len(todos)} estudios · {pendientes} pendientes"
                              f"     ·     {reg.FICHERO}")
        if self.reg_lista.page:
            self.reg_lista.update()
            self.reg_pie.update()

    def fila_registro(self, r):
        ruta = r.get("ruta", "")
        actual, falta = ruta == self.ruta_estudio, not reg.existe(ruta)
        revisado = r.get("estado") == reg.REVISADO
        paciente = "-- oculto --" if self.anonimo else (r.get("paciente") or "-")

        estado = ft.TextButton(
            content=ft.Text(reg.REVISADO if revisado else reg.PENDIENTE, size=8),
            width=74, height=20, tooltip="Marcar como revisado / pendiente",
            on_click=lambda e: self.marcar_registro(ruta, not revisado),
            style=ft.ButtonStyle(color=TINTA if revisado else DIM,
                                 bgcolor=ACC if revisado else ELEV, padding=0,
                                 shape=ft.RoundedRectangleBorder(radius=2)))
        nota = ft.TextField(
            value=r.get("nota", ""), width=150, dense=True, filled=True, fill_color=ELEV,
            border=ft.InputBorder.NONE, border_radius=2, color=TXT, text_size=8.5,
            content_padding=ft.padding.symmetric(6, 6), hint_text="nota",
            hint_style=ft.TextStyle(color="#5A5A5A", size=8.5),
            on_focus=lambda e: setattr(self, "escribiendo", True),
            on_blur=lambda e: self.anotar_registro(ruta, e.control.value),
            on_submit=lambda e: self.anotar_registro(ruta, e.control.value))

        return ft.Container(
            padding=ft.padding.symmetric(3, 0),
            border=ft.border.only(bottom=ft.BorderSide(1, "#141414"),
                                  left=ft.BorderSide(2, ACC if actual else CHROME)),
            content=ft.Row(spacing=6, vertical_alignment=ft.CrossAxisAlignment.CENTER, controls=[
                estado,
                ft.Container(width=76, content=rotulo(str(r.get("abierto", "-"))[5:], 8.5, DIM, True)),
                ft.Container(width=26, content=rotulo(r.get("modalidad", "-"), 8.5, TXT)),
                ft.Container(expand=True, content=ft.Text(
                    f"{paciente}   ·   {r.get('serie', '-')}", size=8.5,
                    color=DIM if falta else TXT, no_wrap=True,
                    overflow=ft.TextOverflow.ELLIPSIS,
                    tooltip=ruta + ("     (la carpeta ya no existe)" if falta else ""))),
                ft.Container(width=42, content=ft.Text(
                    str(r.get("cortes", "-")), size=8.5, color=TXT, font_family=MONO,
                    text_align=ft.TextAlign.RIGHT)),
                nota,
                self.boton(ft.Icons.REPORT_PROBLEM_OUTLINED if falta else ft.Icons.LAUNCH,
                           "La carpeta ya no existe" if falta else "Abrir este estudio",
                           (lambda e: None) if falta else (lambda e: self.abrir_del_registro(ruta)),
                           12, 24),
                self.boton(ft.Icons.DELETE_OUTLINE, "Quitar del registro",
                           lambda e: self.borrar_registro(ruta), 12, 24),
            ]))

    def marcar_registro(self, ruta, revisado):
        reg.actualizar(ruta, estado=reg.REVISADO if revisado else reg.PENDIENTE)
        self.pintar_registro()

    def anotar_registro(self, ruta, nota):
        self.escribiendo = False
        reg.actualizar(ruta, nota=nota)

    def borrar_registro(self, ruta):
        reg.quitar(ruta)
        self.pintar_registro()

    def abrir_del_registro(self, ruta):
        self.page.close(self.dlg_reg)
        self.ruta.value = ruta
        self.abrir(ruta)

    # ----------------------------------------------------------- exportar
    def destino_defecto(self, carpeta=None):
        base = carpeta or Path.home() / "Desktop" / "DCM export"
        nombre = f"{expo.nombre_limpio(self.s.modality)}_{expo.nombre_limpio(self.s.description)}"
        f = self.ex_formato.value
        if f.startswith("PNG"):
            return base / nombre
        return base / (nombre + (".gif" if f.startswith("GIF") else ".mp4"))

    def dialogo_exportar(self, e=None):
        if not self.s:
            return self.estado("primero abre un estudio")
        if self.cine:
            self.alternar_cine()
        n = len(self.s.frames)

        self.ex_formato = ft.Dropdown(
            width=150, dense=True, text_size=10, color=TXT, border_color=LINE,
            content_padding=8, value=expo.FORMATOS[1], on_change=self.cambiar_formato,
            options=[ft.dropdown.Option(f) for f in expo.FORMATOS])
        self.ex_tam = ft.Dropdown(
            width=110, dense=True, text_size=10, color=TXT, border_color=LINE,
            content_padding=8, value="512 px",
            options=[ft.dropdown.Option(k) for k in expo.TAMANIOS])
        self.ex_rango = ft.RangeSlider(
            min=1, max=n, start_value=1, end_value=n, divisions=max(1, n - 1), height=26,
            active_color=ACC, inactive_color=ELEV, on_change=self.cambiar_rango)
        self.ex_lbl_rango = rotulo(f"1 - {n}   ({n} cortes)", 9, TXT, True)
        self.ex_fps = ft.Slider(min=1, max=30, value=self.fps, divisions=29, height=26,
                                active_color=ACC, inactive_color=ELEV,
                                label="{value} fps", expand=True, on_change=self.cambiar_fps_ex)
        self.ex_lbl_fps = rotulo(f"{self.fps} fps", 9, TXT, True)
        self.ex_ruta = ft.TextField(
            value=str(self.destino_defecto()), text_size=9, height=28, content_padding=8,
            border_color=LINE, focused_border_color=ACC, color=TXT, expand=True,
            on_change=lambda ev: setattr(self.ex_ruta, "value", ev.control.value),
            on_focus=lambda ev: setattr(self, "escribiendo", True),
            on_blur=lambda ev: setattr(self, "escribiendo", False))
        self.ex_prog = ft.ProgressBar(height=2, color=ACC, bgcolor=ELEV, value=0)
        self.ex_estado = rotulo("lo exportado sale con la ventana y el invertido de ahora", 9, DIM)
        self.ex_btn = ft.TextButton(
            "EXPORTAR", on_click=self.lanzar_exportar,
            style=ft.ButtonStyle(color=TINTA, bgcolor=ACC, padding=ft.padding.symmetric(2, 14),
                                 shape=ft.RoundedRectangleBorder(radius=3),
                                 text_style=ft.TextStyle(size=10, weight=ft.FontWeight.W_600)))

        def fila(etq, ctrl):
            return ft.Row([ft.Container(rotulo(etq, 9), width=62), ctrl],
                          spacing=6, vertical_alignment=ft.CrossAxisAlignment.CENTER)

        self.dlg = ft.AlertDialog(
            modal=True, bgcolor=PANEL,
            shape=ft.RoundedRectangleBorder(radius=4),
            title=ft.Text("EXPORTAR SECUENCIA", size=11, color=TXT,
                          weight=ft.FontWeight.W_600, style=ft.TextStyle(letter_spacing=1.2)),
            title_padding=ft.padding.only(20, 16, 20, 4),
            content_padding=ft.padding.symmetric(6, 20),
            actions_padding=ft.padding.only(20, 0, 14, 10),
            content=ft.Container(width=440, content=ft.Column(spacing=6, tight=True, controls=[
                fila("Formato", ft.Row([self.ex_formato, self.ex_tam], spacing=6)),
                fila("Cortes", ft.Column([self.ex_rango, self.ex_lbl_rango], spacing=0, expand=True)),
                fila("Velocidad", ft.Row([self.ex_fps, self.ex_lbl_fps], spacing=6, expand=True)),
                fila("Guardar en", ft.Row([
                    self.ex_ruta,
                    self.boton(ft.Icons.FOLDER_OPEN_OUTLINED, "Elegir carpeta",
                               lambda ev: self.picker_dest.get_directory_path("Carpeta de destino")),
                ], spacing=2, expand=True)),
                ft.Container(height=4),
                self.ex_prog,
                self.ex_estado,
            ])),
            actions=[
                ft.TextButton("Cancelar", on_click=lambda ev: self.page.close(self.dlg),
                              style=ft.ButtonStyle(color=DIM,
                                                   text_style=ft.TextStyle(size=10))),
                self.ex_btn,
            ],
        )
        self.page.open(self.dlg)

    def cambiar_formato(self, e):
        # cambiar de formato solo cambia la extension: la carpeta elegida se respeta
        actual = (self.ex_ruta.value or "").strip().strip('"')
        self.ex_ruta.value = str(self.destino_defecto(Path(actual).parent if actual else None))
        self.page.update()

    def cambiar_rango(self, e):
        a, b = int(self.ex_rango.start_value), int(self.ex_rango.end_value)
        self.ex_lbl_rango.value = f"{a} - {b}   ({b - a + 1} cortes)"
        self.ex_lbl_rango.update()

    def cambiar_fps_ex(self, e):
        self.ex_lbl_fps.value = f"{int(e.control.value)} fps"
        self.ex_lbl_fps.update()

    def elegido_destino(self, e: ft.FilePickerResultEvent):
        if e.path:
            self.ex_ruta.value = str(self.destino_defecto(Path(e.path)))
            self.page.update()

    def lanzar_exportar(self, e):
        self.ex_btn.disabled = True
        self.ex_estado.value = "exportando..."
        self.ex_estado.color = DIM
        self.page.update()
        threading.Thread(target=self._exportar, daemon=True).start()

    def _exportar(self):
        def avance(n, total):
            self.ex_prog.value = n / max(1, total)
            self.ex_estado.value = f"corte {n} de {total}"
            self.page.update()

        try:
            i0 = int(self.ex_rango.start_value) - 1
            i1 = int(self.ex_rango.end_value) - 1
            ruta = expo.exportar(self.ex_formato.value, Path(self.ex_ruta.value), self.s,
                                 i0, i1, self.wc, self.ww, self.invert,
                                 expo.TAMANIOS[self.ex_tam.value], int(self.ex_fps.value), avance)
            self.ex_estado.value = f"listo: {ruta}"
            self.ex_estado.color = ACC
            self.estado(f"exportado a {ruta}")
        except Exception as ex:
            self.ex_prog.value = 0
            self.ex_estado.value = f"error: {ex}"
            self.ex_estado.color = TXT
        finally:
            self.ex_btn.disabled = False
            self.page.update()


def main(page: ft.Page):
    # Flet se traga las excepciones del arranque y deja la ventana en negro:
    # mejor escupirlas en pantalla que quedarse adivinando.
    try:
        Visor(page)
    except Exception:
        import traceback
        page.add(ft.Text(traceback.format_exc(), size=11, color=TXT, font_family=MONO))
        page.update()
        raise


if __name__ == "__main__":
    ft.app(main)
