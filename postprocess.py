import io
import os
import logging
from PIL import Image, ImageDraw, ImageFilter, ImageStat, ImageFont

def _get_smart_logo_position(img: Image.Image, text_present: bool) -> str:
    """
    Выбирает угол для логотипа. 
    Если есть текст (он всегда сверху), то логотип принудительно ставим вниз.
    """
    w, h = img.size
    half_w, half_h = w // 2, h // 2
    
    # Если есть текст сверху, логотип ставим только вниз
    candidates = {
        "bottom_left": (0, half_h, half_w, h),
        "bottom_right": (half_w, half_h, w, h)
    } if text_present else {
        "top_left": (0, 0, half_w, half_h),
        "top_right": (half_w, 0, w, half_h),
        "bottom_left": (0, half_h, half_w, h),
        "bottom_right": (half_w, half_h, w, h)
    }
    
    min_score = float('inf')
    best_corner = "bottom_right"
    
    try:
        img_gray = img.convert("L").filter(ImageFilter.FIND_EDGES)
        for name, box in candidates.items():
            crop = img_gray.crop(box)
            stat = ImageStat.Stat(crop)
            # Чем меньше score, тем меньше деталей (чище фон)
            score = stat.mean[0] 
            if score < min_score:
                min_score = score
                best_corner = name
    except Exception:
        pass
            
    return best_corner

def _overlay_logo(base_img: Image.Image, text_present: bool) -> Image.Image:
    logo_path = os.path.join(os.path.dirname(__file__), "logo.png")
    if not os.path.exists(logo_path):
        return base_img 

    try:
        logo = Image.open(logo_path).convert("RGBA")
        base_w, base_h = base_img.size
        
        # Логотип = 18% от ширины
        target_w = max(int(base_w * 0.18), 80)
        aspect = logo.height / logo.width
        target_h = int(target_w * aspect)
        
        # Ресайз
        resample_filter = getattr(Image, "LANCZOS", Image.BICUBIC)
        logo = logo.resize((target_w, target_h), resample_filter)
        
        # Выбор позиции
        corner = _get_smart_logo_position(base_img, text_present)
        
        margin_x = int(base_w * 0.05)
        margin_y = int(base_h * 0.04)
        
        if corner == "top_left": x, y = margin_x, margin_y
        elif corner == "top_right": x, y = base_w - target_w - margin_x, margin_y
        elif corner == "bottom_left": x, y = margin_x, base_h - target_h - margin_y
        else: x, y = base_w - target_w - margin_x, base_h - target_h - margin_y
        
        base_img = base_img.convert("RGBA")
        base_img.alpha_composite(logo, dest=(x, y))
        return base_img.convert("RGB")
    except Exception:
        return base_img

def _overlay_headline(img: Image.Image, text: str) -> Image.Image:
    if not text: return img
    
    draw = ImageDraw.Draw(img)
    w, h = img.size
    
    # Шрифт ~4.5% от высоты
    font_size = int(h * 0.045)
    try:
        font = ImageFont.truetype("arial.ttf", font_size)
    except IOError:
        font = ImageFont.load_default()

    margin_side = int(w * 0.06) 
    max_text_width = w - (2 * margin_side)
    
    # --- Перенос строк (Word Wrap) ---
    words = text.split()
    lines = []
    current_line = []
    
    for word in words:
        test_line = ' '.join(current_line + [word])
        # Замер ширины
        if hasattr(draw, "textlength"): lw = draw.textlength(test_line, font=font)
        else: lw, _ = draw.textsize(test_line, font=font)
            
        if lw <= max_text_width:
            current_line.append(word)
        else:
            if current_line: lines.append(' '.join(current_line))
            current_line = [word]
    if current_line: lines.append(' '.join(current_line))
    
    # Ограничение до 3 строк
    if len(lines) > 3:
        lines = lines[:3]
        lines[-1] += "..."

    # --- Рисование ---
    line_height = int(font_size * 1.4)
    total_h = len(lines) * line_height
    padding = int(font_size * 0.6)
    
    # Координаты плашки
    box_x1 = margin_side - padding
    box_y1 = int(h * 0.06)
    box_x2 = w - margin_side + padding
    box_y2 = box_y1 + total_h + (2 * padding)
    
    # Подложка
    overlay = Image.new("RGBA", img.size, (0,0,0,0))
    dr = ImageDraw.Draw(overlay)
    dr.rectangle((box_x1, box_y1, box_x2, box_y2), fill=(0, 0, 0, 180)) 
    
    img = img.convert("RGBA")
    img = Image.alpha_composite(img, overlay)
    
    # Текст
    draw = ImageDraw.Draw(img)
    current_y = box_y1 + padding
    
    for line in lines:
        if hasattr(draw, "textlength"): lw = draw.textlength(line, font=font)
        else: lw, _ = draw.textsize(line, font=font)
        
        # Центрируем текст
        x_text = (w - lw) // 2
        draw.text((x_text, current_y), line, font=font, fill="white")
        current_y += line_height
        
    return img.convert("RGB")

def process_image(img: Image.Image, spec: dict) -> io.BytesIO:
    has_text = False
    text_content = spec.get("text_overlay", {}).get("headline")
    if spec.get("text_overlay", {}).get("enabled") and text_content:
        has_text = True
    
    # 1. Сначала текст (сверху)
    if has_text:
        img = _overlay_headline(img, text_content)
    
    # 2. Потом лого (снизу или в свободном углу)
    img = _overlay_logo(img, text_present=has_text)
    
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=95, subsampling=0)
    buf.seek(0)
    return buf