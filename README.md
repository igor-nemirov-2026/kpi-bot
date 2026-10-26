# KPI-бот: Excel → GitHub → Telegram

Все файлы лежат в корне репозитория — загружаются одним выделением через Add file → Upload files.
Файл workflow.yml — текст для .github/workflows/main.yml (Actions → set up a workflow yourself).

Данные: KPI_import_template.xlsx. Обновить: Add file → Upload files → тот же файл → Commit changes → пост придёт сам.
Расписание: по будням 10:00 и 15:00 по Киеву (зимой; летом cron "0 7,12 * * 1-5").
Секреты: TELEGRAM_BOT_TOKEN (обязательно), TELEGRAM_CHAT_ID (если бот в нескольких чатах).
