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

def _measure_region_complexity(img_gray: Image.Image, box: tuple) -> tuple:
    crop = img_gray.crop(box)
    edges = crop.filter(ImageFilter.FIND_EDGES)
    edge_score = ImageStat.Stat(edges).mean[0]
    brightness = ImageStat.Stat(crop).mean[0]
    return edge_score, brightness


def _load_headline_font(size: int) -> ImageFont.FreeTypeFont:
    """Пробуем подобрать приятный жирный шрифт для заголовка."""
    preferred = ["DejaVuSans-Bold.ttf", "arialbd.ttf", "arial.ttf"]
    for name in preferred:
        try:
            return ImageFont.truetype(name, size)
        except IOError:
            continue
    return ImageFont.load_default()


def _wrap_text(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.FreeTypeFont, max_width: int, max_lines: int):
    words = text.split()
    lines, current_line = [], []

    for word in words:
        test_line = " ".join(current_line + [word])
        if hasattr(draw, "textlength"):
            lw = draw.textlength(test_line, font=font)
        else:
            lw, _ = draw.textsize(test_line, font=font)

        if lw <= max_width:
            current_line.append(word)
        else:
            if current_line:
                lines.append(" ".join(current_line))
            current_line = [word]
    if current_line:
        lines.append(" ".join(current_line))

    if len(lines) > max_lines:
        lines = lines[:max_lines]
        lines[-1] += "..."

    return lines


def _overlay_headline(img: Image.Image, text: str) -> Image.Image:
    if not text:
        return img

    base_w, base_h = img.size
    margin_side = int(base_w * 0.06)
    max_text_width = base_w - (2 * margin_side)
    max_lines = 3

    # Подбираем размер шрифта под контент, уменьшая если заголовок слишком длинный
    base_font_size = int(base_h * 0.048)
    min_font_size = max(int(base_font_size * 0.7), 16)
    draw = ImageDraw.Draw(img)

    chosen_font = _load_headline_font(base_font_size)
    lines = _wrap_text(draw, text, chosen_font, max_text_width, max_lines)

    if len(lines) > max_lines or any(
        (draw.textlength(line, font=chosen_font) if hasattr(draw, "textlength") else draw.textsize(line, font=chosen_font)[0]) > max_text_width
        for line in lines
    ):
        for size in range(base_font_size, min_font_size - 1, -2):
            candidate_font = _load_headline_font(size)
            candidate_lines = _wrap_text(draw, text, candidate_font, max_text_width, max_lines)
            widths_ok = all(
                (draw.textlength(line, font=candidate_font) if hasattr(draw, "textlength") else draw.textsize(line, font=candidate_font)[0]) <= max_text_width
                for line in candidate_lines
            )
            if len(candidate_lines) <= max_lines and widths_ok:
                chosen_font = candidate_font
                lines = candidate_lines
                break

    line_height = int(chosen_font.size * 1.35)
    total_h = len(lines) * line_height
    padding = int(chosen_font.size * 0.7)

    # Подбор области с минимальным количеством деталей
    overlay_h = total_h + (2 * padding)
    top_y = int(base_h * 0.06)
    center_y = max((base_h - overlay_h) // 2, top_y)
    bottom_y = max(base_h - overlay_h - int(base_h * 0.08), top_y)

    candidate_positions = [top_y, center_y, bottom_y]
    img_gray = img.convert("L")

    best_y = candidate_positions[0]
    best_score = float("inf")
    best_brightness = 128

    for y in candidate_positions:
        box = (
            margin_side - padding,
            y,
            base_w - margin_side + padding,
            y + overlay_h,
        )
        try:
            edge_score, brightness = _measure_region_complexity(img_gray, box)
        except Exception:
            edge_score, brightness = 255, 128

        if edge_score < best_score:
            best_score = edge_score
            best_y = y
            best_brightness = brightness

    box_x1 = margin_side - padding
    box_y1 = best_y
    box_x2 = base_w - margin_side + padding
    box_y2 = box_y1 + overlay_h

    # Динамическая плашка под фон: светлая на темном и наоборот, с мягким блюром
    if best_brightness < 110:
        bg_fill = (255, 255, 255, 185)
        stroke_fill = (0, 0, 0, 90)
        text_color = "#0f0f0f"
    else:
        bg_fill = (0, 0, 0, 185)
        stroke_fill = (255, 255, 255, 90)
        text_color = "white"

    overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    dr = ImageDraw.Draw(overlay)

    # Создаем мягкую подложку под текст с меньшим блюром, чтобы фон не "расползался"
    region = img.crop((box_x1, box_y1, box_x2, box_y2)).filter(ImageFilter.GaussianBlur(radius=3))
    region_overlay = Image.new("RGBA", region.size, (0, 0, 0, 0))
    region_overlay.paste(region.convert("RGBA"))
    tinted_layer = Image.new("RGBA", region.size, bg_fill)
    region_overlay = Image.alpha_composite(region_overlay, tinted_layer)

    overlay.paste(region_overlay, (box_x1, box_y1))
    dr.rounded_rectangle(
        (box_x1, box_y1, box_x2, box_y2),
        radius=int(padding * 0.6),
        outline=stroke_fill,
        width=max(1, chosen_font.size // 16),
        fill=(0, 0, 0, 0),
    )

    img = img.convert("RGBA")
    img = Image.alpha_composite(img, overlay)

    # Отрисовываем текст на отдельном слое, который затем чуть резким маском усиливаем
    text_layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(text_layer)
    current_y = box_y1 + padding

    for line in lines:
        if hasattr(draw, "textlength"):
            lw = draw.textlength(line, font=chosen_font)
        else:
            lw, _ = draw.textsize(line, font=chosen_font)

        x_text = (base_w - lw) // 2
        shadow_offset = max(1, chosen_font.size // 18)
        stroke_width = max(2, int(chosen_font.size * 0.08))
        draw.text((x_text + shadow_offset, current_y + shadow_offset), line, font=chosen_font, fill=stroke_fill)
        draw.text(
            (x_text, current_y),
            line,
            font=chosen_font,
            fill=text_color,
            stroke_width=stroke_width,
            stroke_fill=stroke_fill,
        )
        current_y += line_height

    # Легкое повышение резкости текста
    sharpened_text = text_layer.filter(ImageFilter.UnsharpMask(radius=1.0, percent=170, threshold=2))
    img = Image.alpha_composite(img, sharpened_text)

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