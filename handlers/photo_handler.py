from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from loguru import logger
import aiohttp
import asyncio
from datetime import datetime
import random
import string

from state_manager import UserState
from utils.message_utils import delete_message
from config import WELCOME_IMAGE_URL

class PhotoHandler:
    """Обработчик фотографий для бота"""
    
    def __init__(self, state_manager, db_manager, api_client, media_groups=None):
        """
        Инициализация обработчика фотографий
        
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
        logger.info("Инициализирован PhotoHandler")
    
    async def handle_photo(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """
        Обработчик фотографий
        
        Args:
            update (Update): Объект обновления Telegram
            context (ContextTypes.DEFAULT_TYPE): Контекст Telegram
        """
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
            
            # Получаем ID базового сообщения
            base_message_id = self.state_manager.get_data(user_id, "base_message_id")
            
            # Создаем клавиатуру с кнопкой отмены
            keyboard = [
                [InlineKeyboardButton("❌ Отменить обучение", callback_data="cancel_training")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            # Сообщение о статусе загрузки
            status_message = f"✅ Загружено фотографий: {photos_count}\nОсталось загрузить: не менее {max(0, 3 - photos_count)} фото.\n\nПродолжайте отправлять фотографии для обучения модели."
            
            # Если загружено достаточно фотографий, предлагаем начать обучение
            if photos_count >= 3:
                # Получаем данные о модели
                model_name = self.state_manager.get_data(user_id, "model_name")
                model_type = self.state_manager.get_data(user_id, "model_type")
                
                # Обновляем клавиатуру с кнопками для подтверждения
                keyboard = [
                    [InlineKeyboardButton("🚀 Начать обучение", callback_data="start_training")],
                    [InlineKeyboardButton("❌ Отменить обучение", callback_data="cancel_training")]
                ]
                reply_markup = InlineKeyboardMarkup(keyboard)
                
                status_message = f"✅ Загружено фотографий: {photos_count}\n\nВы можете продолжить загрузку фотографий или начать обучение модели.\n\nДанные для обучения:\nНазвание: {model_name}\nТип: {'Мужская' if model_type == 'male' else 'Женская'}"
            
            # Редактируем сообщение с информацией о статусе загрузки
            if base_message_id:
                try:
                    await context.bot.edit_message_caption(
                        chat_id=user_id,
                        message_id=base_message_id,
                        caption=status_message,
                        reply_markup=reply_markup
                    )
                    logger.info(f"Обновлено сообщение о статусе загрузки для пользователя {user_id}")
                except Exception as e:
                    logger.error(f"Ошибка при обновлении сообщения о статусе: {e}", exc_info=True)
                    # В случае ошибки отправляем новое сообщение
                    sent_message = await context.bot.send_photo(
                        chat_id=user_id,
                        photo=WELCOME_IMAGE_URL,
                        caption=status_message,
                        reply_markup=reply_markup
                    )
                    # Сохраняем ID нового сообщения
                    self.state_manager.set_data(user_id, "base_message_id", sent_message.message_id)
                    logger.info(f"Отправлено новое сообщение о статусе загрузки пользователю {user_id}")
            else:
                # Если нет сохраненного ID сообщения, отправляем новое
                sent_message = await context.bot.send_photo(
                    chat_id=user_id,
                    photo=WELCOME_IMAGE_URL,
                    caption=status_message,
                    reply_markup=reply_markup
                )
                # Сохраняем ID нового сообщения
                self.state_manager.set_data(user_id, "base_message_id", sent_message.message_id)
                logger.info(f"Отправлено новое сообщение о статусе загрузки пользователю {user_id}")
            
            # Удаляем фото пользователя для чистоты чата
            try:
                await update.message.delete()
                logger.info(f"Удалено фото от пользователя {user_id}")
            except Exception as e:
                logger.error(f"Не удалось удалить фото пользователя: {e}", exc_info=True)
                
        except Exception as e:
            logger.error(f"Ошибка при обработке фотографии: {e}")
            await update.message.reply_text(
                "❌ Произошла ошибка при обработке фотографии. Пожалуйста, попробуйте загрузить другую фотографию."
            )
            
    async def handle_media_group(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """
        Обработчик медиагрупп для фотографий
        
        Args:
            update (Update): Объект обновления Telegram
            context (ContextTypes.DEFAULT_TYPE): Контекст Telegram
        """
        if not update.effective_message:
            return
        
        media_group_id = update.effective_message.media_group_id
        if not media_group_id:
            return
            
        user_id = update.effective_user.id
        logger.info(f"Получена фотография из медиагруппы {media_group_id} от пользователя {user_id}")
        
        # Получаем ID базового сообщения
        base_message_id = self.state_manager.get_data(user_id, "base_message_id")

        # Проверяем, есть ли уже эта медиагруппа в словаре
        if media_group_id not in self.media_groups:
            self.media_groups[media_group_id] = {
                "user_id": user_id,
                "file_paths": [],
                "last_update": datetime.now().timestamp(),
                "being_processed": False,  # Флаг обработки
                "processing_task": None,   # Ссылка на активную задачу
                "status_message_id": base_message_id  # Используем базовое сообщение для обновления статуса
            }
            logger.info(f"Создана новая медиагруппа {media_group_id} для пользователя {user_id}")
            
            # Обновляем статус базового сообщения
            if base_message_id:
                try:
                    await context.bot.edit_message_caption(
                        chat_id=user_id,
                        message_id=base_message_id,
                        caption="📸 Получаю вашу медиагруппу фотографий. Пожалуйста, подождите...",
                        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ Отменить", callback_data="cancel_training")]])
                    )
                    logger.info(f"Обновлено базовое сообщение о получении медиагруппы")
                except Exception as e:
                    logger.error(f"Ошибка при обновлении сообщения с медиагруппой: {e}")
            else:
                # Если нет базового сообщения, создаем новое
                try:
                    sent_message = await context.bot.send_photo(
                        chat_id=user_id,
                        photo=WELCOME_IMAGE_URL,
                        caption="📸 Получаю вашу медиагруппу фотографий. Пожалуйста, подождите...",
                        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ Отменить", callback_data="cancel_training")]])
                    )
                    # Сохраняем ID нового сообщения
                    self.state_manager.set_data(user_id, "base_message_id", sent_message.message_id)
                    self.media_groups[media_group_id]["status_message_id"] = sent_message.message_id
                    logger.info(f"Создано новое сообщение о получении медиагруппы, ID: {sent_message.message_id}")
                except Exception as e:
                    logger.error(f"Ошибка при создании нового сообщения о медиагруппе: {e}")
        
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
                await context.bot.edit_message_caption(
                    chat_id=user_id,
                    message_id=status_message_id,
                    caption=f"📸 Получено фотографий: {photos_count}. Пожалуйста, подождите...",
                    reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ Отменить", callback_data="cancel_training")]])
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
        async def process_media_group_later():
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
                    ],
                    [
                        InlineKeyboardButton("❌ Отменить обучение", callback_data="cancel_training")
                    ]
                ]
                reply_markup = InlineKeyboardMarkup(keyboard)
                
                # Получаем или создаем модель для этих фотографий
                model_name = self.state_manager.get_data(user_id, "model_name")
                model_type = self.state_manager.get_data(user_id, "model_type")
                
                # Если нет имени модели, генерируем его
                if not model_name:
                    model_name = f"MediaGroup_{user_id}_{datetime.now().strftime('%Y%m%d%H%M%S')}"
                    self.state_manager.set_data(user_id, "model_name", model_name)
                
                # Если нет типа модели, используем дефолтный
                if not model_type:
                    model_type = "default"
                    self.state_manager.set_data(user_id, "model_type", model_type)
                
                # Обновляем статусное сообщение
                status_message_id = self.media_groups[media_group_id]["status_message_id"]
                if status_message_id:
                    try:
                        await context.bot.edit_message_caption(
                            chat_id=user_id,
                            message_id=status_message_id,
                            caption=f"✅ Все фотографии ({len(file_paths)}) успешно обработаны.\n\nДанные для обучения модели:\nНазвание: {model_name}\nТип: {'Мужская' if model_type == 'male' else 'Женская'}\n\nНажмите кнопку ниже, чтобы начать обучение модели.",
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