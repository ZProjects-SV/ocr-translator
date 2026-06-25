# hook-numpy.py
from PyInstaller.utils.hooks import collect_all

datas, binaries, hiddenimports = collect_all('numpy')

# Excluir testing pero incluir los binarios core completos
excludedimports = [
    'numpy.testing',
    'numpy.testing._private',
]