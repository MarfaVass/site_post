from flask import Flask, render_template, request, jsonify
import requests
import os
import json
import time
import uuid
import threading
from datetime import datetime, timezone
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)

# ============================================================
# PROXY API (генерация постов через AI)
# ============================================================
PROXY_API_KEY = os.getenv("PROXY_API_KEY", "")
AI_MODEL = os.getenv("AI_MODEL", "gpt-4o-mini")
PROXY_API_URL = "https://api.proxyapi.ru/openai/v1/chat/completions"

# ============================================================
# VK API (публикация в сообществе)
# ============================================================
VK_ACCESS_TOKEN = os.getenv("VK_ACCESS_TOKEN", "")
VK_GROUP_ID = os.getenv("VK_GROUP_ID", "")
VK_API_VERSION = "5.199"

# ============================================================
# ФАЙЛЫ ДАННЫХ (JSON, хранятся локально)
# ============================================================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
FAVORITES_FILE = os.path.join(BASE_DIR, "favorites.json")
SCHEDULED_FILE = os.path.join(BASE_DIR, "scheduled_posts.json")


def load_json(filepath):
    if os.path.exists(filepath):
        with open(filepath, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"items": []}


def save_json(filepath, data):
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


# ============================================================
# БАЗА ЗНАНИЙ О СОРТАХ ВИНОГРАДА
# ============================================================
GRAPE_TYPOS = {
    "каберне": "Каберне Совиньон",
    "каберне сов": "Каберне Совиньон",
    "каберне совиньен": "Каберне Совиньон",
    "каберне совиньон": "Каберне Совиньон",
    "мерло": "Мерло",
    "мерлот": "Мерло",
    "мерла": "Мерло",
    "шардоне": "Шардоне",
    "шардонне": "Шардоне",
    "шардонэ": "Шардоне",
    "совиньон блан": "Совиньон Блан",
    "совиньон бланк": "Совиньон Блан",
    "сов блан": "Совиньон Блан",
    "пино нуар": "Пино Нуар",
    "пино нуарь": "Пино Нуар",
    "пино гри": "Пино Гриджио",
    "пино гриджио": "Пино Гриджио",
    "пино гриджо": "Пино Гриджио",
    "пино блан": "Пино Блан",
    "рислинг": "Рислинг",
    "ризлинг": "Рислинг",
    "гевюрцтраминер": "Гевюрцтраминер",
    "гевурцтраминер": "Гевюрцтраминер",
    "гевюрцтрамине": "Гевюрцтраминер",
    "сира": "Сира",
    "шираз": "Сира (Шираз)",
    "зинфандель": "Зинфандель",
    "зинфандел": "Зинфандель",
    "неббиоло": "Неббиоло",
    "небиоло": "Неббиоло",
    "санджовезе": "Санджовезе",
    "сан-джовезе": "Санджовезе",
    "темпранийо": "Темпранийо",
    "темпранильо": "Темпранийо",
    "мальбек": "Мальбек",
    "грарнаш": "Гренаш",
    "гарнача": "Гренаш",
    "мускат": "Мускат",
    "мускатель": "Мускат",
    "семильон": "Семильон",
    "семиийон": "Семильон",
    "вионье": "Вионье",
    "виогнье": "Вионье",
    "альбариньо": "Альбариньо",
    "альбарино": "Альбариньо",
    "верментино": "Верментино",
    "греко": "Греко",
    "фалангина": "Фалангина",
    "примитиво": "Примитиво",
    "траминер": "Траминер",
    "педро хименес": "Педро Хименес",
    "торонтес": "Торронтес",
    "торонтесс": "Торронтес",
}

SPARKLING_TYPES_INFO = {
    "prosecco": "Просекко",
    "champagne": "Шампанское",
    "moscato": "Москато (Асти)",
    "cava": "Кава",
    "cremant": "Кремано",
    "franciacorta": "Франчакорто",
    "lambusco": "Ламбруско",
    "pet_nat": "Пет-нат (Pétillant Naturel)",
    "sekt": "Зект",
    "english_sparkling": "Английское игристое",
    "trentodoc": "Тренто DOC",
}

# ============================================================
# НАСТРОЙКИ ИЗ VOICE.MD
# ============================================================
TONE = "expert"
POST_LENGTH = "medium"
EMOJI_COUNT = "moderate"
TITLE_STYLE = "intriguing"
CTA_TEXT = "Хотите узнать, какие бокалы рекомендуют сомелье? Читайте подробнее в моём блоге на Дзене!"
CTA_LINK = "https://dzen.ru/razborexpert"
CTA_BUTTON_TEXT = "Перейти в блог"
BASE_HASHTAGS = ["#бокалы", "#вино", "#сомелье", "#винныйэтикет", "#дегустация", "#винныйбокал", "#экспертпомокалам"]


def correct_grape_name(grape_input):
    original = grape_input.strip()
    lower = original.lower().strip()
    if lower in GRAPE_TYPOS:
        return GRAPE_TYPOS[lower], True
    for typo, correct in GRAPE_TYPOS.items():
        if lower in typo or typo in lower:
            return correct, True
    return original.capitalize() if len(original) > 1 else original, False


def generate_post_with_ai(wine_type, wine_color, grape, sparkling_type, mood):
    if wine_type == "still":
        wine_desc = f"тихое {wine_color}е вино из винограда сорта {grape}"
        glass_context = f"тип вина: тихое {wine_color}е, сорт винограда: {grape}"
    else:
        sparkling_name = SPARKLING_TYPES_INFO.get(sparkling_type, sparkling_type)
        wine_desc = f"игристое вино типа {sparkling_name}"
        glass_context = f"тип вина: игристое ({sparkling_name})"

    mood_descriptions = {
        "happy": "радостное, позитивное, с лёгким энтузиазмом",
        "romantic": "романтичное, тёплое, с нотками нежности",
        "expert": "экспертное, авторитетное, с профессиональной глубиной",
        "relaxed": "расслабленное, уютное, с атмосферой спокойствия",
    }
    mood_desc = mood_descriptions.get(mood, "нейтральное")

    length_descriptions = {
        "short": "короткий (2-3 абзаца основной части)",
        "medium": "средний (4-5 абзацев основной части)",
        "long": "развёрнутый (6+ абзацев основной части)",
    }
    length_desc = length_descriptions.get(POST_LENGTH, "средний")

    title_descriptions = {
        "question": "вопросительный",
        "statement": "утвердительный",
        "intriguing": "интригующий",
        "howto": "в формате инструкции (как...)",
    }
    title_desc = title_descriptions.get(TITLE_STYLE, "интригующий")

    tone_descriptions = {
        "friendly": "дружелюбный, тёплый",
        "expert": "экспертный, авторитетный",
        "casual": "лёгкий, разговорный",
        "luxurious": "изысканный, премиальный",
    }
    tone_desc = tone_descriptions.get(TONE, "экспертный")

    emoji_descriptions = {
        "none": "без эмодзи",
        "few": "1-3 эмодзи",
        "moderate": "4-7 эмодзи",
        "many": "8+ эмодзи",
    }
    emoji_desc = emoji_descriptions.get(EMOJI_COUNT, "4-7 эмодзи")

    hashtags_str = ", ".join(BASE_HASHTAGS)

    system_prompt = f"""Ты — эксперт-сомелье и автор блога о бокалах для вина. Твоя задача — написать увлекательный, оригинальный пост для блога.

Входные данные:
- {glass_context}
- Настроение поста: {mood_desc}
- Тон: {tone_desc}
- Длина: {length_desc}

Ответь ТОЛЬКО в формате JSON со следующими полями:
{{
  "title": "Заголовок поста (без markdown, без #, без эмодзи)",
  "intro": "Короткое вступление (1-2 предложения)",
  "body": "Основной текст о вине, ароматах, вкусе, важности формы бокала",
  "glass_type": "Тип бокала (бордо, бургундия, тюльпан, флюте, креманка и т.д.)",
  "glass_description": "Описание формы (форма чаши, высота, ширина, сужение к краю)",
  "glass_volume": "Объём в мл (например: 600-750 мл)",
  "glass_why": "Подробное объяснение, почему именно такая форма раскрывает аромат и вкус этого вина",
  "brands": "Рекомендации по брендам: категории, 1-3 производителя (Riedel, Schott Zwiesel и т.д.), ссылка на блог для точного выбора",
  "cta": "Призыв перейти в блог на Дзене с ссылкой {CTA_LINK}",
  "hashtags": "Массив из 3-7 хэштегов",
  "emojis": "Массив из 2-4 эмодзи для поста"
}}

СТРУКТУРА ПОСТА:
1. Заголовок: {title_desc} стиль
2. Вступление: вовлекающее
3. Основной текст: о вине, ароматах, вкусе, важности бокала
4. Рекомендация по бокалу: тип, форма, объём, объяснение
5. Рекомендации по брендам
6. CTA: мягкий призыв с ссылкой на {CTA_LINK}
7. Хэштеги: 3-7 штук

Базовые хэштеги: {hashtags_str}

ВАЖНО:
- НЕ используй markdown (**, ###, *, _) в значениях
- Пиши на русском
- Объясняй, почему выбран такой бокал
- CTA мягкий и естественный
- Ответ ТОЛЬКО валидный JSON"""

    user_prompt = f"Напиши пост про бокал для: {wine_desc}. Настроение: {mood_desc}. Ответь в формате JSON."

    try:
        response = requests.post(
            PROXY_API_URL,
            headers={
                "Authorization": f"Bearer {PROXY_API_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "model": AI_MODEL,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                "temperature": 0.8,
                "max_tokens": 2000,
                "response_format": {"type": "json_object"},
            },
            timeout=60,
        )

        if response.status_code != 200:
            return {"error": f"Ошибка API: {response.status_code}. {response.text[:200]}"}

        data = response.json()
        ai_text = data["choices"][0]["message"]["content"].strip()
        ai_data = json.loads(ai_text)

        emojis = " ".join(ai_data.get("emojis", ["🍷", "✨"]))
        title = ai_data.get("title", "Рекомендация по бокалу")
        title_with_emoji = f"{emojis} {title}" if emojis else title

        hashtags = ai_data.get("hashtags", BASE_HASHTAGS)
        hashtags_str_out = " ".join(hashtags)

        full_post = (
            f"{title_with_emoji}\n\n"
            f"{ai_data.get('intro', '')}\n\n"
            f"{ai_data.get('body', '')}\n\n"
            f"Рекомендация по бокалу:\n"
            f"🫗 Тип: {ai_data.get('glass_type', '')}\n"
            f"📐 Форма: {ai_data.get('glass_description', '')}\n"
            f"📏 Объём: {ai_data.get('glass_volume', '')}\n\n"
            f"Почему: {ai_data.get('glass_why', '')}\n\n"
            f"{ai_data.get('brands', '')}\n\n"
            f"{ai_data.get('cta', '')}\n\n"
            f"🏷 Хэштеги:\n{hashtags_str_out}"
        )

        return {
            "title": title_with_emoji,
            "body": f"{ai_data.get('intro', '')}\n\n{ai_data.get('body', '')}",
            "glass_type": ai_data.get("glass_type", ""),
            "glass_description": ai_data.get("glass_description", ""),
            "glass_volume": ai_data.get("glass_volume", ""),
            "glass_why": ai_data.get("glass_why", ""),
            "brands": ai_data.get("brands", ""),
            "hashtags": hashtags_str_out,
            "cta": ai_data.get("cta", ""),
            "full_post": full_post,
        }

    except requests.exceptions.Timeout:
        return {"error": "Превышено время ожидания ответа от AI. Попробуйте снова."}
    except requests.exceptions.RequestException as e:
        return {"error": f"Ошибка соединения с AI: {str(e)}"}
    except Exception as e:
        return {"error": f"Неизвестная ошибка: {str(e)}"}


# ============================================================
# VK API — ПУБЛИКАЦИЯ ПОСТОВ
# ============================================================

def publish_to_vk_immediately(post_text):
    """Публикует пост в сообществе ВКонтакте немедленно."""
    if not VK_ACCESS_TOKEN or not VK_GROUP_ID:
        return {"error": "VK не настроен. Добавьте VK_ACCESS_TOKEN и VK_GROUP_ID в .env файл. См. VK_SETUP.md"}

    try:
        url = "https://api.vk.com/method/wall.post"
        params = {
            "owner_id": VK_GROUP_ID,
            "from_group": 1,
            "message": post_text,
            "access_token": VK_ACCESS_TOKEN,
            "v": VK_API_VERSION,
        }

        response = requests.post(url, data=params, timeout=30)
        result = response.json()

        if "response" in result and "post_id" in result["response"]:
            post_id = result["response"]["post_id"]
            return {"success": True, "post_id": post_id}
        elif "error" in result:
            error_msg = result["error"].get("error_msg", "Неизвестная ошибка VK")
            return {"error": f"Ошибка VK: {error_msg}"}
        else:
            return {"error": f"Неизвестный ответ VK API: {result}"}

    except Exception as e:
        return {"error": f"Ошибка при публикации в VK: {str(e)}"}


def schedule_vk_post(post_text, publish_date):
    """
    Сохраняет пост в очередь на публикацию.
    publish_date — Unix timestamp (UTC).
    """
    if not VK_ACCESS_TOKEN or not VK_GROUP_ID:
        return {"error": "VK не настроен. Добавьте VK_ACCESS_TOKEN и VK_GROUP_ID в .env файл. См. VK_SETUP.md"}

    scheduled = load_json(SCHEDULED_FILE)

    post_entry = {
        "id": str(uuid.uuid4()),
        "text": post_text,
        "publish_date": publish_date,
        "created_at": datetime.now().isoformat(),
        "status": "scheduled",
    }

    scheduled["items"].append(post_entry)
    save_json(SCHEDULED_FILE, scheduled)

    return {"success": True, "schedule_id": post_entry["id"]}


def get_scheduled_posts():
    """Возвращает список запланированных постов."""
    scheduled = load_json(SCHEDULED_FILE)
    now = int(time.time())

    # Помечаем просроченные как missed
    for item in scheduled["items"]:
        if item["status"] == "scheduled" and item["publish_date"] <= now:
            item["status"] = "missed"

    save_json(SCHEDULED_FILE, scheduled)
    return scheduled["items"]


def delete_scheduled_post(post_id):
    """Удаляет запланированный пост."""
    scheduled = load_json(SCHEDULED_FILE)
    scheduled["items"] = [i for i in scheduled["items"] if i["id"] != post_id]
    save_json(SCHEDULED_FILE, scheduled)
    return {"success": True}


def check_and_publish_scheduled():
    """
    Фоновая задача: проверяет, есть ли посты для публикации,
    и публикует их через VK API.
    """
    scheduled = load_json(SCHEDULED_FILE)
    now = int(time.time())
    updated = False

    for item in scheduled["items"]:
        if item["status"] == "scheduled" and item["publish_date"] <= now:
            result = publish_to_vk_immediately(item["text"])
            if result.get("success"):
                item["status"] = "published"
                item["vk_post_id"] = result.get("post_id")
            else:
                item["status"] = "failed"
                item["error"] = result.get("error", "")
            updated = True

    if updated:
        save_json(SCHEDULED_FILE, scheduled)


def start_scheduler():
    """Запускает фоновый поток проверки запланированных постов."""
    def scheduler_loop():
        while True:
            try:
                check_and_publish_scheduled()
            except Exception:
                pass
            time.sleep(30)

    thread = threading.Thread(target=scheduler_loop, daemon=True)
    thread.start()


# ============================================================
# ИЗБРАННОЕ
# ============================================================

def save_to_favorites(post_data):
    """Сохраняет пост в избранное."""
    favorites = load_json(FAVORITES_FILE)

    entry = {
        "id": str(uuid.uuid4()),
        "title": post_data.get("title", ""),
        "full_post": post_data.get("full_post", ""),
        "glass_type": post_data.get("glass_type", ""),
        "created_at": datetime.now().isoformat(),
    }

    favorites["items"].insert(0, entry)
    save_json(FAVORITES_FILE, favorites)
    return {"success": True, "favorite_id": entry["id"]}


def get_favorites():
    """Возвращает список избранных постов."""
    return load_json(FAVORITES_FILE)["items"]


def delete_favorite(favorite_id):
    """Удаляет пост из избранного."""
    favorites = load_json(FAVORITES_FILE)
    favorites["items"] = [i for i in favorites["items"] if i["id"] != favorite_id]
    save_json(FAVORITES_FILE, favorites)
    return {"success": True}


# ============================================================
# РОУТЫ
# ============================================================

@app.route("/")
def index():
    return render_template("index.html")


@app.route("/generate", methods=["POST"])
def generate():
    wine_type = request.form.get("wine_type", "").strip()
    mood = request.form.get("mood", "").strip()

    errors = []
    if not wine_type:
        errors.append("Выберите тип вина (тихое или игристое)")
    if not mood:
        errors.append("Выберите настроение поста")

    if errors:
        return jsonify({"error": " | ".join(errors)})

    if wine_type == "still":
        wine_color = request.form.get("wine_color", "").strip()
        grape = request.form.get("grape", "").strip()

        if not wine_color:
            errors.append("Выберите цвет вина")
        if not grape:
            errors.append("Введите сорт винограда")

        if errors:
            return jsonify({"error": " | ".join(errors)})

        corrected_grape, was_corrected = correct_grape_name(grape)
        result = generate_post_with_ai(
            wine_type="still", wine_color=wine_color,
            grape=corrected_grape, sparkling_type=None, mood=mood,
        )

        if "error" not in result:
            result["grape_corrected"] = corrected_grape
            result["grape_was_corrected"] = was_corrected

    elif wine_type == "sparkling":
        sparkling_type = request.form.get("sparkling_type", "").strip()

        if not sparkling_type:
            errors.append("Выберите тип игристого вина")

        if errors:
            return jsonify({"error": " | ".join(errors)})

        result = generate_post_with_ai(
            wine_type="sparkling", wine_color=None,
            grape=None, sparkling_type=sparkling_type, mood=mood,
        )

    else:
        return jsonify({"error": "Неизвестный тип вина"})

    return jsonify(result)


@app.route("/publish", methods=["POST"])
def publish():
    """Публикует пост в ВКонтакте немедленно."""
    data = request.get_json()
    post_text = data.get("post_text", "").strip()

    if not post_text:
        return jsonify({"error": "Текст поста пустой"})

    result = publish_to_vk_immediately(post_text)
    return jsonify(result)


@app.route("/schedule", methods=["POST"])
def schedule():
    """Сохраняет пост на отложенную публикацию."""
    data = request.get_json()
    post_text = data.get("post_text", "").strip()
    schedule_time = data.get("schedule_time", "").strip()

    if not post_text:
        return jsonify({"error": "Текст поста пустой"})
    if not schedule_time:
        return jsonify({"error": "Выберите время публикации"})

    try:
        schedule_dt = datetime.strptime(schedule_time, "%Y-%m-%dT%H:%M")
        schedule_ts = int(schedule_dt.replace(tzinfo=timezone.utc).timestamp())
        now_ts = int(time.time())

        if schedule_ts <= now_ts:
            return jsonify({"error": "Время публикации должно быть в будущем"})

        result = schedule_vk_post(post_text, schedule_ts)
        return jsonify(result)

    except ValueError:
        return jsonify({"error": "Неверный формат времени"})


@app.route("/scheduled", methods=["GET"])
def scheduled_list():
    """Список запланированных постов."""
    items = get_scheduled_posts()
    return jsonify({"items": items})


@app.route("/scheduled/<post_id>", methods=["DELETE"])
def scheduled_delete(post_id):
    """Удаляет запланированный пост."""
    return jsonify(delete_scheduled_post(post_id))


@app.route("/favorites", methods=["GET"])
def favorites_list():
    """Список избранных постов."""
    items = get_favorites()
    return jsonify({"items": items})


@app.route("/favorites", methods=["POST"])
def favorites_save():
    """Сохраняет пост в избранное."""
    data = request.get_json()
    result = save_to_favorites(data)
    return jsonify(result)


@app.route("/favorites/<favorite_id>", methods=["DELETE"])
def favorites_delete(favorite_id):
    """Удаляет пост из избранного."""
    return jsonify(delete_favorite(favorite_id))


if __name__ == "__main__":
    if not PROXY_API_KEY:
        print("ВНИМАНИЕ: PROXY_API_KEY не установлен в .env файле!")
    if not VK_ACCESS_TOKEN:
        print("ВНИМАНИЕ: VK_ACCESS_TOKEN не установлен. Публикация в VK не будет работать.")
        print("См. VK_SETUP.md для инструкции по настройке.")

    # Запускаем фоновый планировщик
    start_scheduler()

    print("Сервер запущен: http://127.0.0.1:5000")
    app.run(debug=True, host="127.0.0.1", port=5000)
