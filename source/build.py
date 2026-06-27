import subprocess, sys, os, importlib.metadata, importlib.util
os.chdir(os.path.dirname(os.path.abspath(__file__)))

def get_pkg_path(name):
    spec = importlib.util.find_spec(name)
    if spec and spec.submodule_search_locations:
        return list(spec.submodule_search_locations)[0]
    return None

import Cython
cython_path  = os.path.dirname(Cython.__file__)

METADATA_PACKAGES = [
    'paddleocr', 'shapely', 'pyclipper',
    'Pillow', 'deep-translator', 'keyboard', 'pystray',
    'imageio', 'imgaug', 'scikit-image', 'opencv-python-headless',
]
metadata_args = []
for pkg in METADATA_PACKAGES:
    try:
        importlib.metadata.distribution(pkg)
        metadata_args += ['--copy-metadata', pkg]
    except importlib.metadata.PackageNotFoundError:
        print(f"  [WARN] metadata no encontrado: {pkg}")

cmd = [
    sys.executable, '-m', 'PyInstaller',
    'main.py',
    '--name', 'OCR_Translator',
    '--windowed',
    '--icon', 'resources/icon.ico',
    '--add-data', 'resources;resources',
    '--additional-hooks-dir', 'hooks',
    
    '--add-data', f'{cython_path};Cython',

    '--collect-all', 'paddle',
    '--collect-all', 'paddleocr',
    '--collect-all', 'pyclipper',
    '--collect-all', 'shapely',
    '--collect-all', 'skimage',
    '--collect-all', 'lazy_loader',
    '--collect-all', 'imgaug',
    '--collect-all', 'lmdb',
    '--collect-all', 'PIL',
    '--collect-all', 'numpy',
    '--collect-all', 'scipy',

    '--hidden-import', 'lazy_loader',
    '--hidden-import', 'paddleocr',
    '--hidden-import', 'paddleocr.tools',
    '--hidden-import', 'paddleocr.tools.infer',
    '--hidden-import', 'paddleocr.ppocr',
    '--hidden-import', 'paddleocr.ppocr.utils',
    '--hidden-import', 'paddleocr.ppocr.utils.logging',
    '--hidden-import', 'pystray._win32',
    '--hidden-import', 'deep_translator',
    '--hidden-import', 'keyboard',
    '--hidden-import', 'scipy.special',
    '--hidden-import', 'scipy.special.cython_special',
    '--hidden-import', 'scipy.ndimage',

    '--exclude-module', 'matplotlib',
    '--exclude-module', 'pytest',
    '--exclude-module', 'IPython',
    '--exclude-module', 'torch',
    '--exclude-module', 'tensorflow',
    '--exclude-module', 'paddle.distributed',
    '--exclude-module', 'visualdl',
    '--exclude-module', 'langchain',
    '--exclude-module', 'flask',
    '--exclude-module', 'notebook',
    '--exclude-module', 'numpy.testing',
    '--exclude-module', 'numpy.testing._private',

    *metadata_args,
    '--clean', '-y',
]

subprocess.call(cmd)
print("=" * 60)
print("BUILD COMPLETO: dist/OCR_Translator/OCR_Translator.exe")
print("=" * 60)