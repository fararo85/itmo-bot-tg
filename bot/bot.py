import asyncio
import requests
from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, BotCommand
import os

API_URL = "http://main:8000"  # URL вашего API
BOT_TOKEN = "8028109506:AAHZW9NWG1UsDChaISZTlanB96H5h3RDapk"  # Убедитесь, что токен настроен

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()


# Функция для регистрации команд в Telegram
async def set_my_commands(bot: Bot):
    commands = [
        BotCommand(command="/start", description="Начать изучение слов"),
        BotCommand(command="/learned_words", description="Просмотреть изученные слова"),
    ]
    await bot.set_my_commands(commands)


# Проверка наличия пользователя в БД и регистрация при необходимости
def register_user_in_db(user_id):
    response = requests.get(f"{API_URL}/user/{user_id}/exists")
    print(f"Проверка пользователя {user_id}, статус: {response.status_code}")
    if response.status_code == 404:  # Пользователь не найден
        print("Регистрация нового пользователя...")
        register_response = requests.post(f"{API_URL}/user/{user_id}/register")
        print(f"Регистрация пользователя, статус: {register_response.status_code}")
    else:
        print("Пользователь уже существует в базе данных.")


# Обработчик команды /start
@dp.message(F.text == "/start")
async def cmd_start(message: Message):
    user_id = message.from_user.id
    print(f"Команда /start вызвана пользователем {user_id}")
    register_user_in_db(user_id)
    await message.answer("Привет! Я бот для изучения английского по карточкам.")
    await send_word(message)


# Обработчик команды /learned_words для просмотра списка изученных слов
@dp.message(F.text == "/learned_words")
async def cmd_learned_words(message: Message):
    user_id = message.from_user.id
    response = requests.get(f"{API_URL}/user/{user_id}/learned_words")
    print(f"Запрос на получение изученных слов для пользователя {user_id}, статус: {response.status_code}")

    if response.status_code != 200:
        await message.answer("Ошибка получения списка изученных слов.")
        return

    learned_words_data = response.json()

    # Проверка наличия ключа 'learned_words' в JSON-ответе
    learned_words = learned_words_data.get("learned_words", [])

    if not learned_words:
        await message.answer("Вы пока не выучили ни одного слова.")
        return

    words_list = "\n".join([f"{word['word']} - {word['translation']}" for word in learned_words])
    await message.answer(f"Ваши изученные слова:\n{words_list}")


# Функция для отправки карточки со словом
async def send_word(message: Message, user_id=None):
    if user_id is None:
        user_id = message.from_user.id
    # Запрос теперь будет учитывать слова со статусом `unknown` и `reviewlater`
    response = requests.get(f"{API_URL}/user/{user_id}/next_word?include_reviewlater=true")
    print(f"Запрос на получение слова для пользователя {user_id}, статус: {response.status_code}")

    if response.status_code == 404:
        print("Слов для изучения не найдено.")
        await message.answer("Вы уже выучили все слова!")
        return

    if response.status_code != 200:
        print(f"Ошибка получения карточки: {response.text}")
        await message.answer("Ошибка получения карточки. Попробуйте позже.")
        return

    word_data = response.json()
    print(f"Полученные данные слова: {word_data}")

    word, translation, word_id = word_data['word'], word_data['translation'], word_data['id']
    buttons = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Знаю", callback_data=f"know_{word_id}")],
        [InlineKeyboardButton(text="Не знаю", callback_data=f"don'tknow_{word_id}")],
        [InlineKeyboardButton(text="Знаю, но хочу повторить позже", callback_data=f"reviewlater_{word_id}")]
    ])
    await message.answer(f"{word} - {translation}", reply_markup=buttons)


# Обработка ответов пользователя
@dp.callback_query(F.data.startswith("know") | F.data.startswith("don'tknow") | F.data.startswith("reviewlater"))
async def handle_response(callback_query: CallbackQuery):
    user_id = callback_query.from_user.id
    action, word_id = callback_query.data.split('_')

    if action == "know":
        status = "known"
    elif action == "don'tknow":
        status = "unknown"
    elif action == "reviewlater":
        status = "reviewlater"

    update_response = requests.put(f"{API_URL}/user/{user_id}/word/{word_id}?status={status}", json={"status": status})
    print(f"Обновление статуса слова {word_id} для пользователя {user_id}, статус: {update_response.status_code}")

    if update_response.status_code != 200:
        print(f"Ошибка обновления статуса: {update_response.text}")
        await callback_query.answer("Ошибка при обновлении статуса слова.")
        return

    response_text = {
        "know": "Слово помечено как выучено!",
        "don'tknow": "Слово будет показано снова.",
        "reviewlater": "Слово будет повторено позже."
    }.get(action, "Ответ сохранён.")

    await callback_query.answer(response_text)
    await callback_query.message.edit_text("Отлично! Давайте продолжим.")
    await send_word(callback_query.message, user_id)


# Основная функция для запуска бота
async def main():
    await set_my_commands(bot)
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)


# Запуск бота
if __name__ == '__main__':
    asyncio.run(main())
