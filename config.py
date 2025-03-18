import os
from dotenv import load_dotenv
from loguru import logger
import sys

# Загружаем переменные окружения из .env файла
load_dotenv()

# Настройка логирования
logger.remove()
logger.add(
    sys.stdout,
    format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
    level="INFO"
)
logger.add(
    "logs/bot.log",
    rotation="10 MB",
    retention="1 week",
    format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}",
    level="DEBUG"
)

# Telegram Bot
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
if not TELEGRAM_BOT_TOKEN:
    logger.error("TELEGRAM_BOT_TOKEN не найден в переменных окружения")
    raise ValueError("TELEGRAM_BOT_TOKEN не найден в переменных окружения")

# Webhook Configuration
WEBHOOK_URL = os.getenv("WEBHOOK_URL", "")
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "")

# Supabase
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
if not SUPABASE_URL or not SUPABASE_KEY:
    logger.error("SUPABASE_URL или SUPABASE_KEY не найдены в переменных окружения")
    raise ValueError("SUPABASE_URL или SUPABASE_KEY не найдены в переменных окружения")

# API Endpoints
API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:3000")
TRAIN_MODEL_ENDPOINT = os.getenv("TRAIN_MODEL_ENDPOINT", "/api/bot/train-model")
GENERATE_IMAGES_ENDPOINT = os.getenv("GENERATE_IMAGES_ENDPOINT", "/api/bot/generate")
FINETUNE_WEBHOOK_ENDPOINT = os.getenv("FINETUNE_WEBHOOK_ENDPOINT", "https://n8n2.supashkola.ru/webhook/start_finetune")

# Admin
ADMIN_TELEGRAM_ID = os.getenv("ADMIN_TELEGRAM_ID")
if ADMIN_TELEGRAM_ID:
    ADMIN_TELEGRAM_ID = int(ADMIN_TELEGRAM_ID)

# Константы
MAX_PHOTOS = 4  # Максимальное количество фотографий для обучения модели
DEFAULT_NUM_IMAGES = 4  # Количество изображений для генерации по умолчанию
PHOTO_QUALITY = 95  # Качество сжатия фотографий (0-100)
MAX_PHOTO_SIZE = (1024, 1024)  # Максимальный размер фотографии (ширина, высота)
TIMEOUT = 60  # Таймаут для запросов к API (в секундах)

# Сообщения
WELCOME_MESSAGE = """
🤖 Привет! Я бот для создания AI-фотосессий с помощью Astria AI.

Что я умею:
- Обучать персональную модель на основе ваших фотографий
- Генерировать фотосессии с помощью текстовых промптов

Для начала работы отправьте команду /train, чтобы обучить вашу первую модель.
"""

HELP_MESSAGE = """
📚 Доступные команды:

/start - Начать работу с ботом
/help - Показать эту справку
/train - Обучить новую модель
/generate - Сгенерировать изображения
/models - Показать список ваших моделей
/credits - Информация о ваших кредитах

Если у вас возникли проблемы, обратитесь к @admin_username
"""

UPLOAD_PHOTOS_MESSAGE = """
📸 Пожалуйста, загрузите 4 фотографии для обучения модели.

Рекомендации:
- Фотографии должны быть хорошего качества
- На фотографиях должно быть четко видно ваше лицо
- Используйте разные ракурсы и выражения лица
- Избегайте групповых фотографий

Отправьте фотографии по одной.
"""

ENTER_PROMPT_MESSAGE = """
✍️ Введите текстовый промпт для генерации изображений.

Например:
- "элегантный портрет в роскошной обстановке"
- "профессиональная студийная фотосессия"
- "фото для глянцевого журнала"

Или просто опишите, как вы хотите выглядеть на фотографиях.
""" 