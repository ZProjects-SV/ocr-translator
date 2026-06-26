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
import os
import sys

# Hack de sys.path necesario para que PyInstaller y submódulos encuentren 
# los recursos de PaddleOCR al empaquetar como .exe.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np
from PIL import ImageGrab, Image, ImageFilter, ImageEnhance

from config import (
    PADDLE_LANG,
    PADDLE_MIN_CONFIDENCE,
    TRANSLATION_TO_PADDLE_LANG,
)
from preferences import get_translation_source, get_downloaded_langs, add_downloaded_lang

# ==========================================================
# BLOQUE: Clase Principal y Gestión de Modelos (Singleton-like)
# ==========================================================
class OCREngine:
    """Motor de reconocimiento óptico de caracteres usando PaddleOCR v2.x"""
    
    _instance = None
    _downloaded_langs: set[str] = set()  # idiomas con modelo ya disponible en disco

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance
    
    @classmethod
    def mark_lang_downloaded(cls, source_lang: str) -> None:
        """Registra en memoria y en disco que el modelo ya está disponible."""
        cls._downloaded_langs.add(source_lang)
        add_downloaded_lang(source_lang)

    @classmethod
    def is_model_downloaded(cls, source_lang: str) -> bool:
        """Devuelve True si el modelo para este idioma ya fue descargado."""
        return source_lang in cls._downloaded_langs

    def __init__(self):
        self._engine = None
        self._current_lang = None
        # Restaurar idiomas ya descargados en sesiones anteriores
        OCREngine._downloaded_langs.update(get_downloaded_langs())
        self._init_engine()

    def _init_engine(self, source_lang: str = None) -> None:
        """Inicializa PaddleOCR. Si source_lang es None, lo lee de preferencias."""
        from paddleocr import PaddleOCR
        try:
            source_lang = source_lang or get_translation_source() or "en"
            paddle_lang = TRANSLATION_TO_PADDLE_LANG.get(source_lang, PADDLE_LANG)
            print(f"[INFO] Inicializando PaddleOCR para idioma origen '{source_lang}' -> modelo '{paddle_lang}'...")
            self._engine = PaddleOCR(
                use_angle_cls=True,
                lang=paddle_lang,
                use_gpu=False,
                show_log=False,
            )
            self._current_lang = source_lang
            OCREngine.mark_lang_downloaded(source_lang)
            print("[INFO] PaddleOCR listo.")
        except Exception as e:
            raise RuntimeError(
                f"No se pudo inicializar PaddleOCR: {e}\n"
                "Asegúrate de haber instalado: pip install paddlepaddle==2.6.2 paddleocr==2.8.1"
            )
            
    def _get_paddle_lang(self, source_lang: str) -> str:
        """Devuelve el nombre de modelo Paddle para un idioma origen."""
        return TRANSLATION_TO_PADDLE_LANG.get(source_lang, PADDLE_LANG)
            
    def _ensure_engine_lang(self) -> None:
        """Recrea el engine si cambió el idioma origen en preferencias."""
        source_lang = get_translation_source() or "en"
        if source_lang != self._current_lang:
            print(f"[INFO] Cambio de idioma OCR detectado: {self._current_lang} -> {source_lang}")
            self._init_engine()
# (Dependencias/Interacciones: Depende de 'preferences' para saber qué idioma usar y de 'config' para mapear los idiomas. Es instanciado por 'main.py' en su carga inicial.)


# ==========================================================
# BLOQUE: Captura y Preprocesamiento de Imagen
# ==========================================================
    def capture_area(self, x1, y1, x2, y2) -> Image.Image:
        """Captura un área específica de la pantalla"""
        return ImageGrab.grab(bbox=(x1, y1, x2, y2))
    
    def _preprocess(self, image: Image.Image) -> Image.Image:
        """Mejora la imagen antes del OCR para mayor precisión"""
        if image.width < 400 or image.height < 400:
            image = image.resize(
                (image.width * 2, image.height * 2),
                Image.Resampling.LANCZOS
            )
        image = ImageEnhance.Contrast(image).enhance(1.5)
        image = image.filter(ImageFilter.SHARPEN)
        return image
# (Dependencias/Interacciones: Usa PIL para mejorar la imagen. 'capture_area' es apenas usado por process_area, pero la lógica de preprocesamiento es vital para los métodos de extracción.)


# ==========================================================
# BLOQUE: Extracción de Texto (Plano y con Cajas)
# ==========================================================
    def extract_text(self, image: Image.Image, lang: str = None) -> str:
        """
        Extrae texto de una imagen usando PaddleOCR v2.x.
        lang se ignora (se define al inicializar), se mantiene por compatibilidad.
        """
        try:
            if image.width == 0 or image.height == 0:
                print("[WARN] Imagen vacía recibida (0x0)")
                return ""
            if image.width < 10 or image.height < 10:
                print(f"[WARN] Imagen muy pequeña ({image.width}x{image.height}), OCR puede fallar")
                return ""

            image = self._preprocess(image)
            img_array = np.array(image.convert("RGB"))

            result = self._engine.ocr(img_array, cls=True)

            if not result or not result[0]:
                return ""

            valid = [
                line for line in result[0]
                if line and line[1][1] >= PADDLE_MIN_CONFIDENCE
            ]
            valid.sort(key=lambda l: l[0][0][1])  # ordena por Y del punto superior izquierdo

            lines = [line[1][0] for line in valid]

            return "\n".join(lines).strip()

        except Exception as e:
            print(f"[ERROR] Error en OCR: {str(e)}")
            raise RuntimeError(f"Error en OCR: {str(e)}")
        
    def extract_text_with_boxes(self, image: Image.Image):
        """
        Extrae texto con posiciones. Retorna (texto_completo, lista_de_bloques)
        Cada bloque: {'text': str, 'box': (x1, y1, x2, y2), 'conf': float}
        """
        try:
            if image.width < 10 or image.height < 10:
                return "", []

            scale = 1
            processed = image
            # Si la imagen es pequeña, la duplicamos para que el OCR funcione mejor
            if image.width < 400 or image.height < 400:
                scale = 2
                processed = image.resize(
                    (image.width * 2, image.height * 2),
                    Image.Resampling.LANCZOS
                )
            processed = ImageEnhance.Contrast(processed).enhance(1.5)
            processed = processed.filter(ImageFilter.SHARPEN)

            img_array = np.array(processed.convert("RGB"))
            result = self._engine.ocr(img_array, cls=True)

            if not result or not result[0]:
                return "", []

            valid = [
                line for line in result[0]
                if line and line[1][1] >= PADDLE_MIN_CONFIDENCE
            ]
            valid.sort(key=lambda l: l[0][0][1])

            blocks = []
            for line in valid:
                bbox = line[0]  # [[x1,y1],[x2,y1],[x2,y2],[x1,y2]]
                text = line[1][0]
                conf = line[1][1]
                
                # ✅ CORRECCIÓN: Dividir TODAS las coordenadas por la escala 
                # para devolverlas a la resolución original de la imagen.
                x1 = int(bbox[0][0] / scale)
                y1 = int(bbox[0][1] / scale)
                x2 = int(bbox[2][0] / scale)
                y2 = int(bbox[2][1] / scale)
                
                blocks.append({'text': text, 'box': (x1, y1, x2, y2), 'conf': conf})

            full_text = "\n".join(b['text'] for b in blocks)
            return full_text, blocks

        except Exception as e:
            print(f"[ERROR] extract_text_with_boxes: {e}")
            raise RuntimeError(f"Error en OCR: {e}")

    def process_area(self, x1, y1, x2, y2, lang: str = None) -> str:
        """Captura y extrae texto de un área de pantalla"""
        screenshot = self.capture_area(x1, y1, x2, y2)
        return self.extract_text(screenshot, lang)
# (Dependencias/Interacciones: Depende del _preprocess y del _engine. Es llamado principalmente por 'main.py' (extract_text_with_boxes) para alimentar la 'loading_window' y por 'screen_capture.py' (process_area).)