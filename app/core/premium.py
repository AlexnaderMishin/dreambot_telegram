# app/core/premium.py
from __future__ import annotations

import os
import re
import html
from typing import List, Optional, Tuple
from textwrap import dedent
from loguru import logger

from app.core.llm_client import chat
from app.core.llm_router import Feature
from app.core.telegram_html import sanitize_tg_html

# --- морфология (лемматизация русских слов) ---
try:
    import pymorphy2  # type: ignore
    _MORPH = pymorphy2.MorphAnalyzer()
except Exception:
    _MORPH = None  # безопасный фоллбек: без лемматизации, но всё работает

# =========================================================
# Премиум-анализ (LLM) + демо-шаблон
# =========================================================

def _demo_template(dream_text: str, warn: Optional[str] = None) -> str:
    bullets: List[str] = []
    if dream_text.strip():
        bullets.append("📖 <b>Краткий пересказ</b>\n• " + dream_text.strip())

    bullets.append(
        "🔑 <b>Символы и мотивы</b>\n"
        "• Выделим ключевые образы по контексту сна (в полной версии — гибкий NLP-анализ)."
    )
    bullets.append(
        "🎭 <b>Эмоциональный фон</b>\n"
        "• Определим ведущие эмоции и возможные триггеры."
    )
    bullets.append(
        "🧠 <b>Возможный смысл</b>\n"
        "• Гипотеза о теме сна с опорой на архетипы и текущий контекст."
    )
    bullets.append(
        "✅ <b>Шаги поддержки</b>\n"
        "• 1–3 конкретных шага, подобранных под сюжет сна."
    )

    footer = "\n<i>(Демо премиум-анализа. После подключения ChatGPT API здесь будет развёрнутый разбор.)</i>"
    if warn:
        footer = f"\n<i>{warn}</i>" + footer

    return "<b>Премиум-разбор сна</b>\n\n" + "\n\n".join(bullets) + footer


# --- страховочная чистка HTML под требования Telegram ---
_ALLOWED = {"b", "i"}
_BR_RE = re.compile(r"(?is)<\s*br\s*/?\s*>")
_TAG_RE_ANY = re.compile(r"</?([a-zA-Z0-9]+)(?:\s[^>]*)?>")

def _ensure_tg_html(s: str) -> str:
    # 1) теги, которые эквивалентны переносам
    s = _BR_RE.sub("\n", s)
    # <p>...</p> -> просто текст с пустой строкой между параграфами
    s = re.sub(r"(?is)<\s*p\s*>", "", s)
    s = re.sub(r"(?is)<\s*/\s*p\s*>", "\n\n", s)
    # <ul>/<li> -> буллеты
    s = re.sub(r"(?is)<\s*ul\s*>", "", s)
    s = re.sub(r"(?is)<\s*/\s*ul\s*>", "\n", s)
    s = re.sub(r"(?is)<\s*li\s*>", "• ", s)
    s = re.sub(r"(?is)<\s*/\s*li\s*>", "\n", s)

    # 2) удаляем всё, кроме <b>/<i>
    def _keep_or_strip(m: re.Match) -> str:
        tag = (m.group(1) or "").lower()
        return m.group(0) if tag in _ALLOWED else ""
    s = _TAG_RE_ANY.sub(_keep_or_strip, s)

    # 3) нормализация пустых строк
    s = re.sub(r"\n{3,}", "\n\n", s).strip()
    return s


def premium_analysis(dream_text: str) -> str:
    """
    Премиум-анализ сна через наш LLM-роутер.
    Управляется переменной окружения PREMIUM_MODE=api|stub (stub — демо-ответ без LLM).
    """
    mode = os.getenv("PREMIUM_MODE", "api").lower()
    logger.debug(f"[premium] mode={mode}")

    if mode != "api":
        return _demo_template(dream_text)

    system = dedent("""
    Ты — психологический ассистент по сновидениям. Кратко и структурно анализируй сон.
    Выводи ГОТОВЫЙ HTML для Telegram: разделы с эмодзи, короткие пункты.

    Структура (разделы именно в таком порядке):
    1) 📖 <b>Краткий пересказ</b> — 1–2 предложения.
    2) 🔑 <b>Символы и мотивы</b> — 2–5 пунктов. Каждый пункт в виде:
       «• <эмодзи?> <Символ> — краткое пояснение 3–8 слов».
    3) 🎭 <b>Эмоциональный фон</b> — 2–4 пункта. Каждый пункт ТОЧНО как в «Символах»:
       «• <эмодзи?> <Эмоция> — краткое пояснение 3–8 слов».
       Требования к <Эмоция>: существительное, единственное число (например: радость, тревога,
       спокойствие, уверенность, интерес). Не используй модальные слова («возможно», «скорее всего»,
       «кажется» и т.п.) и не пиши перечни через запятую — каждый пункт отдельной строкой.
    4) 🧠 <b>Возможный смысл</b> — 1 абзац.
    5) ✅ <b>Шаги поддержки</b> — 3–5 конкретных пунктов.

    Никаких дисклеймеров в конце (их добавит бот). Никаких просьб о медпомощи.
    Язык — русский.
    Не используй HTML-теги <br>, <ul>, <li>, <p>. Используй только переносы строк и теги <b> и <i>.
    """).strip()

    user = (dream_text or "").strip() or \
        "Пользователь прислал очень короткий или пустой сон. Дай универсальные мягкие рекомендации."

    messages = [
        {"role": "system", "content": system},
        {"role": "user",   "content": user},
    ]

    try:
        html_out = chat(Feature.DREAM, messages, temperature=0.7)
        html_out = sanitize_tg_html(html_out)
        html_out = _ensure_tg_html(html_out)  # строгая чистка под Telegram HTML
        # на всякий случай подрежем опасные теги
        html_out = html_out.replace("<script", "&lt;script").replace("</script>", "&lt;/script&gt;")
        return html_out
    except Exception as e:
        logger.exception("premium_analysis failed")
        return _demo_template(dream_text, warn=f"(Ошибка LLM: {e})")

# =========================================================
# Парсер для вытаскивания symbols/emotions из премиум-ответа
# + нормализация эмоций через pymorphy2
# =========================================================

_TAG_RE = re.compile(r"</?(?:b|i)>", re.IGNORECASE)

def _strip_tg_html(s: str) -> str:
    """Убираем <b>/<i>, заменяем <br> на переносы, декодируем HTML-entity, нормализуем переносы/пробелы."""
    s = _TAG_RE.sub("", s)
    s = re.sub(r"(?i)<\s*br\s*/?\s*>", "\n", s)  # важно для устойчивого парсинга
    s = html.unescape(s)
    s = s.replace("\r", "")
    s = re.sub(r"[ \t]+\n", "\n", s)
    s = re.sub(r"\n{3,}", "\n\n", s)
    return s.strip()

def _find_section(text: str, titles: List[str]) -> str:
    """
    Возвращает содержимое секции от заголовка до следующего заголовка/пустой строки/конца.
    titles — варианты заголовка (регистронезависимо, эмодзи допустимы).
    """
    title_re = r"|".join([re.escape(t) for t in titles])
    pat = re.compile(
        rf"(?mi)^(?:[\W_]*\s*)({title_re})\s*:?\s*\n+(.*?)(?=\n\s*(?:[^\n]*Символы|[^\n]*Эмоциональный фон|[^\n]*Возможный смысл|[^\n]*Шаги поддержки|[^\n]*Общий вывод|$))",
        re.DOTALL,
    )
    m = pat.search(text)
    return m.group(2).strip() if m else ""

def _split_bullets(block: str) -> List[str]:
    """Разбиваем блок на пункты: строки, начинающиеся с '-', '•', '—', эмодзи и т.п."""
    lines = [ln.strip(" \t") for ln in block.split("\n")]
    items: List[str] = []
    for ln in lines:
        if not ln:
            continue
        if re.match(r"^[\-\–—•\*\u2022\ufe0f\W]\s*", ln):
            items.append(re.sub(r"^[\-\–—•\*\u2022\ufe0f\W]+\s*", "", ln))
        else:
            if items and (ln and (ln[0].islower() or ln[0].isdigit())):
                items[-1] += " " + ln
    return items

def _clean_phrase(s: str) -> str:
    s = s.strip(" .,!?:;„“«»\"'()[]{}")
    s = re.sub(r"\s{2,}", " ", s)
    return s

def _left_before_dash(s: str) -> str:
    """Берём левую часть до тире — часто справа идёт пояснение."""
    parts = re.split(r"\s+[–—-]\s+", s, maxsplit=1)
    return parts[0].strip()

# --- нормализация эмоций ---

_STOP = {
    "и", "в", "во", "на", "по", "к", "ко", "из", "от", "до", "о", "об", "обо",
    "при", "со", "с", "над", "под", "за", "для", "без",
    "мой", "моя", "моё", "мои", "твой", "твоя", "твоё", "твои",
    "его", "её", "их", "наш", "наша", "наше", "наши", "ваш", "ваша", "ваше", "ваши",
    "свой", "своя", "своё", "свои",
    "это", "этот", "эта", "эти",
}

_PUNCT_RE = re.compile(r"[^\w\- ]+", re.UNICODE)

def _tokenize(s: str) -> List[str]:
    s = s.lower()
    s = _PUNCT_RE.sub(" ", s)
    toks = [t for t in s.split() if t and t not in _STOP]
    return toks

def _lemma(token: str) -> str:
    if not _MORPH:
        return token
    p = _MORPH.parse(token)
    if not p:
        return token
    return p[0].normal_form

def _pos(token: str) -> str:
    if not _MORPH:
        return ""
    p = _MORPH.parse(token)
    if not p:
        return ""
    return (p[0].tag.POS or "").upper()

def _normalize_emotion_phrase(phrase: str) -> str:
    """
    «уверенности в своих силах» -> «уверенность»
    «удовлетворение от достижения цели» -> «удовлетворение»
    «сила и спокойствие» -> «сила» (как главная)
    """
    toks = _tokenize(phrase)
    if not toks:
        return ""

    lemmas = [(tok, _lemma(tok), _pos(tok)) for tok in toks]

    nouns = [lem for _, lem, pos in lemmas if pos == "NOUN"]
    if nouns:
        return max(nouns, key=len)

    adjs = [lem for _, lem, pos in lemmas if pos in {"ADJF", "ADJS"}]
    if adjs:
        return max(adjs, key=len)

    return lemmas[0][1]

def _normalize_emotions_list(emotions: List[str]) -> List[str]:
    out: List[str] = []
    seen = set()
    for e in emotions:
        norm = _normalize_emotion_phrase(e)
        if norm and norm not in seen:
            seen.add(norm)
            out.append(norm)
    return out

# --- публичная функция для извлечения маркеров ---

def extract_symbols_emotions(premium_html_or_text: str) -> Tuple[List[str], List[str]]:
    """
    Возвращает (symbols, emotions) из премиум-разбора.
    На вход можно дать Telegram-HTML (с <b>/<i>) — он будет очищен.
    """
    text = _strip_tg_html(premium_html_or_text)

    # 1) Символы
    sym_block = _find_section(
        text,
        titles=[
            "Символы и мотивы",
            "Символы",
            "Ключевые символы",
            "Образы и символы",
        ],
    )
    symbols: List[str] = []
    if sym_block:
        for it in _split_bullets(sym_block):
            left = _left_before_dash(it)
            left = re.sub(r"^[\W_]+", "", left)  # срезаем эмодзи/маркеры в начале
            left = _clean_phrase(left)
            if left:
                symbols.append(left.lower())

    # 2) Эмоции (тот же формат: «Эмоция — пояснение»)
    emo_block = _find_section(
        text,
        titles=[
            "Эмоциональный фон",
            "Эмоции",
            "Чувства",
        ],
    )
    emotions: List[str] = []
    if emo_block:
        for it in _split_bullets(emo_block):
            left = _left_before_dash(it)
            left = re.sub(r"^[\W_]+", "", left)
            left = _clean_phrase(left)
            if not left:
                continue
            emotions.append(left.lower())

    # убираем дубли и нормализуем эмоции лемматизацией
    def _uniq(seq: List[str]) -> List[str]:
        seen = set()
        out: List[str] = []
        for x in seq:
            if x and x not in seen:
                seen.add(x)
                out.append(x)
        return out

    emotions = _normalize_emotions_list(emotions)

    return _uniq(symbols), _uniq(emotions)
