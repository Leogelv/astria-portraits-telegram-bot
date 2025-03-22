import os
import logging
import asyncio
from typing import Dict, List, Optional, Any, Union, Tuple
from datetime import datetime

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from config import MAX_PHOTOS, INSTRUCTIONS_IMAGE_URL
from state_manager import UserState
from services.n8n_service import N8NService

# Инициализация логгера
logger = logging.getLogger(__name__)

class MediaHandlers:
    """Обработчики медиа-контента (фото, медиа-группы)"""
    
    def __init__(self, state_manager, db=None, n8n_service=None):
        """Инициализация обработчиков медиа"""
        self.state_manager = state_manager
        self.db = db
        self.n8n_service = n8n_service or N8NService()
        # Словарь для отслеживания медиагрупп
        self.media_groups = {}
        
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
        photo_url = photo_file.file_path
        
        # Добавляем фотографию в список
        self.state_manager.add_to_list(user_id, "photos", photo_url)
        
        # Получаем текущее количество фотографий
        photos = self.state_manager.get_list(user_id, "photos")
        photos_count = len(photos)
        
        await update.message.reply_text(
            f"✅ Фотография #{photos_count} загружена.\n"
            f"Осталось загрузить: {MAX_PHOTOS - photos_count} фото."
        )
        
        # Если загружены все фотографии, переходим к подтверждению обучения модели
        if photos_count >= MAX_PHOTOS:
            # Получаем данные о модели
            model_name = self.state_manager.get_data(user_id, "model_name")
            model_type = self.state_manager.get_data(user_id, "model_type")
            
            # Создаем клавиатуру для подтверждения
            keyboard = [
                [
                    InlineKeyboardButton("Да, начать обучение", callback_data="start_training"),
                    InlineKeyboardButton("Отмена", callback_data="cancel_training")
                ]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            # Отправляем сообщение о завершении загрузки и запрос на подтверждение
            await context.bot.send_message(
                chat_id=user_id,
                text=f"✅ Все фотографии ({photos_count}) успешно загружены!\n\n"
                     f"Данные для обучения модели:\n"
                     f"Название: {model_name}\n"
                     f"Тип: {'Мужчина' if model_type == 'male' else 'Женщина'}\n"
                     f"Количество фотографий: {photos_count}\n\n"
                     f"Начать обучение модели?",
                reply_markup=reply_markup
            )
            logger.info(f"Отправлен запрос на подтверждение обучения модели пользователю {user_id}")

    async def handle_media_group(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Обработчик медиагрупп"""
        if not update.effective_message:
            return
        
        media_group_id = update.effective_message.media_group_id
        if not media_group_id:
            return
            
        user_id = update.effective_user.id
        logger.info(f"Получена фотография из медиагруппы {media_group_id} от пользователя {user_id}")

        # Проверяем, есть ли уже эта медиагруппа в словаре
        if media_group_id not in self.media_groups:
            self.media_groups[media_group_id] = {
                "user_id": user_id,
                "file_paths": [],
                "last_update": datetime.now().timestamp(),
                "being_processed": False,  # Флаг обработки
                "processing_task": None,   # Ссылка на активную задачу
                "status_message_id": None  # ID сообщения для обновления статуса
            }
            logger.info(f"Создана новая медиагруппа {media_group_id} для пользователя {user_id}")
            
            # Отправляем сообщение пользователю о начале сбора фотографий
            status_message = await context.bot.send_message(
                chat_id=user_id,
                text="📸 Получаю ваши фотографии. Пожалуйста, подождите..."
            )
            # Сохраняем ID сообщения для последующего обновления
            self.media_groups[media_group_id]["status_message_id"] = status_message.message_id
            logger.info(f"Создано статусное сообщение с ID {status_message.message_id} для медиагруппы {media_group_id}")
        
        # Получаем самый большой размер фотографии
        photo = update.effective_message.photo[-1]  # Последний элемент в списке - самый большой размер
        file = await context.bot.get_file(photo.file_id)
        file_path = file.file_path
        
        # Проверяем, не добавлен ли уже этот file_path
        if file_path not in self.media_groups[media_group_id]["file_paths"]:
            # Добавляем путь к файлу в список
            self.media_groups[media_group_id]["file_paths"].append(file_path)
        self.media_groups[media_group_id]["last_update"] = datetime.now().timestamp()
        logger.info(f"Добавлен URL фотографии в медиагруппу {media_group_id}: {file_path}")
        
        # Обновляем статусное сообщение с текущим количеством фотографий
        try:
            status_message_id = self.media_groups[media_group_id]["status_message_id"]
            if status_message_id:
                photos_count = len(self.media_groups[media_group_id]["file_paths"])
                await context.bot.edit_message_text(
                    chat_id=user_id,
                    message_id=status_message_id,
                    text=f"📸 Получено фотографий: {photos_count}. Пожалуйста, подождите..."
                )
                logger.debug(f"Обновлено статусное сообщение ({status_message_id}) для медиагруппы {media_group_id}: {photos_count} фото")
        except Exception as e:
            logger.error(f"Ошибка при обновлении статусного сообщения: {e}")
        
        # Если есть активная задача обработки, отменяем ее
        if self.media_groups[media_group_id].get("processing_task"):
            try:
                self.media_groups[media_group_id]["processing_task"].cancel()
                logger.debug(f"Отменена предыдущая задача обработки для медиагруппы {media_group_id}")
            except Exception as e:
                logger.error(f"Ошибка при отмене задачи: {e}")
        
        # Функция отложенной обработки медиагруппы
        async def process_media_group_later(media_group_id=media_group_id, user_id=user_id):
            await asyncio.sleep(2)  # Ждем 2 секунды после последнего обновления
            
            # Проверяем, существует ли еще медиагруппа и не обрабатывается ли она уже
            if media_group_id not in self.media_groups:
                logger.debug(f"Медиагруппа {media_group_id} уже удалена, отмена обработки")
                return
            
            if self.media_groups[media_group_id]["being_processed"]:
                logger.debug(f"Медиагруппа {media_group_id} уже обрабатывается, отмена дублирующей обработки")
                return
            
            # Отмечаем группу как обрабатываемую
            self.media_groups[media_group_id]["being_processed"] = True
            logger.info(f"Начинаем обработку медиагруппы {media_group_id}")
            
            # Если с момента последнего обновления прошло более 1.5 секунд, считаем, что медиагруппа завершена
            if datetime.now().timestamp() - self.media_groups[media_group_id]["last_update"] > 1.5:
                file_paths = self.media_groups[media_group_id]["file_paths"]
                logger.info(f"Обработка завершенной медиагруппы {media_group_id} с {len(file_paths)} фотографиями")
                
                # Создаем кнопки для действий после загрузки фотографий
                keyboard = [
                    [
                        InlineKeyboardButton("✅ Начать обучение модели", callback_data=f"start_training_{media_group_id}"),
                        InlineKeyboardButton("🔄 Загрузить фото заново", callback_data="cmd_train")
                    ]
                ]
                reply_markup = InlineKeyboardMarkup(keyboard)
                
                # Обновляем статусное сообщение
                status_message_id = self.media_groups[media_group_id]["status_message_id"]
                if status_message_id:
                    try:
                        await context.bot.edit_message_text(
                            chat_id=user_id,
                            message_id=status_message_id,
                            text=f"✅ Все фотографии ({len(file_paths)}) успешно обработаны.",
                            reply_markup=reply_markup
                        )
                        logger.info(f"Обновлено статусное сообщение ({status_message_id}) для медиагруппы {media_group_id} с кнопками")
                    except Exception as e:
                        logger.error(f"Ошибка при обновлении статусного сообщения: {e}")
                
                # НЕ очищаем медиагруппу из словаря, так как она может понадобиться при нажатии кнопки обучения
                logger.info(f"Медиагруппа {media_group_id} обработана и ожидает действий пользователя")
        
        # Запускаем задачу обработки медиагруппы и сохраняем ссылку на нее
        task = asyncio.create_task(process_media_group_later())
        self.media_groups[media_group_id]["processing_task"] = task
        logger.debug(f"Создана новая задача обработки для медиагруппы {media_group_id}")

    async def handle_media_group_type_selection(self, update: Update, context: ContextTypes.DEFAULT_TYPE, media_group_id: str, model_type: str) -> None:
        """Обработка выбора типа модели для медиагруппы"""
        query = update.callback_query
        user_id = query.from_user.id
        logger.info(f"Обработка выбора типа модели для медиагруппы {media_group_id}: {model_type}")
        
        # Проверяем, существует ли медиагруппа
        if media_group_id not in self.media_groups:
            logger.error(f"Медиагруппа {media_group_id} не найдена при выборе типа модели")
            await context.bot.send_message(
                chat_id=user_id,
                text="Ошибка: информация о загруженных фотографиях не найдена. Пожалуйста, загрузите фотографии заново."
            )
            self.state_manager.reset_state(user_id)
            return
        
        # Сохраняем тип модели в состоянии пользователя
        self.state_manager.set_data(user_id, "model_type", model_type)
        
        # Получаем имя модели из состояния
        model_name = self.state_manager.get_data(user_id, "model_name")
        if not model_name:
            logger.error(f"Имя модели не найдено в состоянии пользователя {user_id}")
            await context.bot.send_message(
                chat_id=user_id,
                text="Ошибка: имя модели не найдено. Пожалуйста, начните процесс заново."
            )
            self.state_manager.reset_state(user_id)
            return
        
        # Получаем данные медиагруппы
        file_paths = self.media_groups[media_group_id]["file_paths"]
        status_message_id = self.media_groups[media_group_id]["status_message_id"]
        
        # Отправляем данные на обучение
        success = await self.n8n_service.start_finetune(model_name, model_type, file_paths, user_id)
        
        if success:
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
                    await context.bot.send_message(
                        chat_id=user_id,
                        text=f"✅ Все фотографии ({len(file_paths)}) успешно отправлены на сервер для обучения модели.\n\nМы уведомим вас, когда модель будет готова.",
                        reply_markup=reply_markup
                    )
        else:
            # Восстанавливаем кнопки для повторной попытки
            keyboard = [
                [
                    InlineKeyboardButton("✅ Повторить попытку", callback_data=f"start_training_{media_group_id}"),
                    InlineKeyboardButton("🔄 Загрузить фото заново", callback_data="cmd_train")
                ]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            # Отправляем сообщение об ошибке
            if status_message_id:
                try:
                    await context.bot.edit_message_text(
                        chat_id=user_id,
                        message_id=status_message_id,
                        text=f"❌ Ошибка при отправке фотографий на сервер. Пожалуйста, попробуйте снова.",
                        reply_markup=reply_markup
                    )
                except Exception as e:
                    logger.error(f"Ошибка при обновлении статусного сообщения: {e}")
                    await context.bot.send_message(
                        chat_id=user_id,
                        text=f"❌ Ошибка при отправке фотографий на сервер. Пожалуйста, попробуйте снова.",
                        reply_markup=reply_markup
                    )
        
        # Сбрасываем состояние пользователя
        self.state_manager.reset_state(user_id)
        
        # После обработки очищаем медиагруппу из словаря
        del self.media_groups[media_group_id]
        logger.info(f"Медиагруппа {media_group_id} обработана и удалена из словаря")
