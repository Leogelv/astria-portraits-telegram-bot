#!/usr/bin/env python
import asyncio
from database import DatabaseManager

async def main():
    db = DatabaseManager()
    test_user = await db.create_test_user(telegram_id=12345678, username='test_demo_user', credits=999)
    print(f'Результат создания тестового пользователя: {test_user}')

if __name__ == "__main__":
    asyncio.run(main()) 