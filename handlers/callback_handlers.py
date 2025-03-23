from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
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
        else:
            # Неизвестный callback
            logger.warning(f"Получен неизвестный callback от пользователя {user_id}: {callback_data}")
            try:
                await query.answer("Неизвестная команда")
            except Exception as e:
                logger.error(f"Ошибка при ответе на неизвестный callback: {e}", exc_info=True)
    
    async def _handle_command_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE, query, user_id: int, callback_data: str) -> None:
        """
        Обработка callback-команд (cmd_*)
        
        Args:
            update (Update): Объект обновления Telegram
            context (ContextTypes.DEFAULT_TYPE): Контекст Telegram
            query: Объект callback_query
            user_id (int): ID пользователя
            callback_data (str): Данные callback-запроса
        """
        # Обработка команд из кнопок
        command = callback_data.split("_")[1]
        
        logger.info(f"Обработка команды из callback: {command} для пользователя {user_id}")
        
        try:
            if command == "train":
                await self._handle_cmd_train(update, context, query, user_id)
            elif command == "start":
                await self._handle_cmd_start(update, context, query, user_id)
            elif command == "generate":
                await self._handle_cmd_generate(update, context, query, user_id)
            elif command == "credits":
                await self._handle_cmd_credits(update, context, query, user_id)
            elif command == "models":
                await self._handle_cmd_models(update, context, query, user_id)
            elif command == "video":
                await self._handle_cmd_video(update, context, query, user_id)
            else:
                logger.warning(f"Неизвестная команда в callback: {command}")
                await query.answer(f"Неизвестная команда: {command}")
        except Exception as e:
            logger.error(f"Ошибка при обработке callback команды {command}: {e}", exc_info=True)
            try:
                await context.bot.send_message(
                    chat_id=user_id,
                    text=f"❌ Произошла ошибка при выполнении команды. "
                )
            except Exception as send_error:
                logger.error(f"Не удалось отправить сообщение об ошибке: {send_error}", exc_info=True)
    
    async def _handle_cmd_train(self, update: Update, context: ContextTypes.DEFAULT_TYPE, query, user_id: int) -> None:
        """
        Обработка команды train из callback
        
        Args:
            update (Update): Объект обновления Telegram
            context (ContextTypes.DEFAULT_TYPE): Контекст Telegram
            query: Объект callback_query
            user_id (int): ID пользователя
        """
        logger.info(f"Начинаю обработку команды train из callback для пользователя {user_id}")
        
        # Создаем клавиатуру с кнопкой отмены
        keyboard = [
            [InlineKeyboardButton("❌ Отменить обучение", callback_data="cancel_training")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        # Устанавливаем состояние ввода имени модели
        self.state_manager.set_state(user_id, UserState.ENTERING_MODEL_NAME)
        self.state_manager.clear_data(user_id)
        logger.info(f"Установлено состояние ENTERING_MODEL_NAME для пользователя {user_id}")
        
        # Пробуем изменить текущее сообщение
        try:
            await query.edit_message_caption(
                caption="📝 Введите имя для вашей модели (например, 'Моя фотосессия'):",
                reply_markup=reply_markup
            )
            logger.info(f"Обновлено сообщение для пользователя {user_id}")
        except Exception as e:
            logger.error(f"Ошибка при обновлении сообщения: {e}", exc_info=True)
            # В случае ошибки отправляем новое сообщение
            await context.bot.send_message(
                chat_id=user_id,
                text="📝 Введите имя для вашей модели (например, 'Моя фотосессия'):",
                reply_markup=reply_markup
            )
            logger.info(f"Отправлен запрос имени модели пользователю {user_id}")
    
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
            try:
                await query.edit_message_caption(
                    caption="У вас пока нет обученных моделей. Используйте команду /train, чтобы обучить новую модель."
                )
                logger.info(f"Обновлено сообщение для пользователя {user_id} - нет моделей")
            except Exception as e:
                logger.error(f"Ошибка при обновлении сообщения: {e}", exc_info=True)
                await context.bot.send_message(
                    chat_id=user_id,
                    text="У вас пока нет обученных моделей. Используйте команду /train, чтобы обучить новую модель."
                )
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
        
        # Пробуем изменить текущее сообщение
        try:
            await query.edit_message_caption(
                caption="Выберите модель для генерации изображений:",
                reply_markup=reply_markup
            )
            logger.info(f"Обновлено сообщение для выбора модели пользователем {user_id}")
        except Exception as e:
            logger.error(f"Ошибка при обновлении сообщения для выбора модели: {e}", exc_info=True)
            
            # Если не получилось изменить текущее сообщение, отправляем новое
            try:
                await context.bot.send_photo(
                    chat_id=user_id,
                    photo=WELCOME_IMAGE_URL,
                    caption="Выберите модель для генерации изображений:",
                    reply_markup=reply_markup
                )
                logger.info(f"Отправлен список моделей пользователю {user_id}")
            except Exception as send_err:
                logger.error(f"Ошибка при отправке списка моделей: {send_err}", exc_info=True)
                # Если не удалось отправить фото, отправляем текстовое сообщение
                await context.bot.send_message(
                    chat_id=user_id,
                    text="Выберите модель для генерации изображений:",
                    reply_markup=reply_markup
                )
    
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
                  f"Каждое обучение модели стоит 1 кредит.\n" \
                  f"Каждая генерация изображений стоит 1 кредит."
        
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
            
            # Просим ввести промпт, проверяя тип сообщения
            try:
                # Проверяем, есть ли caption в сообщении (это медиа-сообщение)
                if hasattr(query.message, 'caption') and query.message.caption is not None:
                    sent_message = await query.edit_message_caption(
                        caption=ENTER_PROMPT_MESSAGE,
                        reply_markup=reply_markup
                    )
                    # Сохраняем ID сообщения для последующего редактирования
                    self.state_manager.set_data(user_id, "prompt_message_id", query.message.message_id)
                    logger.info(f"Обновлена подпись с запросом промпта для пользователя {user_id}")
                else:
                    # Если caption нет, меняем текст
                    sent_message = await query.edit_message_text(
                        text=ENTER_PROMPT_MESSAGE,
                        reply_markup=reply_markup
                    )
                    # Сохраняем ID сообщения для последующего редактирования
                    self.state_manager.set_data(user_id, "prompt_message_id", query.message.message_id)
                    logger.info(f"Отправлен запрос на ввод промпта пользователю {user_id}")
            except Exception as e:
                logger.error(f"Ошибка при обновлении сообщения с запросом промпта: {e}", exc_info=True)
                try:
                    # Отправляем новое сообщение с запросом промпта
                    sent_message = await context.bot.send_message(
                        chat_id=user_id,
                        text=ENTER_PROMPT_MESSAGE,
                        reply_markup=reply_markup
                    )
                    # Сохраняем ID нового сообщения
                    self.state_manager.set_data(user_id, "prompt_message_id", sent_message.message_id)
                    logger.info(f"Отправлено новое сообщение с запросом промпта пользователю {user_id}")
                except Exception as send_error:
                    logger.error(f"Не удалось отправить сообщение с запросом промпта: {send_error}", exc_info=True)
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
            await context.bot.send_message(
                chat_id=user_id,
                text="Ошибка: не удалось получить ID модели или промпт. Пожалуйста, начните генерацию заново с помощью команды /generate.")
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
        
        # Отправляем статусное сообщение
        try:
            await query.edit_message_text("⏳ Отправка запроса на генерацию изображений...")
            status_message = await context.bot.send_message(
                chat_id=user_id,
                text="⏳ Отправка запроса на генерацию изображений..."
            )
        except Exception as e:
            logger.error(f"Ошибка при отправке статусного сообщения: {e}", exc_info=True)
            status_message = await context.bot.send_message(
                chat_id=user_id,
                text="⏳ Отправка запроса на генерацию изображений..."
            )
        
        # Отправляем запрос на генерацию
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post('https://n8n2.supashkola.ru/webhook/generate_tg', json=data) as response:
                    response_text = await response.text()
                    if response.status == 200:
                        logger.info(f"Запрос на генерацию изображений для пользователя {user_id} успешно отправлен")
                        try:
                            response_data = await response.json()
                            prompt_id = response_data.get("prompt_id", "unknown")
                            logger.info(f"Получен ID промпта: {prompt_id}")
                            
                            # Обновляем статусное сообщение
                            await context.bot.edit_message_text(
                                chat_id=user_id,
                                message_id=status_message.message_id,
                                text=f"✅ Запрос на генерацию изображений успешно отправлен! ID промпта: {prompt_id}\n\nМы уведомим вас, когда изображения будут готовы."
                            )
                        except json.JSONDecodeError:
                            logger.error(f"Не удалось декодировать JSON-ответ: {response_text}")
                            await context.bot.edit_message_text(
                                chat_id=user_id,
                                message_id=status_message.message_id,
                                text="✅ Запрос на генерацию изображений успешно отправлен!\n\nМы уведомим вас, когда изображения будут готовы."
                            )
                    else:
                        logger.error(f"Ошибка при отправке запроса на генерацию: {response.status}, {response_text}")
                        await context.bot.edit_message_text(
                            chat_id=user_id,
                            message_id=status_message.message_id,
                            text=f"❌ Произошла ошибка при отправке запроса на генерацию изображений: {response.status}. Пожалуйста, попробуйте еще раз."
                        )
        except Exception as e:
            logger.error(f"Исключение при отправке запроса на генерацию: {e}", exc_info=True)
            await context.bot.edit_message_text(
                chat_id=user_id,
                message_id=status_message.message_id,
                text=f"❌ Произошла ошибка при отправке запроса на генерацию изображений: {str(e)}. Пожалуйста, попробуйте еще раз."
            )
        
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
        
        # Отправляем сообщение с запросом нового промпта
        try:
            await query.edit_message_text(
                text="Пожалуйста, введите новый промпт для генерации изображений:",
                reply_markup=reply_markup
            )
            # Сохраняем ID сообщения для последующего редактирования
            self.state_manager.set_data(user_id, "prompt_message_id", query.message.message_id)
            logger.info(f"Отправлен запрос на ввод нового промпта пользователю {user_id}")
        except Exception as e:
            logger.error(f"Ошибка при отправке запроса на ввод нового промпта: {e}", exc_info=True)
            try:
                sent_message = await context.bot.send_message(
                    chat_id=user_id,
                    text="Пожалуйста, введите новый промпт для генерации изображений:",
                    reply_markup=reply_markup
                )
                # Сохраняем ID нового сообщения
                self.state_manager.set_data(user_id, "prompt_message_id", sent_message.message_id)
                logger.info(f"Отправлено новое сообщение с запросом редактирования промпта пользователю {user_id}")
            except Exception as send_error:
                logger.error(f"Не удалось отправить сообщение с запросом нового промпта: {send_error}", exc_info=True)
    
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
        
        # Сбрасываем состояние пользователя
        self.state_manager.reset_state(user_id)
        
        # Используем функцию для создания основной клавиатуры
        reply_markup = create_main_keyboard()
        
        # Отправляем сообщение об отмене и возвращаемся в главное меню
        try:
            # Проверяем, есть ли caption в сообщении
            if hasattr(query.message, 'caption') and query.message.caption is not None:
                await query.edit_message_caption(
                    caption="Генерация изображений отменена.\n\nВыберите действие:",
                    reply_markup=reply_markup
                )
            else:
                # Если caption нет, меняем текст
                await query.edit_message_text(
                    text="Генерация изображений отменена.\n\nВыберите действие:",
                    reply_markup=reply_markup
                )
            logger.info(f"Обновлено сообщение с отменой генерации для пользователя {user_id}")
        except Exception as e:
            logger.error(f"Ошибка при обновлении сообщения с отменой генерации: {e}", exc_info=True)
            
            # В случае ошибки отправляем новое сообщение
            try:
                await context.bot.send_message(
                    chat_id=user_id,
                    text="Генерация изображений отменена.\n\nВыберите действие:",
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
        
        # Сохраняем тип модели
        self.state_manager.set_data(user_id, "model_type", model_type)
        
        # Меняем состояние на загрузку фотографий
        self.state_manager.set_state(user_id, UserState.UPLOADING_PHOTOS)
        
        # Создаем клавиатуру с кнопкой отмены
        keyboard = [
            [InlineKeyboardButton("❌ Отменить обучение", callback_data="cancel_training")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        # Отправляем инструкции по загрузке фотографий с использованием константы из config.py
        try:
            await context.bot.send_photo(
                chat_id=user_id,
                photo=INSTRUCTIONS_IMAGE_URL,
                caption=UPLOAD_PHOTOS_MESSAGE,
                reply_markup=reply_markup
            )
            logger.info(f"Отправлено фото с инструкциями по загрузке фотографий пользователю {user_id}")
        except Exception as e:
            logger.error(f"Ошибка при отправке фото с инструкциями: {e}", exc_info=True)
            # Если не удалось отправить фото, отправляем текстовое сообщение
            await context.bot.send_message(
                chat_id=user_id,
                text=UPLOAD_PHOTOS_MESSAGE,
                reply_markup=reply_markup
            )
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
        
        # Создаем клавиатуру с кнопкой "На главную"
        keyboard = [
            [InlineKeyboardButton("🔙 На главную", callback_data="cmd_start")]
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