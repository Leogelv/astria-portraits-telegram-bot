#!/usr/bin/env python3
"""
Скрипт для тестирования API-эндпоинтов
"""

import os
import asyncio
import json
from dotenv import load_dotenv
from loguru import logger

from api_client import ApiClient


# Загружаем переменные окружения
load_dotenv()

# Настраиваем логирование
logger.add("logs/test_api.log", rotation="10 MB", level="DEBUG")


async def test_train_model():
    """Тестирование эндпоинта для обучения модели"""
    api = ApiClient()
    
    # Тестовые данные
    name = "Тестовая модель"
    type = "woman"
    # Используем тестовые изображения (data URL)
    images = [
        "data:image/jpeg;base64,/9j/4AAQSkZJRgABAQEASABIAAD/2wBDAAMCAgICAgMCAgIDAwMDBAYEBAQEBAgGBgUGCQgKCgkICQkKDA8MCgsOCwkJDRENDg8QEBEQCgwSExIQEw8QEBD/2wBDAQMDAwQDBAgEBAgQCwkLEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBD/wAARCAABAAEDASIAAhEBAxEB/8QAFQABAQAAAAAAAAAAAAAAAAAAAAn/xAAUEAEAAAAAAAAAAAAAAAAAAAAA/8QAFAEBAAAAAAAAAAAAAAAAAAAAAP/EABQRAQAAAAAAAAAAAAAAAAAAAAD/2gAMAwEAAhEDEQA/AL+AD//Z",
        "data:image/jpeg;base64,/9j/4AAQSkZJRgABAQEASABIAAD/2wBDAAMCAgICAgMCAgIDAwMDBAYEBAQEBAgGBgUGCQgKCgkICQkKDA8MCgsOCwkJDRENDg8QEBEQCgwSExIQEw8QEBD/2wBDAQMDAwQDBAgEBAgQCwkLEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBD/wAARCAABAAEDASIAAhEBAxEB/8QAFQABAQAAAAAAAAAAAAAAAAAAAAn/xAAUEAEAAAAAAAAAAAAAAAAAAAAA/8QAFAEBAAAAAAAAAAAAAAAAAAAAAP/EABQRAQAAAAAAAAAAAAAAAAAAAAD/2gAMAwEAAhEDEQA/AL+AD//Z",
        "data:image/jpeg;base64,/9j/4AAQSkZJRgABAQEASABIAAD/2wBDAAMCAgICAgMCAgIDAwMDBAYEBAQEBAgGBgUGCQgKCgkICQkKDA8MCgsOCwkJDRENDg8QEBEQCgwSExIQEw8QEBD/2wBDAQMDAwQDBAgEBAgQCwkLEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBD/wAARCAABAAEDASIAAhEBAxEB/8QAFQABAQAAAAAAAAAAAAAAAAAAAAn/xAAUEAEAAAAAAAAAAAAAAAAAAAAA/8QAFAEBAAAAAAAAAAAAAAAAAAAAAP/EABQRAQAAAAAAAAAAAAAAAAAAAAD/2gAMAwEAAhEDEQA/AL+AD//Z",
        "data:image/jpeg;base64,/9j/4AAQSkZJRgABAQEASABIAAD/2wBDAAMCAgICAgMCAgIDAwMDBAYEBAQEBAgGBgUGCQgKCgkICQkKDA8MCgsOCwkJDRENDg8QEBEQCgwSExIQEw8QEBD/2wBDAQMDAwQDBAgEBAgQCwkLEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBD/wAARCAABAAEDASIAAhEBAxEB/8QAFQABAQAAAAAAAAAAAAAAAAAAAAn/xAAUEAEAAAAAAAAAAAAAAAAAAAAA/8QAFAEBAAAAAAAAAAAAAAAAAAAAAP/EABQRAQAAAAAAAAAAAAAAAAAAAAD/2gAMAwEAAhEDEQA/AL+AD//Z"
    ]
    telegram_id = 123456789  # Тестовый Telegram ID
    
    logger.info(f"Тестирование обучения модели: {name}")
    
    # Отправляем запрос
    response = await api.train_model(name, type, images, telegram_id)
    
    # Выводим результат
    logger.info(f"Статус: {response['status']}")
    logger.info(f"Ответ: {json.dumps(response['data'], indent=2, ensure_ascii=False)}")
    
    return response


async def test_generate_images():
    """Тестирование эндпоинта для генерации изображений"""
    api = ApiClient()
    
    # Тестовые данные
    model_id = 1  # ID тестовой модели
    prompt = "элегантный портрет женщины в роскошной обстановке"
    num_images = 2  # Для теста генерируем меньше изображений
    telegram_id = 123456789  # Тестовый Telegram ID
    
    logger.info(f"Тестирование генерации изображений для модели {model_id}")
    logger.info(f"Промпт: {prompt}")
    
    # Отправляем запрос
    response = await api.generate_images(
        model_id=model_id,
        prompt=prompt,
        num_images=num_images,
        telegram_id=telegram_id,
        wait=True
    )
    
    # Выводим результат
    logger.info(f"Статус: {response['status']}")
    logger.info(f"Ответ: {json.dumps(response['data'], indent=2, ensure_ascii=False)}")
    
    return response


async def main():
    """Основная функция для запуска тестов"""
    # Создаем директорию для логов, если она не существует
    os.makedirs("logs", exist_ok=True)
    
    logger.info("Начало тестирования API-эндпоинтов")
    
    try:
        # Тестируем обучение модели
        train_response = await test_train_model()
        
        # Если обучение модели успешно, тестируем генерацию изображений
        if train_response["status"] in (200, 201, 202):
            model_id = train_response["data"].get("modelId")
            if model_id:
                # Ждем немного, чтобы модель начала обучаться
                logger.info("Ожидание 5 секунд перед генерацией изображений...")
                await asyncio.sleep(5)
                
                # Тестируем генерацию изображений
                await test_generate_images()
            else:
                logger.error("Не удалось получить ID модели из ответа")
        else:
            logger.error("Тест обучения модели не прошел, пропускаем тест генерации изображений")
    
    except Exception as e:
        logger.error(f"Ошибка при тестировании API: {e}")
    
    logger.info("Завершение тестирования API-эндпоинтов")


if __name__ == "__main__":
    asyncio.run(main()) 