from loguru import logger
from typing import Dict, Any, Optional
from datetime import datetime
import json

from database import DatabaseManager


class SupabaseLogger:
    """Класс для логирования в Supabase"""

    def __init__(self, db_manager: DatabaseManager):
        """Инициализация логгера"""
        self.db = db_manager
        logger.info("Инициализирован логгер Supabase")

    async def log_event(
        self,
        event_type: str,
        message: str,
        level: str = "info",
        telegram_id: Optional[int] = None,
        data: Optional[Dict[str, Any]] = None
    ) -> None:
        """Логирование события в Supabase"""
        try:
            # Формируем данные для логирования
            log_data = {
                "event_type": event_type,
                "level": level,
                "message": message,
                "timestamp": datetime.now().isoformat(),
                "telegram_id": telegram_id,
                "data": json.dumps(data) if data else None
            }

            # Логируем в Supabase
            result = await self.db.create_log(log_data)
            
            if not result:
                logger.error(f"Ошибка при логировании события в Supabase: {event_type}")
            
        except Exception as e:
            logger.error(f"Ошибка при логировании события в Supabase: {e}") 