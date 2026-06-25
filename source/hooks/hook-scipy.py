# hook-scipy.py
from PyInstaller.utils.hooks import collect_submodules, collect_data_files

hiddenimports = collect_submodules('scipy', filter=lambda name: 'test' not in name)
datas = collect_data_files('scipy')

# Excluir módulos de testing que causan el crash con subprocess
excludedimports = [
    'numpy.testing',
    'numpy.testing._private',
    'scipy.ndimage._support_alternative_backends',
]