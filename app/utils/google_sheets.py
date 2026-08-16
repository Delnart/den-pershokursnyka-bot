import gspread
import asyncio
import os
import json
from dotenv import load_dotenv

load_dotenv()


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

    return gc.open(os.getenv("LOG_SHEET_NAME"))


def _append_row_sync(sheet_name: str, row_data: list):
    sh = get_sheet()
    ws = sh.worksheet(sheet_name)
    ws.append_row(row_data)


async def add_user_to_sheet(tg_id: int, username: str, name: str,
                            university: str = None, faculty: str = None,
                            group_name: str = None):
    try:
        row = [str(tg_id), username, name, university, faculty, group_name]
        row = [item if item is not None else "" for item in row]

        await asyncio.to_thread(_append_row_sync, "Users", row)
        print(f"✅ Користувача {name} успішно додано в Sheets!")
    except Exception as e:
        print(f"❌ ПОМИЛКА додавання користувача в Sheets: {e}")


def _update_user_sync(tg_id: str, field: str, new_value):
    sh = get_sheet()
    ws = sh.worksheet("Users")
    try:
        cell = ws.find(str(tg_id), in_column=1)
        if cell:
            col_map = {
                "username":   "B",
                "name":       "C",
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
