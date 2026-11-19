"""Шаблонный движок генерации карточек.

Демо-версия собирает карточку из шаблонов. В платной версии функции
build_card() заменяются на вызов LLM — сигнатура сохраняется, бот.py
менять не нужно.
"""

import random

CATEGORY_WORDS = {
    "одежда": ["удобная посадка", "универсальный фасон", "приятная к телу ткань"],
    "электроника": ["современный чипсет", "быстрая зарядка", "стабильная работа"],
    "посуда": ["пищевой материал", "легко моется", "удобно брать с собой"],
    "косметика": ["натуральный состав", "подходит для ежедневного ухода", "быстро впитывается"],
    "товары для дома": ["долговечные материалы", "простой уход", "приятный дизайн"],
}

TONE_OPENERS = {
    "classic": "Практичное решение на каждый день",
    "bright": "Встречайте — ваша новая любовь! 💫",
    "minimal": "Только необходимое. Без лишнего",
}

TONE_CLOSERS = {
    "classic": "Проверенное качество по справедливой цене.",
    "bright": "Берите — и удивляйтесь, как жили без этого раньше! 🎉",
    "minimal": "Всё, что нужно. Ничего лишнего.",
}


def build_card(product: str, category: str, features: list, tone: str) -> dict:
    category_l = category.lower()
    extra = CATEGORY_WORDS.get(category_l, ["высокое качество", "практичность", "надёжность"])

    # SEO-название: товар + главные свойства (маркетплейсы ранжируют по началу строки)
    main_feats = features[:2]
    title = f"{product.capitalize()} " + " ".join(main_feats)
    title = _trim(title, 60)

    # Ключевые слова: свойства + категорийные + купить/заказать
    keywords = list(dict.fromkeys(
        [f.lower() for f in features] + extra[:2]
        + [f"купить {product.lower()}", f"{product.lower()} {category_l}", "доставка по россии"]))

    bullets = "\n".join(f"• {f.capitalize()}" for f in features)
    description = (
        f"{TONE_OPENERS.get(tone, TONE_OPENERS['classic'])}. "
        f"{product.capitalize()} — {category_l}, которая закрывает все бытовые задачи.\n\n"
        f"Преимущества:\n{bullets}\n\n"
        f"{TONE_CLOSERS.get(tone, TONE_CLOSERS['classic'])}"
    )
    return {"title": title, "keywords": keywords, "description": description}


def _trim(s: str, n: int) -> str:
    return s if len(s) <= n else s[:n - 1].rstrip() + "…"
