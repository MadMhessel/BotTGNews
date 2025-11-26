import base64
import io
import logging
import time
from PIL import Image
from google.genai import types

from gemini_client import get_gemini_client

def build_image_prompt(spec: dict) -> str:
    """Создает промпт (без изменений логики)."""
    subject = spec["subject"]
    style = spec["style"]
    chars = spec["characters"]
    
    parts = []
    
    # 1. STYLE
    if style["type"] == "photo_like":
        parts.append(f"Award-winning professional photography: {subject}.")
        parts.append("Cinematic lighting, 8k resolution, highly detailed texture, depth of field, photorealistic.")
    elif style["type"] == "poster":
        parts.append(f"Modern vector art poster design: {subject}.")
        parts.append("Clean lines, flat design, trendy aesthetic, high contrast.")
    else:
        parts.append(f"Digital art masterpiece: {subject}.")
        parts.append("Detailed illustration, vibrant colors.")
    
    # 2. ENV & MOOD
    if spec["environment"]: parts.append(f"Setting: {spec['environment']}.")
    parts.append(f"Mood: {spec['mood_instruction']}.")
    
    # 3. PALETTE
    palette_map = {
        "neutral_news": "Color palette: Neutral, balanced, realistic, professional news grade.",
        "soft_city": "Color palette: Urban soft tones, concrete grey, sky blue, fresh green.",
        "promo_bright": "Color palette: Vivid, saturated, commercial, energetic colors.",
        "dark_serious": "Color palette: Muted, cinematic dark tones, dramatic shadows."
    }
    parts.append(palette_map.get(style["palette"], ""))
    
    # 4. CHARS & NEGATIVE
    if chars["allowed"]:
        parts.append(f"Feature character: {chars['description']}")
    else:
        parts.append("NO PEOPLE close up. Focus on the scene.")

    parts.append("RESTRICTIONS: No text, no watermarks, no logos, no blurry details.")
    parts.append("Format: Vertical aspect ratio 4:5. High resolution.")

    return " ".join(parts)


def generate_image_with_gemini(image_prompt: str) -> Image.Image:
    client = get_gemini_client()
    logging.info(f"🎨 Отправка промпта: {image_prompt[:60]}...")
    
    max_attempts = 2 # Снизим до 2, чтобы не ждать вечность при сбоях
    
    for attempt in range(1, max_attempts + 1):
        try:
            if attempt > 1:
                logging.info(f"🔄 Попытка генерации {attempt}...")
            
            # ВАЖНО: Gemini 3 Image Preview (Multimodal)
            response = client.models.generate_content(
                model="gemini-3-pro-image-preview", # Используем модель пользователя
                contents=image_prompt,
            )

            # === СТРОГАЯ ПРОВЕРКА ОТВЕТА ===
            if not response.candidates:
                logging.warning(f"⚠️ Попытка {attempt}: API вернул пустой список candidates (возможно, Safety Block).")
                continue

            for candidate in response.candidates:
                # Проверка Safety Ratings (если нужно логировать)
                if candidate.finish_reason != "STOP":
                    logging.warning(f"⚠️ Finish reason: {candidate.finish_reason}")

                if not candidate.content or not candidate.content.parts:
                    continue
                
                for part in candidate.content.parts:
                    # Проверяем наличие байтов (изображения)
                    if part.inline_data and part.inline_data.data:
                        raw_data = part.inline_data.data
                        logging.info(f"✅ Изображение получено! Размер: {len(raw_data)} байт.")
                        
                        def _open_image(data: bytes) -> Image.Image:
                            img = Image.open(io.BytesIO(data))
                            img.load()  # Проверка целостности
                            return img

                        try:
                            return _open_image(raw_data)
                        except Exception as img_err:
                            logging.error(f"❌ Ошибка открытия изображения PIL (прямая загрузка): {img_err}")

                        # Попытка декодировать base64, если SDK вернул данные в виде ASCII-строки
                        try:
                            decoded_bytes = base64.b64decode(raw_data)
                            return _open_image(decoded_bytes)
                        except Exception as decode_err:
                            logging.error(f"❌ Ошибка открытия изображения после base64-декодирования: {decode_err}")
                            continue
                    
                    # Если модель вернула текст вместо картинки (отказ)
                    if part.text:
                        logging.warning(f"⚠️ Модель вернула текст вместо картинки: {part.text}")

            # Если цикл прошел, но картинки нет
            logging.warning(f"⚠️ Попытка {attempt}: В ответе не найдено inline_data.")

        except Exception as e:
            logging.error(f"⚠️ Сбой API (попытка {attempt}): {e}")
            if "429" in str(e): # Лимит запросов
                time.sleep(10)
            elif "404" in str(e):
                raise RuntimeError("Модель не найдена. Проверьте название модели в коде.")
            else:
                time.sleep(3)
            
    raise RuntimeError("Не удалось сгенерировать изображение после всех попыток.")