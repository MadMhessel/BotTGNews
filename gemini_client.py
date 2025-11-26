import os
from google import genai
from google.genai import types

_client = None

def get_gemini_client() -> genai.Client:
    global _client
    if _client is not None:
        return _client

    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("❌ ОШИБКА: Переменная окружения GEMINI_API_KEY не найдена в .env")

    # Создаем клиент с явным указанием версии API, если нужно,
    # но для превью моделей (Gemini 3) лучше использовать v1alpha или v1beta
    try:
        _client = genai.Client(
            api_key=api_key,
            http_options={
                'api_version': 'v1alpha',  # Часто требуется для экспериментальных моделей
                'timeout': 300000          # 5 минут таймаут
            }
        )
    except Exception as e:
        # Фоллбэк, если v1alpha не поддерживается
        print(f"⚠️ Warning: v1alpha client init failed, trying default. Error: {e}")
        _client = genai.Client(
            api_key=api_key,
            http_options={'timeout': 300000}
        )
        
    return _client