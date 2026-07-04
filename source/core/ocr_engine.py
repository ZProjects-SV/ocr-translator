import os
import gc
import time
from collections import OrderedDict

import cv2
import numpy as np
from PIL import ImageGrab, Image, ImageFilter

from config import (
    PADDLE_MIN_CONFIDENCE,
    PADDLE_MIN_CONFIDENCE_PIXEL,
)
from preferences import get_translation_source, get_downloaded_langs, add_downloaded_lang


# ==========================================================
# Detección de tipo de fuente y calidad de imagen
# ==========================================================
def _is_pixel_font_from_gray(gray: np.ndarray) -> bool:
    dx = np.abs(np.diff(gray.astype(np.int16), axis=1))
    dy = np.abs(np.diff(gray.astype(np.int16), axis=0))
    hard_edges = np.sum(dx > 200) + np.sum(dy > 200)
    soft_edges = np.sum((dx > 30) & (dx <= 200)) + np.sum((dy > 30) & (dy <= 200))
    total = hard_edges + soft_edges
    del dx, dy
    if total == 0:
        return False
    return (hard_edges / total) > 0.55


def is_pixel_font(image: Image.Image) -> bool:
    gray = np.array(image.convert("L"))
    return _is_pixel_font_from_gray(gray)


def _analyze_image_quality(gray: np.ndarray) -> dict:
    sharpness = cv2.Laplacian(gray, cv2.CV_64F).var()
    contrast = float(gray.std())
    blurred = cv2.GaussianBlur(gray, (3, 3), 0)
    noise = float(np.mean(cv2.absdiff(gray, blurred)))
    del blurred
    return {
        "sharpness": sharpness,
        "contrast": contrast,
        "noise": noise,
        "needs_denoise": noise > 4.0,
        "needs_contrast": contrast < 55.0,
        "needs_sharpen": sharpness < 300.0,
    }


# ==========================================================
# Helper -- normaliza resultado de .predict() a lista de bloques
# ==========================================================
def _parse_predict_result(result, min_conf: float):
    if not result:
        return []
    res = result[0]
    texts = res.get("rec_texts", [])
    scores = res.get("rec_scores", [])
    polys = res.get("rec_polys", res.get("rec_boxes", [None] * len(texts)))
    blocks = []
    for text, score, poly in zip(texts, scores, polys):
        if not text or score is None or score < min_conf:
            continue
        blocks.append({"text": text, "score": float(score), "poly": poly})
    return blocks


def _reading_order_key(b):
    poly = b["poly"]
    if poly is None:
        return (float("inf"), float("inf"))
    y = poly[0][1]
    x = poly[0][0]
    row = round(y / 20) * 20
    return (row, x)


# ==========================================================
# Cache LRU de engines por lang
# ==========================================================
class _EngineCache:
    def __init__(self, max_size: int = 1):
        self.max_size = max_size
        self._cache: "OrderedDict[tuple, object]" = OrderedDict()

    def get(self, key: tuple):
        if key in self._cache:
            self._cache.move_to_end(key)
            return self._cache[key]
        return None

    def put(self, key: tuple, engine) -> None:
        if key in self._cache:
            self._cache.move_to_end(key)
            self._cache[key] = engine
            return
        self._cache[key] = engine
        while len(self._cache) > self.max_size:
            old_key, old_engine = self._cache.popitem(last=False)
            del old_engine
            gc.collect()

    def clear(self) -> None:
        for engine in self._cache.values():
            del engine
        self._cache.clear()
        gc.collect()

    def __contains__(self, key: tuple) -> bool:
        return key in self._cache


# ==========================================================
# Clase Principal -- OCREngine (ONNX Runtime)
# ==========================================================
class OCREngine:
    _downloaded_langs: set = set()
    _FIXED_DET_LIMIT = 960
    _GC_EVERY_N_CALLS = 15
    _MAX_THREADS = 4

    @classmethod
    def mark_lang_downloaded(cls, source_lang: str) -> None:
        cls._downloaded_langs.add(source_lang)
        add_downloaded_lang(source_lang)

    @classmethod
    def is_model_downloaded(cls, source_lang: str) -> bool:
        return source_lang in cls._downloaded_langs

    def __init__(self):
        OCREngine._downloaded_langs.update(get_downloaded_langs())
        self._cache = _EngineCache(max_size=1)
        self._engine = None
        self._current_lang = None
        self._calls_since_gc = 0

        source_lang = get_translation_source() or "en"
        self._load_engine(source_lang)

    def _build_engine(self):
        from paddleocr import PaddleOCR

        engine_config = {
            "device_type": "cpu",
            "providers": ["CPUExecutionProvider"],
            "graph_optimization_level": 99,
            "intra_op_num_threads": self._MAX_THREADS,
            "inter_op_num_threads": 1,
            "execution_mode": "sequential",
            "enable_cpu_mem_arena": False,
            "enable_mem_pattern": False,
            "log_severity_level": 3,
        }

        return PaddleOCR(
            engine="onnxruntime",
            engine_config=engine_config,
            text_detection_model_name="PP-OCRv6_medium_det",
            text_recognition_model_name="PP-OCRv6_medium_rec",
            use_doc_orientation_classify=False,
            use_doc_unwarping=False,
            use_textline_orientation=False,
            text_det_limit_side_len=self._FIXED_DET_LIMIT,
            text_det_limit_type="max",
        )

    def _load_engine(self, source_lang: str) -> None:
        key = (source_lang,)

        cached = self._cache.get(key)
        if cached is not None:
            self._engine = cached
            self._current_lang = source_lang
            return

        engine = self._build_engine()

        self._cache.put(key, engine)
        self._engine = engine
        self._current_lang = source_lang
        OCREngine.mark_lang_downloaded(source_lang)

    def _init_engine(self, source_lang: str = None) -> None:
        source_lang = source_lang or get_translation_source() or "en"
        self._load_engine(source_lang)

    def release_engine(self) -> None:
        self._cache.clear()
        self._engine = None
        self._current_lang = None
        gc.collect()

    def _ensure_engine_ready(self, source_lang: str) -> None:
        if source_lang != self._current_lang or self._engine is None:
            self._load_engine(source_lang)

    def _maybe_collect(self) -> None:
        self._calls_since_gc += 1
        if self._calls_since_gc >= self._GC_EVERY_N_CALLS:
            gc.collect()
            self._calls_since_gc = 0

    def capture_area(self, x1, y1, x2, y2) -> Image.Image:
        img = ImageGrab.grab(bbox=(x1, y1, x2, y2))
        if img.mode != "RGB":
            converted = img.convert("RGB")
            img.close()
            return converted
        return img

    # ---------------------------------------------------------
    # Preprocesamiento
    # ---------------------------------------------------------
    def _preprocess(self, image: Image.Image):
        rgb_arr = np.array(image.convert("RGB"))
        gray = cv2.cvtColor(rgb_arr, cv2.COLOR_RGB2GRAY)

        pixel_font = _is_pixel_font_from_gray(gray)

        if pixel_font:
            out, scale = self._preprocess_pixel_font(rgb_arr, gray, image.height)
            del rgb_arr, gray
            return out, True, scale

        quality = _analyze_image_quality(gray)
        out = self._preprocess_standard(rgb_arr, gray, quality)
        del rgb_arr, gray
        return out, False, 1

    def _preprocess_pixel_font(self, rgb_arr: np.ndarray, gray: np.ndarray, height: int):
        scale = 4 if height < 40 else 2
        img_cv = cv2.cvtColor(rgb_arr, cv2.COLOR_RGB2BGR)
        h, w = img_cv.shape[:2]
        img_cv = cv2.resize(img_cv, (w * scale, h * scale), interpolation=cv2.INTER_NEAREST)
        gray_scaled = cv2.cvtColor(img_cv, cv2.COLOR_BGR2GRAY)
        del img_cv

        _, binary_otsu = cv2.threshold(gray_scaled, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        white_ratio = np.sum(binary_otsu == 255) / binary_otsu.size
        if white_ratio < 0.05 or white_ratio > 0.95:
            binary = cv2.adaptiveThreshold(
                gray_scaled, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                cv2.THRESH_BINARY, 15, 2
            )
        else:
            binary = binary_otsu
        del gray_scaled, binary_otsu

        if h < 30:
            kernel = np.ones((2, 2), np.uint8)
            binary = cv2.dilate(binary, kernel, iterations=1)

        result = cv2.cvtColor(binary, cv2.COLOR_GRAY2RGB)
        del binary
        out = Image.fromarray(result)
        del result
        return out, scale

    def _preprocess_standard(self, rgb_arr: np.ndarray, gray: np.ndarray, quality: dict):
        img_cv = cv2.cvtColor(rgb_arr, cv2.COLOR_RGB2BGR)

        if quality["needs_denoise"]:
            img_cv = cv2.fastNlMeansDenoisingColored(
                img_cv, None, h=3, hColor=3,
                templateWindowSize=7, searchWindowSize=15
            )

        if quality["needs_contrast"]:
            lab = cv2.cvtColor(img_cv, cv2.COLOR_BGR2LAB)
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
        out = Image.fromarray(rgb)
        del rgb

        if quality["needs_sharpen"]:
            sharpened = out.filter(ImageFilter.SHARPEN)
            out.close()
            out = sharpened

        return out

    # ---------------------------------------------------------
    # Debug
    # ---------------------------------------------------------
    def _save_debug(self, res, original_img: Image.Image, prefix: str = "ocr_debug") -> None:
        debug_dir = os.path.join("debug_ocr", prefix)
        os.makedirs(debug_dir, exist_ok=True)
        timestamp = int(time.time() * 1000)
        try:
            original_img.save(os.path.join(debug_dir, f"{timestamp}_original.png"), "PNG")
            res.save_to_img(debug_dir)
            res.save_to_json(debug_dir)
        except Exception:
            pass

    # ---------------------------------------------------------
    # Inferencia unificada
    # ---------------------------------------------------------
    def _run_inference(self, image: Image.Image, lang: str = None,
                       save_debug: bool = False, return_boxes: bool = False):
        if image.width < 10 or image.height < 10:
            return ("", []) if return_boxes else ""

        source_lang = lang or get_translation_source() or "en"
        self._ensure_engine_ready(source_lang)

        if self._engine is None:
            raise RuntimeError("OCR engine no inicializado")

        processed, pixel_font, scale = self._preprocess(image)

        min_conf = PADDLE_MIN_CONFIDENCE_PIXEL if pixel_font else PADDLE_MIN_CONFIDENCE

        img_array = np.array(processed.convert("RGB"))

        result = self._engine.predict(img_array)
        del img_array

        if save_debug and result:
            self._save_debug(result[0], image, prefix="extract_boxes" if return_boxes else "extract_text")

        raw_blocks = _parse_predict_result(result, min_conf)
        del result

        processed.close()
        del processed
        self._maybe_collect()

        if not raw_blocks:
            return ("", []) if return_boxes else ""

        raw_blocks.sort(key=_reading_order_key)

        if not return_boxes:
            text = "\n".join(b["text"] for b in raw_blocks).strip()
            del raw_blocks
            return text

        blocks = []
        for b in raw_blocks:
            poly = b["poly"]
            if poly is not None:
                xs = [p[0] for p in poly]
                ys = [p[1] for p in poly]
                box = (
                    int(min(xs) / scale), int(min(ys) / scale),
                    int(max(xs) / scale), int(max(ys) / scale),
                )
            else:
                box = (0, 0, 0, 0)
            blocks.append({"text": b["text"], "box": box, "conf": b["score"]})

        full_text = "\n".join(b["text"] for b in blocks)
        del raw_blocks
        return full_text, blocks

    # ---------------------------------------------------------
    # API pública
    # ---------------------------------------------------------
    def extract_text(self, image: Image.Image, lang: str = None,
                     save_debug: bool = False) -> str:
        return self._run_inference(image, lang, save_debug, return_boxes=False)

    def extract_text_with_boxes(self, image: Image.Image,
                                save_debug: bool = False):
        return self._run_inference(image, None, save_debug, return_boxes=True)

    def process_area(self, x1, y1, x2, y2, lang: str = None) -> str:
        img = self.capture_area(x1, y1, x2, y2)
        try:
            return self.extract_text(img, lang)
        finally:
            img.close()