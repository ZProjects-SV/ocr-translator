<div align="center">

# 📂 OCR Translator — Portable Executable / Ejecutable Portable

[![License: GPL v3](https://img.shields.io/badge/License-GPLv3-blue.svg)](../LICENSE)
[![Platform](https://img.shields.io/badge/Platform-Windows%2010%2F11-0078d7.svg)](https://www.microsoft.com/windows)

</div>

---

## 🇬🇧 English

Portable version, ready to use. **No installation or Python required.** Just download, extract and run.

### Quick Start

1. **Download** `OCRTranslator-portable.zip` from the [Releases](https://github.com/ZProjects-SV/ocr-translator/releases) page.
2. **Extract** the folder anywhere (e.g. `C:\Tools\OCRTranslator\`).
3. **Run** `OCR_Translator.exe`.

The app will show a loading screen and then minimize to the **system tray** (bottom-right corner, near the clock).

### ⚠️ Windows SmartScreen Warning

On first launch, Windows may show a blue screen saying *"Windows protected your PC"*.

**Why does this happen?**  
The executable doesn't have a paid Digital Signature (a developer certificate that costs hundreds of dollars per year). Windows blocks unknown `.exe` files by default.

**How to safely bypass it:**
1. Click **"More info"** in the SmartScreen window.
2. Click **"Run anyway"**.

The program is fully open source. You can review the code in the [`source/`](../source/) folder.

### System Requirements

| Requirement | Minimum |
| :--- | :--- |
| OS | Windows 10 64-bit (version 1903+) |
| RAM | 4 GB (8 GB recommended) |
| Disk space | ~1.5 GB |
| Internet | Required for real-time translation |

### What is the `_internal/` folder?

After extracting, you will see `OCR_Translator.exe` and a folder named `_internal/`. This folder contains all Python libraries, PaddleOCR models, and resources the app needs. **Do not delete or move it** — the application will not start without it.

---

## 🇸🇻 Español

Versión portable lista para usar. **No requiere instalación ni Python.** Solo descarga, extrae y ejecuta.

### Inicio rápido

1. **Descarga** `OCRTranslator-portable.zip` desde la página de [Releases](https://github.com/ZProjects-SV/ocr-translator/releases).
2. **Extrae** la carpeta en cualquier ubicación (ej. `C:\Tools\OCRTranslator\`).
3. **Ejecuta** `OCR_Translator.exe`.

La app mostrará una pantalla de carga y luego se minimizará a la **bandeja del sistema** (esquina inferior derecha, junto al reloj).

### ⚠️ Advertencia de Windows SmartScreen

Al ejecutar por primera vez, Windows puede mostrar una ventana azul diciendo *"Windows protegió tu PC"*.

**¿Por qué ocurre esto?**  
El ejecutable no tiene una "Firma Digital" comprada (un certificado que cuesta cientos de dólares al año). Windows bloquea por defecto los `.exe` desconocidos.

**¿Cómo omitirlo de forma segura?**
1. En la ventana azul, haz clic en **"Más información"**.
2. Haz clic en **"Ejecutar de todas formas"**.

El programa es completamente de código abierto. Puedes revisar el código en la carpeta [`source/`](../source/).

### Requisitos del sistema

| Requisito | Mínimo |
| :--- | :--- |
| OS | Windows 10 64-bit (versión 1903+) |
| RAM | 4 GB (8 GB recomendado) |
| Espacio en disco | ~1.5 GB |
| Internet | Requerido para traducción en tiempo real |

### ¿Qué es la carpeta `_internal/`?

Al extraer el `.zip`, verás `OCR_Translator.exe` y una carpeta llamada `_internal/`. Esta contiene todas las librerías, modelos de PaddleOCR y recursos necesarios. **¡No la elimines ni muevas!** Sin ella, la aplicación no iniciará.

---

<div align="center">
<sub>© 2026 ZProjects · <em>Developed with AI assistance / Desarrollado con asistencia de IA</em></sub>
</div>
