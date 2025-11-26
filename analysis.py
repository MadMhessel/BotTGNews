import json
import logging
import re

from gemini_client import get_gemini_client, types

SYSTEM_PROMPT_ANALYZE = '''Ты — главный аналитик. Твоя задача: прочитать текст и вернуть ТОЛЬКО валидный JSON.
Не пиши вступлений, не используй Markdown блоки.
Структура JSON:
{
  "category": "строка (news, promo, anons, analytics, story, humor, lifestyle)",
  "subtype": "строка (city_infrastructure, housing, culture, transport, nature, politics, other)",
  "tone": "строка (positive, neutral, tense, negative)",
  "emotion": "строка (joy, calm_interest, pride, anxiety, sorrow, irony, anticipation)",
  "sensitivity": "строка (low, medium, high)", 
  "key_entities": ["список главных объектов"],
  "visual_anchors": ["список из 2-3 фраз для промпта"],
  "risk_flags": {
     "tragedy": boolean,
     "violence": boolean,
     "politics_hard": boolean
  }
}
'''

SYSTEM_PROMPT_HEADLINE = '''Ты — креативный копирайтер. На основе исходного текста придумай подпись или слоган для изображения.
У тебя полная свобода оформления: можешь делать одну строку или несколько, играть с ритмом, использовать заглавные буквы, тире, эмодзи, повторы — всё, что подчеркивает смысл исходных данных.
Учитывай визуальный стиль: фотография — факт и конкретика; постер — слоган и ритм; иллюстрация — образность и эмоция.
Сохраняй факты и избегай кликбейта. Верни только готовый текст без пояснений.'''

SYSTEM_PROMPT_LAYOUT = '''Ты — арт-директор, который решает, как компактный заголовок ляжет на вертикальное изображение 4:5.
Проанализируй контекст, чтобы текст не перекрывал важный сюжет и гармонично смотрелся с визуальным стилем.
Верни строго JSON без пояснений:
{
  "placement": "top | center | bottom | auto",
  "alignment": "left | center | right",
  "style": "glass | soft_card | banner",
  "palette": "auto | light | dark",
  "emphasis": ["слова для акцента в тексте"]
}
Правила:
- placement выбирается по важности фона (например, top, если низ кадра важен для сюжета, иначе auto).
- alignment подбирается под композицию (анонс, промо — по центру; репортаж/новости — смещение влево/вправо возможно).
- style: glass — прозрачная плашка с легким блюром; soft_card — мягкая карточка; banner — вытянутый баннер с минимальным скруглением.
- palette: если фон предполагается темный, выбери light; если светлый — dark; если нет уверенности — auto.
- emphasis: выбери до 2 слов/фраз, которые стоит подсветить цветом, учитывая смысл и эмоцию новости.
'''

def _clean_json_string(text: str) -> str:
    """Очищает строку от Markdown оберток ```json ... ``` и лишних символов."""
    # Убираем обертки markdown
    text = re.sub(r'```json\s*', '', text, flags=re.IGNORECASE)
    text = re.sub(r'```\s*', '', text)
    # Ищем начало и конец JSON объекта
    start = text.find('{')
    end = text.rfind('}')
    if start != -1 and end != -1:
        text = text[start : end + 1]
    return text.strip()

def analyze_news(text: str) -> dict:
    client = get_gemini_client()
    # Дефолтный ответ на случай ошибок
    default_analysis = {
        "category": "news",
        "subtype": "other",
        "tone": "neutral",
        "sensitivity": "low",
        "visual_anchors": ["абстрактный фон", "новости"],
        "risk_flags": {"tragedy": False}
    }

    try:
        response = client.models.generate_content(
            model="gemini-3-pro-preview", # Ваша выбранная модель
            contents=[
                types.Content(role="system", parts=[types.Part(text=SYSTEM_PROMPT_ANALYZE)]),
                types.Content(role="user", parts=[types.Part(text=f"Текст:\n{text}")]),
            ],
            config=types.GenerateContentConfig(
                response_mime_type="application/json"
            ),
        )

        # БЕЗОПАСНОЕ ПОЛУЧЕНИЕ ТЕКСТА
        # В новом SDK .text может упасть, если сработал Safety Filter
        if not response.candidates or not response.candidates[0].content or not response.candidates[0].content.parts:
            logging.warning("⚠️ Gemini вернул пустой ответ (возможно, Safety Filter). Использую дефолт.")
            return default_analysis

        # Пытаемся достать текст из первой части
        raw_text = ""
        for part in response.candidates[0].content.parts:
            if part.text:
                raw_text += part.text
        
        if not raw_text:
            logging.warning("⚠️ Gemini вернул ответ без текста.")
            return default_analysis

        cleaned_json = _clean_json_string(raw_text)
        return json.loads(cleaned_json)

    except json.JSONDecodeError:
        logging.error(f"❌ Ошибка парсинга JSON. Сырой ответ: {raw_text[:100]}...")
        return default_analysis
    except Exception as e:
        logging.error(f"❌ Ошибка в analyze_news: {e}")
        return default_analysis


def build_image_headline(post_text: str, analysis: dict, spec: dict) -> str:
    client = get_gemini_client()
    style = spec.get("style", {})
    text_overlay = spec.get("text_overlay", {})

    # Контекст для адаптации текста под визуализацию
    context_parts = [
        f"Категория: {analysis.get('category')}",
        f"Тональность текста: {analysis.get('tone')}",
        f"Настрой визуала: {spec.get('mood_instruction', style.get('realism', ''))}",
        f"Основной образ: {spec.get('subject')}",
        f"Дополнительная сцена: {spec.get('environment', '')}" if spec.get('environment') else None,
        f"Тип визуала: {style.get('type')}",
        f"Цветовая палитра: {style.get('palette')}",
        "Требуется лаконичный оверлей на изображении" if text_overlay.get("enabled") else None,
    ]
    context = ". ".join(filter(None, context_parts))

    try:
        response = client.models.generate_content(
            model="gemini-3-pro-preview",
            contents=[
                types.Content(role="system", parts=[types.Part(text=SYSTEM_PROMPT_HEADLINE)]),
                types.Content(role="user", parts=[types.Part(text=f"{context}\n\nТекст:\n{post_text}")]),
            ]
        )
        
        if response.candidates and response.candidates[0].content and response.candidates[0].content.parts:
            text = response.candidates[0].content.parts[0].text
            if text:
                return text.strip().replace('"', '').replace("\n", " ")
        
        return ""
    except Exception as e:
        logging.error(f"Ошибка генерации заголовка: {e}")
        return ""


def build_text_overlay_plan(headline: str, analysis: dict, spec: dict) -> dict:
    client = get_gemini_client()

    context_parts = [
        f"Категория: {analysis.get('category')}",
        f"Событие: {analysis.get('subtype')}",
        f"Тон: {analysis.get('tone')}",
        f"Эмоция: {analysis.get('emotion')}",
        f"Основной образ: {spec.get('subject')}",
        f"Сцена: {spec.get('environment', '')}" if spec.get('environment') else None,
        f"Тип визуала: {spec.get('style', {}).get('type')}",
        f"Палитра: {spec.get('style', {}).get('palette')}",
        f"Реализм: {spec.get('style', {}).get('realism')}",
        f"Заголовок: {headline}",
    ]
    context = ". ".join(filter(None, context_parts))

    default_plan = {
        "placement": "auto",
        "alignment": "center",
        "style": "glass",
        "palette": "auto",
        "emphasis": [],
    }

    try:
        response = client.models.generate_content(
            model="gemini-3-pro-preview",
            contents=[
                types.Content(role="system", parts=[types.Part(text=SYSTEM_PROMPT_LAYOUT)]),
                types.Content(role="user", parts=[types.Part(text=context)]),
            ],
            config=types.GenerateContentConfig(response_mime_type="application/json"),
        )

        if not response.candidates or not response.candidates[0].content or not response.candidates[0].content.parts:
            return default_plan

        raw_text = ""
        for part in response.candidates[0].content.parts:
            if part.text:
                raw_text += part.text

        cleaned = _clean_json_string(raw_text)
        plan = json.loads(cleaned)

        if not isinstance(plan, dict):
            return default_plan

        merged = {**default_plan, **{k: v for k, v in plan.items() if k in default_plan}}
        # Нормализуем список эмфазиса
        if not isinstance(merged.get("emphasis"), list):
            merged["emphasis"] = []

        return merged
    except Exception as e:
        logging.error(f"Ошибка выбора расположения текста: {e}")
        return default_plan
