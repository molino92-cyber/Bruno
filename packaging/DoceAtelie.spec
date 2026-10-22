# -*- mode: python ; coding: utf-8 -*-
from pathlib import Path
import sys
from PyInstaller.utils.hooks import collect_all, collect_data_files, copy_metadata

root = Path(SPECPATH).parent
st_data, st_bins, st_hidden = collect_all("streamlit")
datas = st_data + collect_data_files("altair") + collect_data_files("reportlab") + copy_metadata("streamlit")
datas += [(str(root / "app.py"), "."), (str(root / "assets"), "assets")]
a = Analysis(
    [str(root / "desktop.py")], pathex=[str(root)],
    binaries=st_bins, datas=datas,
    hiddenimports=st_hidden + ["confeitaria.domain", "confeitaria.catalog_data", "confeitaria.postal", "confeitaria.demo", "confeitaria.storage", "confeitaria.pdf", "confeitaria.presentation", "confeitaria.ui_customers", "confeitaria.ui_quotes", "PIL.Image", "reportlab.platypus", "pandas", "altair", "pyarrow"],
    hookspath=[], hooksconfig={}, runtime_hooks=[], excludes=["pytest", "pypdf"],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz, a.scripts, [], exclude_binaries=True, name="DoceAtelie",
    debug=False, bootloader_ignore_signals=False, strip=False, upx=False,
    console=sys.platform != "win32", disable_windowed_traceback=False,
    icon=str(root / "assets" / "doce-atelie.ico") if sys.platform == "win32" else None,
)
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name="DoceAtelie")
