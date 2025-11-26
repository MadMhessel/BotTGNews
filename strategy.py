def decide_visual_strategy(analysis: dict) -> dict:
    """
    Принимает решения о стиле, герое и компоновке.
    """
    category = analysis.get("category", "news")
    subtype = analysis.get("subtype", "other")
    sensitivity = analysis.get("sensitivity", "low")
    risks = analysis.get("risk_flags", {})
    tone = analysis.get("tone", "neutral")
    
    # Базовая стратегия
    strategy = {
        "visual_type": "photo_like",
        "realism_level": "mid",
        "palette": "neutral_news",
        "character_type": "none",       # none, red_cat, noble_deer
        "use_text_on_image": False,
        "composition": "wide",
        "mood_instruction": "спокойный новостной стиль"
    }

    # === 1. БЕЗОПАСНОСТЬ (High Sensitivity) ===
    if sensitivity == "high" or risks.get("tragedy") or risks.get("violence"):
        strategy.update({
            "visual_type": "photo_like",
            "realism_level": "high",
            "palette": "dark_serious",
            "character_type": "none",       # СТРОГО БЕЗ ПЕРСОНАЖЕЙ
            "use_text_on_image": False,     # Текст может выглядеть неуместно
            "mood_instruction": "сдержанный, уважительный, документальный стиль",
        })
        return strategy

    # === 2. ГОРОД И СТРОЙКА (Инфраструктура) ===
    if category == "news" and subtype in ["city_infrastructure", "transport", "housing"]:
        strategy.update({
            "visual_type": "photo_like",
            "realism_level": "high",
            "palette": "soft_city",
            # Олень подходит как символ города/природы, если новость позитивная
            "character_type": "noble_deer" if tone == "positive" else "none",
            "use_text_on_image": True,
            "mood_instruction": "архитектурная фотография, чистые линии, свет"
        })
        return strategy

    # === 3. УЮТ, ЖИЗНЬ, ИСТОРИИ (Кот) ===
    if category in ["story", "humor", "lifestyle"] or subtype == "culture":
        strategy.update({
            "visual_type": "illustration" if category == "humor" else "photo_like",
            "realism_level": "mid",
            "palette": "promo_bright",
            "character_type": "red_cat", # Кот для душевности
            "use_text_on_image": True,
            "mood_instruction": "теплая, уютная, живая атмосфера"
        })
        return strategy

    # === 4. ПРОМО И АНОНСЫ ===
    if category in ["promo", "anons"]:
        strategy.update({
            "visual_type": "poster",
            "realism_level": "mid",
            "palette": "promo_bright",
            "character_type": "none",
            "use_text_on_image": True,
            "mood_instruction": "рекламный стиль, высокое качество, привлекательно"
        })
        return strategy

    # Дефолт
    strategy["use_text_on_image"] = True
    return strategy