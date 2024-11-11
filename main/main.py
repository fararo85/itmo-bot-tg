import random
import uvicorn
from fastapi import FastAPI, HTTPException
from supabase import create_client, Client

# Подключение к Supabase
url = "https://drackfxndqbettvvmvff.supabase.co"
key = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImRyYWNrZnhuZHFiZXR0dnZtdmZmIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTczMTE2NzEwMCwiZXhwIjoyMDQ2NzQzMTAwfQ.AJoksdhfLoo0q1wmGX12eSn_DvuCE0LjhXahPZYmSnE"
supabase: Client = create_client(url, key)

app = FastAPI()

# Проверка наличия пользователя в базе
@app.get("/user/{user_id}/exists")
async def check_user_exists(user_id: int):
    response = supabase.table("user_words").select("user_id").eq("user_id", user_id).execute()
    if hasattr(response, 'error'):
        raise HTTPException(status_code=500, detail=f"Ошибка при запросе: {response.error}")
    if not response.data:
        raise HTTPException(status_code=404, detail="Пользователь не найден")
    return {"exists": True}

# Регистрация нового пользователя и привязка к словам
@app.post("/user/{user_id}/register")
async def register_user(user_id: int):
    words_response = supabase.table("words").select("*").execute()
    if hasattr(words_response, 'error'):
        raise HTTPException(status_code=500, detail=f"Ошибка получения списка слов: {words_response.error}")

    if not words_response.data:
        raise HTTPException(status_code=404, detail="Слова отсутствуют в базе данных")

    # Создание записей для каждого слова с начальным статусом 'unknown' для нового пользователя
    new_entries = [{"user_id": user_id, "word_id": word["id"], "status": "unknown"} for word in words_response.data]
    insert_response = supabase.table("user_words").insert(new_entries).execute()

    if hasattr(insert_response, 'error'):
        raise HTTPException(status_code=500, detail=f"Ошибка вставки записей: {insert_response.error}")

    return {"message": "Пользователь успешно зарегистрирован"}

# Получение следующего слова для пользователя с учётом статуса reviewlater
@app.get("/user/{user_id}/next_word")
async def get_next_word(user_id: int, include_reviewlater: bool = False):
    statuses = ["unknown"]
    if include_reviewlater:
        statuses.append("reviewlater")  # Добавляем статус review_later

    response = supabase.table("user_words").select("word_id").match({"user_id": user_id}).in_("status", statuses).limit(10).execute()
    if hasattr(response, 'error'):
        raise HTTPException(status_code=500, detail=f"Ошибка при запросе: {response.error}")
    if not response.data:
        raise HTTPException(status_code=404, detail="Слов для изучения не найдено")

    random_word = random.choice(response.data)
    word_id = random_word["word_id"]
    word_response = supabase.table("words").select("*").eq("id", word_id).single().execute()

    if hasattr(word_response, 'error'):
        raise HTTPException(status_code=500, detail=f"Ошибка получения данных слова: {word_response.error}")

    return {
        "id": word_response.data["id"],
        "word": word_response.data["word"],
        "translation": word_response.data["translation"]
    }

# Обновление статуса слова
@app.put("/user/{user_id}/word/{word_id}")
async def update_word_status(user_id: int, word_id: int, status: str):
    response = supabase.table("user_words").update({"status": status}).match({"user_id": user_id, "word_id": word_id}).execute()
    if hasattr(response, 'error'):
        raise HTTPException(status_code=500, detail=f"Ошибка обновления статуса слова: {response.error}")
    return {"message": "Статус слова успешно обновлен"}


# Получение всех изученных слов для пользователя
@app.get("/user/{user_id}/learned_words")
async def get_learned_words(user_id: int):
    response = supabase.table("user_words").select("word_id").match({"user_id": user_id, "status": "known"}).execute()
    if hasattr(response, 'error'):
        raise HTTPException(status_code=500, detail=f"Ошибка при запросе: {response.error}")
    if not response.data:
        return {"learned_words": []}

    # Получаем слова по их ID из таблицы `words`
    word_ids = [entry["word_id"] for entry in response.data]
    words_response = supabase.table("words").select("word", "translation").in_("id", word_ids).execute()

    if hasattr(words_response, 'error'):
        raise HTTPException(status_code=500, detail=f"Ошибка получения слов: {words_response.error}")

    return {"learned_words": words_response.data}

uvicorn.run(app, host="0.0.0.0", port=8000)
