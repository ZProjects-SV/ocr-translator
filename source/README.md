<div align="center">

# 🏗️ OCR Translator — Source Code / Código Fuente

[![License: GPL v3](https://img.shields.io/badge/License-GPLv3-blue.svg)](../LICENSE)
[![Python](https://img.shields.io/badge/Python-3.11%2B-yellow.svg)](https://www.python.org/)

</div>

---

## 🇬🇧 English

This folder contains the complete source code. Ideal if you want to modify the app, contribute, or compile it yourself.

### Prerequisites

- Windows 10/11 (64-bit)
- Python 3.11 or higher → [download](https://www.python.org/downloads/)
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
├── hooks/              # Custom PyInstaller hooks (numpy, paddle, scipy...)
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

## 🇸🇻 Español

Esta carpeta contiene el código fuente completo. Ideal si quieres modificar la aplicación, contribuir, o compilarla tú mismo.

### Requisitos previos

- Windows 10/11 (64-bit)
- Python 3.11 → [descargar](https://www.python.org/downloads/)
- Git → [descargar](https://git-scm.com/)

### Configuración y ejecución

**1. Clonar el repositorio**
```bash
git clone https://github.com/ZProjects-SV/ocr-translator.git
cd ocr-translator/source
```

**2. Crear un entorno virtual** (recomendado)
```bash
python -m venv venv
venv\Scripts\activate
```

**3. Instalar dependencias**
```bash
pip install -r requirements.txt
```
> ⚠️ PaddleOCR descargará modelos automáticamente en el primer uso (~200 MB). Puede tardar varios minutos.

**4. Ejecutar la aplicación**
```bash
python main.py
```

### Compilar el ejecutable

Se incluye un script `build.py` preconfigurado para empaquetar todas las dependencias nativas de PaddleOCR y PySide6.

```bash
pip install pyinstaller
python build.py
```

El resultado se generará en `dist/OCR_Translator/`.

### Estructura del proyecto

```
source/
├── core/               # Lógica principal (OCR, Traductor, Captura)
├── hooks/              # Hooks personalizados de PyInstaller (numpy, paddle, scipy...)
├── resources/          # Íconos, imágenes y frames de animación
├── ui/                 # Ventanas e interfaz gráfica (PySide6)
├── config.py           # Constantes y configuración global
├── preferences.py      # Gestión de ajustes (QSettings)
├── main.py             # Punto de entrada de la aplicación
├── requirements.txt    # Dependencias de Python
└── build.py            # Script de compilación de PyInstaller
```

### Contribuir

1. Haz un fork del repositorio
2. Crea una rama: `git checkout -b feature/mi-mejora`
3. Commit: `git commit -m "Agrega mi mejora"`
4. Push: `git push origin feature/mi-mejora`
5. Abre un Pull Request

---

<div align="center">
<sub>© 2026 ZProjects · <em>Developed with AI assistance / Desarrollado con asistencia de IA</em></sub>
</div>
