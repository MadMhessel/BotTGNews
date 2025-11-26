import os
import sys
import asyncio
import logging

from dotenv import load_dotenv
from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, BufferedInputFile, InputMediaPhoto
from aiogram.client.session.aiohttp import AiohttpSession

from pipeline import GenerationResult, handle_post

# Настройка логгера
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

async def send_with_retry(func, *args, **kwargs):
    """Пытается отправить сообщение 3 раза при ошибках сети."""
    max_retries = 3
    for i in range(max_retries):
        try:
            await func(*args, **kwargs)
            return
        except Exception as e:
            logging.warning(f"Попытка отправки {i+1}/{max_retries} не удалась: {e}")
            if i == max_retries - 1:
                raise e
            await asyncio.sleep(2)

async def handle_news(message: Message) -> None:
    text = (message.text or "").strip()
    if not text:
        await message.answer("Жду текст новости или поста.")
        return

    # Отправляем "статус"
    status_msg = await message.answer("🎨 Анализирую текст и подбираю стиль...")

    try:
        # === ЭТАП 1: ГЕНЕРАЦИЯ ===
        result: GenerationResult = await asyncio.to_thread(handle_post, text)

        if not result.images:
            await status_msg.edit_text("⚠️ Не удалось сгенерировать изображение. Попробуйте другой текст.")
            return

        # === ЭТАП 2: УДАЛЕНИЕ СТАТУСА ===
        try:
            await status_msg.delete()
        except Exception:
            pass

        # === ЭТАП 3: ОТПРАВКА ===
        def _format_caption(prefix: str, validation_ok: bool, feedback: str) -> str:
            if validation_ok:
                return prefix
            hint = feedback or "Проверка не прошла."
            return f"{prefix}\n⚠️ Возможно, изображение не по теме: {hint}"

        if len(result.images) == 1:
            file = BufferedInputFile(result.images[0].getvalue(), filename="image.jpg")
            caption = _format_caption("Вот ваша визуализация.", result.validation_ok, result.validation_feedback)
            await send_with_retry(message.answer_photo, photo=file, caption=caption)
        else:
            media = [
                InputMediaPhoto(
                    media=BufferedInputFile(img.getvalue(), f"img_{i}.jpg"),
                    caption=_format_caption(
                        "Вот ваша визуализация.", result.validation_ok, result.validation_feedback
                    ) if i == 0 else None,
                )
                for i, img in enumerate(result.images)
            ]
            await send_with_retry(message.answer_media_group, media=media)

        if not result.validation_ok:
            info_msg = await message.answer(
                "⚠️ Проверка показала, что изображение может быть не по теме. Генерирую дополнительный вариант..."
            )
            try:
                extra_result: GenerationResult = await asyncio.to_thread(handle_post, text)
                if extra_result.images:
                    if len(extra_result.images) == 1:
                        extra_file = BufferedInputFile(
                            extra_result.images[0].getvalue(), filename="image_retry.jpg"
                        )
                        extra_caption = _format_caption(
                            "Дополнительная визуализация.",
                            extra_result.validation_ok,
                            extra_result.validation_feedback,
                        )
                        await send_with_retry(message.answer_photo, photo=extra_file, caption=extra_caption)
                    else:
                        extra_media = [
                            InputMediaPhoto(
                                media=BufferedInputFile(img.getvalue(), f"extra_img_{i}.jpg"),
                                caption=_format_caption(
                                    "Дополнительная визуализация.",
                                    extra_result.validation_ok,
                                    extra_result.validation_feedback,
                                ) if i == 0 else None,
                            )
                            for i, img in enumerate(extra_result.images)
                        ]
                        await send_with_retry(message.answer_media_group, media=extra_media)
            finally:
                try:
                    await info_msg.delete()
                except Exception:
                    pass

    except Exception as e:
        logging.exception("Критическая ошибка в handle_news")
        try:
            await message.answer(f"❌ Произошла ошибка: {str(e)}")
        except:
            pass


async def main() -> None:
    load_dotenv()
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        print("ОШИБКА: Не задан TELEGRAM_BOT_TOKEN в файле .env")
        return

    # Таймаут сессии для aiogram
    session = AiohttpSession(timeout=120.0)
    
    bot = Bot(token=token, session=session)
    dp = Dispatcher()

    dp.message.register(handle_news, F.text)

    print("Бот запущен...")
    
    try:
        await bot.delete_webhook(drop_pending_updates=True)
    except Exception:
        pass

    try:
        await dp.start_polling(bot, handle_signals=False, polling_timeout=60)
    finally:
        await bot.session.close()


if __name__ == "__main__":
    # !!! ВАЖНО ДЛЯ WINDOWS !!!
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        print("Бот остановлен")