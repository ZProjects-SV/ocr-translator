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
import gc

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
    gray = np.array(image.convert("L"))
    dx = np.abs(np.diff(gray.astype(np.int16), axis=1))
    dy = np.abs(np.diff(gray.astype(np.int16), axis=0))
    hard_edges = np.sum(dx > 200) + np.sum(dy > 200)
    soft_edges = np.sum((dx > 30) & (dx <= 200)) + np.sum((dy > 30) & (dy <= 200))
    total = hard_edges + soft_edges
    if total == 0:
        return False
    return (hard_edges / total) > 0.60


# ==========================================================
# BLOQUE: Clase Principal — Ephemeral Engine
# ==========================================================
class OCREngine:
    """
    Motor OCR con patrón ephemeral: PaddleOCR se instancia justo antes
    de procesar y se destruye completamente al terminar.
    Memoria ocupada solo durante el procesamiento, ~0 en reposo.
    """

    _downloaded_langs: set = set()

    @classmethod
    def mark_lang_downloaded(cls, source_lang: str) -> None:
        cls._downloaded_langs.add(source_lang)
        add_downloaded_lang(source_lang)

    @classmethod
    def is_model_downloaded(cls, source_lang: str) -> bool:
        return source_lang in cls._downloaded_langs

    def __init__(self):
        print("[OCR] OCREngine.__init__: modo ephemeral activado")
        # Sin engine en memoria — solo restaurar lista de idiomas descargados
        OCREngine._downloaded_langs.update(get_downloaded_langs())
        # Verificar que los modelos existen en disco (sin cargarlos)
        source_lang = get_translation_source() or "en"
        OCREngine.mark_lang_downloaded(source_lang)
        print(f"[OCR] Engine listo en reposo (lang='{source_lang}', sin modelo en RAM)")

    # ----------------------------------------------------------
    # Helpers de idioma
    # ----------------------------------------------------------
    def _get_paddle_lang(self, source_lang: str) -> str:
        return TRANSLATION_TO_PADDLE_LANG.get(source_lang, PADDLE_LANG)

    def _init_engine(self, source_lang: str = None) -> None:
        """
        Solo para descarga inicial de modelos desde PreferencesWindow.
        No se llama en el flujo normal de captura.
        """
        from paddleocr import PaddleOCR
        source_lang = source_lang or get_translation_source() or "en"
        paddle_lang = self._get_paddle_lang(source_lang)
        print(f"[OCR] _init_engine (descarga): lang='{source_lang}' -> modelo='{paddle_lang}'")
        engine = PaddleOCR(
            use_angle_cls=False,
            lang=paddle_lang,
            use_gpu=False,
            show_log=False,
            enable_mkldnn=False,
            cpu_threads=2,
            det_db_thresh=0.2,
            det_db_box_thresh=0.4,
            det_db_unclip_ratio=1.8,
            det_db_score_mode='slow',
            rec_image_shape='3,48,320',
            drop_score=0.3,
        )
        del engine
        gc.collect()
        OCREngine.mark_lang_downloaded(source_lang)
        print(f"[OCR] _init_engine: modelo '{source_lang}' verificado y liberado")

    # ----------------------------------------------------------
    # Core privado: crear engine, usarlo, destruirlo
    # ----------------------------------------------------------
    def _build_ephemeral_engine(self, source_lang: str):
        """Crea una instancia temporal de PaddleOCR. Debe destruirse tras cada uso."""
        from paddleocr import PaddleOCR
        import time
        paddle_lang = self._get_paddle_lang(source_lang)
        print(f"[OCR] _build_ephemeral_engine: instanciando para lang='{source_lang}' (paddle='{paddle_lang}')...")
        t0 = time.perf_counter()
        engine = PaddleOCR(
            use_angle_cls=False,
            lang=paddle_lang,
            use_gpu=False,
            show_log=False,
            enable_mkldnn=False,
            cpu_threads=2,
            det_db_thresh=0.2,
            det_db_box_thresh=0.4,
            det_db_unclip_ratio=1.8,
            det_db_score_mode='slow',
            rec_image_shape='3,48,320',
            drop_score=0.3,
        )
        print(f"[OCR] _build_ephemeral_engine: listo en {time.perf_counter()-t0:.2f}s")
        return engine

    @staticmethod
    def _destroy_engine(engine) -> None:
        import time
        t0 = time.perf_counter()
        try:
            del engine
        except Exception:
            pass

        try:
            import paddle.framework.core as core # type: ignore
            # Limpia el cache del executor (buffers de inferencia)
            core.clear_executor_cache()
            # Limpia el kernel factory (kernels compilados cacheados)
            core.clear_kernel_factory()
            # Cleanup general interno de Paddle
            core._cleanup()
        except Exception as e:
            print(f"[OCR] _destroy_engine: paddle cleanup parcial: {e}")

        gc.collect()
        print(f"[OCR] _destroy_engine: liberado en {time.perf_counter()-t0:.3f}s")


    # ==========================================================
    # BLOQUE: Captura y Preprocesamiento
    # ==========================================================
    def capture_area(self, x1, y1, x2, y2) -> Image.Image:
        return ImageGrab.grab(bbox=(x1, y1, x2, y2))

    def _preprocess(self, image: Image.Image) -> Image.Image:
        if _is_pixel_font(image):
            return self._preprocess_pixel_font(image)
        return self._preprocess_standard(image)

    def _preprocess_pixel_font(self, image: Image.Image) -> Image.Image:
        img_cv = np.array(image.convert("RGB"))
        img_cv = cv2.cvtColor(img_cv, cv2.COLOR_RGB2BGR)
        h, w = img_cv.shape[:2]
        scale_factor = 4
        img_cv = cv2.resize(img_cv, (w * scale_factor, h * scale_factor),
                            interpolation=cv2.INTER_NEAREST)
        gray = cv2.cvtColor(img_cv, cv2.COLOR_BGR2GRAY)
        del img_cv
        _, binary_otsu = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        white_ratio = np.sum(binary_otsu == 255) / binary_otsu.size
        if white_ratio < 0.05 or white_ratio > 0.95:
            binary = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                                           cv2.THRESH_BINARY, 15, 2)
            print("[OCR] Pixel font: binarización adaptativa")
        else:
            binary = binary_otsu
        del gray, binary_otsu
        if h < 30:
            kernel = np.ones((2, 2), np.uint8)
            binary = cv2.dilate(binary, kernel, iterations=1)
        result = cv2.cvtColor(binary, cv2.COLOR_GRAY2RGB)
        del binary
        out = Image.fromarray(result)
        del result
        print(f"[OCR] Preprocesamiento pixel-font aplicado (x{scale_factor})")
        return out

    def _preprocess_standard(self, image: Image.Image) -> Image.Image:
        img_cv = cv2.cvtColor(np.array(image.convert("RGB")), cv2.COLOR_RGB2BGR)
        if image.width < 600:
            denoised = cv2.fastNlMeansDenoisingColored(img_cv, None,
                h=3, hColor=3, templateWindowSize=7, searchWindowSize=21)
            del img_cv
            img_cv = denoised
        lab = cv2.cvtColor(img_cv, cv2.COLOR_BGR2LAB)
        del img_cv
        l, a, b = cv2.split(lab)
        del lab
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        l = clahe.apply(l)
        lab_merged = cv2.merge((l, a, b))
        del l, a, b
        img_cv = cv2.cvtColor(lab_merged, cv2.COLOR_LAB2BGR)
        del lab_merged
        rgb = cv2.cvtColor(img_cv, cv2.COLOR_BGR2RGB)
        del img_cv
        out = Image.fromarray(rgb).filter(ImageFilter.SHARPEN)
        del rgb
        return out


    # ==========================================================
    # BLOQUE: Extracción de Texto — Patrón Ephemeral
    # ==========================================================
    def extract_text(self, image: Image.Image, lang: str = None) -> str:
        import time
        if image.width < 10 or image.height < 10:
            return ""

        source_lang = lang or get_translation_source() or "en"
        pixel_font  = _is_pixel_font(image)
        min_conf    = PADDLE_MIN_CONFIDENCE_PIXEL if pixel_font else PADDLE_MIN_CONFIDENCE

        print(f"[OCR] extract_text: {image.width}x{image.height}, lang='{source_lang}'")
        engine = self._build_ephemeral_engine(source_lang)
        try:
            processed  = self._preprocess(image)
            img_array  = np.array(processed.convert("RGB"))
            t0         = time.perf_counter()
            result     = engine.ocr(img_array, cls=False)
            print(f"[OCR] inference: {time.perf_counter()-t0:.2f}s")
            del img_array, processed

            if not result or not result[0]:
                return ""

            valid = [l for l in result[0] if l and l[1][1] >= min_conf]
            valid.sort(key=lambda l: l[0][0][1])
            text = "\n".join(l[1][0] for l in valid).strip()
            del result, valid
            return text

        finally:
            self._destroy_engine(engine)

    def extract_text_with_boxes(self, image: Image.Image):
        import time
        if image.width < 10 or image.height < 10:
            return "", []

        source_lang = get_translation_source() or "en"
        pixel_font  = _is_pixel_font(image)
        min_conf    = PADDLE_MIN_CONFIDENCE_PIXEL if pixel_font else PADDLE_MIN_CONFIDENCE

        # Preprocesamiento (sin engine todavía — no ocupa RAM de Paddle aún)
        if pixel_font:
            scale     = 4
            processed = self._preprocess_pixel_font(image)
        elif image.width < 400 or image.height < 400:
            scale     = 2
            processed = image.resize((image.width * 2, image.height * 2),
                                     Image.Resampling.LANCZOS)
            processed = ImageEnhance.Contrast(processed).enhance(1.5)
            processed = processed.filter(ImageFilter.SHARPEN)
        else:
            scale     = 1
            processed = ImageEnhance.Contrast(image).enhance(1.5)
            processed = processed.filter(ImageFilter.SHARPEN)

        img_array = np.array(processed.convert("RGB"))
        processed.close()
        del processed

        print(f"[OCR] extract_text_with_boxes: {image.width}x{image.height}, "
              f"lang='{source_lang}', pixel_font={pixel_font}, scale={scale}")

        engine = self._build_ephemeral_engine(source_lang)
        try:
            t0     = time.perf_counter()
            result = engine.ocr(img_array, cls=False)
            print(f"[OCR] inference: {time.perf_counter()-t0:.2f}s")
            del img_array

            if not result or not result[0]:
                del result
                return "", []

            valid = [l for l in result[0] if l and l[1][1] >= min_conf]
            valid.sort(key=lambda l: l[0][0][1])

            blocks = []
            for line in valid:
                bbox = line[0]
                text = line[1][0]
                conf = line[1][1]
                blocks.append({
                    'text': text,
                    'box':  (int(bbox[0][0] / scale), int(bbox[0][1] / scale),
                             int(bbox[2][0] / scale), int(bbox[2][1] / scale)),
                    'conf': conf,
                })

            full_text = "\n".join(b['text'] for b in blocks)
            del result, valid
            print(f"[OCR] resultado: {len(blocks)} bloques, {len(full_text)} chars")
            return full_text, blocks

        finally:
            # Siempre se destruye el engine, incluso si hay excepción
            self._destroy_engine(engine)

    def release_engine(self):
        """
        Compatibilidad con llamadas externas (PreferencesWindow, etc.).
        En modo ephemeral no hay nada que liberar.
        """
        print("[OCR] release_engine: noop (modo ephemeral, no hay engine persistente)")
        gc.collect()

    def process_area(self, x1, y1, x2, y2, lang: str = None) -> str:
        return self.extract_text(self.capture_area(x1, y1, x2, y2), lang)