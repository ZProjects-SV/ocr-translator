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
from core.ocr_engine import OCREngine
from core.translator import Translator

# ==========================================================
# BLOQUE: Coordinador de Captura (Orquestador)
# ==========================================================
class ScreenCapture:
    """Coordina la captura, OCR y traducción"""

    def __init__(self, ocr_engine: OCREngine = None, translator: Translator = None):
        # Si no se inyectan las instancias, lanzamos un error para evitar
        # que PaddleOCR se inicialice múltiples veces consumiendo RAM.
        if ocr_engine is None or translator is None:
            raise RuntimeError("ScreenCapture requiere instancias de OCREngine y Translator ya inicializadas.")
        
        self.ocr_engine = ocr_engine
        self.translator = translator

    def process(self, x1, y1, x2, y2):
        """Procesa un área de pantalla: captura, OCR y traducción"""
        try:
            original_text = self.ocr_engine.process_area(x1, y1, x2, y2)

            if not original_text:
                return None, "No se detectó texto en el área seleccionada"

            original_text = '\n'.join(
                line for line in original_text.split('\n') if line.strip()
            )

            print("=" * 60)
            print("TEXTO ORIGINAL (EN):")
            print("-" * 60)
            print(original_text)
            print("=" * 60)
            print(f"[OK] Traduciendo... ({len(original_text)} caracteres)")

            translated_text = self.translator.translate(original_text)

            print("[OK] Traducción completada")
            print("=" * 60)

            return original_text, translated_text

        except Exception as e:
            return None, f"Error: {str(e)}"
# (Dependencias/Interacciones: Depende directamente de 'ocr_engine.py' y 'translator.py'. Aunque está implementado como orquestador, actualmente 'main.py' hace esta orquestación manualmente en su método _run_result_window. Esta clase se mantiene por compatibilidad o para usos futuros directos.)