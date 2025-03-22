#!/usr/bin/env python3
import requests

# Используем новый токен напрямую
TELEGRAM_BOT_TOKEN = "7841199395:AAFm779B_P_RaeNSjd0H7v-SNWBD0QMi2Z4"
WEBHOOK_URL = "https://astria-portraits-telegram-bot-production.up.railway.app"
WEBHOOK_SECRET = "verySecretWebhookKey123"

# Формируем URL для установки вебхука без токена в пути
webhook_full_url = f"{WEBHOOK_URL}/webhook"
set_webhook_url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/setWebhook"

# Параметры для установки вебхука
webhook_params = {
    "url": webhook_full_url,
    "secret_token": WEBHOOK_SECRET,
    "allowed_updates": ["message", "callback_query", "edited_message", "channel_post", "edited_channel_post", "inline_query", "chosen_inline_result", "shipping_query", "pre_checkout_query", "poll", "poll_answer", "my_chat_member", "chat_member", "chat_join_request"],
}

# Отправляем запрос на установку вебхука
print(f"Устанавливаем вебхук на URL: {webhook_full_url}")
response = requests.post(set_webhook_url, json=webhook_params)

# Проверяем результат
if response.status_code == 200 and response.json().get("ok"):
    print("✅ Вебхук успешно установлен!")
    print(f"URL вебхука: {webhook_full_url}")
    
    # Получаем информацию о вебхуке
    webhook_info_url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/getWebhookInfo"
    info_response = requests.get(webhook_info_url)
    if info_response.status_code == 200:
        info = info_response.json().get("result", {})
        for key, value in info.items():
            print(f"{key}: {value}")
else:
    print(f"❌ Ошибка при установке вебхука: {response.text}") 