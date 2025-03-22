from enum import Enum, auto
from typing import Dict, List, Optional, Any, Union
from loguru import logger
import threading
import time
import copy


class UserState(Enum):
    """Перечисление возможных состояний пользователя"""
    IDLE = auto()  # Начальное состояние
    UPLOADING_PHOTOS = auto()  # Загрузка фотографий
    ENTERING_MODEL_NAME = auto()  # Ввод имени модели
    TRAINING_MODEL = auto()  # Обучение модели
    SELECTING_MODEL = auto()  # Выбор модели
    ENTERING_PROMPT = auto()  # Ввод промпта
    GENERATING_IMAGES = auto()  # Генерация изображений
    SELECTING_MODEL_TYPE = auto()  # Выбор типа модели
    ENTERING_MODEL_NAME_FOR_MEDIA_GROUP = auto()  # Состояние для ввода имени модели при обработке медиагруппы
    SELECTING_MODEL_TYPE_FOR_MEDIA_GROUP = auto()  # Выбор типа модели для медиагруппы


class StateManager:
    """Класс для управления состоянием пользователя с улучшенной поддержкой многопользовательской работы"""

    def __init__(self):
        """Инициализация менеджера состояний"""
        # Словарь для хранения состояний пользователей: {telegram_id: UserState}
        self.user_states: Dict[int, UserState] = {}
        
        # Словарь для хранения данных пользователей: {telegram_id: Dict[str, Any]}
        self.user_data: Dict[int, Dict[str, Any]] = {}
        
        # Блокировки для избежания гонок условий при параллельном доступе
        self.state_lock = threading.RLock()
        self.data_lock = threading.RLock()
        
        # Кэш последнего времени активности пользователя для потенциальной очистки неактивных сессий
        self.last_activity: Dict[int, float] = {}
        
        # Время жизни неактивной сессии в секундах (24 часа)
        self.session_ttl = 24 * 60 * 60
        
        logger.info("Инициализирован улучшенный менеджер состояний с поддержкой многопользовательской работы")

    def get_state(self, user_id: int) -> UserState:
        """Получение текущего состояния пользователя"""
        with self.state_lock:
            state = self.user_states.get(user_id, UserState.IDLE)
            # Обновляем время последней активности
            self.last_activity[user_id] = time.time()
            logger.debug(f"Получено состояние пользователя {user_id}: {state.name}")
            return state

    def set_state(self, user_id: int, state: UserState) -> None:
        """Установка состояния пользователя"""
        with self.state_lock:
            logger.debug(f"Установка состояния пользователя {user_id}: {state.name}")
            self.user_states[user_id] = state
            # Обновляем время последней активности
            self.last_activity[user_id] = time.time()

    def reset_state(self, user_id: int) -> None:
        """Сброс состояния пользователя в начальное с сохранением важных данных"""
        # Сначала сохраняем важные данные
        important_data = self.save_important_data(user_id)
        
        with self.state_lock:
            self.user_states[user_id] = UserState.IDLE
            logger.debug(f"Сброс состояния пользователя {user_id}")
        
        with self.data_lock:
            if user_id in self.user_data:
                self.user_data[user_id] = {}
                # Восстанавливаем важные данные после очистки
                self.restore_important_data(user_id, important_data)
        
        # Обновляем время последней активности
        self.last_activity[user_id] = time.time()

    def get_data(self, user_id: int, key: Optional[str] = None) -> Any:
        """Получение данных пользователя"""
        with self.data_lock:
            # Обновляем время последней активности
            self.last_activity[user_id] = time.time()
            
            if user_id not in self.user_data:
                self.user_data[user_id] = {}
            
            if key is None:
                # Возвращаем копию данных чтобы избежать изменения извне
                return copy.deepcopy(self.user_data[user_id])
            
            # Получаем значение по ключу, если есть
            value = self.user_data[user_id].get(key)
            
            # Для сложных типов делаем копию, чтобы избежать неожиданных изменений
            if isinstance(value, (dict, list)):
                return copy.deepcopy(value)
            
            return value

    def set_data(self, user_id: int, key: str, value: Any) -> None:
        """Установка данных пользователя"""
        with self.data_lock:
            if user_id not in self.user_data:
                self.user_data[user_id] = {}
            
            # Для сложных типов делаем копию, чтобы избежать неожиданных изменений
            if isinstance(value, (dict, list)):
                value = copy.deepcopy(value)
            
            self.user_data[user_id][key] = value
            logger.debug(f"Установлены данные пользователя {user_id}: {key}={value}")
            
            # Обновляем время последней активности
            self.last_activity[user_id] = time.time()

    def update_data(self, user_id: int, data: Dict[str, Any]) -> None:
        """Обновление данных пользователя"""
        with self.data_lock:
            if user_id not in self.user_data:
                self.user_data[user_id] = {}
            
            # Делаем копию данных перед обновлением
            data_copy = copy.deepcopy(data)
            self.user_data[user_id].update(data_copy)
            logger.debug(f"Обновлены данные пользователя {user_id}: {data}")
            
            # Обновляем время последней активности
            self.last_activity[user_id] = time.time()

    def clear_data(self, user_id: int, key: Optional[str] = None) -> None:
        """Очистка данных пользователя"""
        with self.data_lock:
            if user_id not in self.user_data:
                return
            
            if key is None:
                # Сохраняем важные данные перед очисткой
                important_data = self.save_important_data(user_id)
                
                self.user_data[user_id] = {}
                
                # Восстанавливаем важные данные после очистки
                self.restore_important_data(user_id, important_data)
                
                logger.debug(f"Очищены все данные пользователя {user_id} с сохранением важных данных")
            elif key in self.user_data[user_id]:
                del self.user_data[user_id][key]
                logger.debug(f"Очищены данные пользователя {user_id}: {key}")
            
            # Обновляем время последней активности
            self.last_activity[user_id] = time.time()

    def add_to_list(self, user_id: int, key: str, value: Any) -> None:
        """Добавление значения в список данных пользователя"""
        with self.data_lock:
            if user_id not in self.user_data:
                self.user_data[user_id] = {}
            
            if key not in self.user_data[user_id]:
                self.user_data[user_id][key] = []
            
            # Для сложных типов делаем копию, чтобы избежать неожиданных изменений
            if isinstance(value, (dict, list)):
                value = copy.deepcopy(value)
            
            self.user_data[user_id][key].append(value)
            logger.debug(f"Добавлено значение в список {key} пользователя {user_id}: {value}")
            
            # Обновляем время последней активности
            self.last_activity[user_id] = time.time()

    def get_list(self, user_id: int, key: str) -> List[Any]:
        """Получение списка данных пользователя"""
        with self.data_lock:
            # Обновляем время последней активности
            self.last_activity[user_id] = time.time()
            
            if user_id not in self.user_data or key not in self.user_data[user_id]:
                return []
            
            # Возвращаем копию списка
            return copy.deepcopy(self.user_data[user_id][key])

    def save_important_data(self, user_id: int) -> Dict[str, Any]:
        """Сохранение важных данных пользователя (имя и тип модели)"""
        with self.data_lock:
            important_data = {}
            
            if user_id in self.user_data:
                if "model_name" in self.user_data[user_id]:
                    important_data["model_name"] = self.user_data[user_id]["model_name"]
                
                if "model_type" in self.user_data[user_id]:
                    important_data["model_type"] = self.user_data[user_id]["model_type"]
                
                # Можно добавить другие важные данные по необходимости
                # if "other_important_key" in self.user_data[user_id]:
                #     important_data["other_important_key"] = self.user_data[user_id]["other_important_key"]
            
            logger.debug(f"Сохранены важные данные пользователя {user_id}: {important_data}")
            return important_data
    
    def restore_important_data(self, user_id: int, important_data: Dict[str, Any]) -> None:
        """Восстановление важных данных пользователя"""
        with self.data_lock:
            if important_data and user_id in self.user_data:
                for key, value in important_data.items():
                    self.user_data[user_id][key] = value
                
                logger.debug(f"Восстановлены важные данные пользователя {user_id}: {important_data}")
    
    def cleanup_inactive_sessions(self) -> None:
        """Очистка неактивных пользовательских сессий"""
        current_time = time.time()
        users_to_remove = []
        
        with self.state_lock:
            for user_id, last_active in self.last_activity.items():
                if current_time - last_active > self.session_ttl:
                    users_to_remove.append(user_id)
        
        if users_to_remove:
            with self.state_lock, self.data_lock:
                for user_id in users_to_remove:
                    if user_id in self.user_states:
                        del self.user_states[user_id]
                    if user_id in self.user_data:
                        del self.user_data[user_id]
                    if user_id in self.last_activity:
                        del self.last_activity[user_id]
            
            logger.info(f"Очищены сессии {len(users_to_remove)} неактивных пользователей") 