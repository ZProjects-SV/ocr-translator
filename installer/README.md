<div align="center">

# 💿 OCR Translator — Installer

[![License: AGPL v3](https://img.shields.io/badge/License-AGPLv3-blue.svg)](../LICENSE)
[![Platform](https://img.shields.io/badge/Platform-Windows%2010%2F11-0078d7.svg)](https://www.microsoft.com/windows)

</div>

---

## Overview

Traditional Windows installer for OCR Translator.  
Creates Start Menu and Desktop shortcuts and supports clean uninstallation via Settings or Control Panel.

## Installation steps

1. **Download** `OCR_Translator_Setup.exe` from the [Releases](https://github.com/ZProjects-SV/ocr-translator/releases) page.
2. **Run** the downloaded file.
3. If Windows SmartScreen appears:
   - Click **“More info”**.
   - Click **“Run anyway”** (the installer is unsigned, but the source code is fully public).
4. Follow the setup wizard:
   - Accept the license agreement (AGPL v3).
   - Choose the destination folder (default: `C:\Program Files\OCR Translator`).
   - Choose whether to create Desktop and Start Menu shortcuts.
5. Click **“Install”**, then **“Finish”**.

After installation, you can find **OCR Translator** in the Start Menu and (optionally) on the Desktop.

## Uninstalling

**Option 1 — Settings**

> Settings → Apps → OCR Translator → Uninstall

**Option 2 — Control Panel**

> Control Panel → Programs → Programs and Features → right‑click **OCR Translator** → Uninstall

> 💡 Your preferences and custom hotkeys are stored in the Windows Registry and are **not removed** on uninstall.  
> If you reinstall later, your settings will be reused.

## Default installation path

```text
C:\Program Files\OCR Translator\
├── OCR_Translator.exe
├── _internal\      ← Do not delete
└── uninstall.exe
```

The `_internal\` folder contains all runtime files, dependencies, and models.  
Deleting or moving it will prevent the application from starting.

---

<div align="center">
<sub>© 2026 ZProjects · <em>Developed with AI assistance</em></sub>
</div>