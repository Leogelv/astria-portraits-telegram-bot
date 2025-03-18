#!/usr/bin/env python3
"""
Основной файл для запуска телеграм-бота Astria AI
"""

import os
from fastapi import FastAPI, Request, Header, HTTPException
from fastapi.responses import JSONResponse
import uvicorn
from loguru import logger
from bot import AstriaBot
from config import WEBHOOK_SECRET

# Создаем приложение FastAPI
app = FastAPI(title="Astria Bot API")

# Инициализируем бота
bot = AstriaBot()

# Запускаем бота в отдельном потоке
import threading
bot_thread = threading.Thread(target=bot.run)
bot_thread.daemon = True
bot_thread.start()

@app.get("/")
async def root():
    """Корневой эндпоинт для проверки работоспособности сервера"""
    return {"status": "OK", "message": "Astria Telegram Bot is running"}

@app.post("/webhook")
async def telegram_webhook(request: Request, x_telegram_bot_api_secret_token: str = Header(None)):
    """Обработчик вебхуков от Telegram без токена в URL"""
    # Проверяем секретный токен в заголовке
    if x_telegram_bot_api_secret_token != WEBHOOK_SECRET:
        logger.warning(f"Получен запрос с неверным секретным токеном")
        return JSONResponse(status_code=403, content={"error": "Неверный секретный токен"})
    
    # Получаем данные запроса
    update_data = await request.json()
    logger.debug(f"Получен вебхук от Telegram: {update_data}")
    
    # Обрабатываем обновление
    try:
        await bot.handle_webhook_update(update_data)
        return {"status": "OK"}
    except Exception as e:
        logger.error(f"Ошибка при обработке вебхука: {e}")
        return JSONResponse(status_code=500, content={"error": f"Ошибка при обработке вебхука: {str(e)}"})

if __name__ == "__main__":
    # Определяем порт (для Railway)
    port = int(os.environ.get("PORT", 8080))
    
    # Запускаем сервер
    uvicorn.run(app, host="0.0.0.0", port=port)
