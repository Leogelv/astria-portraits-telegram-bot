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

# URL изображений
WELCOME_IMAGE_URL = "https://i.ibb.co/prh3n5nK/file-74.jpg"
INSTRUCTIONS_IMAGE_URL = "https://i.ibb.co/prh3n5nK/file-74.jpg"
PROCESSING_IMAGE_URL = "https://i.ibb.co/prh3n5nK/file-74.jpg"

# Константы
MAX_PHOTOS = 4  # Максимальное количество фотографий для обучения модели
DEFAULT_NUM_IMAGES = 4  # Количество изображений для генерации по умолчанию
PHOTO_QUALITY = 95  # Качество сжатия фотографий (0-100)
MAX_PHOTO_SIZE = (1024, 1024)  # Максимальный размер фотографии (ширина, высота)
TIMEOUT = 60  # Таймаут для запросов к API (в секундах)

# Сообщения
WELCOME_MESSAGE = """
🤖 Привет! Я ИИ-душка для создания твоих улетных чесслово AI-фотосессий! Меня делали с заботой о качестве, так что... Когда увидишь свой шедевр, ты сможешь оживить его в VIDEO!

Как использовать:
1. Обучи нейронку (на самом деле мы я сам, ты мне просто пол, название и фотки отправь)

2 Генерируй фотосессии с помощью текстовых промптов, мы все переведем на англ и сделаем красиво

3. Смотри на результат, если нравится, то жми на кнопку "Оживи в видео" и получай свой шедевр! (soon)
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
📸 Пожалуйста, загрузи 4-10 фотографиq для обучения модели.

Рекомендации:
- Фотографии хорошего качества
- На фотографиях должно быть четко видно твой светлый лик
- Используй разные ракурсы и выражения лица
- Избегай групповых фотографий
- избегай наушников, часов, очков и прочей Иийни. 


Отправь фотографии одним сообщением.
"""

# Пресеты для генерации
GENERATION_PRESETS = {
    "Бизнес-портфолио": "professional business portrait in luxury office, corporate style, confident pose, modern lighting, high-end camera",
    "Путешественник": "adventurous travel photography, natural outdoor lighting, candid moments, scenic locations, lifestyle photography",
    "Творческий": "artistic portrait in studio, creative lighting, dramatic shadows, fashion magazine style, editorial photography",
    "Спортивный": "dynamic sports photography, action shots, athletic pose, outdoor environment, natural lighting, motion capture"
}

ENTER_PROMPT_MESSAGE = """
✍️ Введите текстовый промпт для генерации вашей AI-фотосессии.

🎯 Чем точнее описание, тем лучше результат! Вот несколько подсказок:

1. Опишите стиль фотосессии:
   - Деловой/профессиональный
   - Casual/повседневный 
   - Творческий/артистичный
   - Спортивный/активный

2. Добавьте детали окружения:
   - Место (студия, природа, город)
   - Освещение (естественное, студийное)
   - Время суток (день, закат, ночь)

3. Укажите настроение:
   - Уверенное/деловое
   - Расслабленное/casual
   - Драматичное/эмоциональное
   - Энергичное/динамичное

💡 Примеры готовых пресетов:
- Бизнес: "Профессиональный деловой портрет в современном офисе"
- Путешествия: "Атмосферные фото на фоне живописных пейзажей"
- Творчество: "Артистичный портрет в студии с креативным освещением"
- Спорт: "Динамичные кадры в движении на природе"

✨ Или создайте свой уникальный стиль, описав желаемый результат!
"""