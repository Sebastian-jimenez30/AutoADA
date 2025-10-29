# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_submodules, collect_all, collect_dynamic_libs

# ------------------------
# DATA / BIN / HIDDENIMPS
# ------------------------
datas = [
    ('assets', 'assets'),
    ('config', 'config'),
    ('db', 'db'),
    ('scripts', '_runners'),           # copias “runners” si los usas como archivos
    ('scripts\\REPS.bin', 'vault'),
    ('templates', 'templates'),
]
binaries = []
hiddenimports = [
    'cryptography',
    'cryptography.hazmat.backends.openssl',
    'pymongo',
    'sshtunnel',
    'pymongo.bson',
    'paramiko',
    'bson',
    'tkcalendar',
    'pyxlsb',
    'pyodbc',                          # <- asegura import estático de pyodbc
]

# Paquete scripts como módulos importables (evita "No module named scripts")
hiddenimports += collect_submodules('scripts')

# pymongo y familia
hiddenimports += collect_submodules('pymongo')

# pandas / numpy / openpyxl / tkcalendar / pyxlsb
tmp_ret = collect_all('pandas')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]
tmp_ret = collect_all('numpy')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]
tmp_ret = collect_all('openpyxl')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]
tmp_ret = collect_all('tkcalendar')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]
tmp_ret = collect_all('pyxlsb')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]

# ---- pyodbc: librerías nativas (muy importante en Windows) ----
binaries += collect_dynamic_libs('pyodbc')

# (Opcional) Evita comprimir extensiones C con UPX — a veces falla
upx_exclude = ["pyodbc*.pyd", "pyodbc*.dll"]

# ------------------------
# ANALYSIS / EXE
# ------------------------
a = Analysis(
    ['main.py'],
    pathex=['.'],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=['hooks\\set_cwd_runtime_hook.py'],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='AutoADA',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=upx_exclude,         # <- aquí aplicamos el exclude
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=['assets\\Logodot.ico'],
)
