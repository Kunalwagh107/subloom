# Dynamic Qt DLLs remain replaceable in this directory-based package (LGPL).
from pathlib import Path

root = Path(SPECPATH).parent
runtime = root / '.tools' / 'runtime'
if not (runtime / 'ffmpeg.exe').is_file() or not (runtime / 'whisper-cli.exe').is_file():
    raise SystemExit('Run scripts/bootstrap_runtime.py --download first.')
datas = [(str(root / 'src' / 'subloom' / 'ui' / 'Main.qml'), 'subloom/ui'),
         (str(root / 'src' / 'subloom' / 'ui' / 'icon.svg'), 'subloom/ui'),
         (str(root / 'src' / 'subloom' / 'model_manifest.json'), 'subloom')]
runtime_files = ['ffmpeg.exe', 'ffprobe.exe', 'whisper-cli.exe', 'whisper.dll',
                 'ggml.dll', 'ggml-base.dll', 'ggml-cpu.dll', 'runtime-manifest.json']
datas += [(str(runtime / name), 'tools') for name in runtime_files]
datas += [(str(runtime / 'licenses'), 'tools/licenses'), (str(root / 'LICENSE'), 'licenses'),
          (str(root / 'licenses'), 'licenses/components'),
          (str(root / 'docs' / 'THIRD_PARTY.md'), 'licenses')]
a = Analysis([str(root / 'packaging' / 'launcher.py')], pathex=[str(root / 'src')],
             binaries=[], datas=datas, hiddenimports=['PySide6.QtMultimedia', 'PySide6.QtQuick',
             'PySide6.QtQuickControls2', 'PySide6.QtQml', 'PySide6.QtWidgets'],
             excludes=['tkinter', 'PySide6.QtWebEngineCore', 'PySide6.QtWebEngineWidgets',
                       'PySide6.QtWebEngineQuick', 'PySide6.QtPdf', 'PySide6.Qt3DCore'])
# Qt's automatic hook includes every installed QML plugin and its DLLs, even
# unused browser/3D engines. This app fixes the style to Basic and uses only
# these modules. Keep software OpenGL and multimedia codec fallbacks intact.
qml_allowed = ('qtqml/', 'qtmultimedia/', 'qtquick/layouts/', 'qtquick/window/',
               'qtquick/templates/', 'qtquick/shapes/', 'qtquick/controls/basic/', 'qtquick/controls/impl/')
unneeded = ('qt6web', 'qt6quick3d', 'qt63d', 'qt6pdf', 'qt6charts', 'qt6graphs',
            'qt6datavisualization', 'qt6location', 'qt6positioning', 'qt6virtualkeyboard',
            'qt6scxml', 'qt6remoteobjects', 'qt6sensors', 'qt6texttospeech', 'qtwebengine')
def needed(entry):
    name = entry[0].replace('\\', '/').lower()
    base = name.rsplit('/', 1)[-1]
    if base.startswith(unneeded):
        return False
    if '/qml/' in name:
        module = name.split('/qml/', 1)[1]
        return (module.startswith(qml_allowed) or
                (module.startswith('qtquick/') and module.count('/') == 1) or
                (module.startswith('qtquick/controls/') and module.count('/') == 2))
    return True
a.datas = [entry for entry in a.datas if needed(entry)]
a.binaries = [entry for entry in a.binaries if needed(entry)]
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name='Subloom', debug=False,
          bootloader_ignore_signals=False, strip=False, upx=False, console=False,
          icon=str(root / 'packaging' / 'Subloom.ico'))
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name='Subloom')
