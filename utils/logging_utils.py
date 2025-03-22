import os
from loguru import logger
from enum import Enum, auto

# Константы для типов событий логирования
class LogEventType:
    BOT_MESSAGE_RECEIVED = 'bot_message_received'
    BOT_COMMAND_PROCESSED = 'bot_command_processed'
    BOT_CALLBACK_PROCESSED = 'bot_callback_processed'
    BOT_PHOTO_RECEIVED = 'bot_photo_received'
    BOT_MEDIA_GROUP_RECEIVED = 'bot_media_group_received'
    BOT_ERROR = 'bot_error'
    
    ASTRIA_MODEL_TRAINING_STARTED = 'astria_model_training_started'
    ASTRIA_MODEL_TRAINING_COMPLETED = 'astria_model_training_completed'
    ASTRIA_MODEL_TRAINING_FAILED = 'astria_model_training_failed'
    
    IMAGE_GENERATION_STARTED = 'image_generation_started'
    IMAGE_GENERATION_COMPLETED = 'image_generation_completed'
    IMAGE_GENERATION_FAILED = 'image_generation_failed'

def setup_logger():
    """Настройка логирования"""
    # Создаем директорию для логов, если она не существует
    os.makedirs("logs", exist_ok=True)
    
    # Настройка логирования
    logger.add(
        "logs/telegram_webhook.log", 
        rotation="10 MB", 
        level="DEBUG", 
        backtrace=True, 
        diagnose=True
    )
    
    logger.info("Настройка логирования завершена")
    
    return logger
