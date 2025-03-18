# Руководство по деплою Telegram-бота для Astria AI

В этом руководстве описаны шаги по деплою телеграм-бота на различные платформы.

## Деплой на Railway

[Railway](https://railway.app/) — простая платформа для хостинга приложений с автоматическим деплоем из Git.

### Шаг 1: Создайте аккаунт на Railway

Зарегистрируйтесь на [Railway](https://railway.app/) и войдите в свой аккаунт.

### Шаг 2: Создайте новый проект

1. Нажмите на кнопку "New Project" на дашборде
2. Выберите "Deploy from GitHub repo"
3. Выберите репозиторий с ботом из списка

### Шаг 3: Настройте переменные окружения

1. В проекте перейдите в раздел "Variables"
2. Добавьте все необходимые переменные окружения из `.env.example`:
   - `TELEGRAM_BOT_TOKEN`
   - `SUPABASE_URL`
   - `SUPABASE_KEY`
   - `API_BASE_URL`
   - и другие согласно `.env.example`

### Шаг 4: Настройте команду запуска

1. Перейдите в раздел "Settings"
2. В поле "Start Command" укажите: `python main.py`

### Шаг 5: Настройте вебхуки Telegram

После успешного деплоя получите публичный URL вашего приложения:
1. Перейдите в раздел "Settings"
2. Скопируйте "Domain" вашего приложения
3. Используйте этот URL для настройки вебхука в Telegram API:

```
https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/setWebhook?url={YOUR_RAILWAY_URL}/webhook
```

## Деплой на Vercel

Хотя Vercel больше подходит для фронтенд-приложений, вы можете использовать его для деплоя вебхук-эндпоинтов бота.

### Шаг 1: Создайте аккаунт на Vercel

Зарегистрируйтесь на [Vercel](https://vercel.com/) и войдите в свой аккаунт.

### Шаг 2: Импортируйте проект из GitHub

1. Нажмите на кнопку "New Project"
2. Выберите ваш репозиторий с ботом
3. Нажмите "Import"

### Шаг 3: Настройте проект

1. В разделе "Build and Output Settings" в поле "Output Directory" укажите: `.`
2. В разделе "Environment Variables" добавьте все переменные из `.env.example`

### Шаг 4: Настройте вебхуки для Telegram

После успешного деплоя:
1. Скопируйте домен вашего проекта
2. Используйте этот URL для настройки вебхука в Telegram API:

```
https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/setWebhook?url={YOUR_VERCEL_URL}/api/webhook
```

## Настройка постоянного соединения с Telegram API

Для работы бота необходимо поддерживать постоянное соединение с Telegram API. Это можно сделать двумя способами:

### 1. Использование Polling

В файле `main.py` раскомментируйте код для запуска бота в режиме поллинга:

```python
# Запуск бота в режиме поллинга
bot.polling(none_stop=True)
```

### 2. Использование Webhook

Настройте вебхук для бота, указав URL вашего развернутого приложения:

```python
# Настройка вебхука
bot.set_webhook(url=f"{WEBHOOK_URL}/webhook", 
                certificate=open('webhook_cert.pem', 'r'),
                max_connections=40)
```

## Мониторинг и логирование

Для мониторинга работы бота рекомендуется настроить логирование:

1. Убедитесь, что директория `logs` существует и доступна для записи
2. В Supabase создайте таблицу для логов:

```sql
CREATE TABLE telegram_bot_logs (
  id SERIAL PRIMARY KEY,
  timestamp TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
  level TEXT,
  message TEXT,
  metadata JSONB
);
```

3. В файле `config.py` настройте параметры логирования по необходимости