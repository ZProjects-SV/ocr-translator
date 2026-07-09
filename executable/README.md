<div align="center">

# 📂 OCR Translator — Portable Executable

[![License: AGPL v3](https://img.shields.io/badge/License-AGPLv3-blue.svg)](../LICENSE)
[![Platform](https://img.shields.io/badge/Platform-Windows%2010%2F11-0078d7.svg)](https://www.microsoft.com/windows)

</div>

---

## Overview

Portable, ready‑to‑run version of OCR Translator.  
**No installation and no Python required.** Just download, extract, and run.

## Quick start

1. **Download** `OCRTranslator-portable.zip` from the [Releases](https://github.com/ZProjects-SV/ocr-translator/releases) page.
2. **Extract** the contents anywhere (for example `C:\Tools\OCRTranslator\`).
3. **Run** `OCR_Translator.exe`.

The app will show a loading screen while models are initialized, then minimize to the **system tray** (bottom‑right corner, near the clock).

## Windows SmartScreen warning

On first launch, Windows may show a blue **“Windows protected your PC”** screen.

**Why does this happen?**  
The executable is not digitally signed with a paid code‑signing certificate. Windows treats unsigned `.exe` files from the internet as unknown and warns by default.

**How to bypass it safely:**

1. Click **“More info”** in the SmartScreen window.
2. Click **“Run anyway”**.

The program is fully open source — you can inspect the code in the [`source/`](../source/) folder and build your own executable from it.

## System requirements

| Requirement | Minimum |
| :--- | :--- |
| OS | Windows 10 64‑bit (version 1903+) |
| RAM | 4 GB (8 GB recommended) |
| Disk space | ~1.5 GB |
| Internet | Required for real‑time translation |

## The `_internal/` folder

After extracting the `.zip`, you will see `OCR_Translator.exe` and a folder named `_internal/`.

The `_internal/` folder contains:

- Embedded Python runtime
- Required libraries and dependencies
- PaddleOCR models
- All resources needed by the GUI

**Do not delete, rename, or move `_internal/`.**  
If it is missing or moved, `OCR_Translator.exe` will not start.

---

<div align="center">
<sub>© 2026 ZProjects · <em>Developed with AI assistance</em></sub>
</div>