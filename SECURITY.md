# Seguridad

## Reportar un fallo

Abre un [issue](https://github.com/Losif24/dcm-viewer/issues) contando qué pasa
y cómo reproducirlo. Si prefieres no hacerlo en público, GitHub tiene el aviso
privado en *Security* → *Report a vulnerability*.

## Qué toca el programa

Conviene saberlo antes de instalar nada en un equipo con datos de pacientes.

No escucha en ningún puerto ni acepta conexiones entrantes. La única salida es
la búsqueda de actualizaciones, que viene apagada: un GET por HTTPS a
`api.github.com` y, si aceptas actualizar, la descarga del instalador desde la
página de releases del proyecto. Con eso apagado se puede usar en una máquina
aislada.

No deja servicios ni tareas programadas. Cuando cierras la ventana no queda nada
corriendo.

Se instala para tu usuario, sin administrador. Toca su carpeta de programa, su
entrada de desinstalación y, si lo marcas en el asistente, la asociación de
`.dcm` y la entrada del menú contextual, siempre en la rama del usuario.

## Archivos de entrada

Los DICOM se leen con `pydicom` y se descomprimen con GDCM o pylibjpeg. Un
archivo corrupto o malformado hace que ese estudio se descarte, no que el visor
se caiga: el indexado ignora lo que no puede leer y sigue con el resto. Del
contenido no se interpreta nada más que los píxeles y las etiquetas.

## Dependencias

`pydicom`, `gdcm`, `pylibjpeg`, `numpy`, `Pillow`, `imageio` y `flet`, todas de
código abierto y de uso corriente en imagen médica. El instalador las lleva
congeladas en la versión con la que se compiló y no descarga nada al instalar.

## Versiones

Se mantiene la última publicada en
[releases](https://github.com/Losif24/dcm-viewer/releases).
