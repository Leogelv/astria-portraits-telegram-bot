#!/usr/bin/env python3
"""
Скрипт для запуска локального сервера для тестирования API-эндпоинтов
"""

import os
import json
import asyncio
import uvicorn
from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
from loguru import logger

# Загружаем переменные окружения
load_dotenv()

# Настраиваем логирование
logger.add("logs/local_server.log", rotation="10 MB", level="DEBUG")

# Создаем приложение FastAPI
app = FastAPI(title="Astria API Mock Server")

# Добавляем CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Хранилище для моделей и промптов
models = {}
prompts = {}


@app.post("/api/bot/train-model")
async def train_model(request: Request):
    """Эндпоинт для обучения модели"""
    try:
        data = await request.json()
        logger.info(f"Получен запрос на обучение модели: {data.get('name')}")
        
        # Проверяем обязательные параметры
        if not data.get("name"):
            raise HTTPException(status_code=400, detail="Отсутствует имя модели")
        
        if not data.get("images") or len(data.get("images", [])) < 4:
            raise HTTPException(status_code=400, detail="Недостаточно изображений")
        
        # Генерируем ID модели
        model_id = len(models) + 1
        
        # Создаем запись о модели
        model = {
            "id": model_id,
            "name": data.get("name"),
            "type": data.get("type", "woman"),
            "telegram_id": data.get("telegram_id"),
            "status": "training",
            "tune_id": f"test_tune_{model_id}",
            "created_at": "2023-01-01T00:00:00Z"
        }
        
        # Сохраняем модель
        models[model_id] = model
        
        logger.info(f"Создана модель: {model}")
        
        # Возвращаем ответ
        return {
            "message": "Модель успешно отправлена на обучение",
            "modelId": model_id,
            "status": "training"
        }
    
    except HTTPException as e:
        logger.error(f"Ошибка при обучении модели: {e.detail}")
        raise
    
    except Exception as e:
        logger.error(f"Неожиданная ошибка при обучении модели: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/bot/generate")
async def generate_images(request: Request):
    """Эндпоинт для генерации изображений"""
    try:
        data = await request.json()
        logger.info(f"Получен запрос на генерацию изображений для модели: {data.get('modelId')}")
        
        # Проверяем обязательные параметры
        if not data.get("modelId"):
            raise HTTPException(status_code=400, detail="Отсутствует ID модели")
        
        if not data.get("prompt"):
            raise HTTPException(status_code=400, detail="Отсутствует промпт")
        
        model_id = data.get("modelId")
        
        # Проверяем существование модели
        if model_id not in models:
            raise HTTPException(status_code=404, detail="Модель не найдена")
        
        # Генерируем ID промпта
        prompt_id = len(prompts) + 1
        
        # Создаем запись о промпте
        prompt = {
            "id": prompt_id,
            "model_id": model_id,
            "prompt": data.get("prompt"),
            "telegram_id": data.get("telegram_id"),
            "status": "completed",
            "created_at": "2023-01-01T00:00:00Z",
            "images": [
                f"https://picsum.photos/seed/{prompt_id}_1/512/512",
                f"https://picsum.photos/seed/{prompt_id}_2/512/512",
                f"https://picsum.photos/seed/{prompt_id}_3/512/512",
                f"https://picsum.photos/seed/{prompt_id}_4/512/512"
            ][:data.get("numImages", 4)]
        }
        
        # Сохраняем промпт
        prompts[prompt_id] = prompt
        
        logger.info(f"Создан промпт: {prompt}")
        
        # Если wait=True, возвращаем изображения
        if data.get("wait", False):
            return {
                "message": "Изображения успешно сгенерированы",
                "promptId": prompt_id,
                "status": "completed",
                "images": prompt["images"]
            }
        
        # Иначе возвращаем только ID промпта
        return {
            "message": "Запрос на генерацию изображений отправлен",
            "promptId": prompt_id,
            "status": "processing"
        }
    
    except HTTPException as e:
        logger.error(f"Ошибка при генерации изображений: {e.detail}")
        raise
    
    except Exception as e:
        logger.error(f"Неожиданная ошибка при генерации изображений: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/")
async def root():
    """Корневой эндпоинт"""
    return {
        "message": "Astria API Mock Server",
        "endpoints": [
            "/api/bot/train-model",
            "/api/bot/generate"
        ]
    }


def main():
    """Основная функция для запуска сервера"""
    # Создаем директорию для логов, если она не существует
    os.makedirs("logs", exist_ok=True)
    
    logger.info("Запуск локального сервера для тестирования API-эндпоинтов")
    
    # Запускаем сервер
    uvicorn.run(app, host="0.0.0.0", port=3000)


if __name__ == "__main__":
    main() 