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


import cv2
import numpy as np
from PIL import ImageGrab, Image, ImageFilter, ImageEnhance


from config import (
    PADDLE_LANG,
    PADDLE_MIN_CONFIDENCE,
    PADDLE_MIN_CONFIDENCE_PIXEL,
    TRANSLATION_TO_PADDLE_LANG,
)
from preferences import get_translation_source, get_downloaded_langs, add_downloaded_lang



# ==========================================================
# BLOQUE: Detección de tipo de fuente
# ==========================================================
def _is_pixel_font(image: Image.Image) -> bool:
    """
    Heurística rápida para detectar si la imagen contiene texto pixeleado.
    Analiza el ratio de bordes duros (transiciones abruptas de 0→255) vs suaves.
    Un ratio alto indica pixel art / fuentes de videojuego pixeleadas.
    """
    gray = np.array(image.convert("L"))
    dx = np.abs(np.diff(gray.astype(np.int16), axis=1))
    dy = np.abs(np.diff(gray.astype(np.int16), axis=0))
    # Bordes "duros": transición mayor a 200 niveles de gris en 1 píxel
    hard_edges = np.sum(dx > 200) + np.sum(dy > 200)
    # Bordes "suaves": transición entre 30 y 200
    soft_edges = np.sum((dx > 30) & (dx <= 200)) + np.sum((dy > 30) & (dy <= 200))
    total = hard_edges + soft_edges
    if total == 0:
        return False
    ratio = hard_edges / total
    # Si más del 60% de los bordes son duros, es probablemente pixel font
    return ratio > 0.60



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
                use_angle_cls=False,
                lang=paddle_lang,
                use_gpu=False,
                show_log=False,
                det_db_thresh=0.2,
                det_db_box_thresh=0.4,
                det_db_unclip_ratio=1.8,
                det_db_score_mode='slow', 
                rec_image_shape='3,48,320',
                drop_score=0.3,
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
        """
        Preprocesamiento adaptativo: detecta automáticamente si la imagen tiene
        fuente pixeleada (Minecraft-style) y aplica el pipeline correcto.
        """
        if _is_pixel_font(image):
            return self._preprocess_pixel_font(image)
        else:
            return self._preprocess_standard(image)


    def _preprocess_pixel_font(self, image: Image.Image) -> Image.Image:
        """
        Pipeline especializado para fuentes pixeleadas (Minecraft, RPG, arcade).

        Clave: escalar con NEAREST NEIGHBOR para preservar bordes duros.
        La interpolación bilineal/LANCZOS suaviza el pixel art y destruye la legibilidad.
        Mejora: binarización adaptativa como fallback cuando Otsu falla en fondos
        no uniformes (gradientes, HUDs con sombras).
        """
        img_cv = np.array(image.convert("RGB"))
        img_cv = cv2.cvtColor(img_cv, cv2.COLOR_RGB2BGR)
        h, w = img_cv.shape[:2]

        # 1. Escalar x4 con Nearest Neighbor — preserva los píxeles duros
        #    NUNCA usar LANCZOS o BILINEAR en pixel art
        scale_factor = 4
        img_cv = cv2.resize(
            img_cv,
            (w * scale_factor, h * scale_factor),
            interpolation=cv2.INTER_NEAREST  # <-- crítico para pixel fonts
        )

        # 2. Convertir a escala de grises
        gray = cv2.cvtColor(img_cv, cv2.COLOR_BGR2GRAY)

        # 3. Binarización Otsu — funciona perfecto con bordes duros del pixel art
        _, binary_otsu = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

        # 4. Fallback adaptativo si Otsu produce un resultado extremo
        #    (fondo no uniforme: gradientes, HUDs con sombras)
        white_ratio = np.sum(binary_otsu == 255) / binary_otsu.size
        if white_ratio < 0.05 or white_ratio > 0.95:
            binary = cv2.adaptiveThreshold(
                gray, 255,
                cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                cv2.THRESH_BINARY, 15, 2
            )
            print("[INFO] Pixel font: usando binarización adaptativa (Otsu falló)")
        else:
            binary = binary_otsu

        # 5. Dilate mínimo SOLO si los píxeles están muy aislados (texto muy pequeño)
        #    Esto conecta fragmentos rotos sin fusionar letras
        if h < 30:  # texto muy pequeño en la captura original
            kernel = np.ones((2, 2), np.uint8)
            binary = cv2.dilate(binary, kernel, iterations=1)

        # 6. Reconvertir a PIL RGB para PaddleOCR
        result = cv2.cvtColor(binary, cv2.COLOR_GRAY2RGB)
        print(f"[INFO] Preprocesamiento pixel-font aplicado (escala x{scale_factor}, Nearest Neighbor)")
        return Image.fromarray(result)


    def _preprocess_standard(self, image: Image.Image) -> Image.Image:
        """
        Pipeline estándar para fuentes normales (antialiased).
        Mejoras respecto al original:
        - CLAHE adaptativo por zona en lugar de contraste fijo global
        - Denoise ligero para eliminar artefactos de compresión de pantalla
        """
        if image.width < 400 or image.height < 400:
            image = image.resize(
                (image.width * 2, image.height * 2),
                Image.Resampling.LANCZOS
            )

        img_cv = cv2.cvtColor(np.array(image.convert("RGB")), cv2.COLOR_RGB2BGR)

        # Denoise ligero en imágenes pequeñas — elimina artefactos JPEG/compresión
        # sin borrar el texto. Solo aplicar en capturas pequeñas para evitar lentitud.
        if image.width < 600:
            img_cv = cv2.fastNlMeansDenoisingColored(
                img_cv, None,
                h=3, hColor=3,
                templateWindowSize=7,
                searchWindowSize=21,
            )

        # CLAHE (Contrast Limited Adaptive Histogram Equalization)
        # Ajusta el contraste por zona en lugar de globalmente,
        # ideal para HUDs con fondos variables (oscuro en un lado, claro en otro).
        lab = cv2.cvtColor(img_cv, cv2.COLOR_BGR2LAB)
        l, a, b = cv2.split(lab)
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        l = clahe.apply(l)
        lab = cv2.merge((l, a, b))
        img_cv = cv2.cvtColor(lab, cv2.COLOR_LAB2BGR)

        image = Image.fromarray(cv2.cvtColor(img_cv, cv2.COLOR_BGR2RGB))
        image = image.filter(ImageFilter.SHARPEN)
        return image
# (Dependencias/Interacciones: Usa PIL y OpenCV. _preprocess delega automáticamente según el tipo de fuente detectado.)



# ==========================================================
# BLOQUE: Extracción de Texto (Plano y con Cajas)
# ==========================================================
    def extract_text(self, image: Image.Image, lang: str = None) -> str:
        try:
            if image.width == 0 or image.height == 0:
                return ""
            if image.width < 10 or image.height < 10:
                return ""

            # Detectar ANTES de preprocesar
            pixel_font = _is_pixel_font(image)
            min_conf = PADDLE_MIN_CONFIDENCE_PIXEL if pixel_font else PADDLE_MIN_CONFIDENCE

            image = self._preprocess(image)
            img_array = np.array(image.convert("RGB"))
            result = self._engine.ocr(img_array, cls=False)

            if not result or not result[0]:
                return ""

            valid = [
                line for line in result[0]
                if line and line[1][1] >= min_conf  # <- umbral adaptativo
            ]
            valid.sort(key=lambda l: l[0][0][1])
            return "\n".join(line[1][0] for line in valid).strip()

        except Exception as e:
            print(f"[ERROR] Error en OCR: {str(e)}")
            raise RuntimeError(f"Error en OCR: {str(e)}")


    def extract_text_with_boxes(self, image: Image.Image):
        """
        Extrae texto con posiciones. Retorna (texto_completo, lista_de_bloques)
        Cada bloque: {'text': str, 'box': (x1, y1, x2, y2), 'conf': float}

        NOTA: cuando se aplica preprocesamiento pixel-font (escala x4), las coordenadas
        se dividen entre 'scale' para devolverlas a la resolución original.
        """
        try:
            if image.width < 10 or image.height < 10:
                return "", []

            # Detectar tipo de fuente ANTES de preprocesar para calcular scale correcto
            pixel_font = _is_pixel_font(image)

            if pixel_font:
                # Pixel font: escalamos x4 con Nearest Neighbor
                scale = 4
                processed = self._preprocess_pixel_font(image)
            else:
                # Fuente estándar: escala 2x si es pequeña, 1x si es grande
                if image.width < 400 or image.height < 400:
                    scale = 2
                    processed = image.resize(
                        (image.width * 2, image.height * 2),
                        Image.Resampling.LANCZOS
                    )
                    processed = ImageEnhance.Contrast(processed).enhance(1.5)
                    processed = processed.filter(ImageFilter.SHARPEN)
                else:
                    scale = 1
                    processed = ImageEnhance.Contrast(image).enhance(1.5)
                    processed = processed.filter(ImageFilter.SHARPEN)

            img_array = np.array(processed.convert("RGB"))
            result = self._engine.ocr(img_array, cls=False)

            if not result or not result[0]:
                return "", []

            # Umbral adaptativo según tipo de fuente (igual que extract_text)
            min_conf = PADDLE_MIN_CONFIDENCE_PIXEL if pixel_font else PADDLE_MIN_CONFIDENCE
            valid = [
                line for line in result[0]
                if line and line[1][1] >= min_conf
            ]
            valid.sort(key=lambda l: l[0][0][1])

            blocks = []
            for line in valid:
                bbox = line[0]  # [[x1,y1],[x2,y1],[x2,y2],[x1,y2]]
                text = line[1][0]
                conf = line[1][1]

                # Dividir TODAS las coordenadas por la escala
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
# (Dependencias/Interacciones: Depende del _preprocess y del _engine. Es llamado principalmente
#  por 'main.py' (extract_text_with_boxes) y por 'screen_capture.py' (process_area).)
