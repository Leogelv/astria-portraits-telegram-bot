from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ParseMode
from telegram.ext import ContextTypes, CallbackContext
from loguru import logger
from typing import Dict, Any, Optional
import aiohttp
import asyncio

from state_manager import UserState
from utils.message_utils import delete_message
from config import ENTER_PROMPT_MESSAGE, WELCOME_IMAGE_URL
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
        # Получаем ID чата для отправки сообщений
        chat_id = update.effective_chat.id if update.effective_chat else None
        # Сохраняем chat_id на всякий случай
        if chat_id:
            self.state_manager.set_data(user_id, "chat_id", chat_id)
        else:
            # Пытаемся получить сохраненный chat_id
            chat_id = self.state_manager.get_data(user_id, "chat_id")
            if not chat_id:
                # Если нет сохраненного chat_id, используем user_id
                chat_id = user_id
                logger.warning(f"Не удалось получить chat_id для пользователя {user_id}, используем user_id")
        
        # Пользователь вводит имя модели
        if len(text) > 30:
            await context.bot.send_message(
                chat_id=chat_id,
                text="❌ Название модели не должно превышать 30 символов. Пожалуйста, введите более короткое название."
            )
            logger.info(f"Пользователь {user_id} ввел слишком длинное название модели: {len(text)} символов")
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
        
        # Получаем ID сообщения для редактирования (должен быть сохранен ранее)
        base_message_id = self.state_manager.get_data(user_id, "base_message_id")
        
        success_message = f"✅ Название модели: {text}\n\nТеперь выберите тип модели:"
        
        # ЗАМЕНЯЕМ СЛОЖНУЮ ЛОГИКУ НА ПРОСТУЮ, как в _handle_prompt_input
        if base_message_id:
            # Редактируем существующее сообщение
            try:
                # Попытка редактировать сообщение в двух вариантах: как caption и как text
                try:
                    # Сначала пробуем как caption (для сообщений с фото)
                    await context.bot.edit_message_caption(
                        chat_id=chat_id,
                        message_id=base_message_id,
                        caption=success_message,
                        reply_markup=reply_markup
                    )
                    logger.info(f"Обновлена подпись сообщения ID {base_message_id} для пользователя {user_id}")
                    
                    # Меняем состояние пользователя
                    self.state_manager.set_state(user_id, UserState.SELECTING_MODEL_TYPE)
                    
                    # Удаляем сообщение пользователя для чистоты чата
                    try:
                        await delete_message(context, chat_id, update.message.message_id)
                        logger.info(f"Удалено текстовое сообщение с именем модели от пользователя {user_id}")
                    except Exception as e:
                        logger.error(f"Не удалось удалить сообщение пользователя: {e}", exc_info=True)
                    
                    return
                except Exception as caption_error:
                    logger.info(f"Не удалось отредактировать caption: {str(caption_error)}, пробуем редактировать текст")
                
                # Если не получилось с caption, редактируем как обычный текст
                await context.bot.edit_message_text(
                    chat_id=chat_id,
                    message_id=base_message_id,
                    text=success_message,
                    reply_markup=reply_markup
                )
                logger.info(f"Обновлено сообщение ID {base_message_id} для пользователя {user_id}")
                
                # Меняем состояние пользователя
                self.state_manager.set_state(user_id, UserState.SELECTING_MODEL_TYPE)
                
                # Удаляем сообщение пользователя для чистоты чата
                try:
                    await delete_message(context, chat_id, update.message.message_id)
                    logger.info(f"Удалено текстовое сообщение с именем модели от пользователя {user_id}")
                except Exception as e:
                    logger.error(f"Не удалось удалить сообщение пользователя: {e}", exc_info=True)
            except Exception as e:
                logger.error(f"Ошибка при обновлении сообщения с именем модели: {e}", exc_info=True)
                
                # В случае полного провала отправляем новое сообщение с фото
                sent_message = await context.bot.send_photo(
                    chat_id=chat_id,
                    photo=WELCOME_IMAGE_URL,
                    caption=success_message,
                    reply_markup=reply_markup
                )
                # Сохраняем ID нового сообщения
                self.state_manager.set_data(user_id, "base_message_id", sent_message.message_id)
                logger.info(f"Отправлено новое сообщение с фото, ID: {sent_message.message_id}")
                
                # Меняем состояние пользователя
                self.state_manager.set_state(user_id, UserState.SELECTING_MODEL_TYPE)
                
                # Удаляем сообщение пользователя для чистоты чата
                try:
                    await delete_message(context, chat_id, update.message.message_id)
                    logger.info(f"Удалено текстовое сообщение с именем модели от пользователя {user_id}")
                except Exception as del_e:
                    logger.error(f"Не удалось удалить сообщение пользователя: {del_e}", exc_info=True)
        else:
            # Если ID сообщения не найден, отправляем новое
            logger.warning(f"ID базового сообщения не найден для пользователя {user_id}, отправляем новое сообщение")
            
            sent_message = await context.bot.send_photo(
                chat_id=chat_id,
                photo=WELCOME_IMAGE_URL,
                caption=success_message,
                reply_markup=reply_markup
            )
            # Сохраняем ID нового сообщения
            self.state_manager.set_data(user_id, "base_message_id", sent_message.message_id)
            logger.info(f"Отправлено новое сообщение с ID {sent_message.message_id}")
            
            # Меняем состояние пользователя
            self.state_manager.set_state(user_id, UserState.SELECTING_MODEL_TYPE)
            
            # Удаляем сообщение пользователя для чистоты чата
            try:
                await delete_message(context, chat_id, update.message.message_id)
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
        # Получаем ID чата для отправки сообщений
        chat_id = update.effective_chat.id if update.effective_chat else None
        # Сохраняем chat_id на всякий случай
        if chat_id:
            self.state_manager.set_data(user_id, "chat_id", chat_id)
        else:
            # Пытаемся получить сохраненный chat_id
            chat_id = self.state_manager.get_data(user_id, "chat_id")
            if not chat_id:
                # Если нет сохраненного chat_id, используем user_id
                chat_id = user_id
                logger.warning(f"Не удалось получить chat_id для пользователя {user_id}, используем user_id")
        
        # Проверка длины промпта
        if len(text) > 500:
            # Просто отвечаем в чат, это сообщение потом удалим
            temp_msg = await update.message.reply_text("Промпт слишком длинный (максимум 500 символов). Пожалуйста, введите более короткий промпт.")
            # Удаляем это сообщение через 5 секунд
            asyncio.create_task(self._delete_message_later(context, chat_id, temp_msg.message_id, 5))
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
        
        # ВСЕГДА сначала удаляем сообщение пользователя с промптом
        try:
            await delete_message(context, chat_id, update.message.message_id)
            logger.info(f"Удалено текстовое сообщение с промптом от пользователя {user_id}")
        except Exception as e:
            logger.error(f"Не удалось удалить сообщение пользователя: {e}", exc_info=True)
        
        # Получаем ID сообщения с запросом промпта или базового сообщения
        prompt_message_id = self.state_manager.get_data(user_id, "prompt_message_id")
        base_message_id = self.state_manager.get_data(user_id, "base_message_id")
        
        # Используем сперва prompt_message_id, если его нет - base_message_id
        message_id_to_edit = prompt_message_id or base_message_id
        
        success_message = f"✅ Промпт сохранен:\n\n{text}\n\nНажмите кнопку ниже, чтобы запустить генерацию изображений с этим промптом."
        
        if message_id_to_edit:
            # Редактируем существующее сообщение
            try:
                # Пробуем сначала как caption (если это сообщение с фото)
                try:
                    await context.bot.edit_message_caption(
                        chat_id=chat_id,
                        message_id=message_id_to_edit,
                        caption=success_message,
                        reply_markup=reply_markup
                    )
                    logger.info(f"Обновлена подпись сообщения ID {message_id_to_edit} с промптом для пользователя {user_id}")
                    # Сохраняем ID сообщения для последующего редактирования
                    self.state_manager.set_data(user_id, "prompt_message_id", message_id_to_edit)
                    self.state_manager.set_state(user_id, UserState.GENERATING_IMAGES)
                    return
                except Exception as caption_error:
                    logger.info(f"Не удалось отредактировать caption: {str(caption_error)}, пробуем редактировать текст.")
                
                # Если не получилось с caption, редактируем как обычный текст
                await context.bot.edit_message_text(
                    chat_id=chat_id,
                    message_id=message_id_to_edit,
                    text=success_message,
                    reply_markup=reply_markup
                )
                logger.info(f"Обновлено сообщение ID {message_id_to_edit} с промптом для пользователя {user_id}")
                # Сохраняем ID сообщения для последующего редактирования
                self.state_manager.set_data(user_id, "prompt_message_id", message_id_to_edit)
            except Exception as e:
                logger.error(f"Ошибка при обновлении сообщения с промптом: {e}", exc_info=True)
                
                # В крайнем случае, отправляем новое фото-сообщение
                try:
                    sent_message = await context.bot.send_photo(
                        chat_id=chat_id,
                        photo=WELCOME_IMAGE_URL,
                        caption=success_message,
                        reply_markup=reply_markup
                    )
                    # Сохраняем ID нового сообщения
                    self.state_manager.set_data(user_id, "prompt_message_id", sent_message.message_id)
                    self.state_manager.set_data(user_id, "base_message_id", sent_message.message_id)
                    logger.info(f"Отправлено новое сообщение с фото и промптом, ID: {sent_message.message_id}")
                except Exception as send_err:
                    logger.error(f"Не удалось отправить даже новое сообщение: {send_err}", exc_info=True)
                    # В самом крайнем случае просто текстовое сообщение
                    sent_message = await context.bot.send_message(
                        chat_id=chat_id,
                        text=success_message,
                        reply_markup=reply_markup
                    )
                    self.state_manager.set_data(user_id, "prompt_message_id", sent_message.message_id)
                    self.state_manager.set_data(user_id, "base_message_id", sent_message.message_id)
        else:
            # Нет сохраненных ID сообщений, отправляем новое сообщение с фото
            try:
                sent_message = await context.bot.send_photo(
                    chat_id=chat_id,
                    photo=WELCOME_IMAGE_URL,
                    caption=success_message,
                    reply_markup=reply_markup
                )
                # Сохраняем ID нового сообщения
                self.state_manager.set_data(user_id, "prompt_message_id", sent_message.message_id)
                self.state_manager.set_data(user_id, "base_message_id", sent_message.message_id)
                logger.info(f"Отправлено новое базовое сообщение с фото и промптом, ID: {sent_message.message_id}")
            except Exception as e:
                logger.error(f"Не удалось отправить сообщение с фото: {e}", exc_info=True)
                # В крайнем случае отправляем обычное текстовое сообщение
                sent_message = await context.bot.send_message(
                    chat_id=chat_id,
                    text=success_message,
                    reply_markup=reply_markup
                )
                self.state_manager.set_data(user_id, "prompt_message_id", sent_message.message_id)
                self.state_manager.set_data(user_id, "base_message_id", sent_message.message_id)
        
        # Обновляем состояние
        self.state_manager.set_state(user_id, UserState.GENERATING_IMAGES)
    
    async def _delete_message_later(self, context: ContextTypes.DEFAULT_TYPE, chat_id: int, message_id: int, delay_seconds: int):
        """Удаляет сообщение после указанной задержки"""
        await asyncio.sleep(delay_seconds)
        try:
            await context.bot.delete_message(chat_id=chat_id, message_id=message_id)
            logger.info(f"Автоматически удалено сообщение {message_id} через {delay_seconds} секунд")
        except Exception as e:
            logger.error(f"Не удалось удалить сообщение {message_id}: {e}", exc_info=True)
    
    async def _handle_model_name_for_media_group(self, update: Update, context: ContextTypes.DEFAULT_TYPE, text: str, user_id: int) -> None:
        """
        Обработка ввода названия модели для группы медиафайлов
        
        Args:
            update (Update): Объект обновления
            context (ContextTypes.DEFAULT_TYPE): Контекст бота
            text (str): Текст сообщения (название модели)
            user_id (int): ID пользователя
        """
        try:
            logger.info(f"Обработка названия модели для медиагруппы от пользователя {user_id}: {text}")
            
            # Получаем chat_id
            chat_id = update.effective_chat.id if update.effective_chat else user_id
            
            # Проверяем, что в названии нет запрещенных символов
            model_name = self._sanitize_model_name(text)
            if model_name != text:
                logger.info(f"Название модели было нормализовано: {text} -> {model_name}")
            
            # Сохраняем название модели в состоянии пользователя
            self.state_manager.set_data(user_id, "model_name", model_name)
            
            # Получаем данные пользователя
            user_data = self.state_manager.get_data(user_id)
            
            # Проверяем, есть ли у нас message_id для редактирования
            message_id = user_data.get('message_id')
            
            # Создаем клавиатуру с кнопкой отмены
            keyboard = [
                [
                    InlineKeyboardButton("Отмена", callback_data=f"cancel_generation")
                ]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            # Формируем текст сообщения
            message_text = (
                f"Название модели: <b>{model_name}</b>\n\n"
                f"Выбранный тип: <b>{get_model_type_display_name(user_data.get('model_type', 'unknown'))}</b>\n\n"
                f"Теперь отправьте от 3 до 20 фотографий одной медиагруппой (удерживайте несколько фото при отправке).\n\n"
                f"<i>* фотографии должны быть хорошего качества и содержать четкое изображение вашего лица с разных ракурсов</i>"
            )
            
            # Пытаемся отредактировать существующее сообщение
            edit_success = False
            if message_id:
                edit_success = await self.edit_message(
                    context=context,
                    message_id=message_id,
                    chat_id=chat_id,
                    text=message_text,
                    caption=message_text,
                    reply_markup=reply_markup
                )
                if edit_success:
                    logger.info(f"Успешно отредактировано сообщение для пользователя {user_id}")
            
            # Если редактирование не удалось или message_id не найден, отправляем новое сообщение
            if not edit_success:
                # Пробуем отправить с фото
                try:
                    message = await context.bot.send_photo(
                        chat_id=chat_id,
                        photo=WELCOME_IMAGE_URL,
                        caption=message_text,
                        parse_mode=ParseMode.HTML,
                        reply_markup=reply_markup
                    )
                    logger.info(f"Отправлено новое сообщение с фото для пользователя {user_id}")
                    
                    # Сохраняем message_id для будущих редактирований
                    self.state_manager.set_data(user_id, "message_id", message.message_id)
                    
                except Exception as photo_err:
                    logger.error(f"Ошибка при отправке фото: {photo_err}", exc_info=True)
                    
                    # Если не получилось с фото, отправляем текстовое сообщение
                    try:
                        message = await context.bot.send_message(
                            chat_id=chat_id,
                            text=message_text,
                            parse_mode=ParseMode.HTML,
                            reply_markup=reply_markup
                        )
                        logger.info(f"Отправлено новое текстовое сообщение для пользователя {user_id}")
                        
                        # Сохраняем message_id для будущих редактирований
                        self.state_manager.set_data(user_id, "message_id", message.message_id)
                        
                    except Exception as text_send_err:
                        logger.error(f"Ошибка при отправке текстового сообщения: {text_send_err}", exc_info=True)
            
            # Устанавливаем состояние пользователя на UPLOADING_PHOTOS
            self.state_manager.set_state(user_id, UserState.UPLOADING_PHOTOS)
            
        except Exception as e:
            logger.error(f"Ошибка при обработке названия модели для медиагруппы: {e}", exc_info=True)
            
            # Создаем клавиатуру с кнопкой "Начать сначала"
            keyboard = [
                [
                    InlineKeyboardButton("Начать сначала", callback_data=f"main_menu")
                ]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            # Сбрасываем состояние пользователя
            self.state_manager.reset_state(user_id)
            
            # Отправляем сообщение об ошибке
            try:
                await context.bot.send_message(
                    chat_id=chat_id if 'chat_id' in locals() else user_id,
                    text="Произошла ошибка при обработке названия модели. Пожалуйста, начните сначала.",
                    reply_markup=reply_markup
                )
            except Exception as send_err:
                logger.error(f"Ошибка при отправке сообщения об ошибке: {send_err}", exc_info=True)
                
                # Пробуем отправить фото, если предыдущая отправка не удалась
                try:
                    await context.bot.send_photo(
                        chat_id=user_id,
                        photo=WELCOME_IMAGE_URL,
                        caption="Произошла ошибка при обработке названия модели. Пожалуйста, начните сначала.",
                        reply_markup=reply_markup
                    )
                except Exception as photo_err:
                    logger.error(f"Не удалось отправить фото с ошибкой: {photo_err}", exc_info=True)
    
    async def _handle_unknown_text(self, update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: int) -> None:
        """
        Обработка неизвестного текстового сообщения
        
        Args:
            update (Update): Объект обновления Telegram
            context (ContextTypes.DEFAULT_TYPE): Контекст Telegram
            user_id (int): ID пользователя
        """
        # Получаем ID чата для отправки сообщений
        chat_id = update.effective_chat.id if update.effective_chat else None
        # Сохраняем chat_id на всякий случай
        if chat_id:
            self.state_manager.set_data(user_id, "chat_id", chat_id)
        else:
            # Пытаемся получить сохраненный chat_id
            chat_id = self.state_manager.get_data(user_id, "chat_id")
            if not chat_id:
                # Если нет сохраненного chat_id, используем user_id
                chat_id = user_id
                logger.warning(f"Не удалось получить chat_id для пользователя {user_id}, используем user_id")
                
        await update.message.reply_text(
            "Я не понимаю этой команды. Пожалуйста, воспользуйтесь одной из доступных команд:\n"
            "/start - Начать работу с ботом\n"
            "/help - Получить справку\n"
            "/train - Обучить новую модель\n"
            "/generate - Сгенерировать изображения"
        )
        
        # Удаляем сообщение пользователя для чистоты чата
        try:
            await delete_message(context, chat_id, update.message.message_id)
            logger.info(f"Удалено текстовое сообщение вне контекста от пользователя {user_id}")
        except Exception as e:
            logger.error(f"Не удалось удалить сообщение пользователя: {e}", exc_info=True)

    async def _handle_photo(self, update: Update, context: ContextTypes.DEFAULT_TYPE, photos: list, user_id: int) -> None:
        """
        Обрабатывает фотографию, загруженную пользователем
        
        Args:
            update (Update): Объект обновления Telegram
            context (ContextTypes.DEFAULT_TYPE): Контекст Telegram
            photos (list): Список объектов PhotoSize
            user_id (int): ID пользователя
        """
        # Получаем ID чата для отправки сообщений
        chat_id = update.effective_chat.id if update.effective_chat else None
        # Сохраняем chat_id на всякий случай
        if chat_id:
            self.state_manager.set_data(user_id, "chat_id", chat_id)
        else:
            # Пытаемся получить сохраненный chat_id
            chat_id = self.state_manager.get_data(user_id, "chat_id")
            if not chat_id:
                # Если нет сохраненного chat_id, используем user_id
                chat_id = user_id
                logger.warning(f"Не удалось получить chat_id для пользователя {user_id}, используем user_id")
        
        # Получаем текущее состояние пользователя
        user_state = self.state_manager.get_state(user_id)
        
        if user_state == UserState.UPLOADING_PHOTOS:
            # Обрабатываем фото только если пользователь находится в состоянии загрузки фото
            try:
                # Проверяем, есть ли у сообщения media_group_id
                media_group_id = update.message.media_group_id
                
                if media_group_id:
                    # Если это сообщение из медиа-группы, обрабатываем его как часть группы
                    if not hasattr(context.bot_data, 'media_groups'):
                        context.bot_data['media_groups'] = {}
                        
                    # Инициализируем группу, если её еще нет
                    if media_group_id not in context.bot_data['media_groups']:
                        context.bot_data['media_groups'][media_group_id] = {
                            'photos': {},
                            'processed': False,
                            'user_id': user_id
                        }
                    
                    # Добавляем фото в группу
                    photo_highest_res = photos[-1]  # Фото с наивысшим разрешением
                    
                    # Получаем информацию о файле
                    file_info = await context.bot.get_file(photo_highest_res.file_id)
                    
                    # Добавляем фото в медиа-группу
                    context.bot_data['media_groups'][media_group_id]['photos'][update.message.message_id] = {
                        'file_id': photo_highest_res.file_id,
                        'file_path': file_info.file_path
                    }
                    
                    # Запланируем обработку медиа-группы через 1 секунду после получения последнего сообщения
                    if hasattr(context, 'job_queue'):
                        # Отменяем предыдущее запланированное выполнение для этой группы, если оно есть
                        for job in context.job_queue.get_jobs_by_name(f"process_media_group_{media_group_id}"):
                            job.schedule_removal()
                        
                        # Планируем новое выполнение
                        context.job_queue.run_once(
                            self._process_media_group_callback,
                            1.0,  # Задержка в 1 секунду
                            data={'media_group_id': media_group_id, 'context': context, 'user_id': user_id, 'chat_id': chat_id},
                            name=f"process_media_group_{media_group_id}"
                        )
                    
                    return
                
                # Если фото отправлено отдельно (не в группе)
                photo_highest_res = photos[-1]  # Фото с наивысшим разрешением
                
                # Получаем информацию о файле
                file_info = await context.bot.get_file(photo_highest_res.file_id)
                file_id = photo_highest_res.file_id
                file_path = file_info.file_path
                
                # Сохраняем информацию о файле
                files_data = self.state_manager.get_data(user_id, "files") or []
                files_data.append({
                    'file_id': file_id,
                    'file_path': file_path
                })
                self.state_manager.set_data(user_id, "files", files_data)
                
                # Получаем сообщение со статусом, если оно есть
                status_message_id = self.state_manager.get_data(user_id, "status_message_id")
                
                # Создаем клавиатуру для сообщения
                keyboard = [
                    [InlineKeyboardButton("✅ Начать обучение", callback_data="start_training")],
                    [InlineKeyboardButton("❌ Отменить", callback_data="cancel_training")]
                ]
                reply_markup = InlineKeyboardMarkup(keyboard)
                
                # Получаем модель и ее тип
                model_name = self.state_manager.get_data(user_id, "model_name") or "Без имени"
                model_type = self.state_manager.get_data(user_id, "model_type") or "Не указан"
                
                gender_text = "мужской" if model_type == "male" else "женской" if model_type == "female" else "неизвестного"
                
                # Текст сообщения со статусом
                status_text = (
                    f"📸 Фотографии для модели \"{model_name}\" ({gender_text} пола):\n\n"
                    f"Загружено фотографий: {len(files_data)}\n\n"
                    "Вы можете продолжить загружать фотографии или нажать кнопку \"Начать обучение\" когда закончите."
                )
                
                if status_message_id:
                    # Обновляем существующее сообщение со статусом
                    try:
                        await context.bot.edit_message_text(
                            chat_id=chat_id,
                            message_id=status_message_id,
                            text=status_text,
                            reply_markup=reply_markup
                        )
                        logger.info(f"Обновлено сообщение со статусом для пользователя {user_id}, фотографий загружено: {len(files_data)}")
                    except Exception as e:
                        logger.error(f"Ошибка при обновлении сообщения со статусом: {e}", exc_info=True)
                        # Создаем новое сообщение со статусом
                        status_message = await context.bot.send_message(
                            chat_id=chat_id,
                            text=status_text,
                            reply_markup=reply_markup
                        )
                        self.state_manager.set_data(user_id, "status_message_id", status_message.message_id)
                else:
                    # Создаем новое сообщение со статусом
                    status_message = await context.bot.send_message(
                        chat_id=chat_id,
                        text=status_text,
                        reply_markup=reply_markup
                    )
                    self.state_manager.set_data(user_id, "status_message_id", status_message.message_id)
                    logger.info(f"Создано новое сообщение со статусом для пользователя {user_id}, ID: {status_message.message_id}")
            except Exception as e:
                logger.error(f"Ошибка при обработке фото: {e}", exc_info=True)
                # Отправляем уведомление об ошибке
                keyboard = [[InlineKeyboardButton("🔄 Начать сначала", callback_data="reset_state")]]
                reply_markup = InlineKeyboardMarkup(keyboard)
                await context.bot.send_message(
                    chat_id=chat_id,
                    text="❌ Произошла ошибка при обработке фотографии. Пожалуйста, попробуйте снова или начните процесс заново.",
                    reply_markup=reply_markup
                )
        else:
            # Пользователь не находится в состоянии загрузки фото, отправляем сообщение с инструкцией
            keyboard = [
                [InlineKeyboardButton("🏞️ Обучить новую модель", callback_data="train_new_model")],
                [InlineKeyboardButton("🖼️ Сгенерировать фотки", callback_data="generate_images")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await context.bot.send_message(
                chat_id=chat_id,
                text=(
                    "📸 Я вижу, вы отправили фотографию, но сейчас бот не находится в режиме приема фотографий.\n\n"
                    "Чтобы обучить новую модель, выберите соответствующую опцию ниже."
                ),
                reply_markup=reply_markup
            )
    
    async def _process_media_group_callback(self, context: CallbackContext) -> None:
        """
        Обрабатывает группу фотографий, отправленных пользователем
        
        Args:
            context (CallbackContext): Контекст бота с данными
        """
        # Извлекаем данные из контекста
        data = context.job.data
        media_group_id = data['media_group_id']
        user_id = data['user_id']
        chat_id = data.get('chat_id', user_id)  # Используем chat_id, если доступен, иначе user_id
        
        # Проверяем, есть ли в боте данные о медиа-группах
        if not hasattr(context.bot_data, 'media_groups'):
            logger.error(f"Нет данных о медиа-группах в context.bot_data")
            return
        
        # Проверяем, есть ли данные по указанной медиа-группе
        if media_group_id not in context.bot_data['media_groups']:
            logger.error(f"Нет данных по медиа-группе {media_group_id}")
            return
        
        # Проверяем, не была ли эта группа уже обработана
        media_group = context.bot_data['media_groups'][media_group_id]
        if media_group['processed']:
            logger.info(f"Медиа-группа {media_group_id} уже была обработана ранее")
            return
        
        # Помечаем группу как обработанную
        media_group['processed'] = True
        
        # Извлекаем фотографии из группы
        photos = media_group['photos']
        
        # Если фотографий в группе нет, выходим
        if not photos:
            logger.warning(f"В медиа-группе {media_group_id} нет фотографий")
            return
        
        # Получаем сохраненные файлы пользователя или инициализируем пустой список
        files_data = self.state_manager.get_data(user_id, "files") or []
        
        # Добавляем новые фотографии из медиа-группы
        for msg_id, photo_data in photos.items():
            files_data.append({
                'file_id': photo_data['file_id'],
                'file_path': photo_data['file_path']
            })
        
        # Сохраняем обновленный список файлов
        self.state_manager.set_data(user_id, "files", files_data)
        
        # Запоминаем media_group_id для последующего использования
        self.state_manager.set_data(user_id, "media_group_id", media_group_id)
        
        # Получаем сообщение со статусом, если оно есть
        status_message_id = self.state_manager.get_data(user_id, "status_message_id")
        
        # Получаем модель и ее тип
        model_name = self.state_manager.get_data(user_id, "model_name") or "Без имени"
        model_type = self.state_manager.get_data(user_id, "model_type") or "Не указан"
        
        gender_text = "мужской" if model_type == "male" else "женской" if model_type == "female" else "неизвестного"
        
        # Создаем клавиатуру для сообщения
        keyboard = [
            [InlineKeyboardButton("✅ Начать обучение", callback_data="start_training")],
            [InlineKeyboardButton("❌ Отменить", callback_data="cancel_training")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        # Текст сообщения со статусом
        status_text = (
            f"📸 Фотографии для модели \"{model_name}\" ({gender_text} пола):\n\n"
            f"Загружено фотографий: {len(files_data)}\n\n"
            "Вы можете продолжить загружать фотографии или нажать кнопку \"Начать обучение\" когда закончите."
        )
        
        # Обновляем или создаем сообщение со статусом
        try:
            if status_message_id:
                # Пытаемся обновить существующее сообщение
                try:
                    await context.bot.edit_message_text(
                        chat_id=chat_id,
                        message_id=status_message_id,
                        text=status_text,
                        reply_markup=reply_markup
                    )
                    logger.info(f"Обновлено сообщение со статусом для пользователя {user_id}, загружено фотографий: {len(files_data)}")
                except Exception as edit_error:
                    logger.error(f"Не удалось обновить статусное сообщение: {edit_error}", exc_info=True)
                    # Если не удалось обновить, создаем новое сообщение
                    status_message = await context.bot.send_message(
                        chat_id=chat_id,
                        text=status_text,
                        reply_markup=reply_markup
                    )
                    self.state_manager.set_data(user_id, "status_message_id", status_message.message_id)
                    logger.info(f"Создано новое статусное сообщение после ошибки обновления, ID: {status_message.message_id}")
            else:
                # Создаем новое сообщение со статусом
                status_message = await context.bot.send_message(
                    chat_id=chat_id,
                    text=status_text,
                    reply_markup=reply_markup
                )
                self.state_manager.set_data(user_id, "status_message_id", status_message.message_id)
                logger.info(f"Создано новое статусное сообщение для пользователя {user_id}, ID: {status_message.message_id}")
        except Exception as e:
            logger.error(f"Ошибка при работе со статусным сообщением: {e}", exc_info=True)
            # Отправляем уведомление об ошибке
            keyboard = [[InlineKeyboardButton("🔄 Начать сначала", callback_data="reset_state")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            try:
                await context.bot.send_message(
                    chat_id=chat_id,
                    text="❌ Произошла ошибка при обработке группы фотографий. Пожалуйста, попробуйте снова или начните процесс заново.",
                    reply_markup=reply_markup
                )
            except Exception as send_error:
                logger.error(f"Не удалось отправить сообщение об ошибке: {send_error}", exc_info=True)

    async def edit_message(self, context, message_id, chat_id, text=None, caption=None, reply_markup=None):
        """
        Редактирует сообщение, автоматически определяя тип сообщения (текст или с подписью)
        
        Args:
            context (ContextTypes.DEFAULT_TYPE): Контекст бота
            message_id (int): ID сообщения для редактирования
            chat_id (int): ID чата
            text (str, optional): Новый текст сообщения
            caption (str, optional): Новая подпись сообщения
            reply_markup (InlineKeyboardMarkup, optional): Новая клавиатура
        
        Returns:
            bool: True если редактирование прошло успешно, False в противном случае
        """
        if not message_id or not chat_id:
            logger.warning("Не указан message_id или chat_id для редактирования сообщения")
            return False
        
        try:
            # Пробуем отредактировать как подпись (для фото, видео и т.д.)
            if caption:
                await context.bot.edit_message_caption(
                    chat_id=chat_id,
                    message_id=message_id,
                    caption=caption,
                    parse_mode=ParseMode.HTML,
                    reply_markup=reply_markup
                )
                logger.debug(f"Успешно отредактирована подпись сообщения {message_id}")
                return True
            # Пробуем отредактировать как текст
            elif text:
                await context.bot.edit_message_text(
                    chat_id=chat_id,
                    message_id=message_id,
                    text=text,
                    parse_mode=ParseMode.HTML,
                    reply_markup=reply_markup
                )
                logger.debug(f"Успешно отредактирован текст сообщения {message_id}")
                return True
            # Пробуем отредактировать клавиатуру
            elif reply_markup:
                await context.bot.edit_message_reply_markup(
                    chat_id=chat_id,
                    message_id=message_id,
                    reply_markup=reply_markup
                )
                logger.debug(f"Успешно отредактирована клавиатура сообщения {message_id}")
                return True
            else:
                logger.warning("Не указаны параметры для редактирования сообщения")
                return False
        except Exception as e:
            logger.warning(f"Ошибка при редактировании сообщения: {e}")
            return False
