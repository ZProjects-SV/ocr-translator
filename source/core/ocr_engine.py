import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PIL import ImageGrab, Image

from config import (
    PADDLE_LANG,
    PADDLE_MIN_CONFIDENCE,
    PADDLE_MIN_CONFIDENCE_PIXEL,
    TRANSLATION_TO_PADDLE_LANG,
)
from preferences import get_translation_source, get_downloaded_langs, add_downloaded_lang


# ==========================================================
# Simulación: sin detección real de fuente
# ==========================================================
def _is_pixel_font(image: Image.Image) -> bool:
    return False


# ==========================================================
# Simulación: resultado estático
# ==========================================================
def _parse_predict_result(result, min_conf: float):
    return result


# ==========================================================
# BLOQUE: Clase Simulada — OCREngine (sin carga real)
# ==========================================================
class OCREngine:
    """
    Motor OCR simulado.
    No carga PaddleOCR, devuelve texto estático.
    """

    _downloaded_langs: set = set()
    _MOCK_TEXT = "This is simulated OCR output for testing purposes."
    _MOCK_BLOCKS = [
        {
            "text": "This is simulated OCR output for testing purposes.",
            "score": 0.95,
            "poly": [[10, 10], [200, 10], [200, 30], [10, 30]],
        }
    ]

    @classmethod
    def mark_lang_downloaded(cls, source_lang: str) -> None:
        cls._downloaded_langs.add(source_lang)
        add_downloaded_lang(source_lang)

    @classmethod
    def is_model_downloaded(cls, source_lang: str) -> bool:
        return source_lang in cls._downloaded_langs

    def __init__(self):
        print("[OCR-MOCK] OCREngine.__init__: modo simulación activo")
        OCREngine._downloaded_langs.update(get_downloaded_langs())
        self._engine = "MOCK"
        self._current_lang = get_translation_source() or "en"
        print(f"[OCR-MOCK] Engine simulado listo (lang='{self._current_lang}')")

    def _get_paddle_lang(self, source_lang: str) -> str:
        return TRANSLATION_TO_PADDLE_LANG.get(source_lang, PADDLE_LANG)

    def _load_engine(self, source_lang: str) -> None:
        """Simula la carga del engine."""
        if self._current_lang == source_lang:
            return
        print(f"[OCR-MOCK] Cambiando idioma: '{self._current_lang}' -> '{source_lang}'")
        self._current_lang = source_lang
        OCREngine.mark_lang_downloaded(source_lang)

    def _init_engine(self, source_lang: str = None) -> None:
        source_lang = source_lang or get_translation_source() or "en"
        print(f"[OCR-MOCK] _init_engine: lang='{source_lang}'")
        self._load_engine(source_lang)

    def release_engine(self) -> None:
        print("[OCR-MOCK] release_engine: liberando engine simulado...")
        self._engine = None
        self._current_lang = None
        print("[OCR-MOCK] release_engine: liberado")

    # ==========================================================
    # Captura (real, sin simulación)
    # ==========================================================
    def capture_area(self, x1, y1, x2, y2) -> Image.Image:
        return ImageGrab.grab(bbox=(x1, y1, x2, y2))

    def _preprocess(self, image: Image.Image) -> Image.Image:
        return image

    def _preprocess_pixel_font(self, image: Image.Image) -> Image.Image:
        return image

    def _preprocess_standard(self, image: Image.Image) -> Image.Image:
        return image

    def _save_debug_images(self, original_img: Image.Image, processed_img: Image.Image, prefix: str = "ocr_debug"):
        pass

    # ==========================================================
    # Extracción de Texto — devuelve estático
    # ==========================================================
    def extract_text(self, image: Image.Image, lang: str = None, save_debug: bool = False) -> str:
        if image.width < 10 or image.height < 10:
            return ""

        source_lang = lang or get_translation_source() or "en"
        self._load_engine(source_lang)

        print(f"[OCR-MOCK] extract_text: {image.width}x{image.height}, lang='{source_lang}'")
        return self._MOCK_TEXT

    def extract_text_with_boxes(self, image: Image.Image, save_debug: bool = False):
        if image.width < 10 or image.height < 10:
            return "", []

        source_lang = get_translation_source() or "en"
        self._load_engine(source_lang)

        print(f"[OCR-MOCK] extract_text_with_boxes: {image.width}x{image.height}, lang='{source_lang}'")

        blocks = []
        for b in self._MOCK_BLOCKS:
            poly = b["poly"]
            xs = [p[0] for p in poly]
            ys = [p[1] for p in poly]
            box = (int(min(xs)), int(min(ys)), int(max(xs)), int(max(ys)))
            blocks.append({"text": b["text"], "box": box, "conf": b["score"]})

        full_text = "\n".join(b["text"] for b in blocks)
        return full_text, blocks

    def process_area(self, x1, y1, x2, y2, lang: str = None) -> str:
        return self.extract_text(self.capture_area(x1, y1, x2, y2), lang)