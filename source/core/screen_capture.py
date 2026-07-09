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
from core.ocr_engine import OCREngine
from core.translator import Translator
import gc


# ==========================================================
# BLOQUE: Coordinador de Captura — Simulado
# ==========================================================
class ScreenCapture:
    """Coordina la captura, OCR y traducción (versión simulada)."""

    _MOCK_ORIGINAL = "This is simulated OCR output for testing purposes."
    _MOCK_TRANSLATED = "[Traducción simulada] This is a mock translated text for testing purposes."

    def __init__(self, ocr_engine: OCREngine = None, translator: Translator = None):
        # En modo simulado no forzamos el error para no romper la cadena de inicialización
        self.ocr_engine = ocr_engine
        self.translator = translator

    def process(self, x1, y1, x2, y2):
        """Simula el procesamiento de un área de pantalla."""
        print(f"[ScreenCapture-MOCK] process() llamado para área ({x1}, {y1}, {y2}, {y2})")

        try:
            original_text = self._MOCK_ORIGINAL
            translated_text = self._MOCK_TRANSLATED

            print("=" * 60)
            print("TEXTO ORIGINAL (SIMULADO):")
            print("-" * 60)
            print(original_text)
            print("=" * 60)
            print(f"[ScreenCapture-MOCK] Traducción simulada completada")

            return original_text, translated_text

        except Exception as e:
            return None, f"Error: {str(e)}"

        finally:
            gc.collect()
# (Dependencias/Interacciones: Depende directamente de 'ocr_engine.py' y 'translator.py'. Aunque está implementado como orquestador, actualmente 'main.py' hace esta orquestación manualmente en su método _run_result_window. Esta clase se mantiene por compatibilidad o para usos futuros directos.)