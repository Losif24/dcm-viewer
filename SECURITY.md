# Seguridad

## Reportar un fallo

Si encuentras un problema de seguridad, abre un
[issue](https://github.com/Losif24/dcm-viewer/issues) describiendo qué pasa y
cómo reproducirlo. Si prefieres no hacerlo en público, usa el aviso privado de
GitHub (*Security* → *Report a vulnerability*).

## Superficie de ataque

Merece la pena que la conozcas antes de instalar nada en un equipo con datos
de pacientes:

- **Sin red.** El programa no abre sockets, no escucha en ningún puerto y no
  llama a ningún servidor. Se puede usar en una máquina aislada.
- **Sin servicios ni tareas programadas.** Cuando lo cierras, no queda nada
  corriendo.
- **Instalación por usuario.** No pide administrador. Toca su carpeta de
  programa, su entrada de desinstalación y —si lo aceptas— la asociación de
  `.dcm` y la entrada de menú contextual, siempre en la rama del usuario.
- **Entrada no confiable.** Los DICOM se leen con `pydicom` y se descomprimen
  con GDCM o pylibjpeg. Un archivo corrupto o malformado hace que ese estudio
  se descarte, no que el visor se caiga: el indexado ignora lo que no puede
  leer y sigue.
- **Sin ejecución de código del estudio.** No se interpreta nada del contenido
  del archivo más allá de sus píxeles y sus etiquetas.

## Dependencias

Todas de código abierto y de uso común en imagen médica: `pydicom`, `gdcm`,
`pylibjpeg`, `numpy`, `Pillow`, `imageio` y `flet`. El instalador las lleva
congeladas en la versión con la que se compiló; no descarga nada al instalar.

## Versiones

Sólo se mantiene la última versión publicada en
[releases](https://github.com/Losif24/dcm-viewer/releases).
