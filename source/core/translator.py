from __future__ import annotations

import re
from deep_translator import GoogleTranslator

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
        """Traduce texto leyendo siempre los valores actuales de preferencias."""
        if not text:
            return ""

        # Leer preferencias en cada llamada para reflejar cambios del usuario
        source       = get_translation_source()
        target       = get_translation_target()
        max_chars    = get_translation_max_chars()
        cache_enabled = get_translation_cache_enabled()

        text = "\n".join(line for line in text.split("\n") if line.strip())

        # Crear clave de caché ignorando puntuación básica
        cache_key = f"{source}→{target}::{re.sub(r'[.…,!?]+', '', text.lower().strip())}"

        if cache_enabled and cache_key in self._cache:
            print("[CACHE] Usando traducción en cache.")
            return self._cache[cache_key]

        try:
            translator = GoogleTranslator(source=source, target=target)

            # Manejo de límite de caracteres de la API de Google
            if len(text) > max_chars:
                chunks = [
                    text[i : i + max_chars]
                    for i in range(0, len(text), max_chars)
                ]
                translated = " ".join(translator.translate(chunk) for chunk in chunks)
            else:
                translated = translator.translate(text)

            if cache_enabled:
                self._cache[cache_key] = translated

            return translated

        except Exception as e:
            return f"Error de traducción: {e}"
# (Dependencias/Interacciones: Depende de 'preferences' en tiempo real y de la librería 'deep_translator'. Es instanciado por 'main.py' y su método 'translate' es llamado en el hilo de procesamiento de la captura.)