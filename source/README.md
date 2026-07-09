<div align="center">

# 🏗️ OCR Translator — Source Code / Código Fuente

[![License: GPL v3](https://img.shields.io/badge/License-GPLv3-blue.svg)](../LICENSE)
[![Python](https://img.shields.io/badge/Python-3.9.13-yellow.svg)](https://www.python.org/)

</div>

---

This folder contains the complete source code. Ideal if you want to modify the app, contribute, or compile it yourself.

### Prerequisites

- Windows 10/11 (64-bit)
- Python 3.9.13 → [download](https://www.python.org/downloads/)
- Git → [download](https://git-scm.com/)

### Setup & Run

**1. Clone the repository**
```bash
git clone https://github.com/ZProjects-SV/ocr-translator.git
cd ocr-translator/source
```

**2. Create a virtual environment** (recommended)
```bash
python -m venv venv
venv\Scripts\activate
```

**3. Install dependencies**
```bash
pip install -r requirements.txt
```
> ⚠️ PaddleOCR will download models automatically on first run (~200 MB). This may take a few minutes.

**4. Run the application**
```bash
python main.py
```

### Build the Executable

A `build.py` script is included, preconfigured to bundle all PaddleOCR and PySide6 native dependencies.

```bash
pip install pyinstaller
python build.py
```

The output will be generated in `dist/OCR_Translator/`.

### Project Structure

```
source/
├── core/               # Main logic (OCR, Translator, Capture)
├── resources/          # Icons, images and animation frames
├── ui/                 # Windows and GUI components (PySide6)
├── config.py           # Global constants and configuration
├── preferences.py      # Settings management (QSettings)
├── main.py             # Application entry point
├── requirements.txt    # Python dependencies
└── build.py            # PyInstaller build script
```

### Contributing

1. Fork the repository
2. Create a branch: `git checkout -b feature/my-improvement`
3. Commit: `git commit -m "Add my improvement"`
4. Push: `git push origin feature/my-improvement`
5. Open a Pull Request

---

<div align="center">
<sub>© 2026 ZProjects · <em>Developed with AI assistance / Desarrollado con asistencia de IA</em></sub>
</div>
