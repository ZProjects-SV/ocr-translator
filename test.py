import os
import sys
import gc
import time
import psutil
from collections import OrderedDict

# Asegurarnos de que el path raíz del proyecto esté disponible para los imports de Paddle
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ.setdefault("FLAGS_fraction_of_cpu_memory_to_use", "0.2")
os.environ.setdefault("FLAGS_allocator_strategy", "auto_growth")

import cv2
import numpy as np
from PIL import Image

# ==========================================================
# CONFIGURACIÓN DIRECTA (Sin dependencias de config.py)
# ==========================================================
PADDLE_LANG = "es"
PADDLE_MIN_CONFIDENCE = 0.6
PADDLE_MIN_CONFIDENCE_PIXEL = 0.35
TRANSLATION_TO_PADDLE_LANG = {
    "en": "en", "es": "es", "pt": "en",
    "fr": "en", "de": "en", "it": "en",
    "ja": "japan", "ko": "korean", "zh-cn": "ch",
}

# Función "mock" para reemplazar a preferences.get_translation_source
def get_translation_source() -> str:
    return "en"

# ==========================================================
# BLOQUE: Helper para medir memoria (RSS - Resident Set Size)
# ==========================================================
def get_memory_usage():
    """Retorna la memoria RAM actual usada por el proceso en MB."""
    process = psutil.Process(os.getpid())
    return process.memory_info().rss / (1024 * 1024)

def log_mem(step_name):
    """Imprime un log con la memoria actual y el pico máximo alcanzado."""
    process = psutil.Process(os.getpid())
    mem_info = process.memory_info()
    mem_mb = mem_info.rss / (1024 * 1024)
    peak_mb = mem_info.peak_wset / (1024 * 1024) if hasattr(mem_info, 'peak_wset') else 0
    if peak_mb > 0:
        print(f"  [MEM] {step_name:<40} | RAM: {mem_mb:>8.2f} MB | PICO: {peak_mb:>8.2f} MB")
    else:
        print(f"  [MEM] {step_name:<40} | RAM: {mem_mb:>8.2f} MB")
    return mem_mb

# ==========================================================
# BLOQUE: Detección de capacidades de hardware (una sola vez)
# ==========================================================
_HW_CACHE = {"mkldnn_ok": None, "cpu_threads": None}

def _detect_cpu_threads() -> int:
    if _HW_CACHE["cpu_threads"] is not None:
        return _HW_CACHE["cpu_threads"]
    count = os.cpu_count() or 4
    threads = max(2, min(count - 1, 8))
    _HW_CACHE["cpu_threads"] = threads
    return threads

def _supports_fast_mkldnn() -> bool:
    if _HW_CACHE["mkldnn_ok"] is not None:
        return _HW_CACHE["mkldnn_ok"]
    try:
        import cpuinfo
        flags = cpuinfo.get_cpu_info().get("flags", [])
        result = "avx512f" in flags
    except Exception:
        result = False
    _HW_CACHE["mkldnn_ok"] = result
    return result

# ==========================================================
# BLOQUE: Detección de tipo de fuente y calidad de imagen
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
    return (hard_edges / total) > 0.60

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
        "needs_denoise": noise > 6.0,
        "needs_contrast": contrast < 40.0,
        "needs_sharpen": sharpness < 150.0,
    }

# ==========================================================
# BLOQUE: Helper -- normaliza resultado de .predict() a lista de bloques
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

def _det_limit_tier(width: int, height: int) -> int:
    longest = max(width, height)
    if longest <= 480:
        return 640
    if longest <= 960:
        return 960
    if longest <= 1600:
        return 1280
    return 1600

# ==========================================================
# BLOQUE: Cache LRU de engines por (lang, det_limit)
# ==========================================================
class _EngineCache:
    def __init__(self, max_size: int = 2):
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
            print(f"[OCR] Descartando engine LRU (lang='{old_key[0]}', det_limit={old_key[1]})...")
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
# BLOQUE: Clase Principal -- OCREngine (instancia persistente)
# ==========================================================
class OCREngine:
    # Set interno en memoria, ya no usa Qt Settings
    _downloaded_langs: set = set() 
    _MAX_CACHED_ENGINES = 2
    _GC_EVERY_N_CALLS = 20

    def __init__(self):
        print("[OCR] OCREngine.__init__: iniciando...")
        # Ya no llamamos a get_downloaded_langs()
        self._cache = _EngineCache(max_size=self._MAX_CACHED_ENGINES)
        self._engine = None
        self._current_lang = None
        self._mkldnn_enabled = None
        self._current_det_limit = None
        self._calls_since_gc = 0

        source_lang = get_translation_source()
        self._load_engine(source_lang, det_limit=960)
        
        # LIMPIEZA NATIVA POST-CARGA: Después de que el modelo ya se construyó,
        # forcemos a Paddle 3.x a liberar la memoria de inicialización que ya no usa.
        try:
            import paddle
            allocator = paddle._C.core.Allocator()
            allocator.release()
            print("[OCR] Allocator nativo de Paddle liberado tras carga.")
        except Exception as e:
            print(f"[OCR] Liberación nativa no soportada: {e}")
            
        print(f"[OCR] Engine listo (lang='{source_lang}')")

    def _get_paddle_lang(self, source_lang: str) -> str:
        return TRANSLATION_TO_PADDLE_LANG.get(source_lang, PADDLE_LANG)

    def _build_engine(self, paddle_lang: str, use_mkldnn: bool, det_limit: int):
        from paddleocr import PaddleOCR
        threads = _detect_cpu_threads()
        # Le decimos a Paddle que NO inicialice el predictor todavía.
        # Así guardamos los pesos en RAM sin crear el grafo de inferencia que fugaba memoria.
        return PaddleOCR(
            device="cpu",
            enable_mkldnn=use_mkldnn,
            cpu_threads=threads,
            text_detection_model_name="PP-OCRv6_medium_det",
            text_recognition_model_name="PP-OCRv6_medium_rec",
            use_doc_orientation_classify=False,
            use_doc_unwarping=False,
            use_textline_orientation=False,
            text_det_limit_side_len=det_limit,
            text_det_limit_type="max",
            # EVITAR LA FUGA: No construir el predictor hasta que lo llamemos explícitamente
            use_predictor_cache=False, 
        )

    def _load_engine(self, source_lang: str, det_limit: int = 960) -> None:
        key = (source_lang, det_limit)

        cached = self._cache.get(key)
        if cached is not None:
            if self._engine is not cached:
                print(f"[OCR] Reutilizando engine cacheado (lang='{source_lang}', det_limit={det_limit})")
            self._engine = cached
            self._current_lang = source_lang
            self._current_det_limit = det_limit
            return

        paddle_lang = self._get_paddle_lang(source_lang)
        use_mkldnn = _supports_fast_mkldnn()
        print(f"[OCR] Cargando PaddleOCR 3.x: lang='{source_lang}' "
              f"(paddle='{paddle_lang}', mkldnn={use_mkldnn}, det_limit={det_limit})...")

        try:
            engine = self._build_engine(paddle_lang, use_mkldnn, det_limit)
            if use_mkldnn:
                dummy = np.full((64, 256, 3), 255, dtype=np.uint8)
                t0 = time.perf_counter()
                engine.predict(dummy)
                elapsed = time.perf_counter() - t0
                if elapsed > 2.0:
                    print(f"[OCR] MKL-DNN parece lento en este hardware ({elapsed:.2f}s), recargando sin el...")
                    del engine
                    gc.collect()
                    engine = self._build_engine(paddle_lang, False, det_limit)
                    use_mkldnn = False
                del dummy
        except Exception as e:
            print(f"[OCR] Error cargando con mkldnn={use_mkldnn}: {e}. Reintentando sin mkldnn...")
            engine = self._build_engine(paddle_lang, False, det_limit)
            use_mkldnn = False

        self._cache.put(key, engine)
        self._engine = engine
        self._mkldnn_enabled = use_mkldnn
        _HW_CACHE["mkldnn_ok"] = use_mkldnn
        self._current_lang = source_lang
        self._current_det_limit = det_limit
        
        # Guardamos en el set interno en vez de llamar a add_downloaded_lang()
        self._downloaded_langs.add(source_lang)
        
        print(f"[OCR] Engine cargado correctamente (lang='{source_lang}', mkldnn={use_mkldnn}, det_limit={det_limit})")

    def release_engine(self) -> None:
        print("[OCR] release_engine: liberando todos los engines cacheados...")
        self._cache.clear()
        self._engine = None
        self._current_lang = None
        self._current_det_limit = None
        gc.collect()
        print("[OCR] release_engine: engines liberados")

    def _ensure_engine_ready(self, source_lang: str, det_limit: int) -> None:
        self._load_engine(source_lang, det_limit=det_limit)

    def _maybe_collect(self) -> None:
        self._calls_since_gc += 1
        if self._calls_since_gc >= self._GC_EVERY_N_CALLS:
            gc.collect()
            self._calls_since_gc = 0

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
            binary = cv2.adaptiveThreshold(gray_scaled, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                                            cv2.THRESH_BINARY, 15, 2)
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
        print(f"[OCR] Pixel-font preprocesado (x{scale})")
        return out, scale

    def _preprocess_standard(self, rgb_arr: np.ndarray, gray: np.ndarray, quality: dict):
        img_cv = cv2.cvtColor(rgb_arr, cv2.COLOR_RGB2BGR)

        if quality["needs_denoise"] and img_cv.shape[1] < 900:
            denoised = cv2.fastNlMeansDenoisingColored(
                img_cv, None, h=3, hColor=3, templateWindowSize=7, searchWindowSize=15
            )
            del img_cv
            img_cv = denoised

        if quality["needs_contrast"]:
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
        out = Image.fromarray(rgb)
        del rgb

        if quality["needs_sharpen"]:
            from PIL import ImageFilter
            sharpened = out.filter(ImageFilter.SHARPEN)
            out.close()
            out = sharpened

        print(f"[OCR] Standard preprocesado (denoise={quality['needs_denoise']}, "
              f"contrast={quality['needs_contrast']}, sharpen={quality['needs_sharpen']})")
        return out

    def extract_text_isolated(self, image_path: str) -> dict:
        """Híbrido: Usa los pesos en caché, pero crea y destruye el Ejecutor."""
        
        # 1. Carga de imagen
        img = Image.open(image_path)
        if img.mode != "RGB":
            img = img.convert("RGB")
            
        if img.width < 10 or img.height < 10:
            img.close()
            return {"error": "Imagen muy pequeña"}

        source_lang = get_translation_source()
        det_limit = _det_limit_tier(img.width, img.height)
        
        # Aseguramos que el objeto con los PESOS esté cargado (sin predictor)
        self._ensure_engine_ready(source_lang, det_limit)
        engine_with_weights = self._engine

        # 2. Preprocesamiento
        processed, pixel_font, scale = self._preprocess(img)
        min_conf = PADDLE_MIN_CONFIDENCE_PIXEL if pixel_font else PADDLE_MIN_CONFIDENCE

        img.close()
        del img
        log_mem("Despues de cerrar imagen original")

        img_array = np.array(processed.convert("RGB"))
        processed.close()
        del processed
        log_mem("Despues de preprocesamiento (previo a predict)")

        # 3. INFERENCIA EN EJECUTOR DESECHABLE
        # Extraemos solo el creador de predictores (que no carga pesos de nuevo)
        predictor_factory = engine_with_weights._pipeline.predictor
        temp_predictor = None
        
        try:
            print(f"  [ENGINE] Creando ejecutor desechable para det_limit={det_limit}...")
            # Construimos el predictor (grafo de C++) a partir de los pesos ya en RAM
            temp_predictor = predictor_factory.create_predictor(predictor_factory.get_default_predictor_param())
            
            # Predecimos usando el ejecutor temporal
            result = temp_predictor.predict(img_array)
            log_mem("Despues de predict (resultado en memoria)")

            blocks = _parse_predict_result(result, min_conf)
            
            try:
                del result
            except Exception:
                pass
                
        finally:
            # DESTRUCCIÓN TOTAL solo del ejecutor (el que causaba la fuga de C++)
            if temp_predictor is not None:
                del temp_predictor
            del img_array
            log_mem("Despues de DESTRUIR temp_predictor & img_array")
            
            # Triple limpieza para asegurar que el SO recupere la RAM
            gc.collect()
            gc.collect()
            gc.collect()
            mem_final = log_mem("Despues de TRIPLE gc.collect() FINAL")

        if not blocks:
            return {"blocks": 0, "chars": 0, "mem_mb": mem_final}

        blocks.sort(key=lambda b: b["poly"][0][1] if b["poly"] is not None else 0)
        text = "\n".join(b["text"] for b in blocks).strip()
        
        result_stats = {
            "blocks": len(blocks), 
            "chars": len(text), 
            "mem_mb": mem_final
        }
        
        del blocks
        del text
        
        return result_stats


# ==========================================================
# BLOQUE: Script Principal de Pruebas
# ==========================================================
if __name__ == "__main__":
    print("="*60)
    print("INICIANDO PRUEBA DE MEMORIA AISLADA")
    print("="*60)
    
    mem_inicial = log_mem("Estado inicial (antes de cargar engine)")
    
    # Inicializar el motor (aquí se carga el modelo a memoria)
    ocr_engine = OCREngine()
    log_mem("Despues de cargar OCREngine")
    
    test_dir = "test-images"
    
    print(f"\nEsperando 5 segundos para estabilizar memoria antes de empezar...")
    time.sleep(5)
    log_mem("Base estable antes de bucle")
    
    for i in range(1, 11):
        img_path = os.path.join(test_dir, f"test{i}.png")
        
        if not os.path.exists(img_path):
            print(f"\n[!] No se encontró {img_path}, saltando...")
            continue
            
        print(f"\n{'='*60}")
        print(f"PROCESANDO: {img_path}")
        print(f"{'='*60}")
        log_mem("Inicio de iteración")
        
        stats = ocr_engine.extract_text_isolated(img_path)
        
        # Imprimir solo estadísticas, NO el texto
        print(f"  -> Resultado: {stats.get('blocks', 0)} bloques, {stats.get('chars', 0)} caracteres")
        
        if i < 10:
            print(f"\nEsperando 10 segundos antes de la siguiente imagen...")
            time.sleep(10)
            
    print(f"\n{'='*60}")
    print("PRUEBA FINALIZADA")
    print(f"{'='*60}")
    log_mem("Memoria al final de todo el script")
    
    # Liberar engine al finalizar para ver cuánta memoria se libera
    ocr_engine.release_engine()
    log_mem("Memoria DESPUES de liberar el engine")