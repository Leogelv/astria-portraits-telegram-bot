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
  -p 3000:3000 \
  -e WEBHOOK_URL=https://astria-portraits-telegram-bot-production.up.railway.app \
  -e TELEGRAM_BOT_TOKEN=7841199395:AAFm779B_P_RaeNSjd0H7v-SNWBD0QMi2Z4 \
  -e WEBHOOK_SECRET=verySecretWebhookKey123 \
  -e PORT=8080 \
  -e HEALTHCHECK_PORT=3000 \
  -e NEXT_PUBLIC_SUPABASE_URL=https://txhyoqrbcianrpwsivac.supabase.co \
  -e NEXT_PUBLIC_SUPABASE_ANON_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InR4aHlvcXJiY2lhbnJwd3NpdmFjIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NDAyMjY3ODMsImV4cCI6MjA1NTgwMjc4M30.n1m6fIIyvhhesZYVcdJtpME142G0Wwpg9NuMM12W3hw \
  -e ASTRIA_API_KEY=sd_WMQQoUExY67wjLMWkeqMKXGy6dxume \
  -e ADMIN_TELEGRAM_ID=375634162 \
  astria-bot-image

# Проверяем логи
echo "📋 Логи контейнера:"
docker logs -f astria-bot 