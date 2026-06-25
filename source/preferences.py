# preferences.py
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
from __future__ import annotations

from PySide6.QtCore import QSettings

from config import (
    APP_ORGANIZATION,
    APP_NAME,
    TRANSLATION_SOURCE,
    TRANSLATION_TARGET,
    TRANSLATION_MAX_CHARS,
    TRANSLATION_CACHE_ENABLED,
    CAPTURE_HOTKEYS,
    CAPTURE_SECONDARY_1,
    CAPTURE_SECONDARY_2,
    SELECTION_COLOR,      
    RESULT_FONT_FAMILY,   
    SELECTION_BORDER_WIDTH,     
)

# ==========================================================
# BLOQUE: Instancia de QSettings
# ==========================================================
def _settings() -> QSettings:
    """
    Devuelve la instancia global de QSettings usando APP_ORGANIZATION y APP_NAME.
    """
    return QSettings(APP_ORGANIZATION, APP_NAME)
# (Dependencias/Interacciones: Puente de conexión hacia el registro de Windows/Configuración nativa del SO. Todos los bloques de abajo dependen de esta función.)


# ==========================================================
# BLOQUE: Preferencias de Traducción
# ==========================================================
def get_translation_source() -> str:
    s = _settings()
    return s.value("translation/source", TRANSLATION_SOURCE)

def set_translation_source(value: str) -> None:
    s = _settings()
    s.setValue("translation/source", value)

def get_translation_target() -> str:
    s = _settings()
    return s.value("translation/target", TRANSLATION_TARGET)

def set_translation_target(value: str) -> None:
    s = _settings()
    s.setValue("translation/target", value)

def get_translation_max_chars() -> int:
    s = _settings()
    value = s.value("translation/max_chars", TRANSLATION_MAX_CHARS)
    try:
        return int(value)
    except Exception:
        return TRANSLATION_MAX_CHARS

def set_translation_max_chars(value: int) -> None:
    s = _settings()
    s.setValue("translation/max_chars", int(value))

def get_translation_cache_enabled() -> bool:
    s = _settings()
    value = s.value("translation/cache_enabled", TRANSLATION_CACHE_ENABLED)
    # QSettings puede devolver str, bool, etc. Normalizamos.
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.lower() in ("1", "true", "yes", "on")
    return bool(value)

def set_translation_cache_enabled(enabled: bool) -> None:
    s = _settings()
    s.setValue("translation/cache_enabled", bool(enabled))
# (Dependencias/Interacciones: Llamado por 'translator.py' en tiempo real y por 'preferences_window.py' al guardar.)


# ==========================================================
# BLOQUE: Hotkeys de Captura
# ==========================================================
def get_capture_hotkeys() -> list[str]:
    s = _settings()
    try:
        value = s.value("capture/hotkeys", CAPTURE_HOTKEYS)
    except Exception:
        return CAPTURE_HOTKEYS

    if isinstance(value, list):
        hotkeys = [str(v).strip() for v in value if str(v).strip()]
    elif isinstance(value, str):
        hotkeys = [v.strip() for v in value.split(",") if v.strip()]
    else:
        hotkeys = CAPTURE_HOTKEYS

    # Fallback final por si algo raro pasa
    if not hotkeys:
        hotkeys = CAPTURE_HOTKEYS

    return hotkeys

def set_capture_hotkeys(hotkeys: list[str]) -> None:
    s = _settings()
    s.setValue("capture/hotkeys", hotkeys)

def get_capture_secondary_1() -> str:
    s = _settings()
    value = s.value("capture/secondary1", CAPTURE_SECONDARY_1)
    return str(value) if value is not None else ""

def set_capture_secondary_1(hotkey: str) -> None:
    s = _settings()
    s.setValue("capture/secondary1", hotkey)

def get_capture_secondary_2() -> str:
    s = _settings()
    value = s.value("capture/secondary2", CAPTURE_SECONDARY_2)
    return str(value) if value is not None else ""

def set_capture_secondary_2(hotkey: str) -> None:
    s = _settings()
    s.setValue("capture/secondary2", hotkey)
# (Dependencias/Interacciones: Llamado por 'main.py' al registrar los hooks del teclado y por 'preferences_window.py'.)


# ==========================================================
# BLOQUE: Apariencia (Color, Fuente, Bordes)
# ==========================================================
def get_selection_color() -> str:
    return str(_settings().value("appearance/selection_color", SELECTION_COLOR))

def set_selection_color(color: str) -> None:
    _settings().setValue("appearance/selection_color", color)

def get_result_font_family() -> str:
    return str(_settings().value("appearance/font_family", RESULT_FONT_FAMILY))

def set_result_font_family(family: str) -> None:
    _settings().setValue("appearance/font_family", family)
    
def get_selection_border_width() -> int:
    try:
        return int(_settings().value("appearance/border_width", SELECTION_BORDER_WIDTH))
    except Exception:
        return SELECTION_BORDER_WIDTH

def set_selection_border_width(width: int) -> None:
    _settings().setValue("appearance/border_width", int(width))
# (Dependencias/Interacciones: Llamado por 'selection_window.py' para dibujar el área y por 'loading_window.py' para renderizar el texto traducido.)


# ==========================================================
# BLOQUE: Control de Modelos OCR Descargados
# ==========================================================
def get_downloaded_langs() -> list[str]:
    s = _settings()
    value = s.value("ocr/downloaded_langs", "")
    if not value:
        return []
    return [lang.strip() for lang in value.split(",") if lang.strip()]

def add_downloaded_lang(lang: str) -> None:
    s = _settings()
    langs = get_downloaded_langs()
    if lang not in langs:
        langs.append(lang)
        s.setValue("ocr/downloaded_langs", ",".join(langs))
# (Dependencias/Interacciones: Llamado exclusivamente por 'ocr_engine.py' para saber si un idioma requiere descarga o ya está disponible localmente.)