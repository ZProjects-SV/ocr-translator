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
            # Si la palabra + espacio + chunk actual supera el límite, cerramos el chunk
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

        # Limpiamos el texto de líneas vacías
        text = "\n".join(line for line in text.split("\n") if line.strip())

        source    = get_translation_source()
        target    = get_translation_target()
        max_chars = get_translation_max_chars()

        translator = None
        try:
            print(f"[TRANSLATE] Instanciando GoogleTranslator ({source}→{target})...")
            t0 = time.perf_counter()
            
            # --- 1. INSTANCIAR ---
            translator = GoogleTranslator(source=source, target=target)

            # --- 2. PROCESAR ---
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
            # --- 3. DESTRUIR Y LIMPIAR (El corazón del motor efímero) ---
            if translator is not None:
                del translator
                translator = None  # Aseguramos que la referencia se pierda
            
            # Forzamos al recolector de basura de Python a liberar la memoria RAM
            # de las sesiones HTTP subyacentes inmediatamente.
            gc.collect()
            print("[TRANSLATE] GoogleTranslator destruido y memoria liberada (gc.collect).")

        # Devolvemos el resultado FUERA del try/except para asegurar que 
        # el finally siempre se ejecute antes de retornar.
        return result
# (Dependencias/Interacciones: Depende de 'preferences' en tiempo real y de 'deep_translator'.
#  Es instanciado por 'main.py' y su método 'translate' es llamado en el hilo de procesamiento.)