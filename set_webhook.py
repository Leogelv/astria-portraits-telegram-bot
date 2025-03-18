#!/usr/bin/env python3
import os
import requests
from dotenv import load_dotenv
from loguru import logger

# Загружаем переменные окружения из .env файла
load_dotenv()

# Получаем переменные из .env
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET")

# Проверяем наличие переменных
if not TELEGRAM_BOT_TOKEN:
    logger.error("TELEGRAM_BOT_TOKEN не найден в переменных окружения")
    exit(1)

if not WEBHOOK_URL:
    logger.error("WEBHOOK_URL не найден в переменных окружения")
    exit(1)

if not WEBHOOK_SECRET:
    logger.error("WEBHOOK_SECRET не найден в переменных окружения")
    exit(1)

# Формируем URL для установки вебхука
webhook_full_url = f"{WEBHOOK_URL}/{TELEGRAM_BOT_TOKEN}"
set_webhook_url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/setWebhook"

# Параметры для установки вебхука
webhook_params = {
    "url": webhook_full_url,
    "secret_token": WEBHOOK_SECRET,
}

# Отправляем запрос на установку вебхука
print(f"Устанавливаем вебхук на URL: {webhook_full_url}")
response = requests.post(set_webhook_url, json=webhook_params)

# Проверяем результат
if response.status_code == 200 and response.json().get("ok"):
    print("✅ Вебхук успешно установлен!")
    print(f"URL вебхука: {webhook_full_url}")
    print(f"Секретный токен: {WEBHOOK_SECRET}")
    print("\nИнформация о текущем вебхуке:")
    
    # Получаем информацию о вебхуке
    webhook_info_url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/getWebhookInfo"
    info_response = requests.get(webhook_info_url)
    if info_response.status_code == 200:
        info = info_response.json().get("result", {})
        for key, value in info.items():
            print(f"{key}: {value}")
    else:
        print(f"Не удалось получить информацию о вебхуке: {info_response.text}")
else:
    print(f"❌ Ошибка при установке вебхука: {response.text}")

print("\nДля запуска бота в режиме вебхука выполните:")
print("python main.py") 