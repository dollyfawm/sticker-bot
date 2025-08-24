
# Telegram Sticker/Emoji Converter Bot (Render, free 24/7)

## Что это
Бот, который принимает фото/картинки/видео/GIF и превращает их в стикеры (WEBP) и видеостикеры (WEBM), автоматически создаёт твой набор и добавляет туда новые стикеры.

## Быстрый запуск на Render (бесплатно)
### Подготовка в Telegram
1. Открой **@BotFather** в Telegram.
2. Напиши: `/start`, затем `/newbot`.
3. Придумай **имя** (например, *My Sticker Bot*) и **username** (обязательно оканчивается на `bot`, например, *mysticker_helper_bot*).
4. Скопируй выданный **Bot Token** — пригодится на следующем шаге.

### Загрузка кода на GitHub (через веб-интерфейс, без командной строки)
1. Зайди на **github.com** и создай аккаунт (если нет).
2. Нажми **New Repository** → назови, например, `tg-sticker-bot` → **Public** → Create.
3. Нажми **Add file → Upload files**.
4. С компьютера **распакуй ZIP** с проектом и перетащи **все файлы и папки** внутрь окна загрузки на GitHub (или выбери их через файловый диалог).
5. Нажми **Commit changes**.

### Деплой на Render (без карты, бесплатно)
1. Зайди на **render.com**, создай аккаунт.
2. Нажми **New → Web Service** → **Build and deploy from a Git repository** → подключи GitHub → выбери репозиторий `tg-sticker-bot`.
3. Render найдёт наш **Dockerfile** автоматически.
4. Настройки сервиса:
   - **Name**: любое (например, `mystickerbot`).
   - **Region**: ближе к тебе.
   - **Instance Type**: *Free*.
   - **Environment**: *Docker* (определится автоматически).
5. В разделе **Environment Variables** добавь переменные:
   - `BOT_TOKEN` = твой токен из BotFather.
   - (пока больше ничего не добавляй — начнём в режиме *polling*, так проще)
6. Нажми **Create Web Service** и дождись деплоя.
7. После запуска открой **Logs** — должна быть строка вроде `Bot starting in polling mode`.
8. Найди в настройках сервиса **External URL** (что-то вроде `https://<имя>.onrender.com`). Скопируй его — пригодится.

### Переключаемся на вебхуки (чтобы Telegram сам «будил» бота)
1. В настройках сервиса на Render открой **Environment Variables** и добавь:
   - `USE_WEBHOOK` = `true`
   - `WEBHOOK_URL` = `https://<твоё-имя>.onrender.com/tg`  ← подставь свою External URL + `/tg`
   - `PORT` = `8080`
2. Нажми **Save/Apply** и запусти **Redeploy**.
3. В логах должна появиться строка `Bot starting in webhook mode`.
   PTB автоматически установит webhook на указанный URL.

### Проверка
- Открой своего бота в Telegram (по username, который ты задала в BotFather) и отправь ему фото/GIF/видео.
- В ответ бот пришлёт стикер и ссылку на твой набор.

### Частые вопросы
- **Ошибка про FFmpeg** — в нашем Dockerfile он уже установлен. Если ты меняла Dockerfile, верни `ffmpeg` в список пакетов.
- **Видеостикер не добавляется** — исходник слишком длинный/большой. Бот автоматически обрезает до 3 секунд и 512px, но если видео очень тяжёлое, снизь качество/размер до отправки.
- **Группы** — если хочешь использовать бота в группах, в @BotFather сделай `/setprivacy` → *Disable*, чтобы бот видел медиасообщения.

## Локальный запуск (по желанию)
```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
export BOT_TOKEN=123456:ABC-DEF...   # Windows: set BOT_TOKEN=...
python bot.py                         # по умолчанию режим polling
```

Чтобы запустить локально в webhook-режиме, нужен внешний HTTPS URL (обычно не требуется).
