import json
import logging
from typing import Tuple

from gemini_client import get_gemini_client, types

VALIDATION_PROMPT = (
    "Ты модератор качества изображений. Оцени, отражает ли картинка тему новости. "
    "В ответ верни JSON вида {\"is_relevant\": true/false, \"comment\": \"кратко почему\"}. "
    "Считай нерелевантным, если сцена, объекты или настроение явно расходятся с текстом."
)


def _extract_text(response) -> str:
    if not response or not getattr(response, "candidates", None):
        return ""

    for candidate in response.candidates:
        if candidate.content and candidate.content.parts:
            chunks = []
            for part in candidate.content.parts:
                if part.text:
                    chunks.append(part.text)
            if chunks:
                return "".join(chunks)
    return ""


def validate_image_relevance(image_bytes: bytes, news_text: str) -> Tuple[bool, str]:
    """Проверяет, соответствует ли изображение теме новости."""
    client = get_gemini_client()

    try:
        response = client.models.generate_content(
            model="gemini-3-pro-preview",
            contents=[
                types.Part.from_bytes(image_bytes, mime_type="image/jpeg"),
                types.Part(text=f"{VALIDATION_PROMPT}\nНовость: {news_text}"),
            ],
            config=types.GenerateContentConfig(response_mime_type="application/json"),
        )

        raw_text = _extract_text(response)
        if not raw_text:
            logging.warning("⚠️ Модель вернула пустой ответ при проверке изображения.")
            return True, "Проверка не сработала, пустой ответ модели."

        try:
            payload = json.loads(raw_text)
            is_relevant = bool(payload.get("is_relevant", True))
            comment = payload.get("comment") or ""
            return is_relevant, comment
        except json.JSONDecodeError:
            logging.warning(
                f"⚠️ Не удалось распарсить JSON ответа на проверку: {raw_text[:120]}"
            )
            return True, "Ответ проверки нераспознан, считаем изображение допустимым."
    except Exception as e:
        logging.warning(f"⚠️ Сбой проверки изображения: {e}")
        return True, "Проверка не выполнена из-за ошибки."
