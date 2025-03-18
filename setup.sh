#!/bin/bash

# Скрипт для установки зависимостей и запуска телеграм-бота

# Проверяем наличие Python
if ! command -v python3 &> /dev/null; then
    echo "Python 3 не найден. Пожалуйста, установите Python 3."
    exit 1
fi

# Создаем виртуальное окружение, если его нет
if [ ! -d "venv" ]; then
    echo "Создаем виртуальное окружение..."
    python3 -m venv venv
fi

# Активируем виртуальное окружение
echo "Активируем виртуальное окружение..."
source venv/bin/activate

# Устанавливаем зависимости
echo "Устанавливаем зависимости..."
pip install -r requirements.txt

# Проверяем наличие файла .env
if [ ! -f ".env" ]; then
    echo "Файл .env не найден. Создаем из .env.example..."
    cp .env.example .env
    echo "Пожалуйста, отредактируйте файл .env, добавив необходимые токены и URL."
    exit 1
fi

# Запускаем бота
echo "Запускаем бота..."
python main.py

