from flask import Flask, render_template, request, jsonify
import requests
import os
import re
import json
from dotenv import load_dotenv

# Загружаем переменные окружения из .env
load_dotenv()

app = Flask(__name__)

# ============================================================
# НАСТРОЙКИ PROXY API
# ============================================================
PROXY_API_KEY = os.getenv("PROXY_API_KEY", "")
AI_MODEL = os.getenv("AI_MODEL", "gpt-4o-mini")
PROXY_API_URL = "https://api.proxyapi.ru/openai/v1/chat/completions"

# ============================================================
# БАЗА ЗНАНИЙ О СОРТАХ ВИНОГРАДА (для проверки/исправления)
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

# ============================================================
# СПИСОК ТИПОВ ИГРИСТЫХ (для отображения в UI и промпте)
# ============================================================
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
# НАСТРОЙКИ ИЗ VOICE.MD (можно менять прямо здесь)
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
    """
    Исправляет ошибки в написании сорта винограда.
    """
    original = grape_input.strip()
    lower = original.lower().strip()

    if lower in GRAPE_TYPOS:
        return GRAPE_TYPOS[lower], True

    for typo, correct in GRAPE_TYPOS.items():
        if lower in typo or typo in lower:
            return correct, True

    return original.capitalize() if len(original) > 1 else original, False


def generate_post_with_ai(wine_type, wine_color, grape, sparkling_type, mood):
    """
    Генерирует пост через Proxy API (языковая модель).
    Возвращает dict с полями: title, body, glass_type, glass_description,
    glass_volume, glass_why, brands, hashtags, cta, full_post
    """
    # Определяем контекст
    if wine_type == "still":
        wine_desc = f"тихое {wine_color}е вино из винограда сорта {grape}"
        glass_context = f"тип вина: тихое {wine_color}е, сорт винограда: {grape}"
    else:
        sparkling_name = SPARKLING_TYPES_INFO.get(sparkling_type, sparkling_type)
        wine_desc = f"игристое вино типа {sparkling_name}"
        glass_context = f"тип вина: игристое ({sparkling_name})"

    # Настроение
    mood_descriptions = {
        "happy": "радостное, позитивное, с лёгким энтузиазмом",
        "romantic": "романтичное, тёплое, с нотками нежности",
        "expert": "экспертное, авторитетное, с профессиональной глубиной",
        "relaxed": "расслабленное, уютное, с атмосферой спокойствия",
    }
    mood_desc = mood_descriptions.get(mood, "нейтральное")

    # Длина
    length_descriptions = {
        "short": "короткий (2-3 абзаца основной части)",
        "medium": "средний (4-5 абзацев основной части)",
        "long": "развёрнутый (6+ абзацев основной части)",
    }
    length_desc = length_descriptions.get(POST_LENGTH, "средний")

    # Стиль заголовка
    title_descriptions = {
        "question": "вопросительный",
        "statement": "утвердительный",
        "intriguing": "интригующий",
        "howto": "в формате инструкции (как...)",
    }
    title_desc = title_descriptions.get(TITLE_STYLE, "интригующий")

    # Тон
    tone_descriptions = {
        "friendly": "дружелюбный, тёплый",
        "expert": "экспертный, авторитетный",
        "casual": "лёгкий, разговорный",
        "luxurious": "изысканный, премиальный",
    }
    tone_desc = tone_descriptions.get(TONE, "экспертный")

    # Количество эмодзи
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

СТРУКТУРА ПОСТА (модель должна учитывать):
1. Заголовок: {title_desc} стиль, без markdown-символов, без #
2. Вступление: вовлекающее читателя
3. Основной текст: о вине, ароматах, вкусе, важности бокала
4. Рекомендация по бокалу: тип, форма, объём, объяснение
5. Рекомендации по брендам: категории, примеры производителей
6. CTA: мягкий призыв с ссылкой на {CTA_LINK}
7. Хэштеги: 3-7 штук

Базовые хэштеги для включения: {hashtags_str}

ВАЖНО:
- НЕ используй markdown (**, ###, *, _) в значениях полей
- Каждый пост должен быть оригинальным
- Пиши на русском языке
- Объясняй, почему выбран именно такой бокал
- CTA должен быть мягким и естественным
- Ответ должен быть ТОЛЬКО валидным JSON, без дополнительного текста"""

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
            return {
                "error": f"Ошибка API: {response.status_code}. {response.text[:200]}"
            }

        data = response.json()
        ai_text = data["choices"][0]["message"]["content"].strip()

        # Парсим JSON-ответ
        ai_data = json.loads(ai_text)

        # Собираем полный пост из секций
        emojis = " ".join(ai_data.get("emojis", ["🍷", "✨"]))
        title = ai_data.get("title", "Рекомендация по бокалу")
        title_with_emoji = f"{emojis} {title}" if emojis else title

        hashtags = ai_data.get("hashtags", BASE_HASHTAGS)
        hashtags_str = " ".join(hashtags)

        full_post = f"{title_with_emoji}\n\n{ai_data.get('intro', '')}\n\n{ai_data.get('body', '')}\n\nРекомендация по бокалу:\n🫗 Тип: {ai_data.get('glass_type', '')}\n📐 Форма: {ai_data.get('glass_description', '')}\n📏 Объём: {ai_data.get('glass_volume', '')}\n\nПочему: {ai_data.get('glass_why', '')}\n\n{ai_data.get('brands', '')}\n\n{ai_data.get('cta', '')}\n\n🏷 Хэштеги:\n{hashtags_str}"

        return {
            "title": title_with_emoji,
            "body": f"{ai_data.get('intro', '')}\n\n{ai_data.get('body', '')}",
            "glass_type": ai_data.get("glass_type", ""),
            "glass_description": ai_data.get("glass_description", ""),
            "glass_volume": ai_data.get("glass_volume", ""),
            "glass_why": ai_data.get("glass_why", ""),
            "brands": ai_data.get("brands", ""),
            "hashtags": hashtags_str,
            "cta": ai_data.get("cta", ""),
            "full_post": full_post,
        }

    except requests.exceptions.Timeout:
        return {"error": "Превышено время ожидания ответа от AI. Попробуйте снова."}
    except requests.exceptions.RequestException as e:
        return {"error": f"Ошибка соединения с AI: {str(e)}"}
    except Exception as e:
        return {"error": f"Неизвестная ошибка: {str(e)}"}


@app.route("/")
def index():
    """Главная страница с формой."""
    return render_template("index.html")


@app.route("/generate", methods=["POST"])
def generate():
    """Обработка формы и генерация поста через AI."""
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
            wine_type="still",
            wine_color=wine_color,
            grape=corrected_grape,
            sparkling_type=None,
            mood=mood,
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
            wine_type="sparkling",
            wine_color=None,
            grape=None,
            sparkling_type=sparkling_type,
            mood=mood,
        )

    else:
        return jsonify({"error": "Неизвестный тип вина"})

    return jsonify(result)


if __name__ == "__main__":
    if not PROXY_API_KEY:
        print("ВНИМАНИЕ: PROXY_API_KEY не установлен в .env файле!")
        print("Создайте файл .env и добавьте строку: PROXY_API_KEY=ваш_ключ")
    app.run(debug=True, host="127.0.0.1", port=5000)
