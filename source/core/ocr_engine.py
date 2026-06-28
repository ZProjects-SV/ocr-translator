import os
import sys
import gc
import time
import random

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
# BLOQUE: Detección de tipo de fuente (PLACEBO)
# ==========================================================
def _is_pixel_font(image: Image.Image) -> bool:
    print(f"[PLACEBO] _is_pixel_font: imagen={image.width}x{image.height} -> False (simulado)")
    return False


# ==========================================================
# BLOQUE: Clase Principal (PLACEBO — sin PaddleOCR real)
# ==========================================================
class OCREngine:
    """
    PLACEBO: Simula el OCREngine sin cargar PaddleOCR.
    Retorna texto de prueba fijo para verificar el flujo completo.
    """

    _instance = None
    _downloaded_langs: set = set()

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @classmethod
    def mark_lang_downloaded(cls, source_lang: str) -> None:
        cls._downloaded_langs.add(source_lang)
        add_downloaded_lang(source_lang)

    @classmethod
    def is_model_downloaded(cls, source_lang: str) -> bool:
        return source_lang in cls._downloaded_langs

    def __init__(self):
        print("[PLACEBO] OCREngine.__init__: inicializando motor SIMULADO...")
        self._engine = None
        self._current_lang = None
        OCREngine._downloaded_langs.update(get_downloaded_langs())
        self._init_engine()
        print("[PLACEBO] OCREngine.__init__: listo (sin PaddleOCR)")

    def _init_engine(self, source_lang: str = None) -> None:
        print("[PLACEBO] _init_engine: simulando carga de modelo...")
        t0 = time.perf_counter()
        # Simula el tiempo de carga (~0.5s)
        time.sleep(0.5)
        source_lang = source_lang or get_translation_source() or "en"
        paddle_lang = TRANSLATION_TO_PADDLE_LANG.get(source_lang, PADDLE_LANG)
        self._engine = "FAKE_ENGINE"  # placeholder — nunca se llama
        self._current_lang = source_lang
        OCREngine.mark_lang_downloaded(source_lang)
        print(f"[PLACEBO] _init_engine: 'modelo' listo para lang='{source_lang}' "
              f"(paddle='{paddle_lang}') en {time.perf_counter()-t0:.2f}s")

    def _get_paddle_lang(self, source_lang: str) -> str:
        return TRANSLATION_TO_PADDLE_LANG.get(source_lang, PADDLE_LANG)

    def _ensure_engine_lang(self) -> None:
        source_lang = get_translation_source() or "en"
        if self._engine is None or source_lang != self._current_lang:
            if self._engine is None:
                print("[PLACEBO] _ensure_engine_lang: engine no cargado, reinicializando...")
            else:
                print(f"[PLACEBO] _ensure_engine_lang: cambio de idioma {self._current_lang} -> {source_lang}")
            self._init_engine()


    # ==========================================================
    # BLOQUE: Captura y Preprocesamiento (PLACEBO)
    # ==========================================================
    def capture_area(self, x1, y1, x2, y2) -> Image.Image:
        print(f"[PLACEBO] capture_area: ({x1},{y1})->({x2},{y2})")
        return ImageGrab.grab(bbox=(x1, y1, x2, y2))

    def _preprocess(self, image: Image.Image) -> Image.Image:
        print(f"[PLACEBO] _preprocess: imagen={image.width}x{image.height} -> devolviendo original")
        return image

    def _preprocess_pixel_font(self, image: Image.Image) -> Image.Image:
        print(f"[PLACEBO] _preprocess_pixel_font: omitido, devolviendo original")
        return image

    def _preprocess_standard(self, image: Image.Image) -> Image.Image:
        print(f"[PLACEBO] _preprocess_standard: omitido, devolviendo original")
        return image


    # ==========================================================
    # BLOQUE: Extracción de Texto (PLACEBO — texto fijo simulado)
    # ==========================================================
    def extract_text(self, image: Image.Image, lang: str = None) -> str:
        self._ensure_engine_lang()
        print(f"[PLACEBO] extract_text: imagen={image.width}x{image.height}, lang={lang}")

        if image.width < 10 or image.height < 10:
            print("[PLACEBO] extract_text: imagen demasiado pequeña, retornando ''")
            return ""

        # Simula latencia OCR
        time.sleep(0.3)
        fake_text = "Hello World\nThis is a placeholder OCR result\nLine three of fake text"
        print(f"[PLACEBO] extract_text: retornando texto simulado ({len(fake_text)} chars)")
        return fake_text

    def extract_text_with_boxes(self, image: Image.Image):
        self._ensure_engine_lang()
        print(f"[PLACEBO] extract_text_with_boxes: imagen={image.width}x{image.height}")

        if image.width < 10 or image.height < 10:
            print("[PLACEBO] extract_text_with_boxes: imagen demasiado pequeña, retornando vacío")
            return "", []

        # Simula latencia OCR
        time.sleep(0.3)

        # Bloques simulados proporcionales al tamaño real de la imagen
        w, h = image.width, image.height
        fake_blocks = [
            {
                'text': "Hello World (simulado)",
                'box':  (10, 10, w - 10, max(30, h // 4)),
                'conf': 0.98,
            },
            {
                'text': "Segunda línea de texto OCR",
                'box':  (10, h // 4 + 5, w - 10, max(60, h // 2)),
                'conf': 0.95,
            },
            {
                'text': "Tercera línea placeholder",
                'box':  (10, h // 2 + 5, w - 10, max(90, h - 10)),
                'conf': 0.91,
            },
        ]
        full_text = "\n".join(b['text'] for b in fake_blocks)
        print(f"[PLACEBO] extract_text_with_boxes: retornando {len(fake_blocks)} bloques, "
              f"{len(full_text)} chars")
        return full_text, fake_blocks

    def release_engine(self):
        print("[PLACEBO] release_engine: limpiando engine simulado...")
        self._engine = None
        self._current_lang = None
        gc.collect()
        print("[PLACEBO] release_engine: listo")

    def process_area(self, x1, y1, x2, y2, lang: str = None) -> str:
        print(f"[PLACEBO] process_area: ({x1},{y1})->({x2},{y2}), lang={lang}")
        screenshot = self.capture_area(x1, y1, x2, y2)
        return self.extract_text(screenshot, lang)