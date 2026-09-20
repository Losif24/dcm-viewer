# Privacidad

Escrito en corto, porque en un visor de imagen médica esto importa.

## Qué no hace

- **No abre conexiones de red.** Ninguna. Ni telemetría, ni informes de error,
  ni comprobación de versiones, ni analítica.
- **No copia las imágenes.** Se leen de la carpeta que abres y se quedan ahí.
- **No sube nada a la nube**, porque no sabe hablar con ninguna.

## Qué guarda, dónde y por qué

| Qué | Dónde | Por qué |
|---|---|---|
| Registro de estudios abiertos: ruta, modalidad, serie, número de cortes, fecha, estado y tus notas | `%APPDATA%\DCM Viewer\registro.json` | para que el programa sirva de lista de trabajo entre sesiones |

Ese archivo incluye el **nombre del paciente** tal y como viene en el DICOM,
porque una lista de trabajo sin saber de quién es cada estudio no sirve de
nada. En pantalla se muestra enmascarado mientras el interruptor *anónimo*
esté puesto.

Es un archivo de texto plano: puedes abrirlo, editarlo o borrarlo cuando
quieras. Al desinstalar, el instalador pregunta si quieres eliminarlo.

## Lo que exportas

Las imágenes que saca el programa —PNG, GIF, MP4— contienen píxeles y nada
más: **ninguna etiqueta DICOM viaja dentro**, así que no arrastran datos del
paciente.

La única excepción no depende de él: si el estudio original lleva datos
*quemados* sobre la propia imagen (algunos equipos escriben el nombre en una
esquina), esos píxeles salen en la exportación como cualquier otro.

## Anonimato en pantalla

El interruptor *anónimo* del panel derecho oculta nombre, identificador y
fecha de nacimiento, tanto en la cabecera como en el registro. Viene puesto de
fábrica, pensando en quien enseña la pantalla en una consulta.

## Uso previsto

Esto no es un producto sanitario certificado. No está aprobado por ninguna
agencia reguladora y no debe ser la única base de un diagnóstico ni de una
decisión clínica. Sirve para ver, revisar y documentar estudios.
