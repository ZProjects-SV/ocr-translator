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
import time

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
# BLOQUE: Helper — normaliza resultado de .predict() a lista de bloques
# ==========================================================
def _parse_predict_result(result, min_conf: float):
    """
    PaddleOCR 3.x .predict() devuelve una lista de objetos (uno por imagen),
    cada uno accesible como dict con: rec_texts, rec_scores, rec_polys (o rec_boxes).
    Esta función lo normaliza a: [{'text':..., 'score':..., 'poly':...}, ...]
    """
    if not result:
        return []

    res = result[0]  # una sola imagen -> un solo resultado

    texts = res.get("rec_texts", [])
    scores = res.get("rec_scores", [])
    polys = res.get("rec_polys", res.get("rec_boxes", [None] * len(texts)))

    blocks = []
    for text, score, poly in zip(texts, scores, polys):
        if not text or score is None or score < min_conf:
            continue
        blocks.append({"text": text, "score": float(score), "poly": poly})

    return blocks


# ==========================================================
# BLOQUE: Clase Principal — OCREngine (instancia persistente)
# ==========================================================
class OCREngine:
    """
    Motor OCR con instancia persistente de PaddleOCR 3.x.
    Se carga una vez al iniciar y se reutiliza en cada captura.
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
        print("[OCR] OCREngine.__init__: iniciando...")
        OCREngine._downloaded_langs.update(get_downloaded_langs())
        self._engine = None
        self._current_lang = None

        source_lang = get_translation_source() or "en"
        self._load_engine(source_lang)
        print(f"[OCR] Engine listo (lang='{source_lang}')")

    # ----------------------------------------------------------
    # Helpers de idioma
    # ----------------------------------------------------------
    def _get_paddle_lang(self, source_lang: str) -> str:
        return TRANSLATION_TO_PADDLE_LANG.get(source_lang, PADDLE_LANG)

    # ----------------------------------------------------------
    # Carga/recarga del engine
    # ----------------------------------------------------------
    def _load_engine(self, source_lang: str) -> None:
        """Carga (o recarga si el idioma cambió) la instancia de PaddleOCR 3.x."""
        from paddleocr import PaddleOCR

        paddle_lang = self._get_paddle_lang(source_lang)

        if self._engine is not None and self._current_lang == source_lang:
            return

        if self._engine is not None:
            print(f"[OCR] Recargando engine: '{self._current_lang}' -> '{source_lang}'")
            del self._engine
            gc.collect()

        print(f"[OCR] Cargando PaddleOCR 3.x: lang='{source_lang}' (paddle='{paddle_lang}')...")

        # PaddleOCR 3.x: use_angle_cls -> use_textline_orientation; use_gpu -> device
        self._engine = PaddleOCR(
            lang=paddle_lang,
            device="cpu",
            enable_mkldnn=False,
            cpu_threads=2,
            use_doc_orientation_classify=False,
            use_doc_unwarping=False,
            use_textline_orientation=False,
        )
        self._current_lang = source_lang
        OCREngine.mark_lang_downloaded(source_lang)
        print(f"[OCR] Engine cargado correctamente (lang='{source_lang}')")

    def _init_engine(self, source_lang: str = None) -> None:
        """Para descarga inicial de modelos desde PreferencesWindow."""
        source_lang = source_lang or get_translation_source() or "en"
        print(f"[OCR] _init_engine (descarga/verificación): lang='{source_lang}'")
        self._load_engine(source_lang)
        print(f"[OCR] _init_engine: modelo '{source_lang}' verificado")

    def release_engine(self) -> None:
        """Libera el engine de memoria (p.ej. al cerrar PreferencesWindow)."""
        if self._engine is not None:
            print("[OCR] release_engine: liberando engine...")
            del self._engine
            self._engine = None
            self._current_lang = None
            gc.collect()
            print("[OCR] release_engine: engine liberado")
        else:
            print("[OCR] release_engine: no hay engine activo")

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
    # BLOQUE: Utilidad de Guardado para Debug
    # ==========================================================
    def _save_debug_images(self, original_img: Image.Image, processed_img: Image.Image, prefix: str = "ocr_debug"):
        debug_dir = "debug_ocr"
        os.makedirs(debug_dir, exist_ok=True)
        timestamp = int(time.time() * 1000)
        orig_path = os.path.join(debug_dir, f"{prefix}_1_original_{timestamp}.png")
        proc_path = os.path.join(debug_dir, f"{prefix}_2_processed_{timestamp}.png")
        try:
            original_img.save(orig_path, "PNG")
            processed_img.save(proc_path, "PNG")
            print(f"[DEBUG] Imágenes guardadas en: {debug_dir}/")
        except Exception as e:
            print(f"[DEBUG] Error al guardar imágenes: {e}")

    # ==========================================================
    # BLOQUE: Extracción de Texto
    # ==========================================================
    def extract_text(self, image: Image.Image, lang: str = None, save_debug: bool = False) -> str:
        if image.width < 10 or image.height < 10:
            return ""

        source_lang = lang or get_translation_source() or "en"
        pixel_font = _is_pixel_font(image)
        min_conf = PADDLE_MIN_CONFIDENCE_PIXEL if pixel_font else PADDLE_MIN_CONFIDENCE

        self._load_engine(source_lang)

        print(f"[OCR] extract_text: {image.width}x{image.height}, lang='{source_lang}'")
        processed = self._preprocess(image)

        if save_debug:
            self._save_debug_images(image, processed, prefix="extract_text")

        img_array = np.array(processed.convert("RGB"))
        t0 = time.perf_counter()
        result = self._engine.predict(img_array)
        print(f"[OCR] inference: {time.perf_counter()-t0:.2f}s")
        del img_array, processed

        blocks = _parse_predict_result(result, min_conf)
        del result

        if not blocks:
            return ""

        # Orden vertical aproximado usando la coordenada Y del primer punto del polígono
        blocks.sort(key=lambda b: b["poly"][0][1] if b["poly"] is not None else 0)
        text = "\n".join(b["text"] for b in blocks).strip()
        return text

    def extract_text_with_boxes(self, image: Image.Image, save_debug: bool = False):
        if image.width < 10 or image.height < 10:
            return "", []

        source_lang = get_translation_source() or "en"
        pixel_font = _is_pixel_font(image)
        min_conf = PADDLE_MIN_CONFIDENCE_PIXEL if pixel_font else PADDLE_MIN_CONFIDENCE

        if pixel_font:
            scale = 4
            processed = self._preprocess_pixel_font(image)
        elif image.width < 400 or image.height < 400:
            scale = 2
            processed = image.resize((image.width * 2, image.height * 2),
                                      Image.Resampling.LANCZOS)
            processed = ImageEnhance.Contrast(processed).enhance(1.5)
            processed = processed.filter(ImageFilter.SHARPEN)
        else:
            scale = 1
            processed = ImageEnhance.Contrast(image).enhance(1.5)
            processed = processed.filter(ImageFilter.SHARPEN)

        if save_debug:
            self._save_debug_images(image, processed, prefix="extract_boxes")

        img_array = np.array(processed.convert("RGB"))
        processed.close()
        del processed

        self._load_engine(source_lang)

        print(f"[OCR] extract_text_with_boxes: {image.width}x{image.height}, "
              f"lang='{source_lang}', pixel_font={pixel_font}, scale={scale}")

        t0 = time.perf_counter()
        result = self._engine.predict(img_array)
        print(f"[OCR] inference: {time.perf_counter()-t0:.2f}s")
        del img_array

        raw_blocks = _parse_predict_result(result, min_conf)
        del result

        if not raw_blocks:
            return "", []

        raw_blocks.sort(key=lambda b: b["poly"][0][1] if b["poly"] is not None else 0)

        blocks = []
        for b in raw_blocks:
            poly = b["poly"]
            if poly is not None:
                xs = [p[0] for p in poly]
                ys = [p[1] for p in poly]
                box = (int(min(xs) / scale), int(min(ys) / scale),
                       int(max(xs) / scale), int(max(ys) / scale))
            else:
                box = (0, 0, 0, 0)
            blocks.append({"text": b["text"], "box": box, "conf": b["score"]})

        full_text = "\n".join(b["text"] for b in blocks)
        del raw_blocks
        print(f"[OCR] resultado: {len(blocks)} bloques, {len(full_text)} chars")
        return full_text, blocks

    def process_area(self, x1, y1, x2, y2, lang: str = None) -> str:
        return self.extract_text(self.capture_area(x1, y1, x2, y2), lang)