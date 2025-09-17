# 🌙 DreamBot — духовный помощник с анализом снов и нумерологией

[![Python](https://img.shields.io/badge/python-3.11-blue.svg)](https://www.python.org/)
[![Docker](https://img.shields.io/badge/docker-ready-blue.svg)](https://www.docker.com/)
[![Aiogram](https://img.shields.io/badge/aiogram-3.x-green.svg)](https://docs.aiogram.dev/)
[![OpenAI](https://img.shields.io/badge/OpenAI-API-orange.svg)](https://platform.openai.com/)

---

## 📖 Описание

**DreamBot** — Telegram-бот, который помогает понимать свои сны и строит краткий **нумерологический профиль**.  
Бот сочетает:

- 🔑 Базовый NLP-анализ снов (символы/эмоции/контекст).
- ⭐ Премиум-анализ сна через **OpenAI API**.
- 🔢 **Нумерология**: профиль по ФИО и дате рождения.
- 🗄️ PostgreSQL (история, профили, платежи), ⚡ Redis (кэш/сессии).
- 🐳 Деплой через Docker / Railway.

---

## 🆕 Что нового

### 1) Нумерология (новый модуль)
- Команда/кнопка **«✍ Нумерология»** → бот просит строку вида:  
  `ФИО; ДД.ММ.ГГГГ` (пример: `Иванов Иван Иванович; 22.07.2001`).
- Бэкенд сам **считает числа** (судьбы, имени, души, личности, день рождения, личный год) и передаёт их LLM для **только интерпретации** (LLM не пересчитывает).
- Ответ форматируется для Telegram (жирный/курсив, эмодзи, переносы строк), **без HTML-списков** — чтобы избежать ошибок `can't parse entities`.
- Внизу профиля добавляется сноска:  
  _«В расчётах используется пифагорейская система в адаптации для кириллицы (вариант с отдельной буквой Ё, Й=2, Ь/Ъ игнорируются)»._
- Профиль **сохраняется в БД** (таблица `numerology_profiles`).

### 2) Многоключевая маршрутизация LLM
- Добавлен роутер API-ключей и моделей: `app/core/llm_router.py`.
- Можно хранить **несколько ключей** для каждой фичи (сон / нумерология). Роутер делает циклический перебор и упрощает ротацию ключей и разделение бюджетов.
- Единая точка вызова LLM: `app/core/llm_client.py` → `chat(Feature, messages, temperature=...)`.

### 3) Санитайзер Telegram-HTML
- Добавлен `app/core/telegram_html.py` — пропускает только `<b>` и `<i>`, вырезает всё остальное (`<br>`, списки и т.п.).  
  Так мы избавились от ошибок вида `Unsupported start tag "br"/"ul"`.

### 4) Новая таблица БД
- Alembic-миграция `0006_numerology_profiles` создаёт
  `numerology_profiles(user_id, full_name, birth_date, report_html, created_at)`.

---

## 🚀 Функционал

- Приём текста сна и быстрый базовый разбор.
- Премиум-разбор сна через OpenAI (длинный и тональный ответ).
- Ведение истории снов и профилей.
- ✍ **Нумерологический профиль** по ФИО и дате рождения (удобно читаемый ответ + сохранение в БД).
- Клавиатуры/команды: «Записать сон», «Статистика», «Премиум», «Нумерология», «Напоминания».

---

## 🛠️ Технологии

- Python 3.11, Aiogram 3.x  
- SQLAlchemy + Alembic → PostgreSQL  
- Redis (кэш/сессии)  
- Docker / docker-compose  
- OpenAI API (через единый LLM-клиент и роутер)

---

## 📂 Структура проекта

```bash
dreambot/
├── app/
│   ├── bot/
│   │   ├── handlers/
│   │   │   ├── dreams.py
│   │   │   ├── numerology.py          # новый хэндлер
│   │   │   └── ...
│   │   └── main.py
│   ├── core/
│   │   ├── llm_client.py              # единая обёртка вызова LLM
│   │   ├── llm_router.py              # маршрутизатор ключей/моделей
│   │   ├── numerology_service.py      # логика нумерологии + вызов LLM
│   │   ├── numerology_math.py         # расчёт чисел (локально, без LLM)
│   │   └── telegram_html.py           # санитайзер HTML для Telegram
│   ├── db/
│   │   ├── models.py                  # добавлена модель NumerologyProfile
│   │   └── alembic/versions/
│   │       └── 0006_numerology_profiles.py
│   └── ...
├── data/
├── docker-compose.yml
├── Dockerfile
├── requirements.txt
└── README.md
```

---

## ⚙️ Переменные окружения

Поддерживается несколько ключей для каждой фичи (через запятую).

```env
# Telegram
BOT_TOKEN=...

# БД / Redis
DATABASE_URL=postgresql://...
REDIS_URL=redis://...

# Режим премиума (api | demo)
PREMIUM_MODE=api

# Маршрутизация LLM (сон + нумерология)
LLM_DREAM_KEYS=sk-proj-AAA,sk-proj-BBB
LLM_DREAM_MODEL=gpt-4o-mini

LLM_NUMEROLOGY_KEYS=sk-proj-XXX,sk-proj-YYY
LLM_NUMEROLOGY_MODEL=gpt-4o-mini

# Таймауты/ретраи (необязательно)
LLM_TIMEOUT_SECONDS=60
LLM_MAX_RETRIES=2
```

> Ранее использовавшиеся `OPENAI_API_KEY`, `OPENAI_MODEL` можно оставить для обратной совместимости (если ты их ещё используешь в других местах), но новый код опирается на `LLM_*`.

---

## ▶️ Запуск локально (без Docker)

```bash
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt

alembic upgrade head
python -m app.bot.main
```

---

## 🐳 Запуск через Docker

```bash
docker-compose up --build
```

---

## 🧭 Как работает нумерология

1. Пользователь жмёт **«✍ Нумерология»**, бот просит формат:  
   `ФИО; ДД.ММ.ГГГГ`.
2. Бэкенд считает числа (пифагорейская система для кириллицы; `Ё` отдельная, `Й=2`, `Ь/Ъ` игнорируются).
3. LLM **не пересчитывает**, а только **интерпретирует** заранее посчитанные значения.
4. Ответ форматируется (только `<b>` и `<i>`, переносы — обычные `
`) и **сохраняется в БД**.

---

## 🧪 Быстрый тест

- Напиши боту «✍ Нумерология».  
- Отправь: `Иванов Иван Иванович; 22.07.2001`  
- Получишь структурированный профиль + сноску.

---

## 🧯 Трюки и диагностика

- **Дублирующиеся ответы / “Conflict: terminated by other getUpdates request”**  
  → запущены **два** инстанса бота (локально + Railway / две реплики). Оставь один.
- **`can't parse entities`** (HTML)  
  → LLM прислал теги, которые Telegram не поддерживает. Мы пропускаем все ответы через `telegram_html.sanitize_tg_html` — в ответе должны остаться только `<b>` и `<i>`. Если правили шаблоны — не добавляй `<br>`, списки и т.п.
- **SQLAlchemy: “Mapper … has no property ‘numerology_profiles’”**  
  → проверь `back_populates` у `User` ↔ `NumerologyProfile` и запусти миграции (`alembic upgrade head`).

---

## 🧩 Как добавить ещё одну фичу на LLM

1. Добавь новый `Feature.*` в `app/core/llm_router.py`.
2. Пропиши для неё `LLM_<FEATURE>_KEYS` и `LLM_<FEATURE>_MODEL` в `.env`.
3. Вызывай `chat(Feature.NEW_FEATURE, messages, temperature=...)`.

Маршрутизация и ретраи уже внутри.

---

## 🔐 Замечания по приватности

- В БД хранятся только необходимые для работы данные (истории снов/профилей).  
- ФИО и дата рождения используются для формирования профиля и хранятся вместе с HTML-отчётом.

---

## 🧾 Лицензия

MIT (или укажи свою).
