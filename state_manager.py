from enum import Enum, auto
from typing import Dict, List, Optional, Any, Union
from loguru import logger
import threading


class UserState(Enum):
    """Перечисление возможных состояний пользователя"""
    IDLE = auto()  # Начальное состояние
    UPLOADING_PHOTOS = auto()  # Загрузка фотографий
    ENTERING_MODEL_NAME = auto()  # Ввод имени модели
    TRAINING_MODEL = auto()  # Обучение модели
    SELECTING_MODEL = auto()  # Выбор модели
    ENTERING_PROMPT = auto()  # Ввод промпта
    GENERATING_IMAGES = auto()  # Генерация изображений
    SELECTING_MODEL_TYPE = auto()  # Добавлено для выбора типа модели
    ENTERING_MODEL_NAME_FOR_MEDIA_GROUP = auto()  # Состояние для ввода имени модели при обработке медиагруппы
    SELECTING_MODEL_TYPE_FOR_MEDIA_GROUP = auto()  # Выбор типа модели для медиагруппы
    SELECTING_MODEL_FOR_VIDEO = auto()  # Выбор модели для создания видео
    SELECTING_IMAGE_FOR_VIDEO = auto()  # Выбор изображения для создания видео


class StateManager:
    """Класс для управления состоянием пользователя"""

    def __init__(self):
        """Инициализация менеджера состояний"""
        # Словарь для хранения состояний пользователей: {telegram_id: UserState}
        self.user_states: Dict[int, UserState] = {}
        
        # Словарь для хранения данных пользователей: {telegram_id: Dict[str, Any]}
        self.user_data: Dict[int, Dict[str, Any]] = {}
        
        # Замок для синхронизации доступа к данным
        self.lock = threading.RLock()
        
        logger.info("Инициализирован менеджер состояний с синхронизацией")

    def get_state(self, user_id: int) -> UserState:
        """Получение текущего состояния пользователя"""
        with self.lock:
            state = self.user_states.get(user_id, UserState.IDLE)
            logger.debug(f"Получено состояние пользователя {user_id}: {state.name}")
            return state

    def set_state(self, user_id: int, state: UserState) -> None:
        """Установка состояния пользователя"""
        with self.lock:
            logger.debug(f"Установка состояния пользователя {user_id}: {state.name}")
            self.user_states[user_id] = state

    def reset_state(self, user_id: int) -> None:
        """Сброс состояния пользователя в начальное"""
        with self.lock:
            logger.debug(f"Сброс состояния пользователя {user_id}")
            self.user_states[user_id] = UserState.IDLE
            if user_id in self.user_data:
                self.user_data[user_id] = {}

    def get_data(self, user_id: int, key: Optional[str] = None) -> Any:
        """Получение данных пользователя"""
        with self.lock:
            if user_id not in self.user_data:
                self.user_data[user_id] = {}
            
            if key is None:
                return self.user_data[user_id].copy()  # Возвращаем копию чтобы избежать race condition
            
            return self.user_data[user_id].get(key)

    def set_data(self, user_id: int, key: str, value: Any) -> None:
        """Установка данных пользователя"""
        with self.lock:
            if user_id not in self.user_data:
                self.user_data[user_id] = {}
            
            self.user_data[user_id][key] = value
            logger.debug(f"Установлены данные пользователя {user_id}: {key}={value}")

    def update_data(self, user_id: int, data: Dict[str, Any]) -> None:
        """Обновление данных пользователя"""
        with self.lock:
            if user_id not in self.user_data:
                self.user_data[user_id] = {}
            
            self.user_data[user_id].update(data)
            logger.debug(f"Обновлены данные пользователя {user_id}: {data}")

    def clear_data(self, user_id: int, key: Optional[str] = None, preserve_keys: Optional[List[str]] = None) -> None:
        """
        Очистка данных пользователя
        
        Args:
            user_id (int): ID пользователя
            key (Optional[str]): Конкретный ключ для очистки (если указан)
            preserve_keys (Optional[List[str]]): Список ключей, которые нужно сохранить при полной очистке
        """
        with self.lock:
            if user_id not in self.user_data:
                return
            
            if key:
                if key in self.user_data[user_id]:
                    del self.user_data[user_id][key]
                    logger.debug(f"Удалены данные пользователя {user_id} с ключом {key}")
            else:
                if preserve_keys:
                    # Сохраняем данные, которые должны быть сохранены
                    preserved_data = {}
                    for preserve_key in preserve_keys:
                        if preserve_key in self.user_data[user_id]:
                            preserved_data[preserve_key] = self.user_data[user_id][preserve_key]
                    
                    # Очищаем данные и восстанавливаем сохраненные
                    self.user_data[user_id] = preserved_data
                    logger.debug(f"Очищены данные пользователя {user_id} с сохранением ключей: {preserve_keys}")
                else:
                    # Полная очистка
                    self.user_data[user_id] = {}
                    logger.debug(f"Полностью очищены данные пользователя {user_id}")

    def add_to_list(self, user_id: int, key: str, value: Any) -> None:
        """Добавление значения в список данных пользователя"""
        with self.lock:
            if user_id not in self.user_data:
                self.user_data[user_id] = {}
            
            if key not in self.user_data[user_id]:
                self.user_data[user_id][key] = []
            
            self.user_data[user_id][key].append(value)
            logger.debug(f"Добавлено значение в список {key} пользователя {user_id}: {value}")

    def get_list(self, user_id: int, key: str) -> List[Any]:
        """Получение списка данных пользователя"""
        with self.lock:
            if user_id not in self.user_data or key not in self.user_data[user_id]:
                return []
            
            return self.user_data[user_id][key].copy()  # Возвращаем копию чтобы избежать race condition 