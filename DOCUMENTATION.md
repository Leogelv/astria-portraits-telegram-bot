# Документация Astria Portrait Telegram Bot

## 1. Общая архитектура

Telegram-бот для Astria AI представляет собой асинхронное приложение на Python, построенное на основе библиотеки python-telegram-bot. Бот поддерживает работу как в режиме long polling, так и через вебхуки.

### 1.1. Модульная структура проекта

Проект имеет модульную архитектуру, разделенную на следующие компоненты:

```
├── bot.py                   # Монолитная версия бота (устаревшая)
├── bot_modular.py           # Основной класс бота с модульной структурой
├── main.py                  # Точка входа приложения
├── database.py              # Менеджер базы данных
├── api_client.py            # Клиент для API запросов
├── state_manager.py         # Менеджер состояний пользователей
├── config.py                # Конфигурационные параметры
├── handlers/                # Обработчики различных типов сообщений
│   ├── __init__.py
│   ├── command_handlers.py  # Обработчики команд
│   ├── message_handlers.py  # Обработчики текстовых сообщений
│   ├── callback_handlers.py # Обработчики callback-запросов
│   └── media_handlers.py    # Обработчики медиа-контента
├── services/                # Сервисы для работы с внешними API
│   ├── __init__.py
│   ├── n8n_service.py       # Сервис для работы с N8N API
│   └── notification_service.py # Сервис для обработки уведомлений
└── utils/                   # Вспомогательные утилиты
    ├── __init__.py
    ├── logging_utils.py     # Утилиты для логирования
    ├── message_utils.py     # Утилиты для работы с сообщениями
    └── image_utils.py       # Утилиты для работы с изображениями
```

### 1.2. Поток данных

1. Пользователь отправляет сообщение боту в Telegram
2. Сообщение попадает в соответствующий обработчик (команда, текст, фото или callback)
3. Обработчик взаимодействует с менеджером состояний для определения контекста
4. При необходимости выполняются запросы к базе данных или внешним API
5. Результат отправляется пользователю в виде сообщения или интерактивных кнопок

## 2. Компоненты системы

### 2.1. Основной класс бота (AstriaBot)

`bot_modular.py` содержит основной класс `AstriaBot`, который координирует работу всех компонентов:

- Инициализирует все компоненты системы (логгер, база данных, API клиент, менеджер состояний)
- Регистрирует обработчики команд и сообщений
- Обрабатывает ошибки
- Настраивает вебхук (или запускает long polling)

```python
class AstriaBot:
    def __init__(self):
        # Инициализация компонентов
        self.db = DatabaseManager()
        self.api = ApiClient()
        self.state_manager = StateManager()
        self.media_groups = {}
        
        # Инициализация сервисов
        self.n8n_service = N8NService()
        
        # Инициализация обработчиков
        self.command_handler = BotCommandHandler(...)
        self.message_handler = BotMessageHandler(...)
        self.media_handler = MediaHandler(...)
        self.callback_handler = CallbackHandler(...)
```

### 2.2. Менеджер состояний (StateManager)

`state_manager.py` содержит класс `StateManager`, который управляет состояниями пользователей:

- Хранит текущее состояние каждого пользователя (IDLE, UPLOADING_PHOTOS, ENTERING_PROMPT и т.д.)
- Предоставляет методы для установки, получения и сброса состояния
- Хранит и управляет временными данными пользователей (загруженные фото, введенный текст и т.д.)
- Реализует потокобезопасный доступ через механизм блокировок

```python
class UserState(Enum):
    IDLE = auto()                  # Начальное состояние
    UPLOADING_PHOTOS = auto()      # Загрузка фотографий
    ENTERING_MODEL_NAME = auto()   # Ввод имени модели
    SELECTING_MODEL_TYPE = auto()  # Выбор типа модели
    TRAINING_MODEL = auto()        # Обучение модели
    SELECTING_MODEL = auto()       # Выбор модели для генерации
    ENTERING_PROMPT = auto()       # Ввод промпта
    GENERATING_IMAGES = auto()     # Генерация изображений
    # и другие состояния...

class StateManager:
    def __init__(self):
        self.user_states = {}  # {user_id: UserState}
        self.user_data = {}    # {user_id: {key: value}}
        self.lock = threading.RLock()
    
    def get_state(self, user_id):
        # Возвращает текущее состояние пользователя
    
    def set_state(self, user_id, state):
        # Устанавливает состояние пользователя
    
    def reset_state(self, user_id):
        # Сбрасывает состояние в IDLE
    
    def get_data(self, user_id, key=None):
        # Получает данные пользователя
    
    def set_data(self, user_id, key, value):
        # Устанавливает данные пользователя
```

### 2.3. База данных (DatabaseManager)

`database.py` содержит класс `DatabaseManager`, который взаимодействует с базой данных:

- Предоставляет методы для создания, обновления и получения данных пользователей
- Управляет информацией о моделях и промптах
- Реализует асинхронное взаимодействие с базой данных

```python
class DatabaseManager:
    async def get_user(self, telegram_id):
        # Получает информацию о пользователе
    
    async def create_user(self, user_data):
        # Создает нового пользователя
    
    async def update_user(self, telegram_id, user_data):
        # Обновляет данные пользователя
    
    async def get_user_models(self, telegram_id):
        # Получает модели пользователя
    
    async def create_model(self, model_data):
        # Создает новую модель
    
    async def update_model(self, model_id, model_data):
        # Обновляет данные модели
    
    # ...и другие методы для работы с БД
```

### 2.4. API Клиент (ApiClient)

`api_client.py` содержит класс `ApiClient`, который взаимодействует с внешними API:

- Отправляет запросы на обучение моделей
- Отправляет запросы на генерацию изображений
- Обрабатывает фотографии перед отправкой
- Реализует асинхронное взаимодействие с API

```python
class ApiClient:
    async def process_photo(self, photo_bytes):
        # Обрабатывает фотографию и возвращает data URL
    
    async def train_model(self, photos, model_name, user_id):
        # Отправляет запрос на обучение модели
    
    async def generate_images(self, model_id, prompt, user_id):
        # Отправляет запрос на генерацию изображений
```

### 2.5. Сервисы

Директория `services/` содержит сервисы для работы с внешними API:

#### 2.5.1. N8N Service

`n8n_service.py` содержит класс `N8NService`, который взаимодействует с N8N API:

- Получает список моделей пользователя
- Получает кредиты пользователя
- Отправляет запросы на обучение модели и генерацию изображений через N8N

```python
class N8NService:
    async def get_user_models(self, telegram_id):
        # Получает модели пользователя через N8N API
    
    async def get_user_credits(self, telegram_id):
        # Получает кредиты пользователя через N8N API
    
    async def start_model_training(self, data):
        # Запускает обучение модели через N8N
    
    async def generate_images(self, data):
        # Запускает генерацию изображений через N8N
```

#### 2.5.2. Notification Service

`notification_service.py` содержит класс `NotificationService`, который обрабатывает уведомления и вебхуки:

- Обрабатывает вебхуки от Telegram
- Обрабатывает уведомления о статусе обучения модели
- Обрабатывает уведомления о статусе генерации изображений
- Отправляет уведомления пользователям

```python
class NotificationService:
    async def handle_webhook_update(self, update_data):
        # Обрабатывает обновление от вебхука
    
    async def handle_model_status_update(self, update_data):
        # Обрабатывает обновление статуса модели
    
    async def handle_prompt_status_update(self, update_data):
        # Обрабатывает обновление статуса промпта
    
    async def send_generated_images(self, user_id, images):
        # Отправляет сгенерированные изображения пользователю
```

### 2.6. Обработчики

Директория `handlers/` содержит обработчики для различных типов сообщений:

#### 2.6.1. Command Handlers

`command_handlers.py` содержит класс `CommandHandlers`, который обрабатывает команды:

- `/start` - начало работы с ботом
- `/help` - справка по использованию бота
- `/train` - начать обучение новой модели
- `/generate` - сгенерировать изображения
- `/credits` - информация о кредитах пользователя
- `/cancel` - отмена текущей операции

```python
class CommandHandlers:
    async def start_command(self, update, context):
        # Обработка команды /start
    
    async def help_command(self, update, context):
        # Обработка команды /help
    
    async def train_command(self, update, context):
        # Обработка команды /train
    
    async def generate_command(self, update, context):
        # Обработка команды /generate
    
    async def credits_command(self, update, context):
        # Обработка команды /credits
    
    async def cancel_command(self, update, context):
        # Обработка команды /cancel
```

#### 2.6.2. Message Handlers

`message_handlers.py` содержит класс `MessageHandler`, который обрабатывает текстовые сообщения:

- Обработка ввода имени модели
- Обработка ввода промпта для генерации
- Обработка сообщений вне контекста команд

```python
class MessageHandler:
    async def handle_text(self, update, context):
        # Общий обработчик текстовых сообщений
    
    async def _handle_model_name_input(self, update, context, text, user_id):
        # Обработка ввода имени модели
    
    async def _handle_prompt_input(self, update, context, text, user_id):
        # Обработка ввода промпта
    
    async def _handle_unknown_text(self, update, context, user_id):
        # Обработка неизвестного текста
```

#### 2.6.3. Callback Handlers

`callback_handlers.py` содержит класс `CallbackHandler`, который обрабатывает callback-запросы от кнопок:

- Обработка выбора модели
- Обработка выбора типа модели
- Обработка кнопок навигации
- Обработка кнопок действий (запуск обучения, генерация, отмена)

```python
class CallbackHandler:
    async def handle_callback(self, update, context):
        # Общий обработчик callback-запросов
    
    async def _handle_command_callback(self, update, context, query, user_id, callback_data):
        # Обработка callback-команд (cmd_*)
    
    async def _handle_model_selection(self, update, context, query, user_id, callback_data):
        # Обработка выбора модели
    
    async def _handle_model_type_selection(self, update, context, query, user_id, callback_data):
        # Обработка выбора типа модели
    
    async def _handle_start_generation(self, update, context, query, user_id):
        # Обработка запуска генерации
    
    # ...и другие методы для обработки callback
```

#### 2.6.4. Media Handlers

`media_handlers.py` содержит класс `MediaHandlers`, который обрабатывает фотографии и медиа-группы:

- Обработка одиночных фотографий
- Обработка медиа-групп (альбомов)
- Управление загруженными фотографиями

```python
class MediaHandlers:
    async def handle_photo(self, update, context):
        # Обработка фотографий
    
    async def handle_media_group(self, update, context):
        # Обработка медиа-групп
```

### 2.7. Утилиты

Директория `utils/` содержит вспомогательные утилиты:

#### 2.7.1. Logging Utils

`logging_utils.py` содержит утилиты для логирования:

- Настройка логгера
- Константы для типов событий логирования

```python
def setup_logger():
    # Настройка логирования
    
class LogEventType:
    BOT_MESSAGE_RECEIVED = 'bot_message_received'
    BOT_COMMAND_PROCESSED = 'bot_command_processed'
    # ...и другие типы событий
```

#### 2.7.2. Message Utils

`message_utils.py` содержит утилиты для работы с сообщениями:

- Создание клавиатур и кнопок
- Отправка и редактирование сообщений
- Удаление сообщений

```python
def create_reply_markup(buttons):
    # Создает клавиатуру из кнопок
    
async def send_or_edit_message(update, context, text, reply_markup=None, edit_message_id=None):
    # Отправляет новое сообщение или редактирует существующее
    
async def delete_message(context, chat_id, message_id):
    # Удаляет сообщение
```

#### 2.7.3. Image Utils

`image_utils.py` содержит утилиты для работы с изображениями:

- Преобразование изображений в data URL
- Преобразование data URL в изображения
- Создание батчей фотографий

```python
def image_to_data_url(image_bytes):
    # Преобразует изображение в data URL
    
def data_url_to_image(data_url):
    # Преобразует data URL в изображение
    
def create_photo_batch(photo_data_urls, batch_size=4):
    # Создает батчи фотографий
```

## 3. Основные процессы

### 3.1. Регистрация пользователя

Процесс регистрации пользователя реализован в методе `register_user` класса `AstriaBot`:

1. Пользователь отправляет команду `/start`
2. Бот проверяет наличие пользователя в базе данных по `telegram_id`
3. Если пользователь не найден, бот создает новую запись в базе данных
4. Бот обновляет данные пользователя, если они изменились
5. Бот приветствует пользователя и отображает основное меню

### 3.2. Обучение модели

Процесс обучения модели:

1. Пользователь отправляет команду `/train` (обрабатывается в `CommandHandlers.train_command`)
2. Бот запрашивает имя модели (устанавливает состояние `ENTERING_MODEL_NAME`)
3. Пользователь вводит имя модели (обрабатывается в `MessageHandler._handle_model_name_input`)
4. Бот запрашивает тип модели (устанавливает состояние `SELECTING_MODEL_TYPE`)
5. Пользователь выбирает тип модели (обрабатывается в `CallbackHandler._handle_model_type_selection`)
6. Бот просит загрузить фотографии (устанавливает состояние `UPLOADING_PHOTOS`)
7. Пользователь загружает фотографии (обрабатывается в `MediaHandlers.handle_photo` или `MediaHandlers.handle_media_group`)
8. Бот предлагает начать обучение
9. Пользователь подтверждает начало обучения (обрабатывается в `CallbackHandler._handle_start_training`)
10. Бот отправляет запрос на обучение модели через `N8NService.start_model_training`
11. Бот создает запись о модели в базе данных
12. Бот уведомляет пользователя о начале обучения
13. После завершения обучения `NotificationService.handle_model_status_update` получает уведомление о статусе
14. Бот уведомляет пользователя о завершении обучения

### 3.3. Генерация изображений

Процесс генерации изображений:

1. Пользователь отправляет команду `/generate` (обрабатывается в `CommandHandlers.generate_command`)
2. Бот запрашивает выбор модели (устанавливает состояние `SELECTING_MODEL`)
3. Пользователь выбирает модель (обрабатывается в `CallbackHandler._handle_model_selection`)
4. Бот запрашивает ввод промпта (устанавливает состояние `ENTERING_PROMPT`)
5. Пользователь вводит промпт (обрабатывается в `MessageHandler._handle_prompt_input`)
6. Бот предлагает запустить генерацию (устанавливает состояние `GENERATING_IMAGES`)
7. Пользователь подтверждает запуск генерации (обрабатывается в `CallbackHandler._handle_start_generation`)
8. Бот отправляет запрос на генерацию изображений через `N8NService.generate_images`
9. Бот создает запись о промпте в базе данных
10. Бот уведомляет пользователя о начале генерации
11. После завершения генерации `NotificationService.handle_prompt_status_update` получает уведомление о статусе
12. Бот отправляет сгенерированные изображения пользователю через `NotificationService.send_generated_images`

### 3.4. Управление кредитами

Процесс управления кредитами:

1. Пользователь отправляет команду `/credits` (обрабатывается в `CommandHandlers.credits_command`)
2. Бот запрашивает информацию о кредитах пользователя через `N8NService.get_user_credits`
3. Бот отображает информацию о кредитах пользователя
4. При обучении модели или генерации изображений бот проверяет наличие достаточного количества кредитов
5. При успешном обучении модели или генерации изображений бот списывает кредиты

## 4. Структура базы данных

### 4.1. Таблица `telegram_users`

Хранит информацию о пользователях Telegram:

```sql
CREATE TABLE IF NOT EXISTS telegram_users (
  id SERIAL PRIMARY KEY,
  telegram_id BIGINT UNIQUE NOT NULL,
  username TEXT,
  first_name TEXT,
  last_name TEXT,
  created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
  last_active TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
  status TEXT DEFAULT 'active',
  credits INTEGER DEFAULT 0
);
```

### 4.2. Таблица `telegram_models`

Хранит информацию о моделях пользователей:

```sql
CREATE TABLE IF NOT EXISTS telegram_models (
  id SERIAL PRIMARY KEY,
  telegram_user_id BIGINT REFERENCES telegram_users(telegram_id),
  name TEXT NOT NULL,
  model_id TEXT NOT NULL,
  model_type TEXT NOT NULL,
  status TEXT DEFAULT 'training',
  created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
  updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
  error TEXT
);
```

### 4.3. Таблица `telegram_prompts`

Хранит информацию о промптах пользователей:

```sql
CREATE TABLE IF NOT EXISTS telegram_prompts (
  id SERIAL PRIMARY KEY,
  telegram_user_id BIGINT REFERENCES telegram_users(telegram_id),
  model_id TEXT NOT NULL,
  prompt TEXT NOT NULL,
  prompt_id TEXT,
  status TEXT DEFAULT 'processing',
  created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
  updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
  images JSONB,
  error TEXT
);
```

## 5. Настройка и конфигурация

### 5.1. Переменные окружения

Основные переменные окружения:

- `TELEGRAM_BOT_TOKEN` - токен Telegram бота
- `DATABASE_URL` - URL базы данных
- `WEBHOOK_URL` - URL вебхука
- `WEBHOOK_SECRET` - секретный токен для вебхука
- `API_BASE_URL` - базовый URL для API запросов
- `ADMIN_TELEGRAM_ID` - ID администратора для уведомлений об ошибках

### 5.2. Настройка вебхука

Настройка вебхука реализована в методе `setup_webhook` класса `AstriaBot`:

```python
def setup_webhook(self, application):
    # Настройка вебхука для бота
    application.run_webhook(
        listen="0.0.0.0",
        port=port,
        url_path="webhook",
        webhook_url=f"{WEBHOOK_URL}/webhook",
        secret_token=WEBHOOK_SECRET
    )
```

## 6. Дополнительные функции

### 6.1. Обработка ошибок

Обработка ошибок реализована в методе `error_handler` класса `AstriaBot`:

```python
async def error_handler(self, update, context):
    # Логирование ошибки
    logger.error(f"Ошибка при обработке обновления: {context.error}")
    
    # Уведомление администратора
    if ADMIN_TELEGRAM_ID:
        await context.bot.send_message(
            chat_id=ADMIN_TELEGRAM_ID,
            text=f"❌ Ошибка в боте:\n{context.error}"
        )
    
    # Уведомление пользователя
    if update and update.effective_user:
        await update.effective_message.reply_text(
            "❌ Произошла ошибка при обработке вашего запроса. Пожалуйста, попробуйте позже."
        )
```

### 6.2. Логирование

Логирование реализовано с использованием библиотеки loguru:

```python
from loguru import logger

def setup_logger():
    # Настройка логирования
    os.makedirs("logs", exist_ok=True)
    
    # Настройка логирования
    logger.add(
        "logs/telegram_webhook.log", 
        rotation="10 MB", 
        level="DEBUG", 
        backtrace=True, 
        diagnose=True
    )
```

## 7. Развертывание и масштабирование

### 7.1. Запуск бота

Запуск бота реализован в файле `main.py`:

```python
from bot_modular import AstriaBot

def main():
    # Создаем и запускаем бота
    bot = AstriaBot()
    bot.run()

if __name__ == "__main__":
    main()
```

### 7.2. Развертывание на Railway

Бот развернут на платформе Railway, которая обеспечивает автоматическое масштабирование и мониторинг:

1. Railway отслеживает изменения в репозитории GitHub
2. При коммите в ветку `main` Railway автоматически запускает процесс деплоя
3. Railway запускает бота и настраивает вебхук
4. Railway обеспечивает мониторинг и логирование

## 8. Интеграция с N8N

Бот интегрирован с платформой N8N для обработки запросов на обучение моделей и генерацию изображений:

1. Когда пользователь запрашивает обучение модели, бот отправляет запрос на вебхук N8N
2. N8N запускает рабочий процесс обучения модели
3. После завершения обучения N8N отправляет уведомление на вебхук бота
4. Бот получает уведомление и информирует пользователя

Аналогично для генерации изображений:

1. Когда пользователь запрашивает генерацию изображений, бот отправляет запрос на вебхук N8N
2. N8N запускает рабочий процесс генерации изображений
3. После завершения генерации N8N отправляет уведомление на вебхук бота
4. Бот получает уведомление и отправляет изображения пользователю

## 9. Заключение

Telegram-бот для Astria AI построен с использованием модульной архитектуры, что обеспечивает:

- Легкость расширения функциональности
- Простоту поддержки кода
- Четкое разделение ответственности между компонентами
- Возможность повторного использования кода

Бот поддерживает полный цикл взаимодействия с пользователем: от регистрации и обучения моделей до генерации изображений и управления кредитами. 