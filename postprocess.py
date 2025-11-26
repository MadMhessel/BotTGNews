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


def _calculate_overlay_palette(best_brightness: float, layout_palette: str):
    """Возвращает цвета подложки и текста с учетом желаемой палитры."""
    palette = layout_palette or "auto"

    force_light = palette == "light"
    force_dark = palette == "dark"

    if force_light or (best_brightness < 110 and not force_dark):
        return {
            "bg_fill": (255, 255, 255, 195),
            "stroke_fill": (0, 0, 0, 80),
            "text_color": "#0f0f0f",
            "accent_color": "#b84a00",
        }

    return {
        "bg_fill": (0, 0, 0, 190),
        "stroke_fill": (255, 255, 255, 95),
        "text_color": "white",
        "accent_color": "#ffd166",
    }


def _overlay_headline(img: Image.Image, text: str, layout: dict) -> Image.Image:
    if not text:
        return img

    layout = layout or {}
    preferred_position = layout.get("placement", "auto")
    alignment = layout.get("alignment", "center")
    overlay_style = layout.get("style", "glass")
    palette_hint = layout.get("palette", "auto")
    emphasis_words = set((layout.get("emphasis") or []))

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

    candidate_positions = [
        ("top", top_y),
        ("center", center_y),
        ("bottom", bottom_y),
    ]

    if preferred_position in {"top", "center", "bottom"}:
        candidate_positions.sort(key=lambda item: 0 if item[0] == preferred_position else 1)

    img_gray = img.convert("L")

    best_y = candidate_positions[0][1]
    best_score = float("inf")
    best_brightness = 128

    for _, y in candidate_positions:
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

    colors = _calculate_overlay_palette(best_brightness, palette_hint)
    bg_fill = colors["bg_fill"]
    stroke_fill = colors["stroke_fill"]
    text_color = colors["text_color"]
    accent_color = colors["accent_color"]

    overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    dr = ImageDraw.Draw(overlay)

    # Настройка подложки под стиль
    if overlay_style == "banner":
        blur_radius = 1
        radius_factor = 0.25
        stroke_width = max(1, chosen_font.size // 14)
    elif overlay_style == "soft_card":
        blur_radius = 2
        radius_factor = 0.85
        stroke_width = max(1, chosen_font.size // 18)
    else:  # glass
        blur_radius = 3
        radius_factor = 0.6
        stroke_width = max(1, chosen_font.size // 16)

    # Создаем мягкую подложку под текст, чтобы фон не "расползался"
    region = img.crop((box_x1, box_y1, box_x2, box_y2)).filter(ImageFilter.GaussianBlur(radius=blur_radius))
    region_overlay = Image.new("RGBA", region.size, (0, 0, 0, 0))
    region_overlay.paste(region.convert("RGBA"))
    tinted_layer = Image.new("RGBA", region.size, bg_fill)
    region_overlay = Image.alpha_composite(region_overlay, tinted_layer)

    overlay.paste(region_overlay, (box_x1, box_y1))
    dr.rounded_rectangle(
        (box_x1, box_y1, box_x2, box_y2),
        radius=int(padding * radius_factor),
        outline=stroke_fill,
        width=stroke_width,
        fill=(0, 0, 0, 0),
    )

    img = img.convert("RGBA")
    img = Image.alpha_composite(img, overlay)

    # Отрисовываем текст на отдельном слое, который затем чуть резким маском усиливаем
    text_layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(text_layer)
    current_y = box_y1 + padding

    for line in lines:
        words = line.split()
        if hasattr(draw, "textlength"):
            word_widths = [draw.textlength(word, font=chosen_font) for word in words]
            space_width = draw.textlength(" ", font=chosen_font)
        else:
            word_widths = [draw.textsize(word, font=chosen_font)[0] for word in words]
            space_width = draw.textsize(" ", font=chosen_font)[0]

        total_line_width = sum(word_widths) + space_width * max(len(words) - 1, 0)
        if alignment == "left":
            x_text = margin_side
        elif alignment == "right":
            x_text = max(margin_side, base_w - margin_side - total_line_width)
        else:
            x_text = max(margin_side, (base_w - total_line_width) // 2)

        shadow_offset = max(1, chosen_font.size // 18)
        base_stroke_width = max(2, int(chosen_font.size * 0.08))

        current_x = x_text
        for idx, word in enumerate(words):
            clean_word = word.strip(",.!?:;—–…")
            is_emphasis = clean_word.lower() in {w.lower() for w in emphasis_words}
            fill_color = accent_color if is_emphasis else text_color
            stroke_width = base_stroke_width + (1 if is_emphasis else 0)

            draw.text((current_x + shadow_offset, current_y + shadow_offset), word, font=chosen_font, fill=stroke_fill)
            draw.text(
                (current_x, current_y),
                word,
                font=chosen_font,
                fill=fill_color,
                stroke_width=stroke_width,
                stroke_fill=stroke_fill,
            )

            current_x += word_widths[idx] + space_width

        current_y += line_height

    # Легкое повышение резкости текста
    sharpened_text = text_layer.filter(ImageFilter.UnsharpMask(radius=1.0, percent=170, threshold=2))
    img = Image.alpha_composite(img, sharpened_text)

    return img.convert("RGB")

def process_image(img: Image.Image, spec: dict) -> io.BytesIO:
    has_text = False
    text_overlay_spec = spec.get("text_overlay", {})
    text_content = text_overlay_spec.get("headline")
    layout = text_overlay_spec.get("layout", {})
    if spec.get("text_overlay", {}).get("enabled") and text_content:
        has_text = True

    # 1. Сначала текст (сверху)
    if has_text:
        img = _overlay_headline(img, text_content, layout)
    
    # 2. Потом лого (снизу или в свободном углу)
    img = _overlay_logo(img, text_present=has_text)
    
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=95, subsampling=0)
    buf.seek(0)
    return buf