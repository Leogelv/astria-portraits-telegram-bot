import os
import asyncio
from typing import Dict, List, Optional, Any, Union, Tuple
import random
import string
from datetime import datetime
import json
import traceback
import aiohttp

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
)
from loguru import logger
from enum import Enum, auto

from config import (
    TELEGRAM_BOT_TOKEN,
    ADMIN_TELEGRAM_ID,
    WELCOME_MESSAGE,
    HELP_MESSAGE,
    UPLOAD_PHOTOS_MESSAGE,
    ENTER_PROMPT_MESSAGE,
    MAX_PHOTOS,
    WEBHOOK_URL,
    WEBHOOK_SECRET,
    API_BASE_URL,
)
from database import DatabaseManager
from api_client import ApiClient
from state_manager import StateManager, UserState
from supabase_logger import SupabaseLogger

# Настройка логирования
os.makedirs("logs", exist_ok=True)
logger.add("logs/telegram_webhook.log", rotation="10 MB", level="DEBUG", backtrace=True, diagnose=True)

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

# Словарь для отслеживания медиагрупп
media_groups = {}

class AstriaBot:
    """Основной класс телеграм-бота для работы с Astria AI"""

    def __init__(self):
        """Инициализация бота"""
        self.db = DatabaseManager()
        self.api = ApiClient()
        self.state_manager = StateManager()
        
        # Создаем директорию для логов, если она не существует
        os.makedirs("logs", exist_ok=True)
        
        logger.info("Инициализация бота Astria AI")
        
        # Инициализируем Supabase логгер
        self.supa_logger = SupabaseLogger(API_BASE_URL)
        logger.info("Инициализирован Supabase логгер")
        
        # Словарь для отслеживания медиагрупп
        self.media_groups = {}

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

    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Обработчик команды /start"""
        if not update.effective_user:
            return
        
        user = update.effective_user
        user_id = user.id
        username = user.username or ""
        first_name = user.first_name or ""
        last_name = user.last_name or ""
        
        logger.info(f"Пользователь {user_id} ({username}) запустил бота")
        
        # Регистрируем пользователя
        await self.register_user(user_id, username, first_name, last_name)
        
        # Сбрасываем состояние пользователя
        self.state_manager.reset_state(user_id)
        
        # Создаем клавиатуру с кнопками для команд
        keyboard = [
            [
                InlineKeyboardButton("🖼️ Обучить модель", callback_data="cmd_train"),
                InlineKeyboardButton("🎨 Сгенерировать", callback_data="cmd_generate")
            ],
            [
                InlineKeyboardButton("📋 Мои модели", callback_data="cmd_models"),
                InlineKeyboardButton("💰 Мои кредиты", callback_data="cmd_credits")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        # URL для фото приветствия - используем прямую ссылку на изображение
        welcome_photo_url = "https://raw.githubusercontent.com/Leogelv/astria-portraits-telegram-bot/main/assets/welcome.png"
        
        try:
            # Отправляем фото с приветственным сообщением и кнопками
            await context.bot.send_photo(
                chat_id=user_id,
                photo=welcome_photo_url,
                caption=WELCOME_MESSAGE,
                reply_markup=reply_markup
            )
            logger.info(f"Отправка приветственного фото пользователю {user_id} успешна")
        except Exception as e:
            logger.error(f"Ошибка при отправке приветственного фото: {e}", exc_info=True)
            # Если что-то пошло не так, отправляем текстовое сообщение
            await update.message.reply_text(WELCOME_MESSAGE, reply_markup=reply_markup)

    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Обработчик команды /help"""
        if not update.effective_user:
            return
        
        user_id = update.effective_user.id
        logger.info(f"Пользователь {user_id} запросил помощь")
        
        await update.message.reply_text(HELP_MESSAGE)

    async def train_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Обработчик команды /train"""
        if not update.effective_user:
            return
        
        user_id = update.effective_user.id
        logger.info(f"Пользователь {user_id} начал обучение модели")
        
        # Устанавливаем состояние загрузки фотографий
        self.state_manager.set_state(user_id, UserState.UPLOADING_PHOTOS)
        self.state_manager.clear_data(user_id)
        
        # Создаем клавиатуру с кнопкой отмены
        keyboard = [
            [InlineKeyboardButton("❌ Отменить обучение", callback_data="cancel_training")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        # URL для фото с инструкциями - используем прямую ссылку на изображение
        instructions_photo_url = "https://raw.githubusercontent.com/Leogelv/astria-portraits-telegram-bot/main/assets/welcome.png"
        
        try:
            # Отправляем фото с инструкциями и кнопкой отмены
            await context.bot.send_photo(
                chat_id=user_id,
                photo=instructions_photo_url,
                caption=UPLOAD_PHOTOS_MESSAGE,
                reply_markup=reply_markup
            )
            logger.info(f"Отправка фото с инструкциями пользователю {user_id} успешна")
        except Exception as e:
            logger.error(f"Ошибка при отправке фото с инструкциями: {e}", exc_info=True)
            # Если что-то пошло не так, отправляем текстовое сообщение
            await update.message.reply_text(UPLOAD_PHOTOS_MESSAGE, reply_markup=reply_markup)

    async def generate_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Обработчик команды /generate"""
        if not update.effective_user:
            return
        
        user_id = update.effective_user.id
        logger.info(f"Пользователь {user_id} начал генерацию изображений")
        
        # Получаем модели пользователя
        models = await self.db.get_user_models(user_id)
        
        if not models:
            await update.message.reply_text(
                "У вас пока нет обученных моделей. Используйте команду /train, чтобы обучить новую модель."
            )
            return
        
        # Создаем клавиатуру с моделями
        keyboard = []
        for model in models:
            # Получаем детали модели
            model_details = await self.db.get_model_details(model["model_id"])
            model_name = model_details.get("name", f"Модель #{model['model_id']}") if model_details else f"Модель #{model['model_id']}"
            
            keyboard.append([
                InlineKeyboardButton(model_name, callback_data=f"model_{model['model_id']}")
            ])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        # Устанавливаем состояние выбора модели
        self.state_manager.set_state(user_id, UserState.SELECTING_MODEL)
        
        await update.message.reply_text(
            "Выберите модель для генерации изображений:",
            reply_markup=reply_markup
        )

    async def models_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Обработчик команды /models"""
        if not update.effective_user:
            return
        
        user_id = update.effective_user.id
        logger.info(f"Пользователь {user_id} запросил список моделей")
        
        # Получаем модели пользователя
        models = await self.db.get_user_models(user_id)
        
        if not models:
            await update.message.reply_text(
                "У вас пока нет обученных моделей. Используйте команду /train, чтобы обучить новую модель."
            )
            return
        
        # Формируем сообщение со списком моделей
        message = "📋 Ваши модели:\n\n"
        
        for model in models:
            # Получаем детали модели
            model_details = await self.db.get_model_details(model["model_id"])
            
            model_name = model_details.get("name", f"Модель #{model['model_id']}") if model_details else f"Модель #{model['model_id']}"
            model_status = model["status"]
            model_date = model["created_at"].split("T")[0] if isinstance(model["created_at"], str) else "Неизвестно"
            
            message += f"🔹 {model_name}\n"
            message += f"   ID: {model['model_id']}\n"
            message += f"   Статус: {model_status}\n"
            message += f"   Создана: {model_date}\n\n"
        
        await update.message.reply_text(message)

    async def credits_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Обработчик команды /credits"""
        if not update.effective_user:
            return
        
        user_id = update.effective_user.id
        logger.info(f"Пользователь {user_id} запросил информацию о кредитах")
        
        # Получаем пользователя из базы данных
        user = await self.db.get_user(user_id)
        
        if not user:
            await update.message.reply_text("Произошла ошибка при получении информации о кредитах.")
            return
        
        credits = user.get("credits", 0)
        
        await update.message.reply_text(
            f"💰 У вас {credits} кредитов.\n\n"
            f"Каждое обучение модели стоит 1 кредит.\n"
            f"Каждая генерация изображений стоит 1 кредит."
        )

    async def cancel_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Обработчик команды /cancel"""
        if not update.effective_user:
            return
        
        user_id = update.effective_user.id
        logger.info(f"Пользователь {user_id} отменил текущую операцию")
        
        # Сбрасываем состояние пользователя
        self.state_manager.reset_state(user_id)
        
        await update.message.reply_text(
            "✅ Текущая операция отменена. Что вы хотите сделать дальше?\n\n"
            "Используйте команду /train, чтобы обучить новую модель, или /generate, чтобы сгенерировать изображения."
        )

    async def handle_photo(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Обработчик фотографий"""
        if not update.effective_user or not update.message or not update.message.photo:
            return
        
        # Если есть media_group_id, передаем управление в handle_media_group
        if update.message.media_group_id:
            return await self.handle_media_group(update, context)
        
        user_id = update.effective_user.id
        state = self.state_manager.get_state(user_id)
        
        # Проверяем, что пользователь находится в состоянии загрузки фотографий
        if state != UserState.UPLOADING_PHOTOS:
            await update.message.reply_text(
                "Я не ожидаю фотографий сейчас. Используйте команду /train, чтобы начать обучение модели."
            )
            return
        
        logger.info(f"Пользователь {user_id} загрузил фотографию")
        
        # Получаем фотографию наилучшего качества
        photo = update.message.photo[-1]
        photo_file = await context.bot.get_file(photo.file_id)
        photo_bytes = await photo_file.download_as_bytearray()
        
        try:
            # Обрабатываем фотографию
            photo_data_url = await self.api.process_photo(photo_bytes)
            
            # Добавляем фотографию в список
            self.state_manager.add_to_list(user_id, "photos", photo_data_url)
            
            # Получаем текущее количество фотографий
            photos = self.state_manager.get_list(user_id, "photos")
            photos_count = len(photos)
            
            await update.message.reply_text(
                f"✅ Фотография #{photos_count} загружена.\n"
                f"Осталось загрузить: {MAX_PHOTOS - photos_count} фото."
            )
            
            # Если загружены все фотографии, переходим к вводу имени модели
            if photos_count >= MAX_PHOTOS:
                self.state_manager.set_state(user_id, UserState.ENTERING_MODEL_NAME)
                
                await update.message.reply_text(
                    "📝 Введите имя для вашей модели (например, 'Моя фотосессия'):"
                )
        except Exception as e:
            logger.error(f"Ошибка при обработке фотографии: {e}")
            await update.message.reply_text(
                "❌ Произошла ошибка при обработке фотографии. Пожалуйста, попробуйте загрузить другую фотографию."
            )

    async def handle_media_group(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Обработчик медиагруппы (группы фотографий)"""
        if not update.effective_user or not update.message or not update.message.photo:
            return
        
        if not update.message.media_group_id:
            # Это одиночное фото, не медиагруппа
            return await self.handle_photo(update, context)
        
        user = update.effective_user
        user_id = user.id
        username = user.username or ""
        media_group_id = update.message.media_group_id
        
        # Логируем получение фото из медиагруппы
        logger.info(f"Получено фото из медиагруппы {media_group_id} от пользователя {user_id} ({username})")
        
        # Регистрируем пользователя, если он не зарегистрирован
        await self.register_user(user_id, username, user.first_name or "", user.last_name or "")
        
        # Инициализируем медиагруппу в словаре, если её еще нет
        if media_group_id not in self.media_groups:
            self.media_groups[media_group_id] = {
                "user_id": user_id,
                "photos": [],
                "processed": False,
                "last_update": datetime.now().timestamp()
            }
            
            # Создаем запись о медиагруппе в базе данных
            await self.db.create_media_group(media_group_id, user_id)
            
            # Запрашиваем имя и тип модели у пользователя
            keyboard = [
                [
                    InlineKeyboardButton("Мужчина", callback_data=f"mgtype_{media_group_id}_male"),
                    InlineKeyboardButton("Женщина", callback_data=f"mgtype_{media_group_id}_female")
                ]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await update.message.reply_text(
                "Отлично! Вы отправили группу фотографий. "
                "Пожалуйста, введите название для новой модели и выберите тип:",
                reply_markup=reply_markup
            )
        
        # Проверяем, что фото от того же пользователя
        if self.media_groups[media_group_id]["user_id"] != user_id:
            logger.warning(f"Попытка добавить фото в медиагруппу {media_group_id} от другого пользователя: {user_id}")
            return
        
        # Получаем фото
        photo = update.message.photo[-1]  # Берем самое большое фото
        photo_file = await context.bot.get_file(photo.file_id)
        photo_url = photo_file.file_path
        
        # Добавляем URL фото в список
        self.media_groups[media_group_id]["photos"].append(photo_url)
        self.media_groups[media_group_id]["last_update"] = datetime.now().timestamp()
        
        # Логируем добавление фото в медиагруппу
        logger.debug(f"Добавлено фото в медиагруппу {media_group_id}: {photo_url}")
        
    async def handle_media_group_type_selection(self, update: Update, context: ContextTypes.DEFAULT_TYPE, media_group_id: str, model_type: str) -> None:
        """Обработчик выбора типа модели для медиагруппы"""
        query = update.callback_query
        user_id = query.from_user.id
        
        # Проверяем, существует ли медиагруппа и принадлежит ли она этому пользователю
        if media_group_id not in self.media_groups or self.media_groups[media_group_id]["user_id"] != user_id:
            await query.answer("Медиагруппа не найдена или принадлежит другому пользователю")
            return
        
        # Сохраняем тип модели для медиагруппы
        self.media_groups[media_group_id]["model_type"] = model_type
        
        # Просим ввести название модели
        await query.edit_message_text(
            f"Выбран тип модели: {'Мужчина' if model_type == 'male' else 'Женщина'}\n\n"
            f"Пожалуйста, отправьте название для новой модели:"
        )
        
        # Устанавливаем состояние пользователя для ожидания названия модели
        self.state_manager.set_state(user_id, UserState.ENTERING_MODEL_NAME_FOR_MEDIA_GROUP)
        self.state_manager.set_data(user_id, "media_group_id", media_group_id)
        
    async def process_media_group(self, user_id: int, media_group_id: str, model_name: str) -> None:
        """Обработка медиагруппы и отправка на фиксацию модели"""
        if media_group_id not in self.media_groups:
            logger.error(f"Медиагруппа {media_group_id} не найдена для обработки")
            return
        
        media_group = self.media_groups[media_group_id]
        if media_group["processed"]:
            logger.warning(f"Медиагруппа {media_group_id} уже обработана")
            return
        
        # Отмечаем медиагруппу как обработанную
        media_group["processed"] = True
        media_group["model_name"] = model_name
        
        # Логируем обработку медиагруппы
        logger.info(f"Обработка медиагруппы {media_group_id}: название модели '{model_name}', тип '{media_group.get('model_type', 'unknown')}', фотографий: {len(media_group['photos'])}")
        
        # Обновляем медиагруппу в базе данных
        urls = media_group["photos"]
        await self.db.update_media_group_urls(media_group_id, urls)
        
        # Отправляем медиагруппу на вебхук для фиксации модели
        response = await self.api.send_media_group_to_finetune(
            model_name=model_name,
            model_type=media_group.get("model_type", "unknown"),
            file_urls=urls,
            telegram_id=user_id
        )
        
        # Отправляем пользователю сообщение о результате
        if response["status"] in (200, 201, 202):
            # Отправляем сообщение через бота
            await self.application.bot.send_message(
                user_id,
                f"✅ Ваша медиагруппа успешно отправлена на обучение модели!\n\n"
                f"Название модели: {model_name}\n"
                f"Тип модели: {'Мужчина' if media_group.get('model_type') == 'male' else 'Женщина'}\n"
                f"Количество фотографий: {len(urls)}\n\n"
                f"Мы уведомим вас, когда модель будет готова."
            )
        else:
            error_message = response["data"].get("error", "Unknown error")
            await self.application.bot.send_message(
                user_id,
                f"❌ Произошла ошибка при отправке медиагруппы на обучение модели.\n\n"
                f"Ошибка: {error_message}\n\n"
                f"Пожалуйста, попробуйте еще раз или обратитесь к администратору."
            )

    async def handle_text(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Обработчик текстовых сообщений"""
        if not update.effective_user or not update.message:
            return
        
        user_id = update.effective_user.id
        text = update.message.text
        
        # Получаем текущее состояние пользователя
        state = self.state_manager.get_state(user_id)
        
        logger.info(f"Пользователь {user_id} отправил текст в состоянии {state}: {text}")
        
        if state == UserState.ENTERING_MODEL_NAME:
            # Пользователь вводит название модели
            if len(text) > 50:
                await update.message.reply_text("Название модели слишком длинное (максимум 50 символов). Пожалуйста, введите более короткое название.")
                return
            
            # Сохраняем название модели
            self.state_manager.set_data(user_id, "model_name", text)
            
            # Запрашиваем тип модели
            keyboard = [
                [
                    InlineKeyboardButton("Мужчина", callback_data="type_male"),
                    InlineKeyboardButton("Женщина", callback_data="type_female")
                ]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await update.message.reply_text(
                f"Название модели: {text}\n\nТеперь выберите тип модели:",
                reply_markup=reply_markup
            )
            
            # Устанавливаем состояние выбора типа модели
            self.state_manager.set_state(user_id, UserState.SELECTING_MODEL_TYPE)
        
        elif state == UserState.ENTERING_PROMPT:
            # Пользователь вводит промпт для генерации изображений
            if len(text) > 500:
                await update.message.reply_text("Промпт слишком длинный (максимум 500 символов). Пожалуйста, введите более короткий промпт.")
                return
            
            # Сохраняем промпт
            self.state_manager.set_data(user_id, "prompt", text)
            
            # Начинаем генерацию изображений
            await self.start_image_generation(update, context)
        
        elif state == UserState.ENTERING_MODEL_NAME_FOR_MEDIA_GROUP:
            # Пользователь вводит название модели для медиагруппы
            if len(text) > 50:
                await update.message.reply_text("Название модели слишком длинное (максимум 50 символов). Пожалуйста, введите более короткое название.")
                return
            
            # Получаем ID медиагруппы
            media_group_id = self.state_manager.get_data(user_id, "media_group_id")
            if not media_group_id:
                await update.message.reply_text("Произошла ошибка: ID медиагруппы не найден. Пожалуйста, попробуйте еще раз.")
                self.state_manager.reset_state(user_id)
                return
            
            # Обрабатываем медиагруппу
            await self.process_media_group(user_id, media_group_id, text)
            
            # Сбрасываем состояние пользователя
            self.state_manager.reset_state(user_id)
        
        else:
            # Пользователь отправил текст вне контекста команды
            await update.message.reply_text(
                "Я не понимаю этой команды. Пожалуйста, воспользуйтесь одной из доступных команд:\n"
                "/start - Начать работу с ботом\n"
                "/help - Получить справку\n"
                "/train - Обучить новую модель\n"
                "/generate - Сгенерировать изображения"
            )

    async def handle_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Обработчик callback-запросов"""
        query = update.callback_query
        user_id = query.from_user.id
        callback_data = query.data
        
        logger.info(f"Пользователь {user_id} отправил callback: {callback_data}")
        
        # Обрабатываем callback-данные
        if callback_data.startswith("cmd_"):
            # Обработка команд из кнопок
            command = callback_data.split("_")[1]
            
            # Отвечаем на callback-запрос
            await query.answer(f"Выполняю команду: {command}")
            logger.info(f"Обработка команды из callback: {command}")
            
            try:
                if command == "train":
                    # Создаем клавиатуру с кнопкой отмены
                    keyboard = [
                        [InlineKeyboardButton("❌ Отменить обучение", callback_data="cancel_training")]
                    ]
                    reply_markup = InlineKeyboardMarkup(keyboard)
                    
                    # URL для фото с инструкциями
                    instructions_photo_url = "https://raw.githubusercontent.com/Leogelv/astria-portraits-telegram-bot/main/assets/welcome.png"
                    
                    # Устанавливаем состояние загрузки фотографий
                    self.state_manager.set_state(user_id, UserState.UPLOADING_PHOTOS)
                    self.state_manager.clear_data(user_id)
                    
                    # Отправляем фото с инструкциями напрямую через context.bot
                    await context.bot.send_photo(
                        chat_id=user_id,
                        photo=instructions_photo_url,
                        caption=UPLOAD_PHOTOS_MESSAGE,
                        reply_markup=reply_markup
                    )
                    logger.info(f"Отправлено фото с инструкциями через callback для команды train пользователю {user_id}")
                
                elif command == "generate":
                    # Получаем модели пользователя
                    models = await self.db.get_user_models(user_id)
                    
                    if not models:
                        await context.bot.send_message(
                            chat_id=user_id,
                            text="У вас пока нет обученных моделей. Используйте команду /train, чтобы обучить новую модель."
                        )
                        return
                    
                    # Создаем клавиатуру с моделями
                    keyboard = []
                    for model in models:
                        # Получаем детали модели
                        model_details = await self.db.get_model_details(model["model_id"])
                        model_name = model_details.get("name", f"Модель #{model['model_id']}") if model_details else f"Модель #{model['model_id']}"
                        
                        keyboard.append([
                            InlineKeyboardButton(model_name, callback_data=f"model_{model['model_id']}")
                        ])
                    
                    reply_markup = InlineKeyboardMarkup(keyboard)
                    
                    # Устанавливаем состояние выбора модели
                    self.state_manager.set_state(user_id, UserState.SELECTING_MODEL)
                    
                    # Отправляем сообщение с фото и списком моделей
                    test_image_url = "https://raw.githubusercontent.com/Leogelv/astria-portraits-telegram-bot/main/assets/welcome.png"
                    
                    await context.bot.send_photo(
                        chat_id=user_id,
                        photo=test_image_url,
                        caption="Выберите модель для генерации изображений:",
                        reply_markup=reply_markup
                    )
                    logger.info(f"Отправлен список моделей через callback для команды generate пользователю {user_id}")
                
                elif command == "models":
                    # Получаем модели пользователя
                    models = await self.db.get_user_models(user_id)
                    
                    if not models:
                        await context.bot.send_message(
                            chat_id=user_id,
                            text="У вас пока нет обученных моделей. Используйте команду /train, чтобы обучить новую модель."
                        )
                        return
                    
                    # Формируем сообщение со списком моделей
                    message = "📋 Ваши модели:\n\n"
                    
                    for model in models:
                        # Получаем детали модели
                        model_details = await self.db.get_model_details(model["model_id"])
                        
                        model_name = model_details.get("name", f"Модель #{model['model_id']}") if model_details else f"Модель #{model['model_id']}"
                        model_status = model["status"]
                        model_date = model["created_at"].split("T")[0] if isinstance(model["created_at"], str) else "Неизвестно"
                        
                        message += f"🔹 {model_name}\n"
                        message += f"   ID: {model['model_id']}\n"
                        message += f"   Статус: {model_status}\n"
                        message += f"   Создана: {model_date}\n\n"
                    
                    # Отправляем сообщение с фото
                    test_image_url = "https://raw.githubusercontent.com/Leogelv/astria-portraits-telegram-bot/main/assets/welcome.png"
                    
                    await context.bot.send_photo(
                        chat_id=user_id,
                        photo=test_image_url,
                        caption=message
                    )
                    logger.info(f"Отправлен список моделей через callback для команды models пользователю {user_id}")
                
                elif command == "credits":
                    # Получаем пользователя из базы данных
                    user = await self.db.get_user(user_id)
                    
                    if not user:
                        await context.bot.send_message(
                            chat_id=user_id,
                            text="Произошла ошибка при получении информации о кредитах."
                        )
                        return
                    
                    credits = user.get("credits", 0)
                    message = f"💰 У вас {credits} кредитов.\n\n" \
                              f"Каждое обучение модели стоит 1 кредит.\n" \
                              f"Каждая генерация изображений стоит 1 кредит."
                    
                    # Отправляем сообщение с фото
                    test_image_url = "https://raw.githubusercontent.com/Leogelv/astria-portraits-telegram-bot/main/assets/welcome.png"
                    
                    await context.bot.send_photo(
                        chat_id=user_id,
                        photo=test_image_url,
                        caption=message
                    )
                    logger.info(f"Отправлена информация о кредитах через callback для команды credits пользователю {user_id}")
                
            except Exception as e:
                logger.error(f"Ошибка при обработке callback команды {command}: {e}", exc_info=True)
                await context.bot.send_message(
                    chat_id=user_id,
                    text=f"❌ Произошла ошибка при выполнении команды. Пожалуйста, попробуйте еще раз или используйте команду /start для перезапуска бота."
                )
        
        elif callback_data.startswith("model_"):
            # Выбор модели для генерации изображений
            model_id = int(callback_data.split("_")[1])
            
            # Сохраняем ID модели
            self.state_manager.set_data(user_id, "model_id", model_id)
            
            # Устанавливаем состояние ввода промпта
            self.state_manager.set_state(user_id, UserState.ENTERING_PROMPT)
            
            # Просим ввести промпт
            await query.edit_message_text(ENTER_PROMPT_MESSAGE)
        
        elif callback_data.startswith("type_"):
            # Выбор типа модели
            model_type = callback_data.split("_")[1]
            
            # Сохраняем тип модели
            self.state_manager.set_data(user_id, "model_type", model_type)
            
            # Запрашиваем подтверждение обучения модели
            model_name = self.state_manager.get_data(user_id, "model_name")
            photos = self.state_manager.get_list(user_id, "photos")
            
            if not model_name or not photos:
                await query.edit_message_text("Произошла ошибка: не найдены данные для обучения модели. Пожалуйста, начните сначала с команды /train.")
                self.state_manager.reset_state(user_id)
                return
            
            keyboard = [
                [
                    InlineKeyboardButton("Да, начать обучение", callback_data="start_training"),
                    InlineKeyboardButton("Отмена", callback_data="cancel_training")
                ]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await query.edit_message_text(
                f"Данные для обучения модели:\n\n"
                f"Название: {model_name}\n"
                f"Тип: {'Мужчина' if model_type == 'male' else 'Женщина'}\n"
                f"Количество фотографий: {len(photos)}\n\n"
                f"Начать обучение модели?",
                reply_markup=reply_markup
            )
        
        elif callback_data == "start_training":
            # Начать обучение модели
            await self.start_model_training(update, context)
        
        elif callback_data == "cancel_training":
            # Отмена обучения модели
            await query.edit_message_text("Обучение модели отменено.")
            self.state_manager.reset_state(user_id)
        
        elif callback_data.startswith("mgtype_"):
            # Выбор типа модели для медиагруппы
            parts = callback_data.split("_")
            media_group_id = parts[1]
            model_type = parts[2]
            
            await self.handle_media_group_type_selection(update, context, media_group_id, model_type)
        
        else:
            # Неизвестный callback
            logger.warning(f"Получен неизвестный callback от пользователя {user_id}: {callback_data}")
            await query.answer("Неизвестная команда")

    async def handle_webhook_update(self, update_data: Dict[str, Any]) -> None:
        """Обработка обновления от вебхука"""
        logger.debug(f"Получено обновление от вебхука: {update_data}")
        
        # Обработка обновления статуса модели
        if update_data.get("type") == "model_status_update":
            await self.handle_model_status_update(update_data)
        
        # Обработка обновления статуса промпта
        elif update_data.get("type") == "prompt_status_update":
            await self.handle_prompt_status_update(update_data)
        
        # Неизвестный тип обновления
        else:
            logger.warning(f"Получен неизвестный тип обновления: {update_data}")

    async def handle_model_status_update(self, update_data: Dict[str, Any]) -> None:
        """Обработка обновления статуса модели"""
        model_id = update_data.get("model_id")
        status = update_data.get("status")
        telegram_id = update_data.get("telegram_id")
        
        if not model_id or not status or not telegram_id:
            logger.warning(f"Неполные данные для обновления статуса модели: {update_data}")
            return
        
        logger.info(f"Обновление статуса модели {model_id} на {status} для пользователя {telegram_id}")
        
        # Логируем в Supabase
        event_type = "astria_model_training_completed" if status == "completed" else "astria_model_training_failed"
        await self.supa_logger.log_event(
            event_type=event_type,
            message=f"Статус модели {model_id} изменен на {status}",
            data=update_data,
            telegram_id=telegram_id
        )
        
        # Обновляем статус модели в базе данных
        model_data = {
            "status": status,
            "error": update_data.get("error")
        }
        await self.db.update_model(model_id, model_data)
        
        # Отправляем уведомление пользователю
        try:
            if status == "completed":
                message = f"✅ Ваша модель успешно обучена и готова к использованию!\n\nID модели: {model_id}\n\nТеперь вы можете использовать команду /generate для создания изображений."
            else:
                error_message = update_data.get("error", "Неизвестная ошибка")
                message = f"❌ К сожалению, при обучении модели произошла ошибка:\n\n{error_message}\n\nПожалуйста, попробуйте снова с другими фотографиями."
            
            await self.application.bot.send_message(chat_id=telegram_id, text=message)
            logger.info(f"Отправлено уведомление пользователю {telegram_id} о статусе модели {model_id}")
        except Exception as e:
            logger.error(f"Ошибка при отправке уведомления пользователю {telegram_id}: {e}")

    async def handle_prompt_status_update(self, update_data: Dict[str, Any]) -> None:
        """Обработка обновления статуса промпта"""
        prompt_id = update_data.get("prompt_id")
        status = update_data.get("status")
        telegram_id = update_data.get("telegram_id")
        images = update_data.get("images", [])
        
        if not prompt_id or not status or not telegram_id:
            logger.warning(f"Неполные данные для обновления статуса промпта: {update_data}")
            return
        
        logger.info(f"Обновление статуса промпта {prompt_id} на {status} для пользователя {telegram_id}")
        
        # Логируем в Supabase
        event_type = "image_generation_completed" if status == "completed" else "image_generation_failed"
        await self.supa_logger.log_event(
            event_type=event_type,
            message=f"Статус промпта {prompt_id} изменен на {status}",
            data=update_data,
            telegram_id=telegram_id
        )
        
        # Обновляем статус промпта в базе данных
        prompt_data = {
            "status": status,
            "error": update_data.get("error")
        }
        await self.db.update_prompt(prompt_id, prompt_data)
        
        # Отправляем уведомление пользователю
        try:
            if status == "completed" and images:
                # Отправляем изображения пользователю
                await self.send_generated_images(update, context, images)
                logger.info(f"Отправлены изображения пользователю {telegram_id} для промпта {prompt_id}")
            elif status == "completed" and not images:
                await self.application.bot.send_message(
                    chat_id=telegram_id, 
                    text="✅ Изображения сгенерированы, но не найдены в ответе. Пожалуйста, свяжитесь с администратором."
                )
            else:
                error_message = update_data.get("error", "Неизвестная ошибка")
                await self.application.bot.send_message(
                    chat_id=telegram_id, 
                    text=f"❌ К сожалению, при генерации изображений произошла ошибка:\n\n{error_message}\n\nПожалуйста, попробуйте снова с другим промптом."
                )
        except Exception as e:
            logger.error(f"Ошибка при отправке уведомления пользователю {telegram_id}: {e}")

    async def send_generated_images(self, update: Update, context: ContextTypes.DEFAULT_TYPE, images: List[str]) -> None:
        """Отправка сгенерированных изображений пользователю"""
        if not update.effective_user:
            return
        
        user_id = update.effective_user.id
        logger.info(f"Начало отправки сгенерированных изображений пользователю {user_id}")
        
        # Заменяем URL изображений на GitHub ссылку
        test_image_url = "https://raw.githubusercontent.com/Leogelv/astria-portraits-telegram-bot/main/assets/welcome.png"
        
        # Создаем клавиатуру с кнопками для дальнейших действий
        keyboard = [
            [
                InlineKeyboardButton("🔄 Сгенерировать еще", callback_data="cmd_generate"),
                InlineKeyboardButton("📋 Мои модели", callback_data="cmd_models")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        try:
            # Отправляем сообщение о готовности изображений
            await context.bot.send_message(
                chat_id=user_id,
                text=f"✅ Изображения успешно сгенерированы!\n"
                f"Количество изображений: {len(images)}\n\n"
                f"Отправляю ваши изображения...",
                reply_markup=reply_markup
            )
            logger.info(f"Отправлено сообщение о готовности изображений пользователю {user_id}")
        except Exception as e:
            logger.error(f"Ошибка при отправке сообщения о готовности изображений: {e}", exc_info=True)
        
        # Отправляем каждое изображение отдельным сообщением с мини-кнопками
        for i, image_url in enumerate(images, 1):
            try:
                # Создаем кнопки для каждого изображения
                img_keyboard = [
                    [
                        InlineKeyboardButton("💾 Скачать", url=test_image_url),
                        InlineKeyboardButton("🔍 Открыть", url=test_image_url)
                    ]
                ]
                img_reply_markup = InlineKeyboardMarkup(img_keyboard)
                
                logger.info(f"Попытка отправки изображения #{i} пользователю {user_id}")
                await context.bot.send_photo(
                    chat_id=user_id,
                    photo=test_image_url,  # Используем тестовое изображение
                    caption=f"✨ Изображение #{i} из {len(images)}",
                    reply_markup=img_reply_markup
                )
                logger.info(f"Изображение #{i} успешно отправлено пользователю {user_id}")
            except Exception as e:
                logger.error(f"Ошибка при отправке изображения {i}: {e}", exc_info=True)
                try:
                    await context.bot.send_message(
                        chat_id=user_id,
                        text=f"❌ Не удалось отправить изображение #{i}. URL: {image_url}"
                    )
                except Exception as send_error:
                    logger.error(f"Не удалось отправить сообщение об ошибке: {send_error}", exc_info=True)

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

    async def handle_media_group(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Обработчик медиагрупп"""
        if not update.effective_message:
            return

        media_group = update.effective_message.media_group_id
        if not media_group:
            return

        # Получаем ID всех файлов в медиагруппе
        file_ids = [media.file_id for media in update.effective_message.photo]

        # Получаем пути к файлам
        file_paths = []
        for file_id in file_ids:
            file = await context.bot.get_file(file_id)
            file_paths.append(file.file_path)

        # Формируем данные для отправки
        model_name = "example_model_name"  # Замените на реальное имя модели
        model_type = "example_model_type"  # Замените на реальный тип модели
        data = {
            "model_name": model_name,
            "model_type": model_type,
            "file_paths": file_paths
        }

        # Отправляем данные на вебхук
        async with aiohttp.ClientSession() as session:
            async with session.post('https://n8n2.supashkola.ru/webhook/start_finetune', json=data) as response:
                if response.status == 200:
                    logger.info("Данные успешно отправлены на вебхук")
                else:
                    logger.error(f"Ошибка при отправке данных на вебхук: {response.status}")

        # Логируем событие
        await self.supa_logger.create_log(LogEventType.BOT_MEDIA_GROUP_RECEIVED, data)

    def run(self) -> None:
        """Запуск бота"""
        # Создаем приложение
        application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
        
        # Сохраняем ссылку на приложение
        self.application = application
        
        # Регистрируем обработчики команд
        application.add_handler(CommandHandler("start", self.start_command))
        application.add_handler(CommandHandler("help", self.help_command))
        application.add_handler(CommandHandler("train", self.train_command))
        application.add_handler(CommandHandler("generate", self.generate_command))
        application.add_handler(CommandHandler("models", self.models_command))
        application.add_handler(CommandHandler("credits", self.credits_command))
        application.add_handler(CommandHandler("cancel", self.cancel_command))
        
        # Регистрируем обработчики сообщений
        # Используем один и тот же обработчик для фото, внутри будем проверять media_group_id
        application.add_handler(MessageHandler(filters.PHOTO, self.handle_photo))
        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_text))
        
        # Регистрируем обработчик callback-запросов
        application.add_handler(CallbackQueryHandler(self.handle_callback))
        
        # Регистрируем обработчик ошибок
        application.add_error_handler(self.error_handler)
        
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
