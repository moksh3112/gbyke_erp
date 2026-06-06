# -*- mode: python ; coding: utf-8 -*-
# Build: pyinstaller gbyke_erp.spec --clean

a = Analysis(
    ['main.py'],
    pathex=['.'],
    binaries=[],
    datas=[
        ('version.py', '.'),
        ('.env', '.'),
    ],
    hiddenimports=[
        'PyQt6.QtSvg',
        'PyQt6.sip',
        'desktop.screens.inventory',
        'desktop.screens.manufacturing',
        'desktop.screens.scooter_log',
        'desktop.screens.models',
        'desktop.screens.users',
        'desktop.screens.pdi',
        'desktop.screens.warehouses',
        'desktop.screens.dealers',
        'desktop.screens.shipments',
        'desktop.screens.spare_parts',
        'desktop.screens.damage_log',
        'desktop.screens.reports',
        'desktop.components.sidebar',
        'desktop.updater',
        'desktop.update_notifier',
    ],
    hookspath=[],
    runtime_hooks=[],
    excludes=[
        'app',
        'alembic',
        'fastapi',
        'uvicorn',
        'sqlalchemy',
        'psycopg2',
        'psycopg2_binary',
    ],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='GByke ERP',
    debug=False,
    strip=False,
    upx=False,
    console=False,
    windowed=True,
    icon=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    name='GByke ERP',
)
