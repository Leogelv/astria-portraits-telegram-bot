from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from typing import List, Optional, Dict, Any, Union
from loguru import logger

def create_reply_markup(buttons: List[List[Dict[str, str]]]) -> InlineKeyboardMarkup:
    """
    Создает встроенную клавиатуру из списка кнопок.
    
    Args:
        buttons (List[List[Dict[str, str]]]): Список списков словарей с ключами 'text' и 'callback_data' или 'url'
            Пример: [[{'text': 'Кнопка 1', 'callback_data': 'btn1'}, {'text': 'Кнопка 2', 'callback_data': 'btn2'}]]
            
    Returns:
        InlineKeyboardMarkup: Объект встроенной клавиатуры для Telegram
    """
    keyboard = []
    
    for row in buttons:
        keyboard_row = []
        for button in row:
            if 'url' in button:
                keyboard_row.append(InlineKeyboardButton(button['text'], url=button['url']))
            else:
                keyboard_row.append(InlineKeyboardButton(button['text'], callback_data=button['callback_data']))
        keyboard.append(keyboard_row)
    
    return InlineKeyboardMarkup(keyboard)

async def send_or_edit_message(
    update: Update, 
    context: ContextTypes.DEFAULT_TYPE, 
    text: str, 
    reply_markup: Optional[InlineKeyboardMarkup] = None,
    edit_message_id: Optional[int] = None,
    parse_mode: Optional[str] = None,
    chat_id: Optional[int] = None
) -> Optional[int]:
    """
    Отправляет новое сообщение или редактирует существующее.
    
    Args:
        update (Update): Объект обновления Telegram
        context (ContextTypes.DEFAULT_TYPE): Контекст Telegram
        text (str): Текст сообщения
        reply_markup (Optional[InlineKeyboardMarkup], optional): Клавиатура. По умолчанию None.
        edit_message_id (Optional[int], optional): ID сообщения для редактирования. По умолчанию None.
        parse_mode (Optional[str], optional): Режим парсинга текста. По умолчанию None.
        chat_id (Optional[int], optional): ID чата. По умолчанию None.
        
    Returns:
        Optional[int]: ID отправленного или отредактированного сообщения
    """
    # Если не указан chat_id, берем из update
    if not chat_id and update.effective_chat:
        chat_id = update.effective_chat.id
    
    if not chat_id:
        logger.error("Не удалось определить chat_id для отправки сообщения")
        return None
    
    try:
        if edit_message_id:
            # Редактируем существующее сообщение
            message = await context.bot.edit_message_text(
                chat_id=chat_id,
                message_id=edit_message_id,
                text=text,
                reply_markup=reply_markup,
                parse_mode=parse_mode
            )
            logger.debug(f"Отредактировано сообщение {edit_message_id} для пользователя {chat_id}")
            return message.message_id
        else:
            # Отправляем новое сообщение
            message = await context.bot.send_message(
                chat_id=chat_id,
                text=text,
                reply_markup=reply_markup,
                parse_mode=parse_mode
            )
            logger.debug(f"Отправлено новое сообщение {message.message_id} пользователю {chat_id}")
            return message.message_id
    except Exception as e:
        logger.error(f"Ошибка при отправке/редактировании сообщения: {e}", exc_info=True)
        return None

async def delete_message(
    context: ContextTypes.DEFAULT_TYPE, 
    chat_id: int, 
    message_id: int
) -> bool:
    """
    Удаляет сообщение из чата.
    
    Args:
        context (ContextTypes.DEFAULT_TYPE): Контекст Telegram
        chat_id (int): ID чата
        message_id (int): ID сообщения
        
    Returns:
        bool: True если удаление успешно, иначе False
    """
    try:
        await context.bot.delete_message(chat_id=chat_id, message_id=message_id)
        logger.debug(f"Удалено сообщение {message_id} из чата {chat_id}")
        return True
    except Exception as e:
        logger.error(f"Ошибка при удалении сообщения {message_id}: {e}", exc_info=True)
        return False
