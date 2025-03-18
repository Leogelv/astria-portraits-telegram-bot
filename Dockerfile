FROM python:3.11-slim

WORKDIR /app

# Установка зависимостей
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Копирование файлов проекта
COPY . .

# Переменные окружения для портов
ENV PORT=8080
ENV HEALTHCHECK_PORT=3000

# Открываем оба порта
EXPOSE 8080 3000

# Запуск приложения
CMD ["python", "main.py"] 