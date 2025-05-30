import os
import logging
from typing import Dict, List, Optional, Any, Union, Tuple
from datetime import datetime
import json

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from loguru import logger
import aiohttp
import random
import string

from config import (
    WELCOME_MESSAGE,
    HELP_MESSAGE,
    UPLOAD_PHOTOS_MESSAGE,
    ENTER_PROMPT_MESSAGE,
    MAX_PHOTOS,
    WELCOME_IMAGE_URL,
    INSTRUCTIONS_IMAGE_URL,
)
from state_manager import UserState
from database import DatabaseManager
from utils.message_utils import delete_message, create_main_keyboard

# Инициализация логгера
logger = logging.getLogger(__name__)

class CommandHandlers:
    """Обработчики команд бота"""
    
    def __init__(self, db: DatabaseManager, state_manager, media_handlers=None):
        """Инициализация обработчиков команд"""
        self.db = db
        self.state_manager = state_manager
        self.media_handlers = media_handlers
        
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
                "credits": 210,  # Добавляем начальные 210 кредитов
            }
            await self.db.create_user(user_data)
            logger.info(f"Пользователю {user_id} начислено 210 стартовых кредитов")
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
        if not update.effective_user or not update.effective_chat:
            logger.error("Не удалось получить информацию о пользователе или чате")
            return
        
        user_id = update.effective_user.id
        chat_id = update.effective_chat.id  # Используем ID чата, а не пользователя
        username = update.effective_user.username or ""
        first_name = update.effective_user.first_name or ""
        last_name = update.effective_user.last_name or ""
        
        # Сбрасываем состояние пользователя
        self.state_manager.reset_state(user_id)
        
        # Регистрируем пользователя
        await self.register_user(user_id, username, first_name, last_name)
        
        # Проверяем, есть ли у пользователя модели (для формирования кнопок)
        has_models = False
        try:
            data = {"telegram_id": user_id}
            api_url = 'https://n8n2.supashkola.ru/webhook/my_models'
            logger.info(f"Отправляю API запрос на проверку моделей: URL={api_url}, данные={data}")
            
            async with aiohttp.ClientSession() as session:
                async with session.post(api_url, json=data) as response:
                    response_status = response.status
                    response_text = await response.text()
                    response_headers = dict(response.headers)
                    
                    logger.info(f"Получен ответ API: статус={response_status}, заголовки={response_headers}")
                    logger.info(f"Тело ответа API: {response_text}")
                    
                    if response_status == 200:
                        try:
                            # Проверяем формат ответа
                            if response_text.strip().startswith('['):
                                models = json.loads(response_text)
                                has_models = len(models) > 0
                                logger.info(f"Проверка моделей для пользователя {user_id}: найдено {len(models)} моделей")
                            else:
                                logger.warning(f"Ответ API не является массивом: {response_text}")
                                has_models = False
                        except json.JSONDecodeError as json_err:
                            logger.error(f"Ошибка декодирования JSON при проверке моделей: {json_err}. Ответ: {response_text}")
                            has_models = False
                    else:
                        logger.error(f"Ошибка при получении моделей через API: статус={response_status}, ответ={response_text}")
        except Exception as e:
            logger.error(f"Исключение при проверке моделей через API: {e}", exc_info=True)
        
        # Создаем основную клавиатуру
        keyboard = []
        
        # Кнопка создания новой модели показывается, только если у пользователя нет моделей
        if not has_models:
            keyboard.append([InlineKeyboardButton("🖼️ Начать тут", callback_data="cmd_train")])
        
        # Кнопка генерации всегда видна
        keyboard.append([InlineKeyboardButton("🎨 Сгенерировать", callback_data="cmd_generate")])
        
        # Добавляем кнопку создания видео, если у пользователя есть модели
        if has_models:
            keyboard.append([InlineKeyboardButton("🎬 Создать видео", callback_data="cmd_video")])
            
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        # Отправляем welcome сообщение с фото
        try:
            # Сохраняем chat_id в state_manager для будущего использования
            self.state_manager.set_data(user_id, "chat_id", chat_id)
            logger.info(f"Сохранен chat_id: {chat_id} для пользователя {user_id}")
            
            await context.bot.send_photo(
                chat_id=chat_id,  # Используем chat_id
                photo=WELCOME_IMAGE_URL,
                caption=WELCOME_MESSAGE,
                reply_markup=reply_markup
            )
            logger.info(f"Отправлено welcome сообщение пользователю {user_id} в чат {chat_id}")
        except Exception as e:
            logger.error(f"Ошибка при отправке welcome сообщения: {e}", exc_info=True)
            # Если не удалось отправить фото, отправляем текстовое сообщение
            try:
                await update.message.reply_text(
                    text=WELCOME_MESSAGE,
                    reply_markup=reply_markup
                )
                logger.info(f"Отправлено текстовое welcome сообщение пользователю {user_id}")
            except Exception as text_err:
                logger.error(f"Не удалось отправить даже текстовое сообщение: {text_err}", exc_info=True)
        
        # Удаляем сообщение пользователя для чистоты чата
        if update.message:
            try:
                await update.message.delete()
                logger.info(f"Удалено сообщение команды /start от пользователя {user_id}")
            except Exception as e:
                logger.error(f"Не удалось удалить сообщение пользователя: {e}", exc_info=True)

    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Обработчик команды /help"""
        if not update.effective_user:
            return
        
        user_id = update.effective_user.id
        logger.info(f"Пользователь {user_id} запросил справку")
        
        await update.message.reply_text(HELP_MESSAGE)
        
        # Удаляем сообщение пользователя для чистоты чата
        if update.message:
            try:
                await update.message.delete()
                logger.info(f"Удалено сообщение команды /help от пользователя {user_id}")
            except Exception as e:
                logger.error(f"Не удалось удалить сообщение пользователя: {e}", exc_info=True)

    async def train_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Обработчик команды /train"""
        if not update.effective_user or not update.effective_chat:
            logger.error("Не удалось получить информацию о пользователе или чате")
            return
        
        user_id = update.effective_user.id
        chat_id = update.effective_chat.id
        
        # Сохраняем chat_id в state_manager для последующего использования
        self.state_manager.set_data(user_id, "chat_id", chat_id)
        logger.info(f"Сохранен chat_id: {chat_id} для пользователя {user_id}")
        
        logger.info(f"Пользователь {user_id} запустил команду /train")
        
        # Создаем клавиатуру с кнопкой отмены
        keyboard = [
            [InlineKeyboardButton("❌ Отменить обучение", callback_data="cancel_training")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        # Устанавливаем состояние ввода имени модели
        self.state_manager.set_state(user_id, UserState.ENTERING_MODEL_NAME)
        self.state_manager.clear_data(user_id, preserve_keys=["chat_id"]) # Сохраняем chat_id при очистке данных
        logger.info(f"Установлено состояние ENTERING_MODEL_NAME для пользователя {user_id}")
        
        # Отправляем сообщение с фото для ввода имени модели
        try:
            sent_message = await context.bot.send_photo(
                chat_id=chat_id,  # Используем chat_id
                photo=WELCOME_IMAGE_URL,
                caption="📝 Введите имя для вашей модели (например, 'Моя фотосессия'):",
                reply_markup=reply_markup
            )
            # Сохраняем ID сообщения для последующего редактирования
            self.state_manager.set_data(user_id, "base_message_id", sent_message.message_id)
            logger.info(f"Отправлен запрос имени модели пользователю {user_id}, ID сообщения: {sent_message.message_id}")
        except Exception as e:
            logger.error(f"Ошибка при отправке запроса имени модели: {e}", exc_info=True)
            # В случае ошибки отправляем простое текстовое сообщение
            try:
                sent_message = await context.bot.send_message(
                    chat_id=chat_id,  # Используем chat_id
                    text="📝 Введите имя для вашей модели (например, 'Моя фотосессия'):",
                    reply_markup=reply_markup
                )
                # Сохраняем ID сообщения для последующего редактирования
                self.state_manager.set_data(user_id, "base_message_id", sent_message.message_id)
                logger.info(f"Отправлен текстовый запрос имени модели пользователю {user_id}, ID сообщения: {sent_message.message_id}")
            except Exception as text_send_error:
                logger.error(f"Не удалось отправить даже текстовое сообщение: {text_send_error}", exc_info=True)
                # Если не удалось отправить даже текстовое сообщение, сбрасываем состояние
                self.state_manager.reset_state(user_id)
                return
        
        # Удаляем сообщение пользователя для чистоты чата
        if update.message:
            try:
                await update.message.delete()
                logger.info(f"Удалено сообщение команды /train от пользователя {user_id}")
            except Exception as e:
                logger.error(f"Не удалось удалить сообщение пользователя: {e}", exc_info=True)

    async def generate_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Обработчик команды /generate"""
        if not update.effective_user:
            return
        
        user_id = update.effective_user.id
        logger.info(f"Пользователь {user_id} запустил команду /generate")
        
        # Получаем модели пользователя через API запрос
        try:
            data = {"telegram_id": user_id}
            api_url = 'https://n8n2.supashkola.ru/webhook/my_models'
            logger.info(f"Отправляю API запрос на получение моделей: URL={api_url}, данные={data}")
            
            async with aiohttp.ClientSession() as session:
                async with session.post(api_url, json=data) as response:
                    response_status = response.status
                    response_text = await response.text()
                    response_headers = dict(response.headers)
                    
                    logger.info(f"Получен ответ API: статус={response_status}, заголовки={response_headers}")
                    logger.info(f"Тело ответа API: {response_text}")
                    
                    if response_status == 200:
                        try:
                            # Проверяем, является ли ответ строкой JSON
                            if response_text.strip().startswith('[') and response_text.strip().endswith(']'):
                                models = json.loads(response_text)
                                logger.info(f"Успешно получены модели пользователя {user_id} через API: {len(models)} моделей")
                            else:
                                logger.error(f"Ответ API не является JSON массивом: {response_text}")
                                models = []
                        except json.JSONDecodeError as json_err:
                            logger.error(f"Ошибка декодирования JSON: {json_err}. Ответ: {response_text}")
                            models = []
                    else:
                        logger.error(f"Ошибка при получении моделей через API: статус={response_status}, ответ={response_text}")
                        models = []
        except Exception as e:
            logger.error(f"Исключение при получении моделей через API: {e}", exc_info=True)
            models = []
        
        if not models:
            await update.message.reply_text(
                "У вас пока нет обученных моделей. Используйте команду /train, чтобы обучить новую модель."
            )
            # Удаляем сообщение пользователя для чистоты чата
            if update.message:
                try:
                    await update.message.delete()
                    logger.info(f"Удалено сообщение команды /generate от пользователя {user_id}")
                except Exception as e:
                    logger.error(f"Не удалось удалить сообщение пользователя: {e}", exc_info=True)
            logger.info(f"Пользователь {user_id} не имеет моделей")
            return
        
        # Создаем клавиатуру с моделями
        keyboard = []
        for model in models:
            # Получаем данные модели из API ответа
            model_name = model.get("name", f"Модель #{model.get('model_id', 'без ID')}")
            model_id = model.get("model_id", "unknown")
            
            keyboard.append([
                InlineKeyboardButton(model_name, callback_data=f"model_{model_id}")
            ])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        # Устанавливаем состояние выбора модели
        self.state_manager.set_state(user_id, UserState.SELECTING_MODEL)
        
        # Используем изображение для отображения списка моделей
        try:
            await context.bot.send_photo(
                chat_id=user_id,
                photo=WELCOME_IMAGE_URL,  # Используем изображение из конфигурации
                caption="Выберите модель для генерации изображений:",
                reply_markup=reply_markup
            )
            logger.info(f"Отправлен список моделей с изображением пользователю {user_id}")
        except Exception as e:
            logger.error(f"Ошибка при отправке фото со списком моделей: {e}", exc_info=True)
            # В случае ошибки отправляем текстовое сообщение
            await update.message.reply_text(
                "Выберите модель для генерации изображений:",
                reply_markup=reply_markup
            )
            logger.info(f"Отправлен текстовый список моделей пользователю {user_id}")
        
        # Удаляем сообщение пользователя для чистоты чата
        if update.message:
            try:
                await update.message.delete()
                logger.info(f"Удалено сообщение команды /generate от пользователя {user_id}")
            except Exception as e:
                logger.error(f"Не удалось удалить сообщение пользователя: {e}", exc_info=True)

    async def credits_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Обработчик команды /credits"""
        if not update.effective_user:
            return
        
        user_id = update.effective_user.id
        logger.info(f"Пользователь {user_id} запросил информацию о кредитах")
        
        # Получаем кредиты пользователя через API запрос
        try:
            data = {"telegram_id": user_id}
            async with aiohttp.ClientSession() as session:
                async with session.post('https://n8n2.supashkola.ru/webhook/my_credits', json=data) as response:
                    if response.status == 200:
                        credits_data = await response.text()
                        try:
                            credits = int(credits_data.strip())
                        except ValueError:
                            logger.error(f"Не удалось преобразовать ответ API в число: {credits_data}")
                            credits = 0
                        logger.info(f"Получены кредиты пользователя {user_id} через API: {credits}")
                    else:
                        logger.error(f"Ошибка при получении кредитов через API: {response.status}")
                        credits = 0
        except Exception as e:
            logger.error(f"Исключение при получении кредитов через API: {e}", exc_info=True)
            credits = 0
        
        # Проверяем, есть ли у пользователя модели (для кнопки создания видео)
        has_models = False
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post('https://n8n2.supashkola.ru/webhook/my_models', json=data) as response:
                    if response.status == 200:
                        models = await response.json()
                        has_models = len(models) > 0
                        logger.info(f"Проверка моделей для пользователя {user_id}: {len(models)} моделей")
        except Exception as e:
            logger.error(f"Исключение при проверке моделей через API: {e}", exc_info=True)
        
        message = f"💰 У вас {credits} кредитов.\n\n" \
                   f"Каждое обучение модели стоит 1 кредит.\n" \
                   f"Каждая генерация изображений стоит 1 кредит.\n" \
                   f"Создание видео стоит 1 кредит."
        
        # Создаем основную клавиатуру
        keyboard = [
            [InlineKeyboardButton("🖼️ Начать заново", callback_data="cmd_train")],
            [InlineKeyboardButton("🎨 Сгенерировать фотку", callback_data="cmd_generate")],
        ]
        
        # Добавляем кнопку создания видео, если у пользователя есть модели
        if has_models:
            keyboard.append([InlineKeyboardButton("🎬 Создать видео", callback_data="cmd_video")])
        
        keyboard.append([InlineKeyboardButton("🔄 Начать сначала", callback_data="cmd_start")])
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        # Отправляем сообщение с информацией о кредитах
        if update.callback_query:
            # Если это callback, то редактируем текущее сообщение
            try:
                await update.callback_query.edit_message_text(
                    text=message,
                    reply_markup=reply_markup
                )
                logger.info(f"Обновлено сообщение о кредитах через callback для пользователя {user_id}")
            except Exception as e:
                logger.error(f"Ошибка при обновлении сообщения через callback: {e}", exc_info=True)
                # В случае ошибки отправляем новое сообщение
                await context.bot.send_message(
                    chat_id=user_id,
                    text=message,
                    reply_markup=reply_markup
                )
                logger.info(f"Отправлено новое сообщение о кредитах пользователю {user_id}")
        else:
            # Если это команда, то отправляем новое сообщение
            await context.bot.send_message(
                chat_id=user_id,
                text=message,
                reply_markup=reply_markup
            )
            logger.info(f"Отправлено сообщение о кредитах пользователю {user_id}")
        
        # Удаляем сообщение пользователя для чистоты чата, если это не callback
        if update.message:
            try:
                await update.message.delete()
                logger.info(f"Удалено сообщение команды /credits от пользователя {user_id}")
            except Exception as e:
                logger.error(f"Не удалось удалить сообщение пользователя: {e}", exc_info=True)

    async def cancel_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Обработчик команды /cancel"""
        if not update.effective_user:
            return
        
        user_id = update.effective_user.id
        logger.info(f"Пользователь {user_id} отменил текущую операцию")
        
        # Сбрасываем состояние пользователя
        previous_state = self.state_manager.get_state(user_id)
        self.state_manager.reset_state(user_id)
        
        # Используем функцию create_main_keyboard() для создания клавиатуры
        reply_markup = create_main_keyboard()
        
        # Отправляем welcome сообщение с фото
        try:
            await context.bot.send_photo(
                chat_id=user_id,
                photo=WELCOME_IMAGE_URL,
                caption=WELCOME_MESSAGE,
                reply_markup=reply_markup
            )
            logger.info(f"Отправлено welcome сообщение пользователю {user_id} после команды /cancel")
        except Exception as e:
            logger.error(f"Ошибка при отправке welcome сообщения: {e}", exc_info=True)
            # Если не удалось отправить фото, отправляем текстовое сообщение
            await update.message.reply_text(
                text=WELCOME_MESSAGE,
                reply_markup=reply_markup
            )
        
        # Удаляем сообщение пользователя для чистоты чата
        if update.message:
            try:
                await update.message.delete()
                logger.info(f"Удалено сообщение команды /cancel от пользователя {user_id}")
            except Exception as e:
                logger.error(f"Не удалось удалить сообщение пользователя: {e}", exc_info=True)
