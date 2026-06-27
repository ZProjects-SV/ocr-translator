# config.py
# OCR Translator
# Copyright (C) 2026 ZProjects
#
# This file is part of OCR Translator.
# OCR Translator is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# OCR Translator is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with OCR Translator. If not, see <https://www.gnu.org/licenses/>.
# ==========================================================
# BLOQUE: Identidad básica de la app
# ==========================================================
APP_NAME = "OCR Translator"
APP_VERSION = "1.0.0"
APP_ORGANIZATION = "ZProjects"
APP_USER_MODEL_ID = "OCRTranslator.App.1.0"
# (Dependencias/Interacciones: Usado globalmente por 'main.py' y 'preferences.py' para registrar la app en Windows y en QSettings)


# ==========================================================
# BLOQUE: Traducción (defaults globales)
# ==========================================================
TRANSLATION_SOURCE = "en"
TRANSLATION_TARGET = "es"
TRANSLATION_MAX_CHARS = 4800
TRANSLATION_CACHE_ENABLED = True

TRANSLATION_LANG_CHOICES = [
    "en", "es", "pt", "fr",
    "de", "it", "ja", "ko", "zh-cn",
]

TRANSLATION_TO_PADDLE_LANG = {
    "en": "en", "es": "es", "pt": "en",
    "fr": "en", "de": "en", "it": "en",
    "ja": "japan", "ko": "korean", "zh-cn": "ch",
}

# Nombres completos para mostrar en la UI
TRANSLATION_LANG_DISPLAY = {
    "en":    "English",
    "es":    "Español",
    "pt":    "Português",
    "fr":    "Français",
    "de":    "Deutsch",
    "it":    "Italiano",
    "ja":    "日本語",
    "ko":    "한국어",
    "zh-cn": "中文 (简体)",
}

PADDLE_LANG = "en"
PADDLE_MIN_CONFIDENCE = 0.6
PADDLE_MIN_CONFIDENCE_PIXEL = 0.35
# (Dependencias/Interacciones: Usado por 'translator.py', 'ocr_engine.py' y la UI de 'preferences_window.py')


# ==========================================================
# BLOQUE: Atajos de teclado y Apariencia (defaults globales)
# ==========================================================
CAPTURE_HOTKEYS = ["shift+T"]
CAPTURE_SECONDARY_1 = ""
CAPTURE_SECONDARY_2 = ""

RESULT_FONT_FAMILY     = "Segoe UI"  # fuente del texto traducido
SELECTION_OVERLAY_COLOR = (0, 0, 0, 120)
SELECTION_COLOR  = "#00aaff"
SELECTION_BORDER_WIDTH  = 2
SELECTION_MIN_WIDTH     = 10
SELECTION_MIN_HEIGHT    = 10
# (Dependencias/Interacciones: Usado por 'preferences.py' como fallback, y por 'selection_window.py' y 'loading_window.py' para renderizar las cajas.)


# ==========================================================
# BLOQUE: UI / Textos básicos
# ==========================================================
ABOUT_TITLE = "OCR Translator"
ABOUT_TEXT = (
    "OCR + Traductor v1.0\n\n"
    "Captura texto de pantalla y traduce\n"
)

TRAY_NAME             = "OCR_Translator"
TRAY_MENU_PREFERENCES = "Preferencias…"
TRAY_MENU_ABOUT       = "Acerca de"
TRAY_MENU_QUIT        = "Salir"
# (Dependencias/Interacciones: Usado exclusivamente por 'main.py' para construir el System Tray y la ventana "Acerca de")