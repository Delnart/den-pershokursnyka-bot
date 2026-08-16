import gspread
import asyncio
import os
import json
from dotenv import load_dotenv

load_dotenv()


from datetime import datetime

def get_sheet():
    """
    Підключається до Google Sheets.

    Пріоритет credentials:
      1. GOOGLE_CREDENTIALS_JSON — вміст credentials.json як рядок (для Render)
      2. app/data/credentials.json — локальний файл (для розробки)
    """
    creds_json = os.getenv("GOOGLE_CREDENTIALS_JSON")
    if creds_json:
        gc = gspread.service_account_from_dict(json.loads(creds_json))
    else:
        gc = gspread.service_account(filename="app/data/credentials.json")

    sheet_url_or_id = os.getenv("SHEET_URL", "")
    
    if not sheet_url_or_id:
        # Резервний варіант, якщо SHEET_URL раптом пустий (на всяк випадок)
        return gc.open(os.getenv("LOG_SHEET_NAME"))
        
    try:
        # Якщо користувач ввів лише ID (наприклад 11HUlPn4...)
        if not sheet_url_or_id.startswith("http"):
            return gc.open_by_key(sheet_url_or_id)
        else:
            return gc.open_by_url(sheet_url_or_id)
    except gspread.exceptions.SpreadsheetNotFound:
        # Якщо і це не спрацювало, спробуємо по старинці через назву
        return gc.open(os.getenv("LOG_SHEET_NAME"))


def _append_row_sync(row_data: list):
    sh = get_sheet()
    # Автоматично беремо перший аркуш у файлі (зазвичай "Відповіді форми 1" або "Аркуш1")
    ws = sh.sheet1
    ws.append_row(row_data)


async def add_user_to_sheet(tg_id: int, username: str, name: str,
                            university: str = None, faculty: str = None,
                            group_name: str = None):
    try:
        from zoneinfo import ZoneInfo
        kyiv_tz = ZoneInfo("Europe/Kyiv")
        timestamp = datetime.now(kyiv_tz).strftime("%d.%m.%Y %H:%M:%S")
        
        # Формат колонок:
        # A: Позначка часу
        # B: ПІБ
        # C: Юзернейм
        # D: Університет
        # E: Факультет
        # F: Група
        # G: Правила
        # H: tg_id (потрібен боту для оновлення профілю)
        row = [
            timestamp, 
            name, 
            username, 
            university, 
            faculty, 
            group_name, 
            "Так", 
            str(tg_id)
        ]
        row = [item if item is not None else "" for item in row]

        # Увага: Форма зазвичай пише у "Відповіді форми 1". Якщо ти хочеш 
        # щоб бот писав туди ж, переконайся, що лист називається саме так. 
        # Або можна залишити "Users".
        await asyncio.to_thread(_append_row_sync, row)
        print(f"✅ Користувача {name} успішно додано в Sheets!")
    except Exception as e:
        print(f"❌ ПОМИЛКА додавання користувача в Sheets: {e}")


def _update_user_sync(tg_id: str, field: str, new_value):
    sh = get_sheet()
    ws = sh.sheet1
    try:
        # Шукаємо tg_id у 8-й колонці (H)
        cell = ws.find(str(tg_id), in_column=8)
        if cell:
            col_map = {
                "name":       "B",
                "username":   "C",
                "university": "D",
                "faculty":    "E",
                "group_name": "F",
            }
            if field in col_map:
                cell_label = f"{col_map[field]}{cell.row}"
                write_value = new_value if new_value is not None else ""
                ws.update_acell(cell_label, write_value)
                print(f"✅ Sheets: Оновлено ID {tg_id}, поле {field} -> {write_value}")
        else:
            print(f"⚠️ Sheets: Користувача {tg_id} не знайдено для оновлення.")
    except Exception as e:
        print(f"❌ Sheets: Помилка оновлення користувача: {e}")


async def update_user_in_sheet(tg_id: int, field: str, new_value):
    await asyncio.to_thread(_update_user_sync, str(tg_id), field, new_value)
