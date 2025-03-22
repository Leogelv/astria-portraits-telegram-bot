import os
import asyncio
from typing import Dict, List, Optional, Any, Union
from datetime import datetime
import aiohttp
from loguru import logger
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
)

from config import (
    TELEGRAM_BOT_TOKEN,
    ADMIN_TELEGRAM_ID,
    WEBHOOK_URL,
    WEBHOOK_SECRET
)
from database import DatabaseManager
from api_client import ApiClient
from state_manager import StateManager
from supabase_logger import SupabaseLogger
from utils.logging_utils import setup_logger

# Импорт обработчиков
from handlers.command_handlers import CommandHandler as BotCommandHandler
from handlers.message_handlers import MessageHandler as BotMessageHandler
from handlers.callback_handlers import CallbackHandler
from handlers.media_handlers import MediaHandler

# Импорт сервисов
from services.notification_service import NotificationService
from services.n8n_service import N8NService

class AstriaBot:
    """Основной класс телеграм-бота для работы с Astria AI"""

    def __init__(self):
        """Инициализация бота"""
        # Настройка логирования
        setup_logger()
        logger.info("Инициализация бота Astria AI")
        
        # Инициализация компонентов
        self.db = DatabaseManager()
        self.api = ApiClient()
        self.state_manager = StateManager()
        
        # Словарь для отслеживания медиагрупп
        self.media_groups = {}
        
        # Инициализация обработчиков
        self.command_handler = BotCommandHandler(self.state_manager, self.db, self.api)
        self.message_handler = BotMessageHandler(self.state_manager, self.db, self.api)
        self.callback_handler = CallbackHandler(self.state_manager, self.db, self.api, self.media_groups)
        self.media_handler = MediaHandler(self.state_manager, self.db, self.api, self.media_groups)
        
        # Инициализация сервисов
        self.n8n_service = N8NService()
        
        # Инициализируем application как None, позже заполним в run()
        self.application = None
        self.notification_service = None

    async def register_user(self, user_id: int, username: str, first_name: str, last_name: str) -> None:
        """Регистрация пользователя в базе данных"""
        user = await self.db.get_user(user_id)
        
        if not user:
            logger.info(f"Регистрация нового пользователя: {user_id} ({username})")
            user_data = {
                "telegram_id": user_id,
                "username": username,
                "first_name": first_name,
                "last_name": last_name,
                "credits": 0,
            }
            await self.db.create_user(user_data)
        else:
            # Обновляем данные пользователя, если они изменились
            if (
                user.get("username") != username
                or user.get("first_name") != first_name
                or user.get("last_name") != last_name
            ):
                logger.debug(f"Обновление данных пользователя: {user_id}")
                user_data = {
                    "username": username,
                    "first_name": first_name,
                    "last_name": last_name,
                    "last_active": datetime.now().isoformat(),
                }
                await self.db.update_user(user_id, user_data)

    async def start_command_wrapper(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Обертка для команды /start с регистрацией пользователя"""
        if update.effective_user:
            user_id = update.effective_user.id
            username = update.effective_user.username or ""
            first_name = update.effective_user.first_name or ""
            last_name = update.effective_user.last_name or ""
            
            # Регистрируем пользователя
            await self.register_user(user_id, username, first_name, last_name)
        
        # Передаем управление в основной обработчик команды
        await self.command_handler.start_command(update, context)

    async def error_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Обработчик ошибок"""
        logger.error(f"Ошибка при обработке обновления: {context.error}")
        
        # Отправляем уведомление администратору
        if ADMIN_TELEGRAM_ID:
            try:
                await context.bot.send_message(
                    chat_id=ADMIN_TELEGRAM_ID,
                    text=f"❌ Ошибка в боте:\n{context.error}"
                )
            except Exception as e:
                logger.error(f"Не удалось отправить уведомление администратору: {e}")
        
        # Отправляем сообщение пользователю
        if update and update.effective_user:
            try:
                await update.effective_message.reply_text(
                    "❌ Произошла ошибка при обработке вашего запроса. Пожалуйста, попробуйте позже."
                )
            except Exception as e:
                logger.error(f"Не удалось отправить сообщение об ошибке пользователю: {e}")

    def run(self) -> None:
        """Запуск бота"""
        # Создаем приложение
        application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
        
        # Сохраняем ссылку на приложение
        self.application = application
        
        # Инициализируем сервис уведомлений
        self.notification_service = NotificationService(application, self.db)
        
        # Регистрируем обработчики команд
        application.add_handler(CommandHandler("start", self.start_command_wrapper))
        application.add_handler(CommandHandler("help", self.command_handler.help_command))
        application.add_handler(CommandHandler("train", self.command_handler.train_command))
        application.add_handler(CommandHandler("generate", self.command_handler.generate_command))
        application.add_handler(CommandHandler("credits", self.command_handler.credits_command))
        application.add_handler(CommandHandler("cancel", self.command_handler.cancel_command))
        
        # Регистрируем обработчики сообщений
        # Используем один и тот же обработчик для фото, внутри будем проверять media_group_id
        application.add_handler(MessageHandler(filters.PHOTO, self.media_handler.handle_photo))
        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.message_handler.handle_text))
        
        # Регистрируем обработчик callback-запросов
        application.add_handler(CallbackQueryHandler(self.callback_handler.handle_callback))
        
        # Регистрируем обработчик ошибок
        application.add_error_handler(self.error_handler)
        
        logger.info("Зарегистрированы обработчики команд, сообщений и callback-запросов")
        
        # Проверяем, нужно ли использовать вебхук
        if WEBHOOK_URL:
            self.setup_webhook(application)
        else:
            # Запускаем бота в режиме polling
            logger.info("Запуск бота Astria AI в режиме polling")
            application.run_polling()
    
    def setup_webhook(self, application: Application) -> None:
        """Настройка вебхука для бота"""
        logger.info(f"Настройка вебхука для бота: {WEBHOOK_URL}")
        
        # Получаем порт из переменных окружения или используем порт по умолчанию
        port = int(os.environ.get("PORT", 8443))
        logger.info(f"Используемый порт: {port}")
        
        # Настраиваем вебхук
        application.run_webhook(
            listen="0.0.0.0",
            port=port,
            url_path="webhook",
            webhook_url=f"{WEBHOOK_URL}/webhook",
            secret_token=WEBHOOK_SECRET
        )
        
        logger.info("Вебхук успешно настроен")


if __name__ == "__main__":
    bot = AstriaBot()
    bot.run() 