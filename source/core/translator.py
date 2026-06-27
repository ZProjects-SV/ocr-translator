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

import re

from preferences import (
    get_translation_source,
    get_translation_target,
    get_translation_max_chars,
    get_translation_cache_enabled,
)

# ==========================================================
# BLOQUE: Motor de Traducción y Gestión de Caché
# ==========================================================
class Translator:
    """Motor de traducción usando Google Translate gratuito."""

    def __init__(self) -> None:
        self._cache: dict[str, str] = {}
        print("[OK] Traductor listo.")

    def clear_cache(self) -> None:
        """Limpia la cache de traducciones en memoria."""
        self._cache.clear()
        print("[CACHE] Cache de traducciones vaciada.")

    def translate(self, text: str) -> str:
        from deep_translator import GoogleTranslator
        if not text:
            return ""

        source        = get_translation_source()
        target        = get_translation_target()
        max_chars     = get_translation_max_chars()
        cache_enabled = get_translation_cache_enabled()
        
        text = "\n".join(line for line in text.split("\n") if line.strip())

        #print(f"[TRANSLATE] Texto recibido ({len(text)} chars):\n{'-'*40}\n{text}\n{'-'*40}")

        # Crear clave de caché ignorando puntuación básica
        cache_key = f"{source}→{target}::{re.sub(r'[.…,!?]+', '', text.lower().strip())}"

        if cache_enabled and cache_key in self._cache:
            print("[CACHE] Usando traducción en cache.")
            return self._cache[cache_key]

        try:
            translator = GoogleTranslator(source=source, target=target)

            if len(text) > max_chars:
                chunks = [
                    text[i : i + max_chars]
                    for i in range(0, len(text), max_chars)
                ]
                translated = " ".join(translator.translate(chunk) for chunk in chunks)
            else:
                translated = translator.translate(text)

            # ✅ Log del resultado traducido
            #print(f"[TRANSLATE] Resultado ({source}→{target}):\n{'-'*40}\n{translated}\n{'-'*40}")

            if cache_enabled:
                self._cache[cache_key] = translated

            return translated

        except Exception as e:
            print(f"[TRANSLATE ERROR] {e}")
            return f"Error de traducción: {e}"
# (Dependencias/Interacciones: Depende de 'preferences' en tiempo real y de la librería 'deep_translator'. Es instanciado por 'main.py' y su método 'translate' es llamado en el hilo de procesamiento de la captura.)