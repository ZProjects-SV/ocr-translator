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
import time
import random
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
    Patrón efímero estricto: Instanciar -> Procesar -> Destruir."""

    MAX_RETRIES = 4
    BASE_BACKOFF = 5.0
    REQUEST_DELAY = 0.5
    MAX_BACKOFF = 60.0

    def __init__(self) -> None:
        print("[OK] Traductor listo (ephemeral, sin caché).")

    def _split_text_intelligently(self, text: str, max_chars: int) -> List[str]:
        """Divide el texto respetando los espacios para no romper palabras.
        Si una palabra individual excede max_chars, se corta a la fuerza
        para evitar quedarnos con un chunk imposible de enviar."""
        if len(text) <= max_chars:
            return [text]

        chunks = []
        current_chunk = ""

        for word in text.split():
            if len(word) > max_chars:
                if current_chunk:
                    chunks.append(current_chunk.strip())
                    current_chunk = ""
                for i in range(0, len(word), max_chars):
                    chunks.append(word[i:i + max_chars])
                continue

            if len(current_chunk) + len(word) + 1 > max_chars:
                if current_chunk:
                    chunks.append(current_chunk.strip())
                current_chunk = word
            else:
                current_chunk += " " + word if current_chunk else word

        if current_chunk:
            chunks.append(current_chunk.strip())

        return chunks

    def _translate_chunk_with_retry(self, translator, chunk: str) -> str:
        """Traduce un chunk usando la misma instancia del traductor.
        Si falla por red, espera progresivamente (sin crear sesiones nuevas)
        para no activar alertas de spam en Google."""
        
        last_error = None
        current_backoff = self.BASE_BACKOFF

        for attempt in range(1, self.MAX_RETRIES + 1):
            try:
                # Usamos el mismo objeto translator. deep_translator hará 
                # una única petición HTTP limpia por llamada.
                return translator.translate(chunk)
                
            except Exception as e:
                last_error = e
                jitter = random.uniform(0.8, 1.2)  # Variación aleatoria +/- 20%
                wait = current_backoff * jitter
                
                print(f"[TRANSLATE WARN] Intento {attempt}/{self.MAX_RETRIES} falló "
                      f"({type(e).__name__}). Reintentando en {wait:.1f}s...")
                
                time.sleep(wait)
                
                # Doblamos el tiempo de espera para el próximo intento
                current_backoff = min(current_backoff * 2, self.MAX_BACKOFF)

        print(f"[TRANSLATE ERROR] Chunk falló tras {self.MAX_RETRIES} intentos: "
              f"{type(last_error).__name__}: {last_error}. Se conserva texto original.")
        return chunk

    def translate(self, text: str) -> str:
        # Importación diferida
        from deep_translator import GoogleTranslator

        if not text:
            return ""

        # ======================================================
        # LOG DE ENTRADA EXACTO (Sin modificar)
        # ======================================================
        #print("\n" + "="*60)
        #print("[LOG ENTRADA] Texto exacto recibido por el traductor:")
        #print(repr(text))
        #print("="*60 + "\n")

        source = get_translation_source() or "auto"
        target = get_translation_target() or "en"
        max_chars = get_translation_max_chars() or 4500

        result = ""
        try:
            print(f"[TRANSLATE] Iniciando traducción ({source}→{target})...")
            t0 = time.perf_counter()

            # Instanciamos UNA sola vez
            translator = GoogleTranslator(source=source, target=target)
            chunks = self._split_text_intelligently(text, max_chars)

            translated_chunks = []
            for idx, chunk in enumerate(chunks):
                translated_chunks.append(
                    self._translate_chunk_with_retry(translator, chunk)
                )
                
                # Pausa natural entre chunks exitosos (muy importante para evitar baneos)
                if idx < len(chunks) - 1:
                    time.sleep(self.REQUEST_DELAY)

            translated = " ".join(translated_chunks)

            # ======================================================
            # LOG DE SALIDA EXACTO (Sin modificar)
            # ======================================================
            #print("\n" + "-"*60)
            #print("[LOG SALIDA] Texto exacto devuelto por el traductor:")
            #print(repr(translated))
            #print("-"*60 + "\n")

            elapsed = time.perf_counter() - t0
            print(f"[TRANSLATE] Completado en {elapsed:.2f}s ({len(text)}→{len(translated)} chars, "
                  f"{len(chunks)} chunk(s))")

            result = translated

        except Exception as e:
            print(f"[TRANSLATE ERROR] {type(e).__name__}: {e}")
            result = f"Error de traducción: {e}"

        return result