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
import gc
import time
from typing import List

from preferences import (
    get_translation_source,
    get_translation_target,
    get_translation_max_chars,
)


# ==========================================================
# BLOQUE: Motor de Traducción — Ephemeral sin caché
# ==========================================================
class Translator:
    """Motor de traducción usando Google Translate gratuito.
    Patrón efímero estricto: Instanciar -> Procesar -> Destruir -> Limpiar memoria."""

    def __init__(self) -> None:
        print("[OK] Traductor listo (ephemeral, sin caché).")

    def _split_text_intelligently(self, text: str, max_chars: int) -> List[str]:
        """Divide el texto respetando los espacios para no romper palabras."""
        if len(text) <= max_chars:
            return [text]

        chunks = []
        current_chunk = ""
        for word in text.split():
            if len(current_chunk) + len(word) + 1 > max_chars:
                if current_chunk:
                    chunks.append(current_chunk.strip())
                current_chunk = word
            else:
                current_chunk += " " + word if current_chunk else word

        if current_chunk:
            chunks.append(current_chunk.strip())

        return chunks

    def translate(self, text: str) -> str:
        from deep_translator import GoogleTranslator

        if not text:
            return ""

        text = "\n".join(line for line in text.split("\n") if line.strip())
        if not text:
            return ""

        source = get_translation_source() or "auto"
        target = get_translation_target() or "en"
        max_chars = get_translation_max_chars() or 4500

        translator = None
        result = ""
        try:
            print(f"[TRANSLATE] Instanciando GoogleTranslator ({source}→{target})...")
            t0 = time.perf_counter()

            translator = GoogleTranslator(source=source, target=target)

            chunks = self._split_text_intelligently(text, max_chars)

            translated_chunks = []
            for chunk in chunks:
                translated_chunks.append(translator.translate(chunk))

            translated = " ".join(translated_chunks)

            elapsed = time.perf_counter() - t0
            print(f"[TRANSLATE] Completado en {elapsed:.2f}s ({len(text)}→{len(translated)} chars)")

            result = translated

        except Exception as e:
            print(f"[TRANSLATE ERROR] {type(e).__name__}: {e}")
            result = f"Error de traducción: {e}"

        finally:
            if translator is not None:
                del translator
                translator = None
            gc.collect()
            print("[TRANSLATE] GoogleTranslator destruido y memoria liberada (gc.collect).")

        return result