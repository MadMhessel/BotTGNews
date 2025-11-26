def build_visual_spec(analysis: dict, strategy: dict) -> dict:
    anchors = analysis.get("visual_anchors", [])
    main_subject = anchors[0] if anchors else "тема новости абстрактно"
    
    # Описание героев
    char_desc = ""
    char_type = strategy.get("character_type", "none")
    
    if char_type == "red_cat":
        char_desc = "На втором плане или сбоку аккуратно сидит уютный пушистый Рыжий Кот, наблюдает за сценой."
    elif char_type == "noble_deer":
        char_desc = "Вдалеке или как силуэт виден Благородный Олень (символ города/природы), добавляющий величия."
    
    spec = {
        "subject": main_subject,
        "environment": anchors[1] if len(anchors) > 1 else "",
        
        "style": {
            "type": strategy["visual_type"], 
            "palette": strategy["palette"],
            "realism": strategy["realism_level"]
        },
        
        "characters": {
            "allowed": char_type != "none",
            "description": char_desc
        },
        
        "mood": analysis.get("emotion", "neutral"),
        "mood_instruction": strategy["mood_instruction"],
        
        "text_overlay": {
            "enabled": strategy["use_text_on_image"],
            "headline": None
        },
        
        "format": {
            "ratio": "4:5",
            "width_hint": "vertical"
        }
    }
    return spec