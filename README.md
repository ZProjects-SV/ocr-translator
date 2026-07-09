<div align="center">

# OCR Translator

Capture text from any area of your screen and translate it instantly.

[![License: AGPL v3](https://img.shields.io/badge/License-AGPLv3-blue.svg)](./LICENSE)
[![Python](https://img.shields.io/badge/Python-3.11-yellow.svg)](https://www.python.org/)
[![Platform](https://img.shields.io/badge/Platform-Windows%2010%2F11-0078d7.svg)](https://www.microsoft.com/windows)
[![AI Assisted](https://img.shields.io/badge/Built%20with-AI%20assistance-8a2be2.svg)](#)

</div>

---

## Overview

OCR Translator is a Windows desktop application that lets you capture any region of the screen, extract text with OCR, and translate it in real time.

It is built with Python, PySide6, PaddleOCR, and deep-translator, with a focus on fast capture, tray-based background use, and practical everyday translation.

## Before and After

<img width="1375" height="768" alt="beforeandafter" src="https://github.com/user-attachments/assets/81b23641-3bc7-4b16-85eb-854c3ba519e6" />

## Available versions

| Version | Description | Folder |
| :--- | :--- | :--- |
| 🏗️ **Source Code** | For developers who want to inspect, modify, or build the project themselves. | [`source/`](./source/) |
| 📂 **Portable Executable** | Ready to run with no installation required. | [`executable/`](./executable/) |
| 💿 **Installer** | Standard Windows setup with shortcuts and uninstall support. | [`installer/`](./installer/) |

## Features

- Interactive screen region capture.
- OCR text extraction with image preprocessing.
- Real-time translation workflow.
- Background operation through the system tray.
- Custom keyboard shortcuts.
- Downloadable OCR language models from Preferences.

## Tech stack

OCR Translator is built on the following main technologies:

- Python
- PySide6 (Qt for Python)
- PaddleOCR
- PaddlePaddle
- deep-translator
- Pillow
- NumPy
- PyInstaller
- pystray
- keyboard
- onnxruntime-directml
- Cython
- Hugging Face Hub
- PyYAML
- NVIDIA Management Library (pynvml)

For dependency and license details, see [`THIRD_PARTY_LICENSES.md`](./THIRD_PARTY_LICENSES.md).

## License

Copyright (C) 2026 ZProjects

This project is licensed under the [GNU Affero General Public License v3.0](./LICENSE).

If you modify this project or use it to provide a network-accessible service, you must publish the corresponding source code under the same license.

---

<div align="center">
<sub>© 2026 ZProjects · Made in 🇸🇻 El Salvador · <em>Developed with AI assistance</em></sub>
</div>
