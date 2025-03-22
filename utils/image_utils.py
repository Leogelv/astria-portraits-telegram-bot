import base64
from typing import Optional, List, ByteString
from loguru import logger
from io import BytesIO

def image_to_data_url(image_bytes: ByteString) -> Optional[str]:
    """
    Преобразует изображение в формат base64 data URL.
    
    Args:
        image_bytes (ByteString): Байты изображения
        
    Returns:
        Optional[str]: Строка base64 data URL или None в случае ошибки
    """
    try:
        encoded = base64.b64encode(image_bytes).decode('utf-8')
        return f"data:image/jpeg;base64,{encoded}"
    except Exception as e:
        logger.error(f"Ошибка при преобразовании изображения в data URL: {e}", exc_info=True)
        return None

def data_url_to_image(data_url: str) -> Optional[bytes]:
    """
    Преобразует data URL обратно в байты изображения.
    
    Args:
        data_url (str): Строка data URL
        
    Returns:
        Optional[bytes]: Байты изображения или None в случае ошибки
    """
    try:
        # Отрезаем префикс (data:image/jpeg;base64,)
        if ';base64,' in data_url:
            base64_data = data_url.split(';base64,')[1]
        else:
            base64_data = data_url
            
        return base64.b64decode(base64_data)
    except Exception as e:
        logger.error(f"Ошибка при преобразовании data URL в изображение: {e}", exc_info=True)
        return None

def create_photo_batch(photo_data_urls: List[str], batch_size: int = 4) -> List[List[str]]:
    """
    Разбивает список URL-ов фотографий на батчи.
    
    Args:
        photo_data_urls (List[str]): Список URL-ов фотографий
        batch_size (int, optional): Размер батча. По умолчанию 4.
        
    Returns:
        List[List[str]]: Список батчей фотографий
    """
    return [photo_data_urls[i:i + batch_size] for i in range(0, len(photo_data_urls), batch_size)]
