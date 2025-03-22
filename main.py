#!/usr/bin/env python3
"""
Основной файл для запуска телеграм-бота Astria AI
"""

import os
import logging
import asyncio
from loguru import logger
from telegram import Update
from telegram.ext import Application
from bot_modular import AstriaBot

def main():
    """Точка входа в приложение"""
    logger.info("Запуск Astria Portraits Telegram Bot")
    
    # Создаем и запускаем бота
    bot = AstriaBot()
    bot.run()
    
    logger.info("Бот запущен")

if __name__ == "__main__":
    main()
