from supabase import create_client
from loguru import logger
from typing import Dict, List, Optional, Any, Union
import json

from config import SUPABASE_URL, SUPABASE_KEY


class DatabaseManager:
    """Класс для работы с базой данных Supabase"""

    def __init__(self):
        """Инициализация клиента Supabase"""
        self.supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
        logger.info("Инициализирован клиент Supabase")

    async def get_user(self, telegram_id: int) -> Optional[Dict[str, Any]]:
        """Получение пользователя по Telegram ID"""
        try:
            response = self.supabase.table("telegram_users").select("*").eq("telegram_id", telegram_id).execute()
            if response.data and len(response.data) > 0:
                logger.debug(f"Получен пользователь: {response.data[0]}")
                return response.data[0]
            logger.debug(f"Пользователь с telegram_id={telegram_id} не найден")
            return None
        except Exception as e:
            logger.error(f"Ошибка при получении пользователя: {e}")
            return None

    async def create_user(self, user_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Создание нового пользователя"""
        try:
            # Добавляем начальные 500 кредитов для нового пользователя
            if 'credits' not in user_data:
                user_data['credits'] = 500
            
            response = self.supabase.table("telegram_users").insert(user_data).execute()
            if response.data and len(response.data) > 0:
                logger.info(f"Создан новый пользователь: {response.data[0]}")
                return response.data[0]
            logger.error(f"Ошибка при создании пользователя: {response}")
            return None
        except Exception as e:
            logger.error(f"Ошибка при создании пользователя: {e}")
            return None

    async def update_user(self, telegram_id: int, user_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Обновление данных пользователя"""
        try:
            response = self.supabase.table("telegram_users").update(user_data).eq("telegram_id", telegram_id).execute()
            if response.data and len(response.data) > 0:
                logger.debug(f"Обновлен пользователь: {response.data[0]}")
                return response.data[0]
            logger.error(f"Ошибка при обновлении пользователя: {response}")
            return None
        except Exception as e:
            logger.error(f"Ошибка при обновлении пользователя: {e}")
            return None

    async def get_user_models(self, telegram_id: int) -> List[Dict[str, Any]]:
        """Получение моделей пользователя"""
        try:
            response = self.supabase.table("telegram_models").select("*").eq("telegram_user_id", telegram_id).execute()
            if response.data:
                logger.debug(f"Получены модели пользователя: {len(response.data)}")
                return response.data
            logger.debug(f"Модели пользователя с telegram_id={telegram_id} не найдены")
            return []
        except Exception as e:
            logger.error(f"Ошибка при получении моделей пользователя: {e}")
            return []

    async def create_model(self, model_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Создание новой модели"""
        try:
            response = self.supabase.table("telegram_models").insert(model_data).execute()
            if response.data and len(response.data) > 0:
                logger.info(f"Создана новая модель: {response.data[0]}")
                return response.data[0]
            logger.error(f"Ошибка при создании модели: {response}")
            return None
        except Exception as e:
            logger.error(f"Ошибка при создании модели: {e}")
            return None

    async def update_model(self, model_id: int, model_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Обновление данных модели"""
        try:
            response = self.supabase.table("telegram_models").update(model_data).eq("id", model_id).execute()
            if response.data and len(response.data) > 0:
                logger.debug(f"Обновлена модель: {response.data[0]}")
                return response.data[0]
            logger.error(f"Ошибка при обновлении модели: {response}")
            return None
        except Exception as e:
            logger.error(f"Ошибка при обновлении модели: {e}")
            return None

    async def create_prompt(self, prompt_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Создание нового промпта"""
        try:
            response = self.supabase.table("telegram_prompts").insert(prompt_data).execute()
            if response.data and len(response.data) > 0:
                logger.info(f"Создан новый промпт: {response.data[0]}")
                return response.data[0]
            logger.error(f"Ошибка при создании промпта: {response}")
            return None
        except Exception as e:
            logger.error(f"Ошибка при создании промпта: {e}")
            return None

    async def update_prompt(self, prompt_id: int, prompt_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Обновление данных промпта"""
        try:
            response = self.supabase.table("telegram_prompts").update(prompt_data).eq("id", prompt_id).execute()
            if response.data and len(response.data) > 0:
                logger.debug(f"Обновлен промпт: {response.data[0]}")
                return response.data[0]
            logger.error(f"Ошибка при обновлении промпта: {response}")
            return None
        except Exception as e:
            logger.error(f"Ошибка при обновлении промпта: {e}")
            return None

    async def get_user_prompts(self, telegram_id: int) -> List[Dict[str, Any]]:
        """Получение промптов пользователя"""
        try:
            response = self.supabase.table("telegram_prompts").select("*").eq("telegram_user_id", telegram_id).execute()
            if response.data:
                logger.debug(f"Получены промпты пользователя: {len(response.data)}")
                return response.data
            logger.debug(f"Промпты пользователя с telegram_id={telegram_id} не найдены")
            return []
        except Exception as e:
            logger.error(f"Ошибка при получении промптов пользователя: {e}")
            return []

    async def get_model_details(self, model_id: int) -> Optional[Dict[str, Any]]:
        """Получение деталей модели из основной таблицы models"""
        try:
            response = self.supabase.table("models").select("*").eq("id", model_id).execute()
            if response.data and len(response.data) > 0:
                logger.debug(f"Получены детали модели: {response.data[0]}")
                return response.data[0]
            logger.debug(f"Модель с id={model_id} не найдена")
            return None
        except Exception as e:
            logger.error(f"Ошибка при получении деталей модели: {e}")
            return None

    async def log_event(self, event_type: str, message: str, data: Optional[Dict] = None, 
                        telegram_id: Optional[int] = None, level: str = "info") -> Optional[Dict[str, Any]]:
        """Логирование события в таблицу system_logs"""
        try:
            # Подготавливаем данные для логирования
            log_data = {
                "event_type": event_type,
                "level": level,
                "message": message,
                "data": json.dumps(data) if data else None,
                "telegram_id": telegram_id
            }
            
            # Отправляем запрос в Supabase
            response = self.supabase.table("system_logs").insert(log_data).execute()
            
            if response.data and len(response.data) > 0:
                logger.debug(f"Создана запись лога: {response.data[0]['id']}")
                return response.data[0]
            
            logger.error(f"Ошибка при создании записи лога: {response}")
            return None
        except Exception as e:
            logger.error(f"Исключение при логировании в Supabase: {e}")
            return None

    async def create_log(self, log_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Создание записи в логах"""
        try:
            response = self.supabase.table("telegram_logs").insert(log_data).execute()
            if response.data and len(response.data) > 0:
                logger.debug(f"Создана запись в логах: {response.data[0]}")
                return response.data[0]
            logger.error(f"Ошибка при создании записи в логах: {response}")
            return None
        except Exception as e:
            logger.error(f"Ошибка при создании записи в логах: {e}")
            return None

    async def create_media_group(self, media_group_id: str, telegram_user_id: int) -> Optional[Dict[str, Any]]:
        """Создание новой медиагруппы"""
        try:
            media_group_data = {
                "media_group_id": media_group_id,
                "telegram_user_id": telegram_user_id,
                "processed": False,
                "file_urls": None  # Изначально URLs файлов пустые
            }
            
            response = self.supabase.table("telegram_media_groups").insert(media_group_data).execute()
            if response.data and len(response.data) > 0:
                logger.info(f"Создана новая медиагруппа: {response.data[0]}")
                return response.data[0]
            logger.error(f"Ошибка при создании медиагруппы: {response}")
            return None
        except Exception as e:
            logger.error(f"Ошибка при создании медиагруппы: {e}")
            return None

    async def get_media_group(self, media_group_id: str) -> Optional[Dict[str, Any]]:
        """Получение медиагруппы по её ID"""
        try:
            response = self.supabase.table("telegram_media_groups").select("*").eq("media_group_id", media_group_id).execute()
            if response.data and len(response.data) > 0:
                logger.debug(f"Получена медиагруппа: {response.data[0]}")
                return response.data[0]
            logger.debug(f"Медиагруппа с id={media_group_id} не найдена")
            return None
        except Exception as e:
            logger.error(f"Ошибка при получении медиагруппы: {e}")
            return None

    async def update_media_group_urls(self, media_group_id: str, file_urls: List[str]) -> Optional[Dict[str, Any]]:
        """Обновление URLs файлов медиагруппы"""
        try:
            # Кодируем список URL в формате JSONB для хранения в Supabase
            file_urls_json = json.dumps(file_urls)
            
            response = self.supabase.table("telegram_media_groups").update({
                "file_urls": file_urls_json,
                "processed": True
            }).eq("media_group_id", media_group_id).execute()
            
            if response.data and len(response.data) > 0:
                logger.debug(f"Обновлены URLs медиагруппы: {response.data[0]}")
                return response.data[0]
            logger.error(f"Ошибка при обновлении URLs медиагруппы: {response}")
            return None
        except Exception as e:
            logger.error(f"Ошибка при обновлении URLs медиагруппы: {e}")
            return None 