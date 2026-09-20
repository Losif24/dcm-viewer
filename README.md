<p align="center"><img src="packaging/escaparate/banner.png" alt="DCM Viewer" width="100%"></p>

<p align="center">
  <a href="https://github.com/Losif24/dcm-viewer/releases/latest"><img src="https://img.shields.io/github/v/release/Losif24/dcm-viewer?style=for-the-badge&label=versi%C3%B3n&color=FFFFFF&labelColor=181818" alt="última versión"></a>
  <img src="https://img.shields.io/badge/Windows-10%20%7C%2011-181818?style=for-the-badge&logo=windows&logoColor=white" alt="Windows 10 y 11">
  <img src="https://img.shields.io/badge/Python-3.13-181818?style=for-the-badge&logo=python&logoColor=white" alt="Python 3.13">
  <img src="https://img.shields.io/badge/licencia-MIT-181818?style=for-the-badge" alt="licencia MIT">
</p>

<table>
  <tr>
    <td width="50%"><img src="packaging/escaparate/visor.png" alt="Visor con un estudio abierto"><p align="center"><sub><b>Recorriendo un estudio de 140 cortes</b></sub></p></td>
    <td width="50%"><img src="packaging/escaparate/registro.png" alt="Registro de estudios"><p align="center"><sub><b>Registro de estudios</b></sub></p></td>
  </tr>
  <tr>
    <td width="50%"><img src="packaging/escaparate/exportar.png" alt="Exportar la secuencia"><p align="center"><sub><b>Exportar a PNG, GIF o MP4</b></sub></p></td>
    <td width="50%"><img src="packaging/escaparate/sistema.png" alt="Estado del sistema"><p align="center"><sub><b>Estado del sistema</b></sub></p></td>
  </tr>
</table>

<p align="center"><sub>Hecho con</sub><br><img src="https://skillicons.dev/icons?i=py,windows" alt="Python y Windows"></p>

<details>
<summary><b>In English</b></summary>

A DICOM viewer for Windows. Open a study folder and it groups the series, sorts
the slices by anatomical position and lets you scroll through them, set
window/level by dragging, read Hounsfield values, play cine and export to PNG,
GIF or MP4. The installer carries everything, so there is no Python to install
and no administrator rights needed. It makes no network connection unless you
turn on update checks, which are off by default. The interface is in Spanish.
Not a certified medical device, so don't use it to diagnose.

</details>

# DCM Viewer

Un visor de estudios DICOM para Windows.

Me pasaron un CBCT en una carpeta con 356 archivos `.dcm` y para verlo tenía dos
opciones: instalar el software de la clínica o subirlo a alguna web. No me
convencía ninguna, así que escribí esto.

Le das la carpeta y la abre. Agrupa las series, pone los cortes en orden (por su
posición real, no por el nombre del archivo, que casi nunca coincide) y los
recorres con la rueda. El brillo y el contraste se ajustan arrastrando sobre la
imagen, como en las estaciones de verdad. Si dejas el cursor encima te dice
cuántas Hounsfield hay ahí. Y si tienes que enseñarle el estudio a alguien, lo
saca a PNG, GIF o MP4 sin salir del programa.

El instalador lleva todo dentro. No hay que tener Python, no instala nada más y
no pide permisos de administrador.

---

## Qué hace

| | |
|---|---|
| Encuentra las series | agrupa por `SeriesInstanceUID` y ordena proyectando `ImagePositionPatient` sobre la normal del plano, que es lo que funciona también en adquisiciones oblicuas |
| Recorre los cortes | rueda, flechas, barra o cine |
| Brillo y contraste | arrastrando, o con los preajustes de siempre: cerebro, hueso, pulmón, mediastino, abdomen, hígado, angio |
| Usa la ventana del escáner | si el estudio trae su XML de análisis, coge esa en vez del rango entero del equipo |
| Mide | Hounsfield bajo el cursor, ya con el rescale aplicado |
| Exporta | PNG numerados, GIF o MP4, eligiendo rango de cortes, tamaño y velocidad |
| Recuerda | los estudios que has abierto, con su estado y tus notas |
| Se revisa a sí mismo | una pantalla dice qué componentes hay y cuáles faltan |
| Se actualiza | si lo enciendes, avisa de versiones nuevas y se instala encima |

Los datos del paciente salen ocultos. Hay un interruptor en el panel para
mostrarlos cuando haga falta.

---

## Instalar

Bájate el instalador de [releases](https://github.com/Losif24/dcm-viewer/releases/latest)
y ábrelo.

Si prefieres el código:

```bash
pip install -r requirements.txt
python main.py                       # o: python main.py C:\ruta\al\estudio
```

Arrastrar la carpeta del estudio sobre `DCM Viewer.bat` también vale.

---

## Atajos

| | |
|---|---|
| rueda, `←` `→`, `Inicio` `Fin` | cortes |
| arrastrar | brillo y contraste |
| `espacio` | cine |
| `i` · `m` · `r` | invertir, mover, ajustar |
| `+` `-` | zoom |
| `p` | panel |
| `Ctrl+E` · `Ctrl+L` · `Ctrl+D` | exportar, registro, estado del sistema |

---

## Formatos

Lo que sepa leer `pydicom`: sin comprimir, RLE, JPEG sin pérdida y JPEG 2000.
Da igual un archivo por corte que multiframe. Lo he probado con TAC, con CBCT
dental y con ecografía en color.

Para descomprimir tira de GDCM, que en JPEG sin pérdida va bastante más rápido
que pylibjpeg: 23 ms por corte contra 90 en el CBCT con el que hice las pruebas,
356 cortes de 545×545. Si GDCM no está, usa pylibjpeg y no pasa nada. Hay un
hilo que va descomprimiendo por delante del corte que estás mirando, que es por
lo que el cine no se atasca.

---

## Privacidad

No manda nada a ningún sitio. La única excepción es buscar actualizaciones, y
viene apagado: si lo enciendes, le pregunta a GitHub cuál es la última versión y
ya está, sin enviar ningún dato tuyo.

Las imágenes se leen donde están y no se copian. El registro de estudios (rutas,
fechas, tus notas) se queda en `%APPDATA%\DCM Viewer\registro.json`, y al
desinstalar te pregunta si lo borra. Lo que exportas lleva la imagen y nada más:
ninguna etiqueta DICOM va dentro.

Más detalle en [PRIVACIDAD.md](PRIVACIDAD.md) y [SECURITY.md](SECURITY.md).

> Esto no es un producto sanitario certificado ni está aprobado por ninguna
> agencia. No lo uses para diagnosticar.

---

## Preguntas que me han hecho

**¿Abro un `.dcm` suelto?** Mejor la carpeta entera. Un estudio son cientos de
archivos y el visor los necesita todos para ordenarlos.

**¿Vale para un CBCT dental?** Sí, es con lo que lo probé. Además lee la ventana
que dejó guardada el programa del escáner.

**¿Hace falta Python?** Con el instalador no.

**¿Funciona sin internet?** Siempre. Lo único que usa la red son las
actualizaciones, y vienen apagadas.

**¿Puedo sacar un vídeo del estudio?** `Ctrl+E`, eliges MP4 y el rango de
cortes.

**¿Sirve para diagnosticar?** No.

---

## Apoyar el proyecto

Es gratis y va a seguir siéndolo. Si te saca de un apuro y quieres invitarme a
un café:

| | |
|---|---|
| **Bre-B** | `@NEQUIJOS24501` |

En tu banco: enviar dinero, Bre-B, pegar la llave. Una estrella en el repo
también se agradece.

---

## Por dentro

| Archivo | Qué es |
|---|---|
| `main.py` | la interfaz: barra, lienzo, panel, diálogos |
| `dicomio.py` | indexado, orden, caché de cortes y render |
| `exportar.py` | PNG, GIF y MP4 |
| `registro.py` | el registro de estudios |
| `entorno.py` | qué hay instalado y qué falta |
| `actualizacion.py` | versiones nuevas |
| `packaging/` | empaquetado e instalador |

Para armar el instalador hacen falta PyInstaller e
[Inno Setup 6](https://jrsoftware.org/isdl.php). Con eso,
`packaging\construir.bat` deja el `.exe` en `packaging\salida`.

---

## Licencia

MIT.
