#!/usr/bin/env python3
"""
Простой healthcheck сервер для Railway
"""

import os
import threading
import http.server
import socketserver
from loguru import logger

# Получаем порт для healthcheck из переменных окружения или используем порт по умолчанию
HEALTHCHECK_PORT = int(os.environ.get("HEALTHCHECK_PORT", 3000))

class HealthcheckHandler(http.server.SimpleHTTPRequestHandler):
    """Обработчик для healthcheck"""
    
    def do_GET(self):
        """Обработка GET запросов"""
        if self.path == "/":
            self.send_response(200)
            self.send_header("Content-type", "application/json")
            self.end_headers()
            self.wfile.write(b'{"status": "OK", "message": "Astria Telegram Bot is running"}')
        else:
            self.send_response(404)
            self.send_header("Content-type", "application/json")
            self.end_headers()
            self.wfile.write(b'{"status": "Error", "message": "Not Found"}')
    
    def log_message(self, format, *args):
        """Логирование запросов"""
        logger.debug(f"Healthcheck: {args[0]} {args[1]} {args[2]}")

def start_healthcheck_server():
    """Запуск healthcheck сервера"""
    
    logger.info(f"Запуск healthcheck сервера на порту {HEALTHCHECK_PORT}")
    
    with socketserver.TCPServer(("", HEALTHCHECK_PORT), HealthcheckHandler) as httpd:
        try:
            logger.info("Healthcheck сервер запущен")
            httpd.serve_forever()
        except KeyboardInterrupt:
            logger.info("Healthcheck сервер остановлен пользователем")
        except Exception as e:
            logger.error(f"Ошибка healthcheck сервера: {e}")
        finally:
            httpd.server_close()
            logger.info("Healthcheck сервер остановлен")

def run_healthcheck_in_thread():
    """Запуск healthcheck сервера в отдельном потоке"""
    thread = threading.Thread(target=start_healthcheck_server)
    thread.daemon = True
    thread.start()
    return thread

if __name__ == "__main__":
    # Запускаем healthcheck сервер напрямую
    start_healthcheck_server() 