from aiogram import Router, F, types
from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app.db.db_requests import get_user, update_user_field
from app.utils.google_sheets import update_user_in_sheet

import asyncio

router = Router()


class ProfileForm:
    pass


from aiogram.fsm.state import StatesGroup, State


class ProfileEditForm(StatesGroup):
    waiting_for_new_name = State()
    waiting_for_new_username = State()
    waiting_for_new_university = State()
    waiting_for_new_faculty = State()
    waiting_for_new_group = State()


@router.callback_query(F.data == "profile")
async def show_profile(callback: types.CallbackQuery, state: FSMContext):
    await state.clear()
    tg_id = callback.from_user.id

    user = await get_user(tg_id)
    if not user:
        await callback.message.answer("Профіль не знайдено. Спочатку зареєструйся.")
        await callback.answer()
        return

    text = (
        f"👤 <b>ТВІЙ ПРОФІЛЬ</b>\n"
        f"───────────────\n"
        f"<b>ПІБ:</b> {user.name}\n"
        f"<b>Telegram:</b> {user.username}\n"
        f"<b>Університет:</b> {user.university}\n"
    )
    if user.faculty and user.faculty != "-":
        text += f"<b>Факультет:</b> {user.faculty}\n"
    if user.group_name and user.group_name != "-":
        text += f"<b>Група:</b> {user.group_name}\n"
        
    text += (
        f"───────────────\n"
        f"📅 <b>31 серпня | 17:00–22:00</b>\n"
        f"📍 вул. Політехнічна (біля 18 корпусу)"
    )

    builder = InlineKeyboardBuilder()
    builder.button(text="⚙️ Змінити дані", callback_data="prof_edit_menu")
    builder.button(text="Назад", callback_data="controller_hub_new")
    builder.adjust(1)

    try:
        await callback.message.edit_text(text, reply_markup=builder.as_markup())
    except Exception:
        await callback.message.answer(text, reply_markup=builder.as_markup())

    await callback.answer()


@router.callback_query(F.data == "prof_edit_menu")
async def edit_profile_menu(callback: types.CallbackQuery):
    builder = InlineKeyboardBuilder()
    builder.button(text="✏️ ПІБ", callback_data="edit_prof_name")
    builder.button(text="✏️ Telegram", callback_data="edit_prof_username")
    builder.button(text="✏️ Університет", callback_data="edit_prof_university")
    builder.button(text="✏️ Факультет", callback_data="edit_prof_faculty")
    builder.button(text="✏️ Група", callback_data="edit_prof_group")
    builder.button(text="Назад до профілю", callback_data="profile")
    builder.adjust(2, 2, 1, 1)

    await callback.message.edit_text(
        "⚙️ <b>Що саме ти хочеш змінити?</b>",
        reply_markup=builder.as_markup()
    )
    await callback.answer()


@router.callback_query(F.data.startswith("edit_prof_"))
async def start_edit_text_field(callback: types.CallbackQuery, state: FSMContext):
    field = callback.data.replace("edit_prof_", "")

    prompts = {
        "name":       "Введи нове ПІБ:\nПриклад: Шевченко Тарас Григорович",
        "username":   "Введи новий юзернейм у Telegram:\nПриклад: @username",
        "university": "Введи назву свого університету:\nПриклад: КНУ",
        "faculty":    "Введи новий факультет або напрям:\nПриклад: ФІОТ",
        "group":      "Введи нову групу або курс:\nПриклад: ІА-11",
    }

    states = {
        "name":       ProfileEditForm.waiting_for_new_name,
        "username":   ProfileEditForm.waiting_for_new_username,
        "university": ProfileEditForm.waiting_for_new_university,
        "faculty":    ProfileEditForm.waiting_for_new_faculty,
        "group":      ProfileEditForm.waiting_for_new_group,
    }

    prompt = prompts.get(field)
    target_state = states.get(field)

    await state.set_state(target_state)

    builder = InlineKeyboardBuilder()
    builder.button(text="Скасувати", callback_data="prof_edit_menu")

    new_msg = await callback.message.edit_text(prompt, reply_markup=builder.as_markup())
    await state.update_data(main_message_id=new_msg.message_id)
    await callback.answer()


@router.message(ProfileEditForm.waiting_for_new_name, F.text)
@router.message(ProfileEditForm.waiting_for_new_username, F.text)
@router.message(ProfileEditForm.waiting_for_new_university, F.text)
@router.message(ProfileEditForm.waiting_for_new_faculty, F.text)
@router.message(ProfileEditForm.waiting_for_new_group, F.text)
async def save_text_field(message: types.Message, state: FSMContext):
    current_state = await state.get_state()

    state_to_field = {
        ProfileEditForm.waiting_for_new_name.state:       "name",
        ProfileEditForm.waiting_for_new_username.state:   "username",
        ProfileEditForm.waiting_for_new_university.state: "university",
        ProfileEditForm.waiting_for_new_faculty.state:    "faculty",
        ProfileEditForm.waiting_for_new_group.state:      "group_name",
    }
    field_to_update = state_to_field.get(current_state)
    input_text = message.text.strip()

    # Нормалізуємо юзернейм
    if field_to_update == "username":
        if input_text.lower() != "немає" and not input_text.startswith("@"):
            input_text = f"@{input_text}"

    if field_to_update in ["faculty", "group_name"]:
        input_text = input_text.upper()

    await update_user_field(message.from_user.id, field_to_update, input_text)

    asyncio.create_task(update_user_in_sheet(
        tg_id=message.from_user.id,
        field=field_to_update,
        new_value=input_text
    ))

    data = await state.get_data()

    try:
        await message.delete()
    except Exception:
        pass

    builder = InlineKeyboardBuilder()
    builder.button(text="Повернутися в профіль", callback_data="profile")
    
    main_message_id = data.get("main_message_id")
    if main_message_id:
        try:
            await message.bot.edit_message_text(
                chat_id=message.chat.id,
                message_id=main_message_id,
                text="✅ Дані успішно оновлено!",
                reply_markup=builder.as_markup()
            )
        except Exception:
            await message.answer("✅ Дані успішно оновлено!", reply_markup=builder.as_markup())
    else:
        await message.answer("✅ Дані успішно оновлено!", reply_markup=builder.as_markup())
        
    await state.clear()
