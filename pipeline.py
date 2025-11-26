import logging
import os
from datetime import datetime
from typing import List

from analysis import analyze_news, build_image_headline
from strategy import decide_visual_strategy
from visual_spec import build_visual_spec
from image_generation import build_image_prompt, generate_image_with_gemini
from postprocess import process_image


def handle_post(text: str) -> List[bytes]:
    logging.info("--- НАЧАЛО ОБРАБОТКИ ПОСТА ---")
    
    # 1. Анализ текста
    logging.info("1. Анализ текста (Gemini 3 Pro)...")
    analysis = analyze_news(text)
    logging.info(f"   Категория: {analysis.get('category')}")

    # 2. Стратегия
    strategy = decide_visual_strategy(analysis)
    
    # 3. Спецификация
    spec = build_visual_spec(analysis, strategy)

    # 4. Заголовок
    if spec["text_overlay"]["enabled"]:
        logging.info("3. Генерация заголовка...")
        headline = build_image_headline(text, analysis)
        spec["text_overlay"]["headline"] = headline
        logging.info(f"   Заголовок: {headline}")
    
    # 5. Промпт
    image_prompt = build_image_prompt(spec)
    logging.info(f"4. Промпт готов. Начинаю генерацию...")

    # 6. Генерация изображений
    images_data = []
    
    # Папка для сохранения
    save_dir = os.path.join(os.path.dirname(__file__), "generated_images")
    os.makedirs(save_dir, exist_ok=True)
    
    try:
        logging.info("5. Запрос к API изображений (это может занять 15-40 сек)...")
        raw_image = generate_image_with_gemini(image_prompt)
        
        logging.info("6. Картинка получена! Начинаю постобработку (лого, текст)...")
        final_bytes = process_image(raw_image, spec)
        
        # --- СОХРАНЕНИЕ НА ДИСК ---
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        filename = f"gen_{timestamp}.jpg"
        filepath = os.path.join(save_dir, filename)
        
        with open(filepath, "wb") as f:
            f.write(final_bytes.getvalue())
            
        logging.info(f"💾 Изображение сохранено локально: {filepath}")
        # --------------------------

        images_data.append(final_bytes)
        logging.info("7. Постобработка завершена.")
        
    except Exception as e:
        logging.error(f"!!! КРИТИЧЕСКАЯ ОШИБКА в пайплайне: {e}")
        raise e

    logging.info("--- КОНЕЦ ОБРАБОТКИ ---")
    return images_data