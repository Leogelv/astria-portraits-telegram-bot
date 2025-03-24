from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ParseMode
from telegram.ext import ContextTypes
from loguru import logger
from typing import Dict, Any, Optional, List
from datetime import datetime
import aiohttp
import json

from state_manager import UserState
from utils.message_utils import delete_message, create_main_keyboard
from config import WELCOME_MESSAGE, WELCOME_IMAGE_URL, INSTRUCTIONS_IMAGE_URL, ENTER_PROMPT_MESSAGE, UPLOAD_PHOTOS_MESSAGE

class CallbackHandler:
    """Обработчик callback-запросов бота"""
    
    def __init__(self, state_manager, db_manager, api_client, media_groups=None):
        """
        Инициализация обработчика callback-запросов
        
        Args:
            state_manager: Менеджер состояний пользователей
            db_manager: Менеджер базы данных
            api_client: Клиент API
            media_groups (dict, optional): Словарь для отслеживания медиагрупп
        """
        self.state_manager = state_manager
        self.db = db_manager
        self.api = api_client
        self.media_groups = media_groups if media_groups is not None else {}
        logger.info("Инициализирован CallbackHandler")
    
    async def handle_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """
        Обработчик callback-запросов
        
        Args:
            update (Update): Объект обновления Telegram
            context (ContextTypes.DEFAULT_TYPE): Контекст Telegram
        """
        if not update.callback_query:
            logger.error("Получен пустой callback_query в handle_callback")
            return
            
        query = update.callback_query
        user_id = query.from_user.id
        callback_data = query.data
        
        logger.info(f"Получен callback от пользователя {user_id}: {callback_data}")
        
        # Отвечаем на callback-запрос сразу, чтобы убрать часы загрузки в Telegram
        try:
            await query.answer()
        except Exception as e:
            logger.error(f"Ошибка при ответе на callback: {e}")
        
        # Обрабатываем callback-данные
        if callback_data.startswith("cmd_"):
            await self._handle_command_callback(update, context, query, user_id, callback_data)
        elif callback_data.startswith("model_"):
            await self._handle_model_selection(update, context, query, user_id, callback_data)
        elif callback_data == "start_generation":
            await self._handle_start_generation(update, context, query, user_id)
        elif callback_data == "edit_prompt":
            await self._handle_edit_prompt(update, context, query, user_id)
        elif callback_data == "cancel_generation":
            await self._handle_cancel_generation(update, context, query, user_id)
        elif callback_data.startswith("type_"):
            await self._handle_model_type_selection(update, context, query, user_id, callback_data)
        elif callback_data.startswith("start_training_"):
            await self._handle_start_training(update, context, query, user_id, callback_data)
        elif callback_data == "cancel_training":
            await self._handle_cancel_training(update, context, query, user_id)
        elif callback_data == "cmd_video":
            await self._handle_video_command(update, context, query, user_id)
        elif callback_data.startswith("videomodel_"):
            await self._handle_video_model_selection(update, context, query, user_id, callback_data)
        elif callback_data == "vidimg_prev":
            await self._handle_image_navigation(update, context, query, user_id, "prev")
        elif callback_data == "vidimg_next":
            await self._handle_image_navigation(update, context, query, user_id, "next")
        elif callback_data == "vidimg_info":
            # Просто информационная кнопка, ничего не делаем
            pass
        elif callback_data == "start_video_generation":
            await self._handle_start_video_generation(update, context, query, user_id)
        elif callback_data == "cancel_video":
            # Отмена создания видео - просто возвращаемся в главное меню
            await self._handle_cancel_video(update, context, query, user_id)
        else:
            # Неизвестный callback
            logger.warning(f"Получен неизвестный callback от пользователя {user_id}: {callback_data}")
            try:
                await query.answer("Неизвестная команда")
            except Exception as e:
                logger.error(f"Ошибка при ответе на неизвестный callback: {e}", exc_info=True)
    
    async def _handle_command_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE, query, user_id: int, callback_data: str) -> None:
        """
        Обработка callback-запросов команд
        
        Args:
            update (Update): Объект обновления Telegram
            context (ContextTypes.DEFAULT_TYPE): Контекст Telegram
            query: Объект callback_query
            user_id (int): ID пользователя
            callback_data (str): Данные callback-запроса
        """
        command = callback_data.split("_")[1]
        logger.info(f"Обработка команды из callback: {command} для пользователя {user_id}")
        
        if command == "start":
            # Сбрасываем состояние пользователя
            self.state_manager.reset_state(user_id)
            
            # Используем готовую функцию для создания основной клавиатуры
            reply_markup = create_main_keyboard()
            
            # Обновляем сообщение
            try:
                # Проверяем, есть ли caption в сообщении
                if hasattr(query.message, 'caption') and query.message.caption is not None:
                    await query.edit_message_caption(
                        caption=WELCOME_MESSAGE,
                        reply_markup=reply_markup
                    )
                else:
                    # Если caption нет, меняем текст
                    await query.edit_message_text(
                        text=WELCOME_MESSAGE,
                        reply_markup=reply_markup
                    )
                logger.info(f"Обновлено сообщение с главным меню для пользователя {user_id}")
            except Exception as e:
                logger.error(f"Ошибка при обновлении сообщения в cmd_start: {e}", exc_info=True)
                try:
                    # В случае ошибки отправляем новое сообщение с меню
                    await context.bot.send_photo(
                        chat_id=user_id,
                        photo=WELCOME_IMAGE_URL,
                        caption=WELCOME_MESSAGE,
                        reply_markup=reply_markup
                    )
                    logger.info(f"Отправлено новое welcome сообщение пользователю {user_id}")
                except Exception as send_err:
                    logger.error(f"Ошибка при отправке нового welcome сообщения: {send_err}", exc_info=True)
        
        elif command == "train":
            await self._handle_cmd_train(update, context, query, user_id)
        
        elif command == "generate":
            await self._handle_cmd_generate(update, context, query, user_id)
        
        elif command == "credits":
            await self._handle_cmd_credits(update, context, query, user_id)
        
        elif command == "models":
            await self._handle_cmd_models(update, context, query, user_id)
            
        elif command == "video":
            await self._handle_video_command(update, context, query, user_id)
        
        else:
            logger.warning(f"Неизвестная команда в callback: {command}")
            await query.answer(f"Неизвестная команда: {command}")
            # Отправляем сообщение с доступными командами
            try:
                await query.edit_message_text(
                    text="Неизвестная команда. Пожалуйста, используйте одну из доступных команд:",
                    reply_markup=create_main_keyboard()
                )
            except Exception as e:
                logger.error(f"Ошибка при обновлении сообщения о неизвестной команде: {e}", exc_info=True)
    
    async def _handle_cmd_train(self, update: Update, context: ContextTypes.DEFAULT_TYPE, query, user_id: int) -> None:
        """
        Обрабатывает команду /train для создания новой модели
        
        Args:
            update (Update): Объект обновления Telegram
            context (ContextTypes.DEFAULT_TYPE): Контекст Telegram
            query: Объект callback_query
            user_id (int): ID пользователя
        """
        logger.info(f"Пользователь {user_id} запрашивает создание новой модели")
        
        # Получаем chat_id
        chat_id = update.effective_chat.id if update.effective_chat else user_id
        self.state_manager.update_data(user_id, chat_id=chat_id)
        
        # Сбрасываем состояние пользователя (сохраняем chat_id)
        self.state_manager.clear_data(user_id, preserve_keys=['chat_id'])
        
        # Устанавливаем состояние пользователя на ENTERING_MODEL_NAME
        self.state_manager.set_state(user_id, UserState.ENTERING_MODEL_NAME)
        
        # Создаем клавиатуру с кнопкой отмены
        keyboard = [
            [
                InlineKeyboardButton("Отмена", callback_data=f"cancel_generation")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        # Формируем текст сообщения
        message_text = (
            "Вы начали процесс обучения новой модели.\n\n"
            "Сначала придумайте название модели (до 30 символов).\n"
            "<i>* название может содержать только буквы, цифры и символы _ - .</i>"
        )
        
        # Отправляем сообщение о начале процесса обучения
        edit_success = await self.edit_message(
            context=context,
            query=query,
            chat_id=chat_id,
            text=message_text,
            caption=message_text,
            reply_markup=reply_markup
        )
        
        if edit_success:
            logger.info(f"Обновлено сообщение с запросом названия модели для пользователя {user_id}")
            # Если успешно отредактировали, то сохраняем message_id для будущих редактирований
            message_id = query.message.message_id
            self.state_manager.update_data(user_id, message_id=message_id)
        else:
            # В случае ошибки отправляем новое сообщение
            try:
                # Попробуем отправить фото
                try:
                    message = await context.bot.send_photo(
                        chat_id=chat_id,
                        photo=WELCOME_IMAGE_URL,
                        caption=message_text,
                        parse_mode=ParseMode.HTML,
                        reply_markup=reply_markup
                    )
                    logger.info(f"Отправлено новое сообщение с фото для пользователя {user_id}")
                except Exception as photo_err:
                    logger.error(f"Ошибка при отправке фото: {photo_err}", exc_info=True)
                    # Если с фото не получилось, отправляем обычное сообщение
                    message = await context.bot.send_message(
                        chat_id=chat_id,
                        text=message_text,
                        parse_mode=ParseMode.HTML,
                        reply_markup=reply_markup
                    )
                    logger.info(f"Отправлено новое текстовое сообщение для пользователя {user_id}")
                
                # Сохраняем ID сообщения для будущих редактирований
                self.state_manager.update_data(user_id, message_id=message.message_id)
                
            except Exception as e:
                logger.error(f"Ошибка при отправке сообщения с запросом названия модели: {e}", exc_info=True)
    
    async def _handle_cmd_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE, query, user_id: int) -> None:
        """
        Обработка команды start из callback
        
        Args:
            update (Update): Объект обновления Telegram
            context (ContextTypes.DEFAULT_TYPE): Контекст Telegram
            query: Объект callback_query
            user_id (int): ID пользователя
        """
        logger.info(f"Начинаю обработку команды start из callback для пользователя {user_id}")
        
        # Сбрасываем состояние пользователя
        self.state_manager.reset_state(user_id)
        
        # Используем функцию для создания основной клавиатуры
        reply_markup = create_main_keyboard()
        
        # Редактируем текущее сообщение
        try:
            # Проверяем, есть ли caption в сообщении
            if hasattr(query.message, 'caption') and query.message.caption is not None:
                await query.edit_message_caption(
                    caption=WELCOME_MESSAGE,
                    reply_markup=reply_markup
                )
            else:
                # Если caption нет, меняем текст
                await query.edit_message_text(
                    text=WELCOME_MESSAGE,
                    reply_markup=reply_markup
                )
            logger.info(f"Обновлено сообщение с главным меню для пользователя {user_id}")
        except Exception as e:
            logger.error(f"Ошибка при обновлении сообщения в cmd_start: {e}", exc_info=True)
            # В случае ошибки отправляем новое фото с меню
            try:
                await context.bot.send_photo(
                    chat_id=user_id,
                    photo=WELCOME_IMAGE_URL,
                    caption=WELCOME_MESSAGE,
                    reply_markup=reply_markup
                )
                logger.info(f"Отправлено новое welcome сообщение пользователю {user_id}")
            except Exception as send_err:
                logger.error(f"Ошибка при отправке нового welcome сообщения: {send_err}", exc_info=True)
    
    async def _handle_cmd_generate(self, update: Update, context: ContextTypes.DEFAULT_TYPE, query, user_id: int) -> None:
        """
        Обработка команды generate из callback
        
        Args:
            update (Update): Объект обновления Telegram
            context (ContextTypes.DEFAULT_TYPE): Контекст Telegram
            query: Объект callback_query
            user_id (int): ID пользователя
        """
        logger.info(f"Начинаю обработку команды generate из callback для пользователя {user_id}")
        
        # Получаем chat_id
        chat_id = update.effective_chat.id if update.effective_chat else user_id
        self.state_manager.set_data(user_id, "chat_id", chat_id)
        
        # Получаем модели пользователя через API запрос
        try:
            data = {"telegram_id": user_id}
            async with aiohttp.ClientSession() as session:
                async with session.post('https://n8n2.supashkola.ru/webhook/my_models', json=data) as response:
                    if response.status == 200:
                        models = await response.json()
                        logger.info(f"Получены модели пользователя {user_id} через API: {len(models)} моделей")
                    else:
                        logger.error(f"Ошибка при получении моделей через API: {response.status}")
                        models = []
        except Exception as e:
            logger.error(f"Исключение при получении моделей через API: {e}", exc_info=True)
            models = []
        
        if not models:
            # Редактируем текущее сообщение
            message_text = "У вас пока нет обученных моделей. Используйте команду /train, чтобы обучить новую модель."
            
            edit_success = await self.edit_message(
                context=context,
                query=query,
                chat_id=chat_id,
                caption=message_text,
                text=message_text
            )
            
            if edit_success:
                logger.info(f"Обновлено сообщение для пользователя {user_id} - нет моделей")
            else:
                # Если не удалось отредактировать, отправляем новое сообщение
                await context.bot.send_message(
                    chat_id=chat_id,
                    text=message_text
                )
                logger.info(f"Отправлено новое сообщение для пользователя {user_id} - нет моделей")
            
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
        logger.info(f"Установлено состояние SELECTING_MODEL для пользователя {user_id}")
        
        message_text = "Выберите модель для генерации изображений:"
        
        # Редактируем сообщение с помощью нашего метода
        edit_success = await self.edit_message(
            context=context,
            query=query,
            chat_id=chat_id,
            caption=message_text,
            text=message_text,
            reply_markup=reply_markup
        )
        
        if edit_success:
            logger.info(f"Обновлено сообщение для выбора модели пользователем {user_id}")
        else:
            # Если не получилось изменить текущее сообщение, отправляем новое
            try:
                await context.bot.send_photo(
                    chat_id=chat_id,
                    photo=WELCOME_IMAGE_URL,
                    caption=message_text,
                    reply_markup=reply_markup
                )
                logger.info(f"Отправлено новое сообщение с выбором модели пользователю {user_id}")
            except Exception as e:
                logger.error(f"Ошибка при отправке фото с выбором модели: {e}", exc_info=True)
                # В крайнем случае отправляем текстовое сообщение
                await context.bot.send_message(
                    chat_id=chat_id,
                    text=message_text,
                    reply_markup=reply_markup
                )
                logger.info(f"Отправлено текстовое сообщение с выбором модели пользователю {user_id}")
    
    async def _handle_cmd_credits(self, update: Update, context: ContextTypes.DEFAULT_TYPE, query, user_id: int) -> None:
        """
        Обработка команды credits из callback
        
        Args:
            update (Update): Объект обновления Telegram
            context (ContextTypes.DEFAULT_TYPE): Контекст Telegram
            query: Объект callback_query
            user_id (int): ID пользователя
        """
        logger.info(f"Начинаю обработку команды credits из callback для пользователя {user_id}")
        
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
        message = f"💰 У вас {credits} кредитов.\n\n" \
                  f"🎓 Обучение модели по вашим фотографиям стоит 200 кредитов.\n\n" \
                  f"🖼 Каждое изображение стоит 3 кредита.\n"
        
        # Создаем клавиатуру с кнопкой "Назад"
        keyboard = [
            [InlineKeyboardButton("🔙 Назад", callback_data="cmd_start")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        # Пробуем изменить текущее сообщение
        try:
            await query.edit_message_caption(
                caption=message,
                reply_markup=reply_markup
            )
            logger.info(f"Обновлено сообщение с информацией о кредитах для пользователя {user_id}")
        except Exception as e:
            logger.error(f"Ошибка при обновлении сообщения с информацией о кредитах: {e}", exc_info=True)
            
            # Если не получилось изменить текущее сообщение, отправляем новое
            try:
                await context.bot.send_photo(
                    chat_id=user_id,
                    photo=WELCOME_IMAGE_URL,
                    caption=message,
                    reply_markup=reply_markup
                )
                logger.info(f"Отправлена информация о кредитах пользователю {user_id}")
            except Exception as send_err:
                logger.error(f"Ошибка при отправке информации о кредитах: {send_err}", exc_info=True)
                # Если не удалось отправить фото, отправляем текстовое сообщение
                await context.bot.send_message(
                    chat_id=user_id,
                    text=message,
                    reply_markup=reply_markup
                )
    
    async def _handle_cmd_models(self, update: Update, context: ContextTypes.DEFAULT_TYPE, query, user_id: int) -> None:
        """
        Обработка команды models из callback
        
        Args:
            update (Update): Объект обновления Telegram
            context (ContextTypes.DEFAULT_TYPE): Контекст Telegram
            query: Объект callback_query
            user_id (int): ID пользователя
        """
        logger.info(f"Начинаю обработку команды models из callback для пользователя {user_id}")
        
        # Получаем модели пользователя через API запрос
        try:
            data = {"telegram_id": user_id}
            async with aiohttp.ClientSession() as session:
                async with session.post('https://n8n2.supashkola.ru/webhook/my_models', json=data) as response:
                    if response.status == 200:
                        models = await response.json()
                        logger.info(f"Получены модели пользователя {user_id} через API: {len(models)} моделей")
                    else:
                        logger.error(f"Ошибка при получении моделей через API: {response.status}")
                        models = []
        except Exception as e:
            logger.error(f"Исключение при получении моделей через API: {e}", exc_info=True)
            models = []
        
        if not models:
            try:
                await query.edit_message_caption(
                    caption="У вас пока нет обученных моделей. Используйте команду /train, чтобы обучить новую модель."
                )
            except Exception as e:
                logger.error(f"Ошибка при обновлении сообщения: {e}", exc_info=True)
                await context.bot.send_message(
                    chat_id=user_id,
                    text="У вас пока нет обученных моделей. Используйте команду /train, чтобы обучить новую модель."
                )
            logger.info(f"Пользователь {user_id} не имеет моделей")
            return
        
        # Формируем сообщение со списком моделей
        message = "📋 Ваши модели:\n\n"
        
        for model in models:
            model_name = model.get("name", f"Модель #{model.get('model_id', 'без ID')}")
            model_status = model.get("status", "неизвестно")
            model_date = model.get("created_at", "").split("T")[0] if isinstance(model.get("created_at", ""), str) else "Неизвестно"
            model_id = model.get("model_id", "неизвестно")
            
            message += f"🔹 {model_name}\n"
            message += f"   ID: {model_id}\n"
            message += f"   Статус: {model_status}\n"
            message += f"   Создана: {model_date}\n\n"
        
        # Создаем клавиатуру с кнопкой "Назад"
        keyboard = [
            [InlineKeyboardButton("🔙 Назад", callback_data="cmd_start")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        # Пробуем изменить текущее сообщение
        try:
            await query.edit_message_caption(
                caption=message,
                reply_markup=reply_markup
            )
            logger.info(f"Обновлено сообщение со списком моделей для пользователя {user_id}")
        except Exception as e:
            logger.error(f"Ошибка при обновлении сообщения со списком моделей: {e}", exc_info=True)
            
            # Если не получилось изменить текущее сообщение, отправляем новое
            try:
                await context.bot.send_photo(
                    chat_id=user_id,
                    photo=WELCOME_IMAGE_URL,
                    caption=message,
                    reply_markup=reply_markup
                )
                logger.info(f"Отправлен список моделей пользователю {user_id}")
            except Exception as send_err:
                logger.error(f"Ошибка при отправке списка моделей: {send_err}", exc_info=True)
                # Если не удалось отправить фото, отправляем текстовое сообщение
                await context.bot.send_message(
                    chat_id=user_id,
                    text=message,
                    reply_markup=reply_markup
                )
    
    async def _handle_model_selection(self, update: Update, context: ContextTypes.DEFAULT_TYPE, query, user_id: int, callback_data: str) -> None:
        """
        Обработка выбора модели для генерации изображений
        
        Args:
            update (Update): Объект обновления Telegram
            context (ContextTypes.DEFAULT_TYPE): Контекст Telegram
            query: Объект callback_query
            user_id (int): ID пользователя
            callback_data (str): Данные callback-запроса
        """
        try:
            model_id_str = callback_data.split("_")[1]
            if model_id_str.lower() == "none" or not model_id_str:
                logger.error(f"Некорректный ID модели в callback_data: {model_id_str}")
                await context.bot.send_message(
                    chat_id=user_id,
                    text="Ошибка: некорректный ID модели. Пожалуйста, выберите модель заново."
                )
                return
            
            model_id = int(model_id_str)
            logger.info(f"Пользователь {user_id} выбрал модель {model_id}")
            
            # Сохраняем ID модели
            self.state_manager.set_data(user_id, "model_id", model_id)
            
            # Устанавливаем состояние ввода промпта
            self.state_manager.set_state(user_id, UserState.ENTERING_PROMPT)
            logger.info(f"Установлено состояние ENTERING_PROMPT для пользователя {user_id}")
            
            # Создаем клавиатуру с кнопкой отмены
            keyboard = [
                [InlineKeyboardButton("❌ Отменить", callback_data="cancel_generation")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            # Важно: всегда сохраняем ID сообщения для последующего редактирования
            self.state_manager.set_data(user_id, "prompt_message_id", query.message.message_id)
            logger.info(f"Сохранен ID сообщения {query.message.message_id} для редактирования при вводе промпта")
            
            # Просим ввести промпт, редактируя текущее сообщение
            try:
                # Проверяем, есть ли caption в сообщении (это медиа-сообщение)
                if hasattr(query.message, 'caption') and query.message.caption is not None:
                    await query.edit_message_caption(
                        caption=ENTER_PROMPT_MESSAGE,
                        reply_markup=reply_markup
                    )
                    logger.info(f"Обновлена подпись с запросом промпта для пользователя {user_id}")
                else:
                    # Если caption нет, меняем текст
                    await query.edit_message_text(
                        text=ENTER_PROMPT_MESSAGE,
                        reply_markup=reply_markup
                    )
                    logger.info(f"Обновлен текст с запросом промпта для пользователя {user_id}")
            except Exception as e:
                logger.error(f"Ошибка при обновлении сообщения с запросом промпта: {e}", exc_info=True)
                try:
                    # Отправляем новое сообщение с запросом промпта только в случае ошибки
                    sent_message = await context.bot.send_message(
                        chat_id=user_id,
                        text=ENTER_PROMPT_MESSAGE,
                        reply_markup=reply_markup
                    )
                    # Обновляем ID сообщения
                    self.state_manager.set_data(user_id, "prompt_message_id", sent_message.message_id)
                    logger.info(f"Отправлено новое сообщение с ID {sent_message.message_id} для ввода промпта (резервный вариант)")
                except Exception as send_error:
                    logger.error(f"Не удалось отправить даже новое сообщение с запросом промпта: {send_error}", exc_info=True)
        except ValueError as e:
            logger.error(f"Ошибка при преобразовании ID модели: {e}", exc_info=True)
            await context.bot.send_message(
                chat_id=user_id,
                text="Ошибка: некорректный формат ID модели. Пожалуйста, выберите модель заново."
            )
        except Exception as e:
            logger.error(f"Неизвестная ошибка при обработке выбора модели: {e}", exc_info=True)
            await context.bot.send_message(
                chat_id=user_id,
                text=f"Произошла ошибка при выборе модели: {str(e)}. Пожалуйста, попробуйте еще раз."
            )
    
    async def _handle_start_generation(self, update: Update, context: ContextTypes.DEFAULT_TYPE, query, user_id: int) -> None:
        """
        Обработка запуска генерации изображений
        
        Args:
            update (Update): Объект обновления Telegram
            context (ContextTypes.DEFAULT_TYPE): Контекст Telegram
            query: Объект callback_query
            user_id (int): ID пользователя
        """
        logger.info(f"Пользователь {user_id} запустил генерацию изображений")
        
        # Получаем данные из состояния пользователя
        model_id = self.state_manager.get_data(user_id, "model_id")
        prompt = self.state_manager.get_data(user_id, "prompt")
        
        if not model_id or not prompt:
            logger.error(f"Не удалось получить model_id или prompt для пользователя {user_id}")
            
            # Сохраняем ID сообщения для последующего редактирования
            try:
                await query.edit_message_text(
                    text="❌ Ошибка: не удалось получить ID модели или промпт. Пожалуйста, начните генерацию заново с помощью кнопки ниже.",
                    reply_markup=create_main_keyboard()
                )
            except Exception as e:
                logger.error(f"Ошибка при обновлении сообщения об ошибке: {e}", exc_info=True)
            
            self.state_manager.reset_state(user_id)
            return
        
        # Создаем данные для запроса
        data = {
            "model_id": model_id,
            "prompt": prompt,
            "telegram_id": user_id,
            "num_images": 4  # Количество изображений для генерации
        }
        
        logger.info(f"Данные для генерации: model_id={model_id}, prompt='{prompt}', telegram_id={user_id}")
        
        # Редактируем текущее сообщение, показывая что запрос обрабатывается
        try:
            # Проверяем, есть ли caption в сообщении (это медиа-сообщение)
            if hasattr(query.message, 'caption') and query.message.caption is not None:
                await query.edit_message_caption(
                    caption="⏳ Отправка запроса на генерацию изображений...",
                    reply_markup=None
                )
            else:
                # Если caption нет, меняем текст
                await query.edit_message_text(
                    text="⏳ Отправка запроса на генерацию изображений...",
                    reply_markup=None
                )
        except Exception as e:
            logger.error(f"Ошибка при обновлении сообщения: {e}", exc_info=True)
        
        # Отправляем запрос на генерацию
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post('https://n8n2.supashkola.ru/webhook/generate_tg', json=data) as response:
                    if response.status == 200:
                        logger.info(f"Запрос на генерацию изображений для пользователя {user_id} успешно отправлен")
                        
                        # Создаем клавиатуру с кнопкой возврата в главное меню
                        keyboard = [
                            [InlineKeyboardButton("🔄 Начать сначала", callback_data="cmd_start")]
                        ]
                        reply_markup = InlineKeyboardMarkup(keyboard)
                        
                        success_message = (
                            "✅ Запрос на генерацию изображений успешно отправлен!\n\n"
                            "Мы уведомим вас, когда изображения будут готовы.\n\n"
                            "💫 Этот бот создан для креаторов и будет становиться лучше с каждым обновлением! "
                            "Скоро вы сможете создавать умопомрачительные видео, анимации и многое другое!"
                        )
                        
                        # Обновляем то же самое сообщение с информацией об успехе
                        try:
                            # Проверяем, есть ли caption в сообщении
                            if hasattr(query.message, 'caption') and query.message.caption is not None:
                                await query.edit_message_caption(
                                    caption=success_message,
                                    reply_markup=reply_markup
                                )
                            else:
                                # Если caption нет, меняем текст
                                await query.edit_message_text(
                                    text=success_message,
                                    reply_markup=reply_markup
                                )
                        except Exception as edit_err:
                            logger.error(f"Ошибка при обновлении сообщения: {edit_err}", exc_info=True)
                            
                    else:
                        response_text = await response.text()
                        logger.error(f"Ошибка при отправке запроса на генерацию: {response.status}, {response_text}")
                        
                        # Создаем клавиатуру с кнопкой повтора и возврата в меню
                        keyboard = [
                            [InlineKeyboardButton("🔄 Повторить", callback_data="start_generation")],
                            [InlineKeyboardButton("🔄 Начать сначала", callback_data="cmd_start")]
                        ]
                        reply_markup = InlineKeyboardMarkup(keyboard)
                        
                        error_message = f"❌ Произошла ошибка при отправке запроса на генерацию изображений. Пожалуйста, попробуйте еще раз."
                        
                        try:
                            # Проверяем, есть ли caption в сообщении
                            if hasattr(query.message, 'caption') and query.message.caption is not None:
                                await query.edit_message_caption(
                                    caption=error_message,
                                    reply_markup=reply_markup
                                )
                            else:
                                # Если caption нет, меняем текст
                                await query.edit_message_text(
                                    text=error_message,
                                    reply_markup=reply_markup
                                )
                        except Exception as edit_err:
                            logger.error(f"Ошибка при обновлении сообщения об ошибке: {edit_err}", exc_info=True)
        except Exception as e:
            logger.error(f"Исключение при отправке запроса на генерацию: {e}", exc_info=True)
            
            # Создаем клавиатуру с кнопкой повтора и возврата в меню
            keyboard = [
                [InlineKeyboardButton("🔄 Повторить", callback_data="start_generation")],
                [InlineKeyboardButton("🔄 Начать сначала", callback_data="cmd_start")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            error_message = f"❌ Произошла ошибка при отправке запроса на генерацию изображений. Пожалуйста, попробуйте еще раз."
            
            try:
                # Проверяем, есть ли caption в сообщении
                if hasattr(query.message, 'caption') and query.message.caption is not None:
                    await query.edit_message_caption(
                        caption=error_message,
                        reply_markup=reply_markup
                    )
                else:
                    # Если caption нет, меняем текст
                    await query.edit_message_text(
                        text=error_message,
                        reply_markup=reply_markup
                    )
            except Exception as edit_err:
                logger.error(f"Ошибка при обновлении сообщения об ошибке: {edit_err}", exc_info=True)
        
        # Сбрасываем состояние пользователя
        self.state_manager.reset_state(user_id)
    
    async def _handle_edit_prompt(self, update: Update, context: ContextTypes.DEFAULT_TYPE, query, user_id: int) -> None:
        """
        Обработка изменения промпта
        
        Args:
            update (Update): Объект обновления Telegram
            context (ContextTypes.DEFAULT_TYPE): Контекст Telegram
            query: Объект callback_query
            user_id (int): ID пользователя
        """
        logger.info(f"Пользователь {user_id} решил изменить промпт")
        
        # Устанавливаем состояние ввода промпта
        self.state_manager.set_state(user_id, UserState.ENTERING_PROMPT)
        
        # Создаем клавиатуру с кнопкой отмены
        keyboard = [
            [InlineKeyboardButton("❌ Отменить", callback_data="cancel_generation")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        # Важно: всегда сохраняем ID текущего сообщения для последующего редактирования
        self.state_manager.set_data(user_id, "prompt_message_id", query.message.message_id)
        logger.info(f"Сохранен ID сообщения {query.message.message_id} для редактирования при изменении промпта")
        
        # Отправляем сообщение с запросом нового промпта и сохраняем ID для последующего редактирования
        try:
            await query.edit_message_text(
                text="Пожалуйста, введите новый промпт для генерации изображений:",
                reply_markup=reply_markup
            )
            logger.info(f"Обновлено сообщение для ввода нового промпта пользователем {user_id}")
        except Exception as e:
            logger.error(f"Ошибка при обновлении сообщения с запросом нового промпта: {e}", exc_info=True)
            try:
                # Отправляем новое сообщение только в случае ошибки
                sent_message = await context.bot.send_message(
                    chat_id=user_id,
                    text="Пожалуйста, введите новый промпт для генерации изображений:",
                    reply_markup=reply_markup
                )
                # Обновляем ID сообщения
                self.state_manager.set_data(user_id, "prompt_message_id", sent_message.message_id)
                logger.info(f"Отправлено новое сообщение с ID {sent_message.message_id} для ввода нового промпта (резервный вариант)")
            except Exception as send_error:
                logger.error(f"Не удалось отправить даже новое сообщение с запросом нового промпта: {send_error}", exc_info=True)
    
    async def _handle_cancel_generation(self, update: Update, context: ContextTypes.DEFAULT_TYPE, query, user_id: int) -> None:
        """
        Обработка отмены генерации изображений
        
        Args:
            update (Update): Объект обновления Telegram
            context (ContextTypes.DEFAULT_TYPE): Контекст Telegram
            query: Объект callback_query
            user_id (int): ID пользователя
        """
        logger.info(f"Пользователь {user_id} отменил генерацию изображений")
        
        # Получаем chat_id
        chat_id = update.effective_chat.id if update.effective_chat else user_id
        
        # Сбрасываем состояние пользователя
        self.state_manager.reset_state(user_id)
        
        # Используем функцию для создания основной клавиатуры
        reply_markup = create_main_keyboard()
        
        cancel_message = "Генерация изображений отменена.\n\nВыберите действие:"
        
        # Отправляем сообщение об отмене и возвращаемся в главное меню
        edit_success = await self.edit_message(
            context=context,
            query=query,
            chat_id=chat_id,
            text=cancel_message,
            caption=cancel_message,
            reply_markup=reply_markup
        )
        
        if edit_success:
            logger.info(f"Обновлено сообщение с отменой генерации для пользователя {user_id}")
        else:
            # В случае ошибки отправляем новое сообщение
            try:
                await context.bot.send_message(
                    chat_id=chat_id,
                    text=cancel_message,
                    reply_markup=reply_markup
                )
                logger.info(f"Отправлено сообщение с отменой генерации пользователю {user_id}")
            except Exception as send_err:
                logger.error(f"Ошибка при отправке сообщения с отменой генерации: {send_err}", exc_info=True)
    
    async def _handle_model_type_selection(self, update: Update, context: ContextTypes.DEFAULT_TYPE, query, user_id: int, callback_data: str) -> None:
        """
        Обработка выбора типа модели
        
        Args:
            update (Update): Объект обновления Telegram
            context (ContextTypes.DEFAULT_TYPE): Контекст Telegram
            query: Объект callback_query
            user_id (int): ID пользователя
            callback_data (str): Данные callback-запроса
        """
        model_type = callback_data.split("_")[1]
        logger.info(f"Пользователь {user_id} выбрал тип модели: {model_type}")
        
        # Получаем chat_id
        chat_id = update.effective_chat.id if update.effective_chat else user_id
        self.state_manager.set_data(user_id, "chat_id", chat_id)
        
        # Сохраняем ID сообщения для последующего использования
        message_id = query.message.message_id
        self.state_manager.set_data(user_id, "base_message_id", message_id)
        logger.info(f"Сохранен base_message_id={message_id} для пользователя {user_id}")
        
        # Сохраняем тип модели
        self.state_manager.set_data(user_id, "model_type", model_type)
        
        # Меняем состояние на загрузку фотографий
        self.state_manager.set_state(user_id, UserState.UPLOADING_PHOTOS)
        
        # Создаем клавиатуру с кнопкой отмены
        keyboard = [
            [InlineKeyboardButton("❌ Отменить обучение", callback_data="cancel_training")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        # Редактируем сообщение с помощью нашей вспомогательной функции
        edit_success = await self.edit_message(
            context=context,
            query=query,
            chat_id=chat_id,
            text=UPLOAD_PHOTOS_MESSAGE,
            caption=UPLOAD_PHOTOS_MESSAGE,
            reply_markup=reply_markup
        )
        
        if edit_success:
            logger.info(f"Обновлено сообщение с инструкциями по загрузке фото для пользователя {user_id}")
        else:
            # В случае ошибки отправляем новое сообщение
            try:
                sent_message = await context.bot.send_photo(
                    chat_id=chat_id,
                    photo=INSTRUCTIONS_IMAGE_URL,
                    caption=UPLOAD_PHOTOS_MESSAGE,
                    reply_markup=reply_markup
                )
                # Сохраняем ID нового сообщения
                self.state_manager.set_data(user_id, "base_message_id", sent_message.message_id)
                logger.info(f"Отправлено новое фото с инструкциями пользователю {user_id}")
            except Exception as send_err:
                logger.error(f"Ошибка при отправке фото с инструкциями: {send_err}", exc_info=True)
                
                # Если и это не удалось, отправляем текстовое сообщение
                sent_message = await context.bot.send_message(
                    chat_id=chat_id,
                    text=UPLOAD_PHOTOS_MESSAGE,
                    reply_markup=reply_markup
                )
                # Сохраняем ID нового сообщения
                self.state_manager.set_data(user_id, "base_message_id", sent_message.message_id)
                logger.info(f"Отправлено текстовое сообщение с инструкциями пользователю {user_id}")
    
    async def _handle_start_training(self, update: Update, context: ContextTypes.DEFAULT_TYPE, query, user_id: int, callback_data: str) -> None:
        """
        Обработка запуска обучения модели после загрузки фотографий
        
        Args:
            update (Update): Объект обновления Telegram
            context (ContextTypes.DEFAULT_TYPE): Контекст Telegram
            query: Объект callback_query
            user_id (int): ID пользователя
            callback_data (str): Данные callback-запроса
        """
        media_group_id = callback_data.split("_")[2]
        logger.info(f"Пользователь {user_id} запустил обучение модели для медиагруппы {media_group_id}")
        
        # Проверяем, существует ли медиагруппа
        if media_group_id not in self.media_groups:
            logger.error(f"Медиагруппа {media_group_id} не найдена при попытке начать обучение")
            await context.bot.send_message(
                chat_id=user_id,
                text="Ошибка: информация о загруженных фотографиях не найдена. Пожалуйста, загрузите фотографии заново."
            )
            return
        
        # Получаем данные медиагруппы
        file_paths = self.media_groups[media_group_id]["file_paths"]
        status_message_id = self.media_groups[media_group_id]["status_message_id"]
        
        # Получаем модель и тип из состояния пользователя
        model_name = self.state_manager.get_data(user_id, "model_name")
        model_type = self.state_manager.get_data(user_id, "model_type")
        
        # Если нет данных, используем значения по умолчанию
        if not model_name:
            model_name = f"model_{user_id}_{datetime.now().strftime('%Y%m%d%H%M%S')}"
            logger.warning(f"Не найдено имя модели для пользователя {user_id}, используем сгенерированное: {model_name}")
            
        if not model_type:
            model_type = "default"
            logger.warning(f"Не найден тип модели для пользователя {user_id}, используем значение по умолчанию: {model_type}")
        
        # Формируем данные для отправки
        data = {
            "model_name": model_name,
            "model_type": model_type,
            "file_paths": file_paths,
            "telegram_id": user_id
        }
        
        logger.info(f"Отправка данных для обучения: модель '{model_name}', тип '{model_type}', файлов: {len(file_paths)}")
        
        # Обновляем статусное сообщение
        if status_message_id:
            try:
                await context.bot.edit_message_text(
                    chat_id=user_id,
                    message_id=status_message_id,
                    text=f"⏳ Отправка фотографий на сервер для обучения модели..."
                )
            except Exception as e:
                logger.error(f"Ошибка при обновлении статусного сообщения: {e}")
        
        # Отправляем данные на вебхук
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post('https://n8n2.supashkola.ru/webhook/start_finetune', json=data) as response:
                    if response.status == 200:
                        logger.info(f"Данные медиагруппы {media_group_id} успешно отправлены на вебхук: {len(file_paths)} фотографий")
                        
                        # Создаем кнопки для навигации
                        keyboard = [
                            [
                                InlineKeyboardButton("🏠 В главное меню", callback_data="cmd_start")
                            ]
                        ]
                        reply_markup = InlineKeyboardMarkup(keyboard)
                        
                        # Обновляем статусное сообщение, если оно существует
                        if status_message_id:
                            try:
                                await context.bot.edit_message_text(
                                    chat_id=user_id,
                                    message_id=status_message_id,
                                    text=f"✅ Все фотографии ({len(file_paths)}) успешно отправлены на сервер для обучения модели.\n\nМы уведомим вас, когда модель будет готова.",
                                    reply_markup=reply_markup
                                )
                            except Exception as e:
                                logger.error(f"Ошибка при обновлении статусного сообщения: {e}")
                                # Если не удалось обновить статусное сообщение, отправляем новое
                                try:
                                    await context.bot.send_message(
                                        chat_id=user_id,
                                        text=f"✅ Все фотографии ({len(file_paths)}) успешно отправлены на сервер для обучения модели.\n\nМы уведомим вас, когда модель будет готова.",
                                        reply_markup=reply_markup
                                    )
                                except Exception as send_error:
                                    logger.error(f"Не удалось отправить сообщение об успехе: {send_error}")
                        else:
                            # Если нет статусного сообщения, отправляем новое
                            try:
                                await context.bot.send_message(
                                    chat_id=user_id,
                                    text=f"✅ Все фотографии ({len(file_paths)}) успешно отправлены на сервер для обучения модели.\n\nМы уведомим вас, когда модель будет готова.",
                                    reply_markup=reply_markup
                                )
                            except Exception as send_error:
                                logger.error(f"Не удалось отправить сообщение об успехе: {send_error}")
                    else:
                        logger.error(f"Ошибка при отправке данных медиагруппы на вебхук: {response.status}")
                        
                        # Обновляем статусное сообщение
                        if status_message_id:
                            try:
                                # Восстанавливаем кнопки для повторной попытки
                                keyboard = [
                                    [
                                        InlineKeyboardButton("✅ Повторить попытку", callback_data=f"start_training_{media_group_id}"),
                                        InlineKeyboardButton("🔄 Загрузить фото заново", callback_data="cmd_train")
                                    ],
                                    [
                                        InlineKeyboardButton("🔄 Начать сначала", callback_data="cmd_start")
                                    ]
                                ]
                                reply_markup = InlineKeyboardMarkup(keyboard)
                                
                                await context.bot.edit_message_text(
                                    chat_id=user_id,
                                    message_id=status_message_id,
                                    text=f"❌ Ошибка при отправке фотографий на сервер. Пожалуйста, попробуйте снова.",
                                    reply_markup=reply_markup
                                )
                            except Exception as e:
                                logger.error(f"Ошибка при обновлении статусного сообщения: {e}")
        except Exception as e:
            logger.error(f"Исключение при отправке данных медиагруппы на вебхук: {e}")
            
            # Обновляем статусное сообщение
            if status_message_id:
                try:
                    # Восстанавливаем кнопки для повторной попытки
                    keyboard = [
                        [
                            InlineKeyboardButton("✅ Повторить попытку", callback_data=f"start_training_{media_group_id}"),
                            InlineKeyboardButton("🔄 Загрузить фото заново", callback_data="cmd_train")
                        ],
                        [
                            InlineKeyboardButton("🔄 Начать сначала", callback_data="cmd_start")
                        ]
                    ]
                    reply_markup = InlineKeyboardMarkup(keyboard)
                    
                    await context.bot.edit_message_text(
                        chat_id=user_id,
                        message_id=status_message_id,
                        text=f"❌ Произошла ошибка при обработке фотографий: {str(e)}",
                        reply_markup=reply_markup
                    )
                except Exception as edit_error:
                    logger.error(f"Ошибка при обновлении статусного сообщения: {edit_error}")
    
    async def _handle_cancel_training(self, update: Update, context: ContextTypes.DEFAULT_TYPE, query, user_id: int) -> None:
        """
        Обработка отмены обучения модели
        
        Args:
            update (Update): Объект обновления Telegram
            context (ContextTypes.DEFAULT_TYPE): Контекст Telegram
            query: Объект callback_query
            user_id (int): ID пользователя
        """
        logger.info(f"Пользователь {user_id} отменил обучение модели")
        
        # Сбрасываем состояние пользователя
        self.state_manager.reset_state(user_id)
        
        # Используем функцию для создания основной клавиатуры
        reply_markup = create_main_keyboard()
        
        # Отправляем сообщение об отмене и возвращаемся в главное меню
        try:
            # Проверяем, есть ли caption в сообщении
            if hasattr(query.message, 'caption') and query.message.caption is not None:
                await query.edit_message_caption(
                    caption="Обучение модели отменено.\n\nВыберите действие:",
                    reply_markup=reply_markup
                )
            else:
                # Если caption нет, меняем текст
                await query.edit_message_text(
                    text="Обучение модели отменено.\n\nВыберите действие:",
                    reply_markup=reply_markup
                )
            logger.info(f"Обновлено сообщение с отменой обучения для пользователя {user_id}")
        except Exception as e:
            logger.error(f"Ошибка при обновлении сообщения с отменой обучения: {e}", exc_info=True)
            
            # В случае ошибки отправляем новое сообщение
            try:
                await context.bot.send_message(
                    chat_id=user_id,
                    text="Обучение модели отменено.\n\nВыберите действие:",
                    reply_markup=reply_markup
                )
                logger.info(f"Отправлено сообщение с отменой обучения пользователю {user_id}")
            except Exception as send_err:
                logger.error(f"Ошибка при отправке сообщения с отменой обучения: {send_err}", exc_info=True)
    
    async def _handle_cmd_video(self, update: Update, context: ContextTypes.DEFAULT_TYPE, query, user_id: int) -> None:
        """
        Обработка команды video из callback
        
        Args:
            update (Update): Объект обновления Telegram
            context (ContextTypes.DEFAULT_TYPE): Контекст Telegram
            query: Объект callback_query
            user_id (int): ID пользователя
        """
        logger.info(f"Начинаю обработку команды video из callback для пользователя {user_id}")
        
        message = "🎬 Функция создания видео находится в разработке.\n\nМы сообщим вам, когда эта функция станет доступна!"
        
        # Создаем клавиатуру с кнопкой "Начать сначала"
        keyboard = [
            [InlineKeyboardButton("🔄 Начать сначала", callback_data="cmd_start")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        # Пробуем изменить текущее сообщение
        try:
            # Проверяем, есть ли caption в сообщении
            if hasattr(query.message, 'caption') and query.message.caption is not None:
                await query.edit_message_caption(
                    caption=message,
                    reply_markup=reply_markup
                )
            else:
                # Если caption нет, меняем текст
                await query.edit_message_text(
                    text=message,
                    reply_markup=reply_markup
                )
            logger.info(f"Обновлено сообщение с информацией о video-функции для пользователя {user_id}")
        except Exception as e:
            logger.error(f"Ошибка при обновлении сообщения с информацией о video-функции: {e}", exc_info=True)
            
            # Если не получилось изменить текущее сообщение, отправляем новое
            try:
                await context.bot.send_photo(
                    chat_id=user_id,
                    photo=WELCOME_IMAGE_URL,
                    caption=message,
                    reply_markup=reply_markup
                )
                logger.info(f"Отправлена информация о video-функции пользователю {user_id}")
            except Exception as send_err:
                logger.error(f"Ошибка при отправке информации о video-функции: {send_err}", exc_info=True)
                # Если не удалось отправить фото, отправляем текстовое сообщение
                await context.bot.send_message(
                    chat_id=user_id,
                    text=message,
                    reply_markup=reply_markup
                )

    async def _handle_video_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE, query, user_id: int) -> None:
        """
        Обработка команды создания видео
        
        Args:
            update (Update): Объект обновления Telegram
            context (ContextTypes.DEFAULT_TYPE): Контекст Telegram
            query: Объект callback_query
            user_id (int): ID пользователя
        """
        logger.info(f"Пользователь {user_id} запросил создание видео")
        
        # Сбрасываем предыдущее состояние
        self.state_manager.reset_state(user_id)
        self.state_manager.set_state(user_id, UserState.SELECTING_MODEL_FOR_VIDEO)
        
        # Получаем модели пользователя через API запрос
        try:
            data = {"telegram_id": user_id}
            async with aiohttp.ClientSession() as session:
                async with session.post('https://n8n2.supashkola.ru/webhook/my_models', json=data) as response:
                    if response.status == 200:
                        models = await response.json()
                        logger.info(f"Получены модели пользователя {user_id} через API: {len(models)} моделей")
                    else:
                        logger.error(f"Ошибка при получении моделей через API: {response.status}")
                        models = []
        except Exception as e:
            logger.error(f"Исключение при получении моделей через API: {e}", exc_info=True)
            models = []
        
        if not models:
            # Отправляем сообщение об отсутствии моделей
            try:
                await query.edit_message_text(
                    text="У вас пока нет обученных моделей. Сначала создайте модель с помощью команды 'Обучить модель'.",
                    reply_markup=create_main_keyboard()
                )
            except Exception as e:
                logger.error(f"Ошибка при редактировании сообщения: {e}", exc_info=True)
                # В случае ошибки отправляем новое сообщение
                try:
                    await context.bot.send_message(
                        chat_id=user_id,
                        text="У вас пока нет обученных моделей. Сначала создайте модель с помощью команды 'Обучить модель'.",
                        reply_markup=create_main_keyboard()
                    )
                except Exception as send_err:
                    logger.error(f"Ошибка при отправке сообщения: {send_err}", exc_info=True)
            return
        
        # Формируем клавиатуру для выбора модели
        keyboard = []
        for model in models:
            model_name = model.get("name", f"Модель #{model.get('model_id', 'без ID')}")
            model_id = model.get("model_id", "unknown")
            keyboard.append([InlineKeyboardButton(model_name, callback_data=f"videomodel_{model_id}")])
        
        # Добавляем кнопку отмены
        keyboard.append([InlineKeyboardButton("❌ Отменить", callback_data="cancel_video")])
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        # Отправляем сообщение с выбором модели
        try:
            await query.edit_message_text(
                text="Выберите модель для создания видео:",
                reply_markup=reply_markup
            )
            logger.info(f"Отправлен список моделей для видео пользователю {user_id}")
        except Exception as e:
            logger.error(f"Ошибка при редактировании сообщения: {e}", exc_info=True)
            try:
                await context.bot.send_message(
                    chat_id=user_id, 
                    text="Выберите модель для создания видео:",
                    reply_markup=reply_markup
                )
            except Exception as send_err:
                logger.error(f"Ошибка при отправке сообщения с моделями: {send_err}", exc_info=True)

    async def _handle_video_model_selection(self, update: Update, context: ContextTypes.DEFAULT_TYPE, query, user_id: int, callback_data: str) -> None:
        """
        Обработка выбора модели для создания видео
        
        Args:
            update (Update): Объект обновления Telegram
            context (ContextTypes.DEFAULT_TYPE): Контекст Telegram
            query: Объект callback_query
            user_id (int): ID пользователя
            callback_data (str): Данные callback-запроса, содержащие ID модели
        """
        try:
            model_id_str = callback_data.split("_")[1]
            model_id = int(model_id_str)
            logger.info(f"Пользователь {user_id} выбрал модель {model_id} для создания видео")
            
            # Сохраняем ID модели
            self.state_manager.set_data(user_id, "video_model_id", model_id)
            
            # Отправляем запрос для получения изображений
            try:
                data = {"telegram_id": user_id, "model_id": model_id}
                async with aiohttp.ClientSession() as session:
                    async with session.post('https://n8n2.supashkola.ru/webhook/my_imgs', json=data) as response:
                        if response.status == 200:
                            images = await response.json()
                            logger.info(f"Получены изображения для пользователя {user_id}, модель {model_id}: {len(images)} изображений")
                            
                            if not images:
                                # Нет изображений для выбранной модели
                                await query.edit_message_text(
                                    text="У выбранной модели нет сгенерированных изображений. Сначала создайте изображения с этой моделью.",
                                    reply_markup=create_main_keyboard()
                                )
                                self.state_manager.reset_state(user_id)
                                return
                            
                            # Сохраняем список изображений и текущий индекс
                            self.state_manager.set_data(user_id, "video_images", images)
                            self.state_manager.set_data(user_id, "video_current_image_index", 0)
                            
                            # Устанавливаем состояние выбора изображения
                            self.state_manager.set_state(user_id, UserState.SELECTING_IMAGE_FOR_VIDEO)
                            
                            # Показываем первое изображение с кнопками навигации
                            await self._show_image_selection(context, query, user_id, images, 0)
                        else:
                            logger.error(f"Ошибка при получении изображений через API: {response.status}")
                            await query.edit_message_text(
                                text="Произошла ошибка при получении изображений. Пожалуйста, попробуйте позже.",
                                reply_markup=create_main_keyboard()
                            )
                            self.state_manager.reset_state(user_id)
            except Exception as e:
                logger.error(f"Исключение при получении изображений: {e}", exc_info=True)
                
                # Создаем клавиатуру с кнопкой сброса бота
                keyboard = [
                    [InlineKeyboardButton("🔄 Начать сначала", callback_data="cmd_start")]
                ]
                reply_markup = InlineKeyboardMarkup(keyboard)
                
                await query.edit_message_text(
                    text="Произошла ошибка при получении изображений. Пожалуйста, попробуйте позже.",
                    reply_markup=reply_markup
                )
                self.state_manager.reset_state(user_id)
        except (ValueError, IndexError) as e:
            logger.error(f"Ошибка при обработке ID модели: {e}", exc_info=True)
            
            # Создаем клавиатуру с кнопкой сброса бота
            keyboard = [
                [InlineKeyboardButton("🔄 Начать сначала", callback_data="cmd_start")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await query.edit_message_text(
                text="Ошибка при выборе модели. Пожалуйста, попробуйте снова.",
                reply_markup=reply_markup
            )
            self.state_manager.reset_state(user_id)

    async def _show_image_selection(self, context: ContextTypes.DEFAULT_TYPE, query, user_id: int, images: list, current_index: int) -> None:
        """
        Показывает изображение с кнопками навигации
        
        Args:
            context (ContextTypes.DEFAULT_TYPE): Контекст Telegram
            query: Объект callback_query
            user_id (int): ID пользователя
            images (list): Список URL изображений
            current_index (int): Текущий индекс изображения
        """
        # Убедимся, что индекс в допустимых пределах
        if current_index < 0:
            current_index = len(images) - 1
        elif current_index >= len(images):
            current_index = 0
        
        # Создаем клавиатуру с кнопками навигации и создания видео
        keyboard = [
            [
                InlineKeyboardButton("⬅️", callback_data="vidimg_prev"),
                InlineKeyboardButton(f"{current_index + 1}/{len(images)}", callback_data="vidimg_info"),
                InlineKeyboardButton("➡️", callback_data="vidimg_next")
            ],
            [InlineKeyboardButton("🎬 Оживить меня в видео!", callback_data="start_video_generation")],
            [InlineKeyboardButton("❌ Отменить", callback_data="cancel_video")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        # Получаем URL текущего изображения
        image_url = images[current_index]
        self.state_manager.set_data(user_id, "video_current_image_index", current_index)
        self.state_manager.set_data(user_id, "video_current_image_url", image_url)
        
        caption = f"Просмотр изображения {current_index + 1} из {len(images)}.\nВыберите изображение для создания видео или нажмите на кнопки навигации для просмотра других изображений."
        
        try:
            # Проверяем, существует ли сообщение для редактирования
            message_id = self.state_manager.get_data(user_id, "video_image_message_id")
            
            if message_id and query:
                # Редактируем существующее сообщение
                from telegram import InputMediaPhoto
                await context.bot.edit_message_media(
                    chat_id=user_id,
                    message_id=message_id,
                    media=InputMediaPhoto(
                        media=image_url,
                        caption=caption
                    ),
                    reply_markup=reply_markup
                )
            else:
                # Первая отправка сообщения с изображением
                sent_message = await context.bot.send_photo(
                    chat_id=user_id,
                    photo=image_url,
                    caption=caption,
                    reply_markup=reply_markup
                )
                # Сохраняем ID сообщения для последующего редактирования
                self.state_manager.set_data(user_id, "video_image_message_id", sent_message.message_id)
        except Exception as e:
            logger.error(f"Ошибка при отправке/редактировании изображения: {e}", exc_info=True)
            try:
                # В случае ошибки отправляем текстовое сообщение
                sent_message = await context.bot.send_message(
                    chat_id=user_id,
                    text=f"Ошибка при загрузке изображения. URL: {image_url}\nПожалуйста, попробуйте выбрать другое изображение.",
                    reply_markup=reply_markup
                )
                self.state_manager.set_data(user_id, "video_image_message_id", sent_message.message_id)
            except Exception as send_err:
                logger.error(f"Ошибка при отправке сообщения об ошибке: {send_err}", exc_info=True)

    async def _handle_image_navigation(self, update: Update, context: ContextTypes.DEFAULT_TYPE, query, user_id: int, direction: str) -> None:
        """
        Обработка навигации по изображениям (предыдущее/следующее)
        
        Args:
            update (Update): Объект обновления Telegram
            context (ContextTypes.DEFAULT_TYPE): Контекст Telegram
            query: Объект callback_query
            user_id (int): ID пользователя
            direction (str): Направление навигации ('prev' или 'next')
        """
        # Получаем список изображений и текущий индекс
        images = self.state_manager.get_data(user_id, "video_images")
        current_index = self.state_manager.get_data(user_id, "video_current_image_index")
        
        if not images or current_index is None:
            logger.error(f"Не найдены данные о изображениях для пользователя {user_id}")
            
            # Создаем клавиатуру с кнопкой сброса бота
            keyboard = [
                [InlineKeyboardButton("🔄 Начать сначала", callback_data="cmd_start")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await query.edit_message_text(
                text="Ошибка при навигации по изображениям. Пожалуйста, начните заново.",
                reply_markup=reply_markup
            )
            self.state_manager.reset_state(user_id)
            return
        
        # Определяем новый индекс
        if direction == "prev":
            new_index = current_index - 1
            if new_index < 0:
                new_index = len(images) - 1
        else:  # next
            new_index = current_index + 1
            if new_index >= len(images):
                new_index = 0
        
        # Показываем изображение с новым индексом
        await self._show_image_selection(context, query, user_id, images, new_index)

    async def _handle_start_video_generation(self, update: Update, context: ContextTypes.DEFAULT_TYPE, query, user_id: int) -> None:
        """
        Обработка запуска генерации видео
        
        Args:
            update (Update): Объект обновления Telegram
            context (ContextTypes.DEFAULT_TYPE): Контекст Telegram
            query: Объект callback_query
            user_id (int): ID пользователя
        """
        # Получаем URL выбранного изображения
        image_url = self.state_manager.get_data(user_id, "video_current_image_url")
        model_id = self.state_manager.get_data(user_id, "video_model_id")
        
        if not image_url or not model_id:
            logger.error(f"Не найдены данные о выбранном изображении для пользователя {user_id}")
            
            # Создаем клавиатуру с кнопкой сброса бота
            keyboard = [
                [InlineKeyboardButton("🔄 Начать сначала", callback_data="cmd_start")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await query.edit_message_caption(
                caption="Ошибка: не найдена информация о выбранном изображении. Пожалуйста, попробуйте выбрать изображение заново.",
                reply_markup=reply_markup
            )
            self.state_manager.reset_state(user_id)
            return
        
        logger.info(f"Пользователь {user_id} запустил генерацию видео для изображения {image_url}")
        
        # Создаем данные для запроса
        data = {
            "image_url": image_url,
            "telegram_id": user_id,
            "model_id": model_id
        }
        
        # Создаем клавиатуру с кнопкой возврата в главное меню
        keyboard = [
            [InlineKeyboardButton("🔄 Начать сначала", callback_data="cmd_start")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        # Отправляем запрос на генерацию видео
        try:
            # Сначала редактируем сообщение, чтобы показать процесс
            await query.edit_message_caption(
                caption="⏳ Отправка запроса на генерацию видео...",
                reply_markup=None
            )
            
            # Отправляем запрос
            async with aiohttp.ClientSession() as session:
                async with session.post('https://n8n2.supashkola.ru/webhook/gen_vid', json=data) as response:
                    if response.status == 200:
                        logger.info(f"Запрос на генерацию видео для пользователя {user_id} успешно отправлен")
                        
                        success_message = (
                            "✅ Запрос на генерацию видео успешно отправлен!\n\n"
                            "Мы уведомим вас, когда видео будет готово.\n\n"
                            "💫 Этот бот создан для креаторов и будет становиться лучше с каждым обновлением!"
                        )
                        
                        await query.edit_message_caption(
                            caption=success_message,
                            reply_markup=reply_markup
                        )
                    else:
                        response_text = await response.text()
                        logger.error(f"Ошибка при отправке запроса на генерацию видео: {response.status}, {response_text}")
                        
                        error_message = f"❌ Произошла ошибка при отправке запроса на генерацию видео. Пожалуйста, попробуйте еще раз."
                        
                        # Создаем клавиатуру с кнопкой повтора
                        keyboard = [
                            [InlineKeyboardButton("🔄 Повторить", callback_data="cmd_video")],
                            [InlineKeyboardButton("🔄 Начать сначала", callback_data="cmd_start")]
                        ]
                        error_reply_markup = InlineKeyboardMarkup(keyboard)
                        
                        await query.edit_message_caption(
                            caption=error_message,
                            reply_markup=error_reply_markup
                        )
        except Exception as e:
            logger.error(f"Исключение при отправке запроса на генерацию видео: {e}", exc_info=True)
            
            # Создаем клавиатуру с кнопкой повтора
            keyboard = [
                [InlineKeyboardButton("🔄 Повторить", callback_data="cmd_video")],
                [InlineKeyboardButton("🔄 Начать сначала", callback_data="cmd_start")]
            ]
            error_reply_markup = InlineKeyboardMarkup(keyboard)
            
            try:
                await query.edit_message_caption(
                    caption=f"❌ Произошла ошибка при отправке запроса на генерацию видео: {str(e)}. Пожалуйста, попробуйте еще раз.",
                    reply_markup=error_reply_markup
                )
            except Exception as edit_err:
                logger.error(f"Ошибка при редактировании сообщения: {edit_err}", exc_info=True)
        
        # Сбрасываем состояние пользователя
        self.state_manager.reset_state(user_id)

    async def _handle_cancel_video(self, update: Update, context: ContextTypes.DEFAULT_TYPE, query, user_id: int) -> None:
        """
        Обработка отмены создания видео
        
        Args:
            update (Update): Объект обновления Telegram
            context (ContextTypes.DEFAULT_TYPE): Контекст Telegram
            query: Объект callback_query
            user_id (int): ID пользователя
        """
        from config import WELCOME_MESSAGE, WELCOME_IMAGE_URL  # Локальный импорт для избежания ошибки
        
        logger.info(f"Пользователь {user_id} отменил создание видео")
        
        # Очищаем ID сообщения с изображением
        self.state_manager.clear_data(user_id, "video_image_message_id")
        
        # Сбрасываем состояние пользователя
        self.state_manager.reset_state(user_id)
        
        # Используем функцию для создания основной клавиатуры
        reply_markup = create_main_keyboard()
        
        # Отправляем сообщение об отмене и возвращаемся в главное меню
        try:
            # Проверяем, есть ли caption в сообщении
            if hasattr(query.message, 'caption') and query.message.caption is not None:
                await query.edit_message_caption(
                    caption="Создание видео отменено.\n\nВыберите действие:",
                    reply_markup=reply_markup
                )
            else:
                # Если caption нет, меняем текст
                await query.edit_message_text(
                    text="Создание видео отменено.\n\nВыберите действие:",
                    reply_markup=reply_markup
                )
            logger.info(f"Обновлено сообщение для пользователя {user_id} после отмены создания видео")
        except Exception as e:
            logger.error(f"Ошибка при обновлении сообщения отмены: {e}", exc_info=True)
            # В случае ошибки отправляем новое сообщение с меню
            try:
                # Локальный импорт для избежания ошибки
                from config import WELCOME_MESSAGE, WELCOME_IMAGE_URL
                
                await context.bot.send_photo(
                    chat_id=user_id,
                    photo=WELCOME_IMAGE_URL,
                    caption=WELCOME_MESSAGE,
                    reply_markup=reply_markup
                )
                logger.info(f"Отправлено новое welcome сообщение пользователю {user_id}")
            except Exception as send_err:
                logger.error(f"Ошибка при отправке нового welcome сообщения: {send_err}", exc_info=True)

    async def edit_message(self, context: ContextTypes.DEFAULT_TYPE, query, chat_id: int, 
                          text: Optional[str] = None, caption: Optional[str] = None,
                          reply_markup = None, parse_mode = ParseMode.HTML) -> bool:
        """
        Редактирует сообщение через context.bot вместо query напрямую
        
        Args:
            context (ContextTypes.DEFAULT_TYPE): Контекст Telegram
            query: Объект callback_query
            chat_id (int): ID чата для отправки сообщений
            text (Optional[str]): Текст сообщения для редактирования (для текстовых сообщений)
            caption (Optional[str]): Подпись сообщения для редактирования (для сообщений с медиа)
            reply_markup: Разметка клавиатуры
            parse_mode: Режим форматирования текста (по умолчанию HTML)
            
        Returns:
            bool: True если редактирование успешно, False в случае ошибки
        """
        try:
            message_id = query.message.message_id
            
            # Проверяем, есть ли caption в сообщении
            if caption is not None and hasattr(query.message, 'caption'):
                await context.bot.edit_message_caption(
                    chat_id=chat_id,
                    message_id=message_id,
                    caption=caption,
                    parse_mode=parse_mode,
                    reply_markup=reply_markup
                )
                return True
            elif text is not None:
                # Редактируем текст
                await context.bot.edit_message_text(
                    chat_id=chat_id,
                    message_id=message_id,
                    text=text,
                    parse_mode=parse_mode,
                    reply_markup=reply_markup
                )
                return True
            else:
                # Редактируем только разметку клавиатуры
                await context.bot.edit_message_reply_markup(
                    chat_id=chat_id,
                    message_id=message_id,
                    reply_markup=reply_markup
                )
                return True
        except Exception as e:
            logger.warning(f"Ошибка при редактировании сообщения: {e}")
            return False