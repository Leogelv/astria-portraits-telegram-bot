#!/bin/bash

# Останавливаем и удаляем контейнер, если он существует
docker stop astria-bot 2>/dev/null || true
docker rm astria-bot 2>/dev/null || true

# Удаляем образ, если он существует
docker rmi astria-bot-image 2>/dev/null || true

# Строим новый образ
echo "🔨 Сборка Docker образа..."
docker build -t astria-bot-image .

# Запускаем контейнер
echo "🚀 Запуск контейнера..."
docker run -d --name astria-bot \
  -p 8080:8080 \
  -e WEBHOOK_URL=https://astria-portraits-telegram-bot-production.up.railway.app \
  -e TELEGRAM_BOT_TOKEN=7841199395:AAFm779B_P_RaeNSjd0H7v-SNWBD0QMi2Z4 \
  -e WEBHOOK_SECRET=verySecretWebhookKey123 \
  -e PORT=8080 \
  astria-bot-image

# Проверяем логи
echo "📋 Логи контейнера:"
docker logs -f astria-bot 