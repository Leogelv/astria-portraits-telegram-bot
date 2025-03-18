# Telegram Bot для Astria AI

Телеграм-бот для создания AI-фотосессий с использованием Astria API.

## Возможности

- Обучение персональных моделей на основе фотографий пользователя
- Генерация фотосессий с помощью текстовых промптов
- Управление моделями и промптами
- Интеграция с Supabase для хранения данных

## Установка

1. Клонируйте репозиторий:
```bash
git clone https://github.com/yourusername/astria-telegram-bot.git
cd astria-telegram-bot
```

2. Создайте виртуальное окружение и установите зависимости:
```bash
python -m venv venv
source venv/bin/activate  # На Windows: venv\Scripts\activate
pip install -r requirements.txt
```

3. Создайте файл `.env` на основе `.env.example` и заполните его:
```bash
cp .env.example .env
# Отредактируйте файл .env, добавив необходимые токены и URL
```

## Настройка

### Telegram Bot Token

1. Создайте нового бота через [@BotFather](https://t.me/BotFather)
2. Получите токен бота и добавьте его в файл `.env`

### Supabase

1. Создайте проект в [Supabase](https://supabase.com/)
2. Создайте таблицы в базе данных:
   - `telegram_users`
   - `telegram_models`
   - `telegram_prompts`
3. Добавьте URL и ключ Supabase в файл `.env`

### API Endpoints

1. Укажите базовый URL вашего API в файле `.env`
2. Убедитесь, что эндпоинты для обучения модели и генерации изображений доступны

## Запуск

```bash
python main.py
```

## Команды бота

- `/start` - Начало работы с ботом
- `/help` - Справка по использованию бота
- `/train` - Обучение новой модели
- `/generate` - Генерация изображений
- `/models` - Список моделей пользователя
- `/credits` - Информация о кредитах пользователя
- `/cancel` - Отмена текущей операции

## Структура проекта

- `main.py` - Основной файл для запуска бота
- `bot.py` - Основной класс бота с обработчиками команд
- `config.py` - Конфигурация и константы
- `database.py` - Класс для работы с базой данных Supabase
- `api_client.py` - Класс для работы с API эндпоинтами
- `state_manager.py` - Класс для управления состоянием пользователя

## Лицензия

MIT 