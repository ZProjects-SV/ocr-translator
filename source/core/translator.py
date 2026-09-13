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
import requests
from typing import List

BROWSER_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/126.0.0.0 Safari/537.36"
)

HEADERS = {"User-Agent": BROWSER_UA}


def google_chrome_ex_translate(text: str, source: str = "en", target: str = "es", timeout: int = 10) -> str:
    """Motor principal: mismo endpoint que usan extensiones de Chrome y MORT.
    No usa client=gtx (saturado/bloqueado), evita el scraping HTML."""
    url = "https://translate.googleapis.com/translate_a/t"
    params = {"client": "dict-chrome-ex", "sl": source, "tl": target, "q": text}
    r = requests.get(url, params=params, headers=HEADERS, timeout=timeout)
    r.raise_for_status()
    data = r.json()
    if isinstance(data, list) and data:
        return data[0] if isinstance(data[0], str) else "".join(data[0])
    raise ValueError("Respuesta inesperada de Google (dict-chrome-ex)")


def mymemory_translate(text: str, source: str = "en", target: str = "es", email: str | None = None, timeout: int = 10) -> str:
    """Respaldo: API oficial de MyMemory, ya confirmada como estable."""
    url = "https://api.mymemory.translated.net/get"
    params = {"q": text, "langpair": f"{source}|{target}"}
    if email:
        params["de"] = email
    r = requests.get(url, params=params, timeout=timeout)
    r.raise_for_status()
    data = r.json()
    if data.get("responseStatus") != 200:
        raise RuntimeError(data.get("responseDetails", "error MyMemory"))
    return data["responseData"]["translatedText"]


class Translator:
    MAX_RETRIES = 2
    BASE_BACKOFF = 3.0
    REQUEST_DELAY = 0.4
    MAX_BACKOFF = 30.0

    def __init__(self, mymemory_email: str | None = None) -> None:
        self._request_count = 0
        self._mymemory_email = mymemory_email
        print("[OK] Traductor listo (Chrome-ex + MyMemory, sin scraping).")

    def _split_text_intelligently(self, text: str, max_chars: int) -> List[str]:
        if len(text) <= max_chars:
            return [text]
        chunks, current = [], ""
        for word in text.split():
            if len(word) > max_chars:
                if current:
                    chunks.append(current.strip())
                    current = ""
                for i in range(0, len(word), max_chars):
                    chunks.append(word[i:i + max_chars])
                continue
            if len(current) + len(word) + 1 > max_chars:
                if current:
                    chunks.append(current.strip())
                current = word
            else:
                current += " " + word if current else word
        if current:
            chunks.append(current.strip())
        return chunks

    def _wait_before_request(self) -> None:
        if self._request_count > 0:
            time.sleep(self.REQUEST_DELAY)
        self._request_count += 1

    def _translate_chunk(self, chunk: str, source: str, target: str) -> str:
        current_backoff = self.BASE_BACKOFF
        last_error = None

        for attempt in range(1, self.MAX_RETRIES + 1):
            self._wait_before_request()
            try:
                return google_chrome_ex_translate(chunk, source, target)
            except Exception as e:
                last_error = e
                jitter = random.uniform(0.8, 1.2)
                wait = current_backoff * jitter
                print(f"[TRANSLATE WARN] Google intento {attempt}/{self.MAX_RETRIES} falló "
                      f"({type(e).__name__}). Reintentando en {wait:.1f}s...")
                time.sleep(wait)
                current_backoff = min(current_backoff * 2, self.MAX_BACKOFF)

        print(f"[TRANSLATE ERROR] Google falló tras {self.MAX_RETRIES} intentos "
              f"({type(last_error).__name__}). Probando MyMemory...")
        try:
            self._wait_before_request()
            return mymemory_translate(chunk, source, target, self._mymemory_email)
        except Exception as e2:
            print(f"[TRANSLATE ERROR] MyMemory también falló: {type(e2).__name__}: {e2}. Se conserva original.")
            return chunk

    def translate(self, text: str, source: str = "en", target: str = "es", max_chars: int = 4500) -> str:
        if not text:
            return ""
        t0 = time.perf_counter()
        chunks = self._split_text_intelligently(text, max_chars)
        translated = " ".join(self._translate_chunk(c, source, target) for c in chunks)
        elapsed = time.perf_counter() - t0
        print(f"[TRANSLATE] Completado en {elapsed:.2f}s ({len(chunks)} chunk(s), "
              f"{self._request_count} petición(es) HTTP)")
        return translated