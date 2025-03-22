import os
import json
import logging
import aiohttp
from typing import Dict, List, Optional, Any, Union

from config import (
    API_BASE_URL,
    FINETUNE_WEBHOOK_ENDPOINT,
)

# Инициализация логгера
logger = logging.getLogger(__name__)

class N8NService:
    """Сервис для взаимодействия с N8N API"""

    def __init__(self):
        """Инициализация сервиса"""
        self.base_url = API_BASE_URL
        self.finetune_webhook_endpoint = FINETUNE_WEBHOOK_ENDPOINT

    async def get_user_models(self, telegram_id: int) -> List[Dict[str, Any]]:
        """Получение списка моделей пользователя"""
        try:
            data = {"telegram_id": telegram_id}
            async with aiohttp.ClientSession() as session:
                async with session.post('https://n8n2.supashkola.ru/webhook/my_models', json=data) as response:
                    if response.status == 200:
                        models = await response.json()
                        logger.info(f"Получены модели пользователя {telegram_id} через API: {len(models)} моделей")
                        return models
                    else:
                        logger.error(f"Ошибка при получении моделей через API: {response.status}")
                        return []
        except Exception as e:
            logger.error(f"Исключение при получении моделей через API: {e}", exc_info=True)
            return []

    async def get_user_credits(self, telegram_id: int) -> int:
        """Получение количества кредитов пользователя"""
        try:
            data = {"telegram_id": telegram_id}
            async with aiohttp.ClientSession() as session:
                async with session.post('https://n8n2.supashkola.ru/webhook/my_credits', json=data) as response:
                    if response.status == 200:
                        credits_data = await response.text()
                        try:
                            credits = int(credits_data.strip())
                            logger.info(f"Получены кредиты пользователя {telegram_id} через API: {credits}")
                            return credits
                        except ValueError:
                            logger.error(f"Не удалось преобразовать ответ API в число: {credits_data}")
                            return 0
                    else:
                        logger.error(f"Ошибка при получении кредитов через API: {response.status}")
                        return 0
        except Exception as e:
            logger.error(f"Исключение при получении кредитов через API: {e}", exc_info=True)
            return 0

    async def start_finetune(self, model_name: str, model_type: str, file_paths: List[str], telegram_id: int) -> bool:
        """Отправка запроса на обучение модели"""
        # Формируем данные для отправки
        data = {
            "model_name": model_name,
            "model_type": model_type,
            "file_paths": file_paths,
            "telegram_id": telegram_id
        }
        
        logger.info(f"Отправка данных для обучения: модель '{model_name}', тип '{model_type}', файлов: {len(file_paths)}")
        
        # Отправляем данные на вебхук
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(self.finetune_webhook_endpoint, json=data) as response:
                    if response.status == 200:
                        logger.info(f"Данные успешно отправлены на вебхук: {len(file_paths)} фотографий")
                        return True
                    else:
                        logger.error(f"Ошибка при отправке данных на вебхук: {response.status}")
                        return False
        except Exception as e:
            logger.error(f"Исключение при отправке данных на вебхук: {e}")
            return False

    async def generate_images(self, model_id: int, prompt: str, telegram_id: int, num_images: int = 4) -> bool:
        """Отправка запроса на генерацию изображений"""
        # Создаем данные для запроса
        data = {
            "model_id": model_id,
            "prompt": prompt,
            "telegram_id": telegram_id,
            "num_images": num_images
        }
        
        logger.info(f"Данные для генерации: model_id={model_id}, prompt='{prompt}', telegram_id={telegram_id}")
        
        # Отправляем запрос на генерацию
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post('https://n8n2.supashkola.ru/webhook/generate_tg', json=data) as response:
                    if response.status == 200:
                        try:
                            response_data = await response.json()
                            prompt_id = response_data.get("prompt_id", "unknown")
                            logger.info(f"Получен ID промпта: {prompt_id}")
                            return True
                        except json.JSONDecodeError:
                            response_text = await response.text()
                            logger.error(f"Не удалось декодировать JSON-ответ: {response_text}")
                            return True  # Возвращаем True, так как запрос был успешным
                    else:
                        response_text = await response.text()
                        logger.error(f"Ошибка при отправке запроса на генерацию: {response.status}, {response_text}")
                        return False
        except Exception as e:
            logger.error(f"Исключение при отправке запроса на генерацию: {e}", exc_info=True)
            return False
