# app/core/telegram_html.py
import re

_ALLOWED = r"(?:b|strong|i|em|u|ins|s|strike|del|a|code|pre|br)"

def sanitize_tg_html(html: str) -> str:
    if not html:
        return ""

    # 1) списки -> строки с буллитами
    html = re.sub(r"(?is)</?\s*(ul|ol)\b[^>]*>", "", html)
    html = re.sub(r"(?is)<\s*li\b[^>]*>\s*", "\n• ", html)
    html = html.replace("</li>", "")

    # 2) параграфы/блоки -> перевод строки
    html = re.sub(r"(?is)</?\s*(p|div|section|article|header|footer)\b[^>]*>", "\n", html)

    # 3) убрать все прочие теги, кроме разрешённых Telegram
    html = re.sub(rf"(?is)</?(?!{_ALLOWED})\w+[^>]*>", "", html)

    # 4) безопасно: не даём вставить скрипт/стили
    html = re.sub(r"(?is)<\s*script[^>]*>.*?<\s*/\s*script\s*>", "", html)
    html = re.sub(r"(?is)</?\s*style[^>]*>.*?</\s*style\s*>", "", html)

    # 5) нормализуем пустые строки
    html = re.sub(r"\n{3,}", "\n\n", html)
    return html.strip()
