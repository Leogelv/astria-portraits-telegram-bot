#!/usr/bin/env python3
"""
Основной файл для запуска телеграм-бота Astria AI
"""

import os
from loguru import logger
from bot import AstriaBot
from healthcheck import run_healthcheck_in_thread

def main():
    """Основная функция для запуска бота"""
    # Создаем директорию для логов, если она не существует
    os.makedirs("logs", exist_ok=True)
    
    logger.info("Запуск телеграм-бота Astria AI")
    
    # Запускаем healthcheck сервер в отдельном потоке
    healthcheck_thread = run_healthcheck_in_thread()
    logger.info("Healthcheck сервер запущен в отдельном потоке")
    
    try:
        # Создаем и запускаем бота
        bot = AstriaBot()
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
