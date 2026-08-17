from aiogram import Router, F, types
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import ReplyKeyboardRemove

from app.data.bot_state import global_state
from app.utils.google_sheets import add_user_to_sheet
from app.db.db_requests import add_user, get_user
import asyncio
import logging
import os
from dotenv import load_dotenv

load_dotenv()
router = Router()

FACULTIES_KPI = [
    "ФМФ", "ФЕЛ", "ФІОТ", "ФТІ", "ХТФ", "ІХФ", "ФБТ",
    "ФАКС", "ФЕА", "ММІ", "ВПІ", "ФПМ", "ФСП", "ІЕЕ",
    "ТЕФ", "РТФ", "ІПСА", "ФЛ"
]

MONO_JAR_URL = "https://send.monobank.ua/jar/9hyDPD94ni"
MONO_CARD = "4874 1000 3144 1507"

RULES_TEXT = (
    "📜 <b>Правила заходу</b>\n\n"
    "<b>Заборонено:</b>\n"
    "1) Діяти всупереч чинному законодавству України\n"
    "2) Проносити напої, їжу, зброю та наркотичні речовини. "
    "Охорона буде здійснювати обшук на вході\n"
    "3) Приходити у стані алкогольного чи наркотичного сп'яніння\n"
    "4) Псувати майно закладу та Студради\n"
    "5) Палити в приміщенні, включно з електронними сигаретами "
    "(окрім спеціально відведеного місця)\n"
    "6) Смітити\n"
    "7) Поводитись зневажливо або агресивно до інших гостей та персоналу\n\n"
    "<i>У разі порушення правил організатори залишають за собою право "
    "вивести людину з заходу без пояснення причин.</i>\n\n"
    "Ти погоджуєшся з правилами заходу?"
)


class RegisterForm(StatesGroup):
    entering_name = State()
    entering_username = State()

    # Вибір університету
    choosing_university = State()

    # Гілка КПІ
    choosing_faculty_kpi = State()
    entering_faculty_text_kpi = State()
    entering_group_kpi = State()

    # Гілка «Інший університет»
    entering_university_other = State()
    entering_faculty_other = State()
    entering_group_other = State()

    # Спільні кроки
    agreeing_to_rules = State()
    waiting_confirmation = State()


@router.callback_query(F.data == "registration")
async def start_registration(callback: types.CallbackQuery, state: FSMContext):
    if not global_state.get("registration_open", True):
        await callback.answer("На жаль, реєстрація вже закрита ❌", show_alert=True)
        return

    existing_user = await get_user(callback.from_user.id)

    if existing_user:
        builder = InlineKeyboardBuilder()
        builder.button(text="🪪 Перейти в профіль", callback_data="profile")
        builder.button(text="Головне меню", callback_data="controller_hub")
        builder.adjust(1)

        await callback.message.edit_text(
            "❌ <b>Ти вже зареєстрований на цей захід!</b>\n\n"
            "Якщо ти хочеш змінити свої дані, перейди у свій Профіль.",
            reply_markup=builder.as_markup()
        )
        await callback.answer()
        return

    try:
        await callback.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass

    text = (
        "[1/5] 👤 Введи твоє ПІБ\n"
        "Приклад: Шевченко Тарас Григорович\n\n"
        "<i>*після підтвердження реєстрації дані можна змінити в профілі</i>"
    )

    try:
        new_msg = await callback.message.edit_text(text)
    except Exception:
        new_msg = await callback.message.answer(text)

    await state.update_data(main_message_id=new_msg.message_id)
    await state.set_state(RegisterForm.entering_name)
    await callback.answer()


# ==================== КРОК 1: ПІБ ====================

@router.message(RegisterForm.entering_name, F.text)
async def process_name(message: types.Message, state: FSMContext):
    await state.update_data(name=message.text.strip())
    data = await state.get_data()
    main_msg_id = data.get("main_message_id")

    try:
        await message.delete()
    except Exception:
        pass

    if message.from_user.username:
        # Юзернейм є — пропускаємо цей крок і переходимо до вибору університету
        await state.update_data(tg_username=f"@{message.from_user.username}")
        
        builder = InlineKeyboardBuilder()
        builder.button(text="🎓 КПІ ім. Ігоря Сікорського", callback_data="uni_kpi")
        builder.button(text="🏫 Інший університет", callback_data="uni_other")
        builder.adjust(1)
        
        text = "🏛 Обери свій університет (Крок 2 з 4):"
        
        if main_msg_id:
            try:
                await message.bot.edit_message_text(
                    chat_id=message.chat.id,
                    message_id=main_msg_id,
                    text=text,
                    reply_markup=builder.as_markup()
                )
            except Exception:
                new_msg = await message.answer(text, reply_markup=builder.as_markup())
                await state.update_data(main_message_id=new_msg.message_id)
        else:
            new_msg = await message.answer(text, reply_markup=builder.as_markup())
            await state.update_data(main_message_id=new_msg.message_id)
            
        await state.set_state(RegisterForm.choosing_university)
        
    else:
        # Юзернейму немає — запитуємо вручну
        text = (
            "📱 Введи свій юзернейм (або телефон/інстаграм) для зв'язку\n"
            "Приклад: @username\n\n"
            "<i>(Оскільки у тебе не встановлений юзернейм в налаштуваннях Telegram, ми запитуємо контактні дані вручну. "
            "Якщо не хочеш нічого вказувати — введи «немає».)</i>"
        )
    
        if main_msg_id:
            try:
                await message.bot.edit_message_text(
                    chat_id=message.chat.id,
                    message_id=main_msg_id,
                    text=text
                )
            except Exception:
                new_msg = await message.answer(text)
                await state.update_data(main_message_id=new_msg.message_id)
        else:
            new_msg = await message.answer(text)
            await state.update_data(main_message_id=new_msg.message_id)
            
        await state.set_state(RegisterForm.entering_username)


# ==================== КРОК 2: ЮЗЕРНЕЙМ ====================

@router.message(RegisterForm.entering_username, F.text)
async def process_username_input(message: types.Message, state: FSMContext):
    raw = message.text.strip()
    # Нормалізуємо — якщо не вказано @ і не "немає", додаємо
    if raw.lower() == "немає":
        tg_username = "немає"
    elif raw.startswith("@"):
        tg_username = raw
    else:
        tg_username = f"@{raw}"

    await state.update_data(tg_username=tg_username)
    data = await state.get_data()
    main_msg_id = data.get("main_message_id")

    try:
        await message.delete()
    except Exception:
        pass

    builder = InlineKeyboardBuilder()
    builder.button(text="🎓 КПІ ім. Ігоря Сікорського", callback_data="uni_kpi")
    builder.button(text="🏫 Інший університет", callback_data="uni_other")
    builder.adjust(1)
    
    text = "🏛 Обери свій університет (Крок 2 з 4):"

    if main_msg_id:
        try:
            await message.bot.edit_message_text(
                chat_id=message.chat.id,
                message_id=main_msg_id,
                text=text,
                reply_markup=builder.as_markup()
            )
        except Exception:
            new_msg = await message.answer(text, reply_markup=builder.as_markup())
            await state.update_data(main_message_id=new_msg.message_id)
    else:
        new_msg = await message.answer(text, reply_markup=builder.as_markup())
        await state.update_data(main_message_id=new_msg.message_id)
    await state.set_state(RegisterForm.choosing_university)


# ==================== КРОК 3: УНІВЕРСИТЕТ ====================

@router.callback_query(RegisterForm.choosing_university, F.data.startswith("uni_"))
async def process_university_choice(callback: types.CallbackQuery, state: FSMContext):
    choice = callback.data

    if choice == "uni_kpi":
        await state.update_data(university="КПІ ім. Ігоря Сікорського")

        # Будуємо клавіатуру факультетів КПІ
        builder = InlineKeyboardBuilder()
        for fac in FACULTIES_KPI:
            builder.button(text=fac, callback_data=f"fac_{fac}")
        builder.button(text="🏫 Інший факультет", callback_data="fac_other")
        builder.adjust(3)

        await callback.message.edit_text(
            "[4/5] 🏛 Обери свій факультет:",
            reply_markup=builder.as_markup()
        )
        await state.set_state(RegisterForm.choosing_faculty_kpi)

    elif choice == "uni_other":
        await callback.message.edit_text(
            "[3/5] 🏫 Введи назву свого університету:"
        )
        await state.set_state(RegisterForm.entering_university_other)

    await callback.answer()


# ==================== ГІЛКА КПІ ====================

@router.callback_query(RegisterForm.choosing_faculty_kpi, F.data.startswith("fac_"))
async def process_kpi_faculty_choice(callback: types.CallbackQuery, state: FSMContext):
    choice = callback.data

    if choice == "fac_other":
        await callback.message.edit_text("[4/5] 🏛 Введи назву свого факультету:")
        await state.set_state(RegisterForm.entering_faculty_text_kpi)
    else:
        faculty_name = choice.replace("fac_", "")
        await state.update_data(faculty=faculty_name)
        
        builder = InlineKeyboardBuilder()
        builder.button(text="Не знаю шифру (Першокурсник)", callback_data="group_unknown")
        
        await callback.message.edit_text(
            "[5/5] 👥 Введи свою групу\nПриклад: ІА-11",
            reply_markup=builder.as_markup()
        )
        await state.set_state(RegisterForm.entering_group_kpi)

    await callback.answer()


@router.message(RegisterForm.entering_faculty_text_kpi, F.text)
async def process_kpi_faculty_text(message: types.Message, state: FSMContext):
    await state.update_data(faculty=message.text.strip().upper())

    data = await state.get_data()
    main_msg_id = data.get("main_message_id")
    
    builder = InlineKeyboardBuilder()
    builder.button(text="Не знаю шифру (Першокурсник)", callback_data="group_unknown")
    text = "[5/5] 👥 Введи свою групу\nПриклад: ІА-11"
    
    try:
        await message.delete()
        await message.bot.edit_message_text(
            chat_id=message.chat.id,
            message_id=main_msg_id,
            text=text,
            reply_markup=builder.as_markup()
        )
    except Exception:
        new_msg = await message.answer(text, reply_markup=builder.as_markup())
        await state.update_data(main_message_id=new_msg.message_id)

    await state.set_state(RegisterForm.entering_group_kpi)


@router.message(RegisterForm.entering_group_kpi, F.text)
async def process_kpi_group(message: types.Message, state: FSMContext):
    await state.update_data(group=message.text.strip().upper())
    try:
        await message.delete()
    except Exception:
        pass
    await ask_for_rules(message, state)


# ==================== ГІЛКА ІНШИЙ УНІВЕРСИТЕТ ====================

@router.message(RegisterForm.entering_university_other, F.text)
async def process_other_university(message: types.Message, state: FSMContext):
    await state.update_data(
        university=message.text.strip(),
        faculty="-",
        group="-"
    )

    try:
        await message.delete()
    except Exception:
        pass

    await ask_for_rules(message, state)


# ==================== ПРАВИЛА ЗАХОДУ ====================

@router.callback_query(RegisterForm.entering_group_kpi, F.data == "group_unknown")
async def process_unknown_group(callback: types.CallbackQuery, state: FSMContext):
    await state.update_data(group="Не знаю (Першокурсник)")
    await ask_for_rules(callback, state)
    await callback.answer()


async def ask_for_rules(event: types.Message | types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    main_msg_id = data.get("main_message_id")
    bot = event.bot
    chat_id = event.message.chat.id if isinstance(event, types.CallbackQuery) else event.chat.id

    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Погоджуюсь з правилами", callback_data="agree_rules")

    if isinstance(event, types.CallbackQuery):
        await event.message.edit_text(
            text=RULES_TEXT,
            reply_markup=builder.as_markup()
        )
    else:
        if main_msg_id:
            try:
                await bot.edit_message_text(
                    chat_id=chat_id,
                    message_id=main_msg_id,
                    text=RULES_TEXT,
                    reply_markup=builder.as_markup()
                )
            except Exception:
                new_msg = await event.answer(text=RULES_TEXT, reply_markup=builder.as_markup())
                await state.update_data(main_message_id=new_msg.message_id)

    await state.set_state(RegisterForm.agreeing_to_rules)


@router.callback_query(RegisterForm.agreeing_to_rules, F.data == "agree_rules")
async def process_agree_rules(callback: types.CallbackQuery, state: FSMContext):
    await show_confirmation_screen(callback, state)
    await callback.answer()


# ==================== ЕКРАН ПІДТВЕРДЖЕННЯ ====================

async def show_confirmation_screen(event: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    name = data.get('name')
    tg_username = data.get('tg_username')
    university = data.get('university')
    faculty = data.get('faculty')
    group = data.get('group')

    confirmation_text = (
        f"📋 <b>Перевір свої дані перед підтвердженням:</b>\n\n"
        f"👤 <b>ПІБ:</b> {name}\n"
        f"📱 <b>Telegram:</b> {tg_username}\n"
        f"🎓 <b>Університет:</b> {university}\n"
    )
    
    if faculty and faculty != "-":
        confirmation_text += f"🏛 <b>Факультет:</b> {faculty}\n"
    if group and group != "-":
        confirmation_text += f"👥 <b>Група:</b> {group}\n"
        
    confirmation_text += "\nУсе правильно? Натисни підтвердити або скасуй реєстрацію."

    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Підтвердити реєстрацію", callback_data="confirm_registration")
    builder.button(text="❌ Скасувати", callback_data="cancel_registration")
    builder.adjust(1)

    await event.message.edit_text(text=confirmation_text, reply_markup=builder.as_markup())
    await state.set_state(RegisterForm.waiting_confirmation)


@router.callback_query(RegisterForm.waiting_confirmation, F.data == "confirm_registration")
async def confirm_registration(callback: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    name = data.get('name')
    tg_username = data.get('tg_username')
    university = data.get('university')
    faculty = data.get('faculty')
    group = data.get('group')

    # Якщо юзер вводив юзернейм вручну — беремо його,
    # але також беремо реальний Telegram username для ідентифікації
    real_username = callback.from_user.username
    stored_username = tg_username if tg_username else (f"@{real_username}" if real_username else "немає")

    try:
        await add_user(
            tg_id=callback.from_user.id,
            username=stored_username,
            name=name,
            university=university,
            faculty=faculty,
            group_name=group,
        )

        asyncio.create_task(add_user_to_sheet(
            tg_id=callback.from_user.id,
            username=stored_username,
            name=name,
            university=university,
            faculty=faculty,
            group_name=group,
        ))

        builder = InlineKeyboardBuilder()
        builder.button(text="🪪 Мій профіль", callback_data="profile")
        builder.button(text="Головне меню", callback_data="controller_hub")
        builder.adjust(1)

        await callback.message.edit_text(
            text=(
                "🎉 <b>Реєстрацію підтверджено!</b>\n\n"
                "Твої дані збережено. Чекаємо тебе на <b>Дні Першокурсника</b>!\n\n"
                "📅 <b>Коли:</b> 31 серпня\n"
                "📍 <b>Де:</b> вул. Політехнічна (біля 18 корпусу)\n"
                "⏰ <b>Час:</b> 17:00–22:00\n\n"
                "💙 Будемо вдячні за донат на підтримку Сил оборони:\n"
                f"🔗 <a href='{MONO_JAR_URL}'>Посилання на банку</a>\n"
                f"💳 {MONO_CARD}"
            ),
            reply_markup=builder.as_markup(),
            disable_web_page_preview=True
        )
        await state.clear()

    except Exception as e:
        logging.error(f"\033[31mПомилка БД під час реєстрації: {e}\033[0m")
        builder = InlineKeyboardBuilder()
        builder.button(text="Спробувати ще раз", callback_data="registration")

        await callback.message.edit_text(
            text="⚠️ Виникла помилка під час збереження даних. Спробуй ще раз.",
            reply_markup=builder.as_markup()
        )
        await state.clear()

    await callback.answer()


@router.callback_query(RegisterForm.waiting_confirmation, F.data == "cancel_registration")
async def cancel_registration(callback: types.CallbackQuery, state: FSMContext):
    builder = InlineKeyboardBuilder()
    builder.button(text="Повернутись в меню", callback_data="controller_hub")

    await callback.message.edit_text(
        text="❌ <b>Реєстрацію скасовано.</b> Твої дані не було збережено в системі.",
        reply_markup=builder.as_markup()
    )
    await state.clear()
    await callback.answer()
