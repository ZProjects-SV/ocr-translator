# OCR Translator
# Copyright (C) 2026 ZProjects
#
# This file is part of OCR Translator.
# OCR Translator is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# OCR Translator is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with OCR Translator. If not, see <https://www.gnu.org/licenses/>.
from __future__ import annotations
import time
import random
from typing import List

from requests import Session

from preferences import (
    get_translation_source,
    get_translation_target,
    get_translation_max_chars,
)


# ==========================================================
# BLOQUE: Parche User-Agent (fix issue #289 de deep-translator)
#
# Google bloquea por ratos el UA por defecto de requests
# ('python-requests/2.x') devolviendo una página SIN la traducción,
# y la librería lo reporta como TranslationNotFound. Este parche
# sobreescribe el UA por uno de navegador en TODAS las peticiones.
# ==========================================================
BROWSER_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/126.0.0.0 Safari/537.36"
)


def aplicar_parche_ua() -> None:
    if getattr(Session.send, "_ua_patched", False):
        return

    original_send = Session.send

    def _send(self, request, **kwargs):
        ua = request.headers.get("User-Agent", "")
        if not ua or ua.startswith("python-requests"):
            request.headers["User-Agent"] = BROWSER_UA
        return original_send(self, request, **kwargs)

    _send._ua_patched = True
    Session.send = _send


aplicar_parche_ua()


# ==========================================================
# BLOQUE: Motor de Traducción — Ephemeral sin caché
# ==========================================================
class Translator:
    """Motor de traducción usando Google Translate gratuito, con
    respaldo automático en MyMemory. Patrón efímero estricto:
    Instanciar -> Procesar -> Destruir.

    Regla de timing: la primera petición de toda la sesión de
    traducción SIEMPRE se envía sin demora (Google permite ~5 req/s,
    así que una sola llamada nunca activa el rate-limit). Los delays
    y backoff solo se activan a partir de la segunda petición en
    adelante (más chunks o reintentos)."""

    MAX_RETRIES = 4
    BASE_BACKOFF = 5.0
    REQUEST_DELAY = 0.5
    MAX_BACKOFF = 60.0

    def __init__(self) -> None:
        self._request_count = 0  # contador global de peticiones HTTP hechas
        print("[OK] Traductor listo (ephemeral, sin caché).")

    def _split_text_intelligently(self, text: str, max_chars: int) -> List[str]:
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

    def _wait_before_request(self) -> None:
        """Solo aplica delay si ya hicimos al menos una petición antes.
        La primera petición de toda la sesión sale sin esperar."""
        if self._request_count > 0:
            time.sleep(self.REQUEST_DELAY)
        self._request_count += 1

    def _translate_chunk_with_retry(self, translator, chunk: str, mymemory_factory):
        """Traduce un chunk. Google primero; si agota reintentos, cae
        a MyMemory como respaldo."""
        last_error = None
        current_backoff = self.BASE_BACKOFF

        for attempt in range(1, self.MAX_RETRIES + 1):
            self._wait_before_request()
            try:
                return translator.translate(chunk)
            except Exception as e:
                last_error = e
                jitter = random.uniform(0.8, 1.2)
                wait = current_backoff * jitter

                print(f"[TRANSLATE WARN] Google intento {attempt}/{self.MAX_RETRIES} falló "
                      f"({type(e).__name__}). Reintentando en {wait:.1f}s...")

                time.sleep(wait)
                current_backoff = min(current_backoff * 2, self.MAX_BACKOFF)

        print(f"[TRANSLATE ERROR] Google falló tras {self.MAX_RETRIES} intentos "
              f"({type(last_error).__name__}: {last_error}). Probando MyMemory...")

        try:
            self._wait_before_request()
            mymemory = mymemory_factory()
            return mymemory.translate(chunk)
        except Exception as e2:
            print(f"[TRANSLATE ERROR] MyMemory también falló: "
                  f"{type(e2).__name__}: {e2}. Se conserva texto original.")
            return chunk

    def translate(self, text: str) -> str:
        from deep_translator import GoogleTranslator, MyMemoryTranslator

        if not text:
            return ""

        source = get_translation_source() or "auto"
        target = get_translation_target() or "en"
        max_chars = get_translation_max_chars() or 4500

        result = ""
        try:
            print(f"[TRANSLATE] Iniciando traducción ({source}→{target})...")
            t0 = time.perf_counter()

            translator = GoogleTranslator(source=source, target=target)

            def mymemory_factory():
                locale_map = {"en": "en-GB", "es": "es-ES"}
                s = locale_map.get(source, source)
                t = locale_map.get(target, target)
                return MyMemoryTranslator(source=s, target=t)

            chunks = self._split_text_intelligently(text, max_chars)

            translated_chunks = []
            for chunk in chunks:
                translated_chunks.append(
                    self._translate_chunk_with_retry(translator, chunk, mymemory_factory)
                )

            translated = " ".join(translated_chunks)

            elapsed = time.perf_counter() - t0
            print(f"[TRANSLATE] Completado en {elapsed:.2f}s ({len(text)}→{len(translated)} chars, "
                  f"{len(chunks)} chunk(s), {self._request_count} petición(es) HTTP)")

            result = translated

        except Exception as e:
            print(f"[TRANSLATE ERROR] {type(e).__name__}: {e}")
            result = f"Error de traducción: {e}"

        return result