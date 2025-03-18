-- Таблица для хранения пользователей Telegram
CREATE TABLE IF NOT EXISTS telegram_users (
  id SERIAL PRIMARY KEY,
  telegram_id BIGINT UNIQUE NOT NULL,
  username TEXT,
  first_name TEXT,
  last_name TEXT,
  created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
  last_active TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
  status TEXT DEFAULT 'active',
  credits INTEGER DEFAULT 0
);

-- Таблица для хранения моделей пользователей
CREATE TABLE IF NOT EXISTS telegram_models (
  id SERIAL PRIMARY KEY,
  telegram_user_id BIGINT REFERENCES telegram_users(telegram_id),
  model_id INTEGER NOT NULL, -- ID модели из основной таблицы models
  created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
  status TEXT DEFAULT 'training'
);

-- Таблица для хранения промптов пользователей
CREATE TABLE IF NOT EXISTS telegram_prompts (
  id SERIAL PRIMARY KEY,
  telegram_user_id BIGINT REFERENCES telegram_users(telegram_id),
  model_id INTEGER NOT NULL,
  prompt TEXT NOT NULL,
  prompt_id TEXT, -- ID промпта из Astria API
  created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
  status TEXT DEFAULT 'processing',
  images JSONB -- массив URL-адресов сгенерированных изображений
);

-- Индексы для ускорения запросов
CREATE INDEX IF NOT EXISTS idx_telegram_users_telegram_id ON telegram_users(telegram_id);
CREATE INDEX IF NOT EXISTS idx_telegram_models_telegram_user_id ON telegram_models(telegram_user_id);
CREATE INDEX IF NOT EXISTS idx_telegram_models_model_id ON telegram_models(model_id);
CREATE INDEX IF NOT EXISTS idx_telegram_prompts_telegram_user_id ON telegram_prompts(telegram_user_id);
CREATE INDEX IF NOT EXISTS idx_telegram_prompts_model_id ON telegram_prompts(model_id); 