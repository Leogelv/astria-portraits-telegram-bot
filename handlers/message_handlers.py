from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from loguru import logger
from typing import Dict, Any, Optional
import aiohttp

from state_manager import UserState
from utils.message_utils import delete_message
from config import ENTER_PROMPT_MESSAGE
from utils.logging_utils import LogEventType

class MessageHandler:
    """Обработчик текстовых сообщений бота"""
    
    def __init__(self, state_manager, db_manager, api_client):
        """
        Инициализация обработчика сообщений
        
        Args:
            state_manager: Менеджер состояний пользователей
            db_manager: Менеджер базы данных
            api_client: Клиент API
        """
        self.state_manager = state_manager
        self.db = db_manager
        self.api = api_client
        logger.info("Инициализирован MessageHandler")
    
    async def handle_text(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """
        Обработчик текстовых сообщений
        
        Args:
            update (Update): Объект обновления Telegram
            context (ContextTypes.DEFAULT_TYPE): Контекст Telegram
        """
        if not update.effective_message or not update.effective_user:
            return
        
        text = update.effective_message.text
        user_id = update.effective_user.id
        
        # Получаем текущее состояние пользователя
        state = self.state_manager.get_state(user_id)
        
        logger.info(f"Пользователь {user_id} отправил текст: '{text}', состояние: {state}")
        
        if state == UserState.ENTERING_MODEL_NAME:
            await self._handle_model_name_input(update, context, text, user_id)
        elif state == UserState.ENTERING_PROMPT:
            await self._handle_prompt_input(update, context, text, user_id)
        elif state == UserState.ENTERING_MODEL_NAME_FOR_MEDIA_GROUP:
            await self._handle_model_name_for_media_group(update, context, text, user_id)
        else:
            # Пользователь отправил текст вне контекста команды
            await self._handle_unknown_text(update, context, user_id)
    
    async def _handle_model_name_input(self, update: Update, context: ContextTypes.DEFAULT_TYPE, text: str, user_id: int) -> None:
        """
        Обработка ввода имени модели
        
        Args:
            update (Update): Объект обновления Telegram
            context (ContextTypes.DEFAULT_TYPE): Контекст Telegram
            text (str): Текст сообщения
            user_id (int): ID пользователя
        """
        # Пользователь вводит имя модели
        if len(text) > 50:
            await update.message.reply_text("Имя модели слишком длинное (максимум 50 символов). Пожалуйста, введите более короткое имя.")
            return
        
        # Сохраняем имя модели
        self.state_manager.set_data(user_id, "model_name", text)
        logger.info(f"Пользователь {user_id} ввел имя модели: {text}")
        
        # Создаем клавиатуру для выбора типа модели
        keyboard = [
            [
                InlineKeyboardButton("Мужская", callback_data="type_male"),
                InlineKeyboardButton("Женская", callback_data="type_female")
            ],
            [InlineKeyboardButton("❌ Отменить обучение", callback_data="cancel_training")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            f"Название модели: {text}\n\nТеперь выберите тип модели:",
            reply_markup=reply_markup
        )
        
        # Устанавливаем состояние выбора типа модели
        self.state_manager.set_state(user_id, UserState.SELECTING_MODEL_TYPE)
        
        # Удаляем сообщение пользователя для чистоты чата
        try:
            await delete_message(context, user_id, update.message.message_id)
            logger.info(f"Удалено текстовое сообщение с именем модели от пользователя {user_id}")
        except Exception as e:
            logger.error(f"Не удалось удалить сообщение пользователя: {e}", exc_info=True)
    
    async def _handle_prompt_input(self, update: Update, context: ContextTypes.DEFAULT_TYPE, text: str, user_id: int) -> None:
        """
        Обработка ввода промпта для генерации изображений
        
        Args:
            update (Update): Объект обновления Telegram
            context (ContextTypes.DEFAULT_TYPE): Контекст Telegram
            text (str): Текст сообщения
            user_id (int): ID пользователя
        """
        # Пользователь вводит промпт для генерации изображений
        if len(text) > 500:
            await update.message.reply_text("Промпт слишком длинный (максимум 500 символов). Пожалуйста, введите более короткий промпт.")
            return
        
        # Сохраняем промпт
        self.state_manager.set_data(user_id, "prompt", text)
        logger.info(f"Пользователь {user_id} ввел промпт: {text}")
        
        # Получаем ID модели
        model_id = self.state_manager.get_data(user_id, "model_id")
        
        # Создаем клавиатуру с кнопками для запуска генерации
        keyboard = [
            [InlineKeyboardButton("🚀 Запустить генерацию", callback_data="start_generation")],
            [InlineKeyboardButton("✏️ Изменить промпт", callback_data="edit_prompt")],
            [InlineKeyboardButton("❌ Отменить", callback_data="cancel_generation")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        # Получаем message_id сообщения с запросом промпта
        prompt_message_id = self.state_manager.get_data(user_id, "prompt_message_id")
        
        if prompt_message_id:
            logger.info(f"Редактирую сообщение {prompt_message_id} для пользователя {user_id}")
            try:
                await context.bot.edit_message_text(
                    chat_id=user_id,
                    message_id=prompt_message_id,
                    text=f"✅ Промпт сохранен:\n\n{text}\n\nНажмите кнопку ниже, чтобы запустить генерацию изображений с этим промптом.",
                    reply_markup=reply_markup
                )
                logger.info(f"Обновлено сообщение с промптом для пользователя {user_id}")
            except Exception as e:
                logger.error(f"Ошибка при обновлении сообщения с промптом: {e}", exc_info=True)
                # Если не удалось обновить сообщение (возможно оно устарело), пробуем найти последнее сообщение от бота
                try:
                    # Пробуем редактировать последнее сообщение от бота
                    updates = await context.bot.get_updates(limit=10, timeout=1)
                    bot_messages = [u.message for u in updates if u.message and u.message.from_user and u.message.from_user.is_bot and u.message.chat.id == user_id]
                    if bot_messages:
                        latest_bot_message = bot_messages[-1]
                        await context.bot.edit_message_text(
                            chat_id=user_id,
                            message_id=latest_bot_message.message_id,
                            text=f"✅ Промпт сохранен:\n\n{text}\n\nНажмите кнопку ниже, чтобы запустить генерацию изображений с этим промптом.",
                            reply_markup=reply_markup
                        )
                        # Сохраняем ID нового сообщения
                        self.state_manager.set_data(user_id, "prompt_message_id", latest_bot_message.message_id)
                        logger.info(f"Отредактировано последнее сообщение бота с ID {latest_bot_message.message_id}")
                        return
                except Exception as latest_err:
                    logger.error(f"Не удалось найти и отредактировать последнее сообщение бота: {latest_err}", exc_info=True)
                
                # Если все попытки редактирования не удались, отправляем новое сообщение в крайнем случае
                sent_message = await context.bot.send_message(
                    chat_id=user_id,
                    text=f"✅ Промпт сохранен:\n\n{text}\n\nНажмите кнопку ниже, чтобы запустить генерацию изображений с этим промптом.",
                    reply_markup=reply_markup
                )
                # Сохраняем ID нового сообщения
                self.state_manager.set_data(user_id, "prompt_message_id", sent_message.message_id)
                logger.info(f"Отправлено новое сообщение с ID {sent_message.message_id} с подтверждением промпта (резервный вариант)")
        else:
            logger.warning(f"Не найден message_id для редактирования промпта пользователя {user_id}, отправляю новое сообщение")
            # Если нет сохраненного ID сообщения, отправляем новое
            sent_message = await context.bot.send_message(
                chat_id=user_id,
                text=f"✅ Промпт сохранен:\n\n{text}\n\nНажмите кнопку ниже, чтобы запустить генерацию изображений с этим промптом.",
                reply_markup=reply_markup
            )
            # Сохраняем ID нового сообщения
            self.state_manager.set_data(user_id, "prompt_message_id", sent_message.message_id)
            logger.info(f"Отправлено новое сообщение с ID {sent_message.message_id} с подтверждением промпта")
        
        # Обновляем состояние
        self.state_manager.set_state(user_id, UserState.GENERATING_IMAGES)
        
        # Удаляем сообщение пользователя для чистоты чата
        try:
            await delete_message(context, user_id, update.message.message_id)
            logger.info(f"Удалено текстовое сообщение с промптом от пользователя {user_id}")
        except Exception as e:
            logger.error(f"Не удалось удалить сообщение пользователя: {e}", exc_info=True)
    
    async def _handle_model_name_for_media_group(self, update: Update, context: ContextTypes.DEFAULT_TYPE, text: str, user_id: int) -> None:
        """
        Обработка ввода имени модели для медиагруппы
        
        Args:
            update (Update): Объект обновления Telegram
            context (ContextTypes.DEFAULT_TYPE): Контекст Telegram
            text (str): Текст сообщения
            user_id (int): ID пользователя
        """
        # Пользователь вводит имя модели для медиагруппы
        if len(text) > 50:
            await update.message.reply_text("Имя модели слишком длинное (максимум 50 символов). Пожалуйста, введите более короткое имя.")
            return
        
        # Сохраняем имя модели
        self.state_manager.set_data(user_id, "model_name", text)
        logger.info(f"Пользователь {user_id} ввел имя модели для медиагруппы: {text}")
        
        # Создаем клавиатуру для выбора типа модели
        keyboard = [
            [
                InlineKeyboardButton("Мужская", callback_data="mgtype_male"),
                InlineKeyboardButton("Женская", callback_data="mgtype_female")
            ],
            [InlineKeyboardButton("❌ Отменить обучение", callback_data="cancel_training")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            f"Название модели: {text}\n\nТеперь выберите тип модели:",
            reply_markup=reply_markup
        )
        
        # Устанавливаем состояние выбора типа модели для медиагруппы
        self.state_manager.set_state(user_id, UserState.SELECTING_MODEL_TYPE_FOR_MEDIA_GROUP)
        
        # Удаляем сообщение пользователя для чистоты чата
        try:
            await delete_message(context, user_id, update.message.message_id)
            logger.info(f"Удалено текстовое сообщение с именем модели для медиагруппы от пользователя {user_id}")
        except Exception as e:
            logger.error(f"Не удалось удалить сообщение пользователя: {e}", exc_info=True)
    
    async def _handle_unknown_text(self, update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: int) -> None:
        """
        Обработка неизвестного текстового сообщения
        
        Args:
            update (Update): Объект обновления Telegram
            context (ContextTypes.DEFAULT_TYPE): Контекст Telegram
            user_id (int): ID пользователя
        """
        await update.message.reply_text(
            "Я не понимаю этой команды. Пожалуйста, воспользуйтесь одной из доступных команд:\n"
            "/start - Начать работу с ботом\n"
            "/help - Получить справку\n"
            "/train - Обучить новую модель\n"
            "/generate - Сгенерировать изображения"
        )
        
        # Удаляем сообщение пользователя для чистоты чата
        try:
            await delete_message(context, user_id, update.message.message_id)
            logger.info(f"Удалено текстовое сообщение вне контекста от пользователя {user_id}")
        except Exception as e:
            logger.error(f"Не удалось удалить сообщение пользователя: {e}", exc_info=True)
