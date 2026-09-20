# -*- mode: python ; coding: utf-8 -*-
# Paquete autonomo del visor: dentro va el interprete, las librerias y el cliente
# de la interfaz, para que la maquina de destino no necesite nada instalado.

a = Analysis(
    ['..\main.py'],
    pathex=[],
    binaries=[],
    datas=[('..\icono.ico', '.')],
    # pydicom y imageio cargan estos por nombre en tiempo de ejecucion
    hiddenimports=['gdcm', 'pylibjpeg', 'openjpeg', 'libjpeg', 'imageio_ffmpeg'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    # se cuelan por las dependencias opcionales de imageio y pesan 165 MB de nada
    excludes=['cv2', 'pandas', 'matplotlib', 'scipy', 'tkinter', 'IPython', 'pytest',
              'PySide6', 'PyQt5', 'notebook'],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz, a.scripts, [],
    exclude_binaries=True,
    name='DCM Viewer',
    debug=False, strip=False, upx=True, console=False,
    disable_windowed_traceback=False,
    version='version.txt',
    icon=['..\icono.ico'],
)
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=True, name='DCM Viewer')
