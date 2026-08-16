import gspread
import asyncio
import os
import base64
import json
import tempfile
from dotenv import load_dotenv

load_dotenv()

# Шлях до тимчасового credentials файлу (для Render)
_TMP_CREDS_PATH: str | None = None


def _ensure_credentials() -> str:
    """
    Повертає шлях до credentials.json.

    Пріоритет:
      1. Env var GOOGLE_CREDENTIALS_B64 — base64-рядок (для Render та інших хостингів)
         Декодується і зберігається у тимчасовий файл один раз за сесію.
      2. app/data/credentials.json — локальний файл (для розробки)
    """
    global _TMP_CREDS_PATH

    b64 = os.getenv("GOOGLE_CREDENTIALS_B64")
    if b64:
        if _TMP_CREDS_PATH and os.path.exists(_TMP_CREDS_PATH):
            return _TMP_CREDS_PATH

        creds_data = json.loads(base64.b64decode(b64).decode("utf-8"))
        tmp = tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False, encoding="utf-8"
        )
        json.dump(creds_data, tmp)
        tmp.flush()
        tmp.close()
        _TMP_CREDS_PATH = tmp.name
        return _TMP_CREDS_PATH

    # Фолбек для локальної розробки
    local_path = "app/data/credentials.json"
    if os.path.exists(local_path):
        return local_path

    raise FileNotFoundError(
        "Google credentials не знайдено. "
        "Встанови змінну GOOGLE_CREDENTIALS_B64 або поклади credentials.json в app/data/"
    )


def get_sheet():
    gc = gspread.service_account(filename=_ensure_credentials())
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
