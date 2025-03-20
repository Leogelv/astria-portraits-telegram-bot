#!/usr/bin/env python3
"""
Основной файл для запуска телеграм-бота Astria AI
"""

import os
import logging
import sys
import json
from loguru import logger

# Настройка логирования
logger.remove()  # Удаляем стандартный обработчик
logger.add(sys.stderr, format="{time} | {level:<8} | {module}:{function}:{line} - {message}")
logger.add("logs/bot.log", rotation="10 MB", retention="7 days", level="DEBUG")

# Добавляем путь к проекту в PATH
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

def main():
    """Основная функция для запуска бота"""
    # Создаем директорию для логов, если она не существует
    os.makedirs("logs", exist_ok=True)
    
    logger.info("Запуск телеграм-бота Astria AI")
    
    try:
        from bot import AstriaBot
        
        # ВАЖНО: Добавляем обработчик входящих вебхук-запросов перед запуском бота
        # Это поможет понять, какие типы обновлений приходят (и приходят ли колбэки)
        
        # Класс для перехвата и логирования обработки вебхуков
        class DebugBot(AstriaBot):
            async def handle_webhook_update(self, update_data):
                logger.debug(f"DEBUG: Получен вебхук: {json.dumps(update_data, indent=2)}")
                # Затем вызываем оригинальный метод
                await super().handle_webhook_update(update_data)
            
            def setup_webhook(self, application):
                logger.debug("DEBUG: Настраиваю вебхук с обработкой колбэков")
                # Переопределяем метод application.process_update для логирования
                original_process_update = application.process_update
                
                async def logged_process_update(update, *args, **kwargs):
                    logger.debug(f"DEBUG: Обрабатываю обновление: {update}")
                    if hasattr(update, 'callback_query') and update.callback_query:
                        logger.debug(f"DEBUG: CALLBACK QUERY ОБНАРУЖЕН: {update.callback_query.data}")
                    return await original_process_update(update, *args, **kwargs)
                
                application.process_update = logged_process_update
                super().setup_webhook(application)
        
        # Используем наш отладочный бот
        bot = DebugBot()
        bot.run()
    except KeyboardInterrupt:
        logger.info("Бот остановлен пользователем")
    except Exception as e:
        logger.error(f"Ошибка при запуске бота: {e}")
        logger.exception(e)
    finally:
        logger.info("Завершение работы бота")

if __name__ == "__main__":
    main()
