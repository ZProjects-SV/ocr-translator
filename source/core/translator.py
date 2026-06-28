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
)


# ==========================================================
# BLOQUE: Motor de Traducción — Ephemeral sin caché
# ==========================================================
class Translator:
    """Motor de traducción usando Google Translate gratuito. Sin caché, patrón ephemeral."""

    def __init__(self) -> None:
        print("[OK] Traductor listo (ephemeral, sin caché).")

    def translate(self, text: str) -> str:
        from deep_translator import GoogleTranslator
        import time

        if not text:
            return ""

        source    = get_translation_source()
        target    = get_translation_target()
        max_chars = get_translation_max_chars()

        text = "\n".join(line for line in text.split("\n") if line.strip())

        translator = None
        try:
            print(f"[TRANSLATE] Instanciando GoogleTranslator ({source}→{target})...")
            t0         = time.perf_counter()
            translator = GoogleTranslator(source=source, target=target)

            if len(text) > max_chars:
                chunks     = [text[i : i + max_chars] for i in range(0, len(text), max_chars)]
                translated = " ".join(translator.translate(chunk) for chunk in chunks)
            else:
                translated = translator.translate(text)

            print(f"[TRANSLATE] Completado en {time.perf_counter()-t0:.2f}s "
                  f"({len(text)}→{len(translated)} chars)")
            return translated

        except Exception as e:
            print(f"[TRANSLATE ERROR] {type(e).__name__}: {e}")
            return f"Error de traducción: {e}"

        finally:
            if translator is not None:
                try:
                    del translator
                except Exception:
                    pass
            print("[TRANSLATE] GoogleTranslator destruido")
# (Dependencias/Interacciones: Depende de 'preferences' en tiempo real y de 'deep_translator'.
#  Es instanciado por 'main.py' y su método 'translate' es llamado en el hilo de procesamiento.)