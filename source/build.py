# OCR Translator
# Copyright (C) 2026 ZProjects
#
# This file is part of OCR Translator.
# OCR Translator is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# OCR Translator is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with OCR Translator. If not, see <https://www.gnu.org/licenses/>.
import subprocess, sys, os
import importlib.metadata
sys.setrecursionlimit(5000)
os.chdir(os.path.dirname(os.path.abspath(__file__)))
import Cython
cython_path  = os.path.dirname(Cython.__file__)
# --- Detección dinámica de dependencias de PaddleX ---
try:
    import paddlex
    user_deps = [dist.metadata["Name"] for dist in importlib.metadata.distributions()]
    deps_all = list(paddlex.utils.deps.BASE_DEP_SPECS.keys())
    deps_need = [dep for dep in user_deps if dep in deps_all]
except ImportError:
    deps_need = []

cmd = [
    sys.executable, '-m', 'PyInstaller',
    'main.py',
    '--name', 'OCR_Translator',
    '--windowed',
    '--icon', 'resources/icon.ico',
    '--add-data', 'resources;resources',
    '--add-data', 'translations;translations',

    # === PaddleOCR 3.x core ===
    '--collect-data', 'paddlex',
    '--collect-binaries', 'paddle',

    # === ONNX Runtime (tu motor de inferencia real) ===
    '--collect-all', 'onnxruntime',
    '--collect-all', 'onnx',
    '--hidden-import', 'onnxruntime.capi._pybind_state',
    
    # === Cython (preprocesamiento) ===
    '--add-data', f'{cython_path};Cython',
    '--hidden-import', 'Cython.Compiler.Code',
    '--hidden-import', 'Cython.Compiler.Symtab',
    '--hidden-import', 'Cython.Compiler.PyrexTypes',

    # === HuggingFace Hub (descarga de modelos PP-OCRv6) ===
    '--collect-all', 'huggingface_hub',
    '--hidden-import', 'huggingface_hub.constants',
    '--hidden-import', 'huggingface_hub.file_download',

    # === OpenCV (preprocesamiento) ===
    '--collect-all', 'cv2',

    # === PySide6 (GUI) ===
    '--collect-all', 'PySide6',

    # === Dependencias de tu app ===
    '--hidden-import', 'pystray._win32',
    '--hidden-import', 'deep_translator',
    '--hidden-import', 'keyboard',
    '--hidden-import', 'pynvml',
    '--hidden-import', 'yaml',

    # === Exclusiones ===
    '--exclude-module', 'matplotlib',
    '--exclude-module', 'pytest',
    '--exclude-module', 'IPython',
    '--exclude-module', 'torch',
    '--exclude-module', 'tensorflow',
    '--exclude-module', 'visualdl',
    '--exclude-module', 'langchain',
    '--exclude-module', 'flask',
    '--exclude-module', 'notebook',
    '--exclude-module', 'numpy.testing',
    '--exclude-module', 'numpy.testing._private',
]

# Metadata dinámica
for dep in deps_need:
    cmd += ['--copy-metadata', dep]

cmd += ['--clean', '-y']

from PyInstaller.__main__ import run as pyinstaller_run

print("Ejecutando:", " ".join(cmd[3:]))
pyinstaller_run(cmd[3:])