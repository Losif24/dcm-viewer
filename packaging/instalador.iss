; Instalador de DCM Viewer. Se compila con ISCC.exe desde packaging\construir.bat
; Va todo dentro: el equipo de destino no necesita Python ni dependencias.

#define Nombre     "DCM Viewer"
#define Version    "1.0.0"
#define Autor      "Jose Duran"
#define Sitio      "https://github.com/Losif24/dcm-viewer"
#define Ejecutable "DCM Viewer.exe"

[Setup]
AppId={{7B3F2B18-9A4C-4D2E-9C51-0B7A6E1D4C90}
AppName={#Nombre}
AppVersion={#Version}
AppVerName={#Nombre} {#Version}
AppPublisher={#Autor}
AppPublisherURL={#Sitio}
AppSupportURL={#Sitio}/issues
AppUpdatesURL={#Sitio}/releases
VersionInfoVersion={#Version}
VersionInfoDescription=Visor de estudios DICOM

; Se instala para el usuario: sin UAC. Quien quiera para todo el equipo puede elegirlo.
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
DefaultDirName={autopf}\{#Nombre}
DefaultGroupName={#Nombre}
DisableProgramGroupPage=yes
AllowNoIcons=yes

LicenseFile=..\LICENSE
InfoBeforeFile=aviso.txt
SetupIconFile=..\icono.ico
UninstallDisplayIcon={app}\{#Ejecutable}
WizardStyle=modern
WizardSizePercent=110
SolidCompression=yes
Compression=lzma2/max
OutputDir=salida
OutputBaseFilename=DCMViewer-{#Version}-instalador
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible

[Languages]
Name: "es"; MessagesFile: "compiler:Languages\Spanish.isl"

[Tasks]
Name: "escritorio"; Description: "Crear un acceso directo en el escritorio"; GroupDescription: "Accesos:"
Name: "asociar";    Description: "Abrir los archivos .dcm con {#Nombre}"; GroupDescription: "Integracion con Windows:"
Name: "carpeta";    Description: "Anadir ""Abrir con {#Nombre}"" al menu de las carpetas"; GroupDescription: "Integracion con Windows:"

[Files]
Source: "dist\{#Nombre}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "aviso.txt";        DestDir: "{app}"; DestName: "PRIVACIDAD Y SEGURIDAD.txt"; Flags: ignoreversion
Source: "..\LICENSE";       DestDir: "{app}"; DestName: "LICENCIA.txt"; Flags: ignoreversion

[Icons]
Name: "{group}\{#Nombre}";           Filename: "{app}\{#Ejecutable}"
Name: "{group}\Privacidad y seguridad"; Filename: "{app}\PRIVACIDAD Y SEGURIDAD.txt"
Name: "{autodesktop}\{#Nombre}";     Filename: "{app}\{#Ejecutable}"; Tasks: escritorio

[Registry]
; Asociacion de .dcm, solo en la rama del usuario que instala
Root: HKA; Subkey: "Software\Classes\.dcm\OpenWithProgids"; ValueType: string; ValueName: "DCMViewer.estudio"; ValueData: ""; Flags: uninsdeletevalue; Tasks: asociar
Root: HKA; Subkey: "Software\Classes\DCMViewer.estudio"; ValueType: string; ValueName: ""; ValueData: "Estudio DICOM"; Flags: uninsdeletekey; Tasks: asociar
Root: HKA; Subkey: "Software\Classes\DCMViewer.estudio\DefaultIcon"; ValueType: string; ValueName: ""; ValueData: "{app}\{#Ejecutable},0"; Tasks: asociar
Root: HKA; Subkey: "Software\Classes\DCMViewer.estudio\shell\open\command"; ValueType: string; ValueName: ""; ValueData: """{app}\{#Ejecutable}"" ""%1"""; Tasks: asociar
; "Abrir con" en el menu contextual de una carpeta
Root: HKA; Subkey: "Software\Classes\Directory\shell\DCMViewer"; ValueType: string; ValueName: ""; ValueData: "Abrir con {#Nombre}"; Flags: uninsdeletekey; Tasks: carpeta
Root: HKA; Subkey: "Software\Classes\Directory\shell\DCMViewer"; ValueType: string; ValueName: "Icon"; ValueData: "{app}\{#Ejecutable},0"; Tasks: carpeta
Root: HKA; Subkey: "Software\Classes\Directory\shell\DCMViewer\command"; ValueType: string; ValueName: ""; ValueData: """{app}\{#Ejecutable}"" ""%V"""; Tasks: carpeta

[Run]
Filename: "{app}\{#Ejecutable}"; Description: "Abrir {#Nombre}"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
Type: filesandordirs; Name: "{app}"

[Code]
// Al desinstalar, el registro de estudios es del usuario: se pregunta antes de borrarlo.
procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
var
  Datos: String;
begin
  if CurUninstallStep = usPostUninstall then
  begin
    Datos := ExpandConstant('{userappdata}\DCM Viewer');
    if DirExists(Datos) then
      if MsgBox('¿Borrar también el registro de estudios y sus notas?' + #13#10 + #13#10 +
                Datos + #13#10 + #13#10 +
                'Las imágenes no se tocan: solo se borra la lista de estudios abiertos.',
                mbConfirmation, MB_YESNO) = IDYES then
        DelTree(Datos, True, True, True);
  end;
end;
