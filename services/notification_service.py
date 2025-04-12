from typing import Dict, Any, Optional, List
import aiohttp
from loguru import logger
from telegram.ext import Application
from utils.logging_utils import LogEventType
from state_manager import StateManager

class NotificationService:
    """Сервис для обработки уведомлений и вебхуков"""
    
    def __init__(self, application: Application, state_manager: StateManager, db_manager=None, supa_logger=None):
        """
        Инициализация сервиса уведомлений
        
        Args:
            application (Application): Приложение Telegram бота
            state_manager (StateManager): Менеджер состояний
            db_manager: Менеджер базы данных
            supa_logger: Логгер Supabase
        """
        self.application = application
        self.state_manager = state_manager
        self.db_manager = db_manager
        self.supa_logger = supa_logger
        logger.info("Инициализирован NotificationService с StateManager")
    
    async def handle_webhook_update(self, update_data: Dict[str, Any]) -> None:
        """
        Обработка обновления от вебхука
        
        Args:
            update_data (Dict[str, Any]): Данные обновления
        """
        logger.debug(f"Получено обновление от вебхука: {update_data}")
        
        # Проверяем, является ли это обновлением от Telegram
        if "update_id" in update_data:
            await self._handle_telegram_update(update_data)
        elif update_data.get("type") == "model_status_update":
            await self.handle_model_status_update(update_data)
        elif update_data.get("type") == "prompt_status_update":
            await self.handle_prompt_status_update(update_data)
        else:
            logger.warning(f"Получен неизвестный тип обновления: {update_data}")
    
    async def _handle_telegram_update(self, update_data: Dict[str, Any]) -> None:
        """
        Обработка обновления от Telegram
        
        Args:
            update_data (Dict[str, Any]): Данные обновления
        """
        from telegram import Update
        
        logger.info(f"Получено обновление от Telegram: {update_data.get('update_id')}")
        
        # Конвертируем dict в объект Update и обрабатываем
        update = Update.de_json(data=update_data, bot=self.application.bot)
        if update:
            logger.info(f"Успешно создан объект Update с ID {update.update_id}")
            await self.application.process_update(update)
        else:
            logger.error(f"Не удалось создать объект Update из данных: {update_data}")
    
    async def handle_model_status_update(self, update_data: Dict[str, Any]) -> None:
        """
        Обработка обновления статуса модели
        
        Args:
            update_data (Dict[str, Any]): Данные обновления
        """
        model_id = update_data.get("model_id")
        status = update_data.get("status")
        telegram_id = update_data.get("telegram_id")
        
        if not model_id or not status or not telegram_id:
            logger.warning(f"Неполные данные для обновления статуса модели: {update_data}")
            return
        
        logger.info(f"Обновление статуса модели {model_id} на {status} для пользователя {telegram_id}")
        
        # Логируем в Supabase, если логгер доступен
        event_type = LogEventType.ASTRIA_MODEL_TRAINING_COMPLETED if status == "completed" else LogEventType.ASTRIA_MODEL_TRAINING_FAILED
        if self.supa_logger:
            await self.supa_logger.log_event(
                event_type=event_type,
                message=f"Статус модели {model_id} изменен на {status}",
                data=update_data,
                telegram_id=telegram_id
            )
        logger.info(f"Event: {event_type} - Статус модели {model_id} изменен на {status} для пользователя {telegram_id}")
        
        # Обновляем статус модели в базе данных, если менеджер доступен
        if self.db_manager:
            model_data = {
                "status": status,
                "error": update_data.get("error")
            }
            await self.db_manager.update_model(model_id, model_data)
        
        # Отправляем уведомление пользователю
        try:
            # Проверяем статус: может быть 'completed' или 'ready'
            if status in ["completed", "ready"]:
                message = f"✅ Ваша модель успешно обучена и готова к использованию!\n\nID модели: {model_id}\n\nТеперь вы можете использовать команду /generate для создания изображений."
                # Очищаем кеш моделей для этого пользователя
                if self.state_manager:
                    self.state_manager.clear_data(telegram_id, "user_models")
                    logger.info(f"Кеш моделей очищен для пользователя {telegram_id} после успешного обучения.")
                else:
                    logger.warning("StateManager не доступен в NotificationService, кеш моделей не очищен.")
            else:
                error_message = update_data.get("error", "Неизвестная ошибка")
                message = f"❌ К сожалению, при обучении модели произошла ошибка:\n\n{error_message}\n\nПожалуйста, попробуйте снова с другими фотографиями."
            
            await self.application.bot.send_message(chat_id=telegram_id, text=message)
            logger.info(f"Отправлено уведомление пользователю {telegram_id} о статусе модели {model_id}")
        except Exception as e:
            logger.error(f"Ошибка при отправке уведомления пользователю {telegram_id}: {e}", exc_info=True)
    
    async def handle_prompt_status_update(self, update_data: Dict[str, Any]) -> None:
        """
        Обработка обновления статуса промпта
        
        Args:
            update_data (Dict[str, Any]): Данные обновления
        """
        prompt_id = update_data.get("prompt_id")
        status = update_data.get("status")
        telegram_id = update_data.get("telegram_id")
        images = update_data.get("images", [])
        
        if not prompt_id or not status or not telegram_id:
            logger.warning(f"Неполные данные для обновления статуса промпта: {update_data}")
            return
        
        logger.info(f"Обновление статуса промпта {prompt_id} на {status} для пользователя {telegram_id}")
        
        # Логируем в Supabase, если логгер доступен
        event_type = LogEventType.IMAGE_GENERATION_COMPLETED if status == "completed" else LogEventType.IMAGE_GENERATION_FAILED
        if self.supa_logger:
            await self.supa_logger.log_event(
                event_type=event_type,
                message=f"Статус промпта {prompt_id} изменен на {status}",
                data=update_data,
                telegram_id=telegram_id
            )
        logger.info(f"Event: {event_type} - Статус промпта {prompt_id} изменен на {status} для пользователя {telegram_id}")
        
        # Обновляем статус промпта в базе данных, если менеджер доступен
        if self.db_manager:
            prompt_data = {
                "status": status,
                "error": update_data.get("error")
            }
            await self.db_manager.update_prompt(prompt_id, prompt_data)
        
        # Отправляем уведомление пользователю
        try:
            if status == "completed" and images:
                # Отправляем изображения пользователю
                await self.send_generated_images(telegram_id, images)
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
            logger.error(f"Ошибка при отправке уведомления пользователю {telegram_id}: {e}", exc_info=True)
    
    async def send_generated_images(self, user_id: int, images: List[str]) -> None:
        """
        Отправка сгенерированных изображений пользователю
        
        Args:
            user_id (int): ID пользователя Telegram
            images (List[str]): Список URL изображений
        """
        from telegram import InlineKeyboardButton, InlineKeyboardMarkup
        
        logger.info(f"Начало отправки сгенерированных изображений пользователю {user_id}")
        
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
            await self.application.bot.send_message(
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
                        InlineKeyboardButton("💾 Скачать", url=image_url),
                        InlineKeyboardButton("🔍 Открыть", url=image_url)
                    ]
                ]
                img_reply_markup = InlineKeyboardMarkup(img_keyboard)
                
                logger.info(f"Попытка отправки изображения #{i} пользователю {user_id}")
                await self.application.bot.send_photo(
                    chat_id=user_id,
                    photo=image_url,
                    caption=f"✨ Изображение #{i} из {len(images)}",
                    reply_markup=img_reply_markup
                )
                logger.info(f"Изображение #{i} успешно отправлено пользователю {user_id}")
            except Exception as e:
                logger.error(f"Ошибка при отправке изображения {i}: {e}", exc_info=True)
                try:
                    await self.application.bot.send_message(
                        chat_id=user_id,
                        text=f"❌ Не удалось отправить изображение #{i}. URL: {image_url}"
                    )
                except Exception as send_error:
                    logger.error(f"Не удалось отправить сообщение об ошибке: {send_error}", exc_info=True)
