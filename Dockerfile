FROM python:3.11-slim

WORKDIR /app

# Установка зависимостей
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Копирование файлов проекта
COPY . .

# Переменные окружения для порта
ENV PORT=8080

# Запуск приложения
CMD ["python", "main.py"] 