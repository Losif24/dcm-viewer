# Privacidad

Esto va en corto porque en un visor de imagen médica es lo primero que hay que
poder comprobar.

## Qué no hace

No abre conexiones de red, salvo una que enciendes tú: buscar actualizaciones.
Viene apagada. Se enciende en *Estado del sistema* (`Ctrl+D`), o se usa a mano
con el botón de ahí mismo. Esa petición va a la API pública de GitHub, pregunta
cuál es la última versión publicada y no manda nada: ni quién eres, ni qué
estudios tienes, ni un identificador. Con el interruptor apagado no abre un solo
socket.

Tampoco hay telemetría, ni informes de error, ni analítica. Las imágenes se leen
de la carpeta que abres y se quedan ahí; no se copian a ningún lado.

## Qué guarda y dónde

| Qué | Dónde |
|---|---|
| Los estudios que has abierto: ruta, modalidad, serie, número de cortes, fecha, estado y tus notas | `%APPDATA%\DCM Viewer\registro.json` |
| Si quieres que avise de versiones nuevas | `%APPDATA%\DCM Viewer\ajustes.json` |

El registro guarda el nombre del paciente tal cual viene en el DICOM. Una lista
de trabajo en la que no sabes de quién es cada estudio no sirve para nada. En
pantalla sale enmascarado mientras el interruptor *anónimo* esté puesto.

Son dos archivos de texto. Los puedes abrir, editar o borrar cuando quieras, y
al desinstalar te pregunta si los elimina.

## Lo que exportas

Los PNG, GIF y MP4 que saca el programa llevan píxeles y nada más. Ninguna
etiqueta DICOM va dentro, así que no arrastran datos del paciente.

Hay un caso que no depende del programa: si el estudio original trae datos
escritos encima de la imagen (algunos equipos ponen el nombre en una esquina),
esos píxeles salen en la exportación como cualquier otro.

## El interruptor de anónimo

Oculta nombre, identificador y fecha de nacimiento, tanto en la cabecera como en
el registro. Viene puesto, pensando en quien tiene la pantalla a la vista en una
consulta.

## Uso previsto

No es un producto sanitario certificado ni está aprobado por ninguna agencia. No
debe ser la única base de un diagnóstico. Sirve para ver, revisar y documentar
estudios.
