from aiogram import Router, F, types

from aiogram.utils.keyboard import InlineKeyboardBuilder

from app.data.csv_handler import CSVHandler

router = Router()
handler = CSVHandler()


# [key: id -> question,answer]
@router.callback_query(F.data == "handle_questions")
async def show_faq(callback: types.CallbackQuery):

    questions = handler.get_questions()
    if not questions:
        await callback.answer("Помилка: Файл питань порожній або не знайдений", show_alert=True)
        return

    builder = InlineKeyboardBuilder()

    for question in questions:
        callback_str = f"faq_answer_{question['id']}"
        builder.add(
            types.InlineKeyboardButton(
                text=question['question'],
                callback_data=callback_str
            )
        )
    builder.adjust(1)

    await callback.message.answer("Ось найчастіші запитання:\n", reply_markup=builder.as_markup())
    await callback.answer()


@router.callback_query(F.data.startswith("faq_answer_"))
async def answer_faq(callback: types.CallbackQuery):
    question_id = int(callback.data.split("_")[2])
    answer = handler.get_answer_by_id(question_id)
    if not answer:
        answer = "Ой! На жаль відповідь на це питання не знайдена."

    builder = InlineKeyboardBuilder()

    builder.add(
        types.InlineKeyboardButton(
            text="Назад",
            callback_data="controller_hub"
        )
    )
    builder.add(
        types.InlineKeyboardButton(
            text="Інше питання",
            callback_data="more_questions_faq"
        )
    )

    await callback.message.edit_text(answer, reply_markup=builder.as_markup(), parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data == "more_questions_faq")
async def handle_more_questions(callback: types.CallbackQuery):
    await callback.message.edit_reply_markup(reply_markup=None)
    await show_faq(callback)
