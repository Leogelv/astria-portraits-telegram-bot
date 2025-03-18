import aiohttp
import json
from loguru import logger
from typing import Dict, List, Optional, Any, Union
import base64
from io import BytesIO
from PIL import Image
import asyncio

from config import (
    API_BASE_URL,
    TRAIN_MODEL_ENDPOINT,
    GENERATE_IMAGES_ENDPOINT,
    FINETUNE_WEBHOOK_ENDPOINT,
    TIMEOUT,
    MAX_PHOTO_SIZE,
    PHOTO_QUALITY
)


class ApiClient:
    """Класс для работы с API эндпоинтами"""

    def __init__(self):
        """Инициализация клиента API"""
        self.base_url = API_BASE_URL
        self.train_model_endpoint = f"{self.base_url}{TRAIN_MODEL_ENDPOINT}"
        self.generate_images_endpoint = f"{self.base_url}{GENERATE_IMAGES_ENDPOINT}"
        self.finetune_webhook_endpoint = FINETUNE_WEBHOOK_ENDPOINT
        logger.info(f"Инициализирован API клиент с базовым URL: {self.base_url}")

    async def _make_request(
        self, method: str, url: str, data: Optional[Dict[str, Any]] = None, timeout: int = TIMEOUT
    ) -> Dict[str, Any]:
        """Выполнение HTTP-запроса к API"""
        try:
            async with aiohttp.ClientSession() as session:
                # Логируем детали запроса
                request_id = f"req_{id(data)}"
                logger.debug(f"[{request_id}] Отправка {method} запроса к {url}")
                if data:
                    # Логируем данные запроса, но скрываем большие поля (например, изображения)
                    log_data = data.copy()
                    if 'images' in log_data:
                        log_data['images'] = f"[{len(log_data['images'])} изображений]"
                    logger.debug(f"[{request_id}] Данные запроса: {json.dumps(log_data, ensure_ascii=False)}")
                
                if method.upper() == "GET":
                    async with session.get(url, timeout=timeout) as response:
                        response_text = await response.text()
                        try:
                            response_data = json.loads(response_text)
                            # Логируем ответ API
                            logger.debug(f"[{request_id}] Получен ответ от {url}: статус {response.status}")
                            logger.debug(f"[{request_id}] Заголовки ответа: {dict(response.headers)}")
                            # Логируем тело ответа, но ограничиваем размер для больших ответов
                            log_response = json.dumps(response_data, ensure_ascii=False)
                            if len(log_response) > 1000:
                                logger.debug(f"[{request_id}] Тело ответа (сокращено): {log_response[:1000]}...")
                            else:
                                logger.debug(f"[{request_id}] Тело ответа: {log_response}")
                            return {
                                "status": response.status,
                                "data": response_data
                            }
                        except json.JSONDecodeError as e:
                            logger.error(f"[{request_id}] Ошибка декодирования JSON: {e}")
                            logger.error(f"[{request_id}] Текст ответа: {response_text[:500]}...")
                            return {
                                "status": response.status,
                                "data": {"error": "Invalid JSON response", "text": response_text[:500]}
                            }
                elif method.upper() == "POST":
                    async with session.post(url, json=data, timeout=timeout) as response:
                        response_text = await response.text()
                        try:
                            response_data = json.loads(response_text)
                            # Логируем ответ API
                            logger.debug(f"[{request_id}] Получен ответ от {url}: статус {response.status}")
                            logger.debug(f"[{request_id}] Заголовки ответа: {dict(response.headers)}")
                            # Логируем тело ответа, но ограничиваем размер для больших ответов
                            log_response = json.dumps(response_data, ensure_ascii=False)
                            if len(log_response) > 1000:
                                logger.debug(f"[{request_id}] Тело ответа (сокращено): {log_response[:1000]}...")
                            else:
                                logger.debug(f"[{request_id}] Тело ответа: {log_response}")
                            return {
                                "status": response.status,
                                "data": response_data
                            }
                        except json.JSONDecodeError as e:
                            logger.error(f"[{request_id}] Ошибка декодирования JSON: {e}")
                            logger.error(f"[{request_id}] Текст ответа: {response_text[:500]}...")
                            return {
                                "status": response.status,
                                "data": {"error": "Invalid JSON response", "text": response_text[:500]}
                            }
        except aiohttp.ClientError as e:
            logger.error(f"Ошибка HTTP-клиента: {e}")
            return {
                "status": 500,
                "data": {"error": f"Client error: {str(e)}"}
            }
        except asyncio.TimeoutError:
            logger.error(f"Таймаут запроса к {url} после {timeout} секунд")
            return {
                "status": 408,
                "data": {"error": f"Request timeout after {timeout} seconds"}
            }
        except Exception as e:
            logger.error(f"Неожиданная ошибка при выполнении запроса: {e}")
            return {
                "status": 500,
                "data": {"error": f"Unexpected error: {str(e)}"}
            }

    async def process_photo(self, photo_data: bytes) -> str:
        """Обработка фотографии (изменение размера и конвертация в base64)"""
        try:
            # Открываем изображение из байтов
            image = Image.open(BytesIO(photo_data))
            
            # Изменяем размер изображения, если оно больше максимального
            if image.width > MAX_PHOTO_SIZE[0] or image.height > MAX_PHOTO_SIZE[1]:
                image.thumbnail(MAX_PHOTO_SIZE, Image.LANCZOS)
            
            # Определяем оптимальное качество сжатия в зависимости от размера
            original_size = len(photo_data)
            target_size = 1 * 1024 * 1024  # Целевой размер 1MB
            
            # Начинаем с высокого качества
            quality = PHOTO_QUALITY
            
            # Конвертируем изображение в JPEG и сохраняем в буфер
            buffer = BytesIO()
            image.convert("RGB").save(buffer, format="JPEG", quality=quality, optimize=True)
            compressed_size = buffer.tell()
            
            # Если размер все еще слишком большой, уменьшаем качество
            if compressed_size > target_size and original_size > target_size:
                # Рассчитываем новое качество пропорционально
                new_quality = int(quality * (target_size / compressed_size) * 0.9)  # 10% запас
                new_quality = max(30, min(95, new_quality))  # Ограничиваем качество в разумных пределах
                
                # Пробуем сжать с новым качеством
                buffer = BytesIO()
                image.convert("RGB").save(buffer, format="JPEG", quality=new_quality, optimize=True)
                logger.debug(f"Изображение сжато с качеством {new_quality} (было {quality})")
            
            buffer.seek(0)
            
            # Конвертируем в base64
            base64_image = base64.b64encode(buffer.getvalue()).decode("utf-8")
            
            # Добавляем префикс для data URL
            data_url = f"data:image/jpeg;base64,{base64_image}"
            
            logger.debug(f"Фотография обработана: {image.width}x{image.height}, размер: {len(data_url) / 1024:.1f}KB")
            return data_url
        except Exception as e:
            logger.error(f"Ошибка при обработке фотографии: {e}")
            raise

    async def train_model(
        self, name: str, type: str, images: List[str], telegram_id: int
    ) -> Dict[str, Any]:
        """Отправка запроса на обучение модели"""
        data = {
            "name": name,
            "type": type,
            "images": images,
            "telegram_id": telegram_id
        }
        
        logger.info(f"Отправка запроса на обучение модели: {name}, тип: {type}, изображений: {len(images)}, telegram_id: {telegram_id}")
        
        # Добавляем детальное логирование
        logger.debug(f"Параметры обучения модели: name={name}, type={type}, images_count={len(images)}, telegram_id={telegram_id}")
        
        response = await self._make_request("POST", self.train_model_endpoint, data)
        
        # Логируем результат запроса
        if response["status"] in (200, 201, 202):
            logger.info(f"Успешный запрос на обучение модели: {name}, статус: {response['status']}")
            model_id = response["data"].get("modelId")
            if model_id:
                logger.info(f"Получен ID модели: {model_id}")
            else:
                logger.warning(f"ID модели отсутствует в ответе API")
        else:
            logger.error(f"Ошибка при запросе на обучение модели: {name}, статус: {response['status']}, ошибка: {response['data'].get('error', 'Unknown error')}")
        
        return response

    async def generate_images(
        self, model_id: int, prompt: str, num_images: int = 4, telegram_id: int = None, wait: bool = True
    ) -> Dict[str, Any]:
        """Отправка запроса на генерацию изображений"""
        data = {
            "modelId": model_id,
            "prompt": prompt,
            "numImages": num_images,
            "wait": wait
        }
        
        if telegram_id:
            data["telegram_id"] = telegram_id
        
        logger.info(f"Отправка запроса на генерацию изображений: модель: {model_id}, промпт: {prompt}, количество: {num_images}, telegram_id: {telegram_id}")
        
        # Добавляем детальное логирование
        logger.debug(f"Параметры генерации изображений: model_id={model_id}, prompt='{prompt}', num_images={num_images}, wait={wait}, telegram_id={telegram_id}")
        
        response = await self._make_request("POST", self.generate_images_endpoint, data)
        
        # Логируем результат запроса
        if response["status"] in (200, 201, 202):
            logger.info(f"Успешный запрос на генерацию изображений: модель {model_id}, статус: {response['status']}")
            prompt_id = response["data"].get("promptId")
            if prompt_id:
                logger.info(f"Получен ID промпта: {prompt_id}")
            else:
                logger.warning(f"ID промпта отсутствует в ответе API")
                
            # Логируем информацию о сгенерированных изображениях
            images = response["data"].get("images", [])
            logger.info(f"Получено {len(images)} изображений")
        else:
            logger.error(f"Ошибка при запросе на генерацию изображений: модель {model_id}, статус: {response['status']}, ошибка: {response['data'].get('error', 'Unknown error')}")
        
        return response
        
    async def send_media_group_to_finetune(
        self, model_name: str, model_type: str, file_urls: List[str], telegram_id: int
    ) -> Dict[str, Any]:
        """Отправка медиагруппы на вебхук для фиксации модели"""
        data = {
            "name": model_name,
            "type": model_type,
            "images": file_urls,
            "telegram_id": telegram_id
        }
        
        logger.info(f"Отправка медиагруппы на вебхук: {model_name}, тип: {model_type}, изображений: {len(file_urls)}, telegram_id: {telegram_id}")
        
        # Добавляем детальное логирование
        logger.debug(f"Параметры для вебхука: name={model_name}, type={model_type}, images_count={len(file_urls)}, telegram_id={telegram_id}")
        
        response = await self._make_request("POST", self.finetune_webhook_endpoint, data)
        
        # Логируем результат запроса
        if response["status"] in (200, 201, 202):
            logger.info(f"Успешная отправка медиагруппы на вебхук: {model_name}, статус: {response['status']}")
        else:
            logger.error(f"Ошибка при отправке медиагруппы на вебхук: {model_name}, статус: {response['status']}, ошибка: {response['data'].get('error', 'Unknown error')}")
        
        return response 