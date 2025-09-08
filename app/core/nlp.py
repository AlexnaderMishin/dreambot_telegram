# app/core/nlp.py
from __future__ import annotations

import json
import re
import hashlib
from dataclasses import dataclass, asdict, field
from typing import List, Dict, Optional, Tuple

# --- Redis (опционально, мягкий фолбэк)
try:
    import redis  # type: ignore
except Exception:
    redis = None

# слова/цифры, без пунктуации; ё нормализуем к е
WORD_RE = re.compile(r"[a-zA-Zа-яА-ЯёЁ0-9]+")


# ====================== ВСПОМОГАТЕЛЬНОЕ ======================

def _norm(s: str) -> str:
    return s.lower().replace("ё", "е").strip()


def _levenshtein(a: str, b: str) -> int:
    """Расстояние Левенштейна (O(len(a)*len(b)))."""
    if a == b:
        return 0
    if not a:
        return len(b)
    if not b:
        return len(a)
    dp = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        prev = dp[0]
        dp[0] = i
        for j, cb in enumerate(b, 1):
            cur = dp[j]
            if ca == cb:
                dp[j] = prev
            else:
                dp[j] = 1 + min(prev, dp[j], dp[j - 1])
            prev = cur
    return dp[-1]


def normalize(text: str) -> List[str]:
    """В токены: нижний регистр, ё->е, без пунктуации."""
    t = _norm(text)
    return [w for w in WORD_RE.findall(t) if w]


def make_bigrams(tokens: List[str]) -> List[str]:
    return [f"{tokens[i]} {tokens[i + 1]}" for i in range(len(tokens) - 1)]


# ====================== ЗАГРУЗКА ДАННЫХ ======================

def _load_json(path: str):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def load_symbols_from_json(path: str = "data/symbols.ru.json") -> Dict[str, dict]:
    data = _load_json(path)
    assert isinstance(data, dict), "symbols.ru.json должен быть словарём"
    return data


def load_emotions_map(path: str = "data/emotions.ru.json") -> Dict[str, dict]:
    """
    Поддерживает 2 формата и приводит их к единому виду:
      1) {"страх": ["страх","ужас",...]}
      2) {"страх": {"keywords":[...], "description":"...", "coping":[...]}}
    Возвращает: {"страх": {"keywords":[...], "description":str|None, "coping":list|None}, ...}
    """
    raw = _load_json(path)
    assert isinstance(raw, dict), "emotions.ru.json должен быть словарём"

    out: Dict[str, dict] = {}
    for name, val in raw.items():
        key = _norm(name)
        if isinstance(val, list):
            out[key] = {"keywords": [_norm(x) for x in val], "description": None, "coping": None}
        elif isinstance(val, dict):
            kws = val.get("keywords") or val.get("keys") or []
            out[key] = {
                "keywords": [_norm(x) for x in kws if isinstance(x, str)],
                "description": val.get("description"),
                "coping": val.get("coping") if isinstance(val.get("coping"), list) else None,
            }
        else:
            out[key] = {"keywords": [], "description": None, "coping": None}
    return out


def load_crisis_from_json(path: str = "data/crisis.ru.json") -> List[dict]:
    """
    Элемент: { "phrase": "...", "severity": 1..3, "help": "...", "help_url": "..." }
    """
    data = _load_json(path)
    if isinstance(data, dict) and "items" in data:
        return list(data["items"])
    if isinstance(data, list):
        return list(data)
    return []


# ====================== КЭШ СЛОВАРЕЙ (REDIS) ======================

class SymbolsCache:
    def __init__(self, redis_url: Optional[str], ttl_sec: int = 3600):
        self.redis_url = redis_url
        self.ttl_sec = ttl_sec
        self.key = "dreambot:symbols:v1"

    def _r(self):
        if not self.redis_url or not redis:
            return None
        try:
            return redis.from_url(self.redis_url, decode_responses=True)
        except Exception:
            return None

    def get(self) -> Dict[str, dict]:
        r = self._r()
        if r:
            cached = r.get(self.key)
            if cached:
                try:
                    return json.loads(cached)
                except Exception:
                    pass
            data = load_symbols_from_json()
            try:
                r.setex(self.key, self.ttl_sec, json.dumps(data, ensure_ascii=False))
            except Exception:
                pass
            return data
        return load_symbols_from_json()


class EmotionsCache:
    def __init__(self, redis_url: Optional[str], ttl_sec: int = 3600):
        self.redis_url = redis_url
        self.ttl_sec = ttl_sec
        self.key = "dreambot:emotions:v2"  # унифицированный формат

    def _r(self):
        if not self.redis_url or not redis:
            return None
        try:
            return redis.from_url(self.redis_url, decode_responses=True)
        except Exception:
            return None

    def get(self) -> Dict[str, dict]:
        r = self._r()
        if r:
            cached = r.get(self.key)
            if cached:
                try:
                    return json.loads(cached)
                except Exception:
                    pass
            data = load_emotions_map()
            try:
                r.setex(self.key, self.ttl_sec, json.dumps(data, ensure_ascii=False))
            except Exception:
                pass
            return data
        return load_emotions_map()


# ====================== РЕЗУЛЬТАТ АНАЛИЗА ======================

@dataclass
class Analysis:
    symbols: List[dict]                 # [{key, meaning, actions}]
    emotions: List[str]                 # упорядоченный список эмоций
    emotions_count: Dict[str, int]      # счётчики совпадений по эмоциям
    actions: List[str]                  # агрегированные рекомендации (top N)
    archetypes: List[str]
    summary: str
    crisis: bool = False
    crisis_matches: List[str] = field(default_factory=list)
    crisis_help: Optional[str] = None
    crisis_help_url: Optional[str] = None


# ====================== ДЕТЕКТОРЫ ======================

def _match_symbol(tokens_set: set, bigrams_set: set, key: str, syns: List[str]) -> bool:
    """Жёсткий токенный/биграмный матч + аккуратный нечёткий (Левенштейн<=1) для слов длиной >=5."""
    cands = [_norm(key), *[_norm(s) for s in (syns or [])]]

    # 1) точные токены/фразы
    for c in cands:
        if " " in c:
            if c in bigrams_set:
                return True
        else:
            if c in tokens_set:
                return True

    # 2) нечёткий (только для длинных слов)
    for c in cands:
        if " " in c or len(c) < 5:
            continue
        for t in tokens_set:
            if abs(len(t) - len(c)) <= 1 and _levenshtein(t, c) <= 1:
                return True
    return False


def detect_symbols(tokens: List[str], bigrams: List[str], symbols_dict: Dict[str, Dict]) -> List[dict]:
    res: List[dict] = []
    token_set = set(tokens)
    bigram_set = set(bigrams)

    for key, info in symbols_dict.items():
        syns = [key, *info.get("synonyms", [])]
        syns = [s for s in (syns or []) if s]
        if _match_symbol(token_set, bigram_set, key, syns):
            res.append({
                "key": _norm(key),
                "meaning": (info.get("meaning", "") or "").strip(),
                "actions": list(info.get("actions", []) or []),
            })
    return res


def detect_emotions(tokens: List[str],
                    bigrams: List[str],
                    emotions_map: Dict[str, dict]) -> Tuple[List[str], Dict[str, int]]:
    """Возвращает (эмоции по убыванию частоты, счётчики)."""
    token_set = set(tokens)
    bigram_set = set(bigrams)

    counts: Dict[str, int] = {}
    for emo, data in emotions_map.items():
        kws = [k for k in data.get("keywords", [])]
        c = 0
        for k in kws:
            k = _norm(k)
            if not k:
                continue
            if " " in k:
                if k in bigram_set:
                    c += 1
            else:
                if k in token_set:
                    c += 1
                elif len(k) >= 5:
                    # немного мягкости
                    for t in token_set:
                        if abs(len(t) - len(k)) <= 1 and _levenshtein(t, k) <= 1:
                            c += 1
                            break
        if c > 0:
            counts[_norm(emo)] = c

    ordered = sorted(counts.keys(), key=lambda e: (-counts[e], e))
    return ordered, counts


# ====================== АРХЕТИПЫ/ОБЩИЙ СМЫСЛ ======================

ARCH_RULES: Dict[str, str] = {
    # базовые изначальные
    "вода": "эмоции/подсознание",
    "наводнение": "эмоции/подсознание",
    "шторм": "эмоции/подсознание",
    "дом": "внутренний мир/границы",
    "дверь": "границы/порог",
    "мост": "переход/связь",
    "лестница": "рост/спуск, переход между уровнями",
    "поезд": "путь/перемены",
    "автомобиль": "контроль/жизненный путь",
    "авто": "контроль/жизненный путь",
    "транспорт": "контроль/жизненный путь",
    "авария": "контроль/жизненный путь",
    "погоня": "избегание/встреча с задачей",
    "змея": "трансформация/инстинкты",
    "зубы": "самопрезентация/уверенность",
    "темнота": "неопределённость/скрытое",
    "ночь": "неопределённость/скрытое",
    "тьма": "неопределённость/скрытое",
    "животное": "инстинкты/базовые эмоции",
    "падение": "потеря контроля/уязвимость",
    "смерть": "обновление/завершение цикла",
    "одежда": "уязвимость/самопрезентация",
    "нагота": "уязвимость/самопрезентация",
    "экзамен": "проверка/страх несоответствия",
    "учёба": "проверка/страх несоответствия",
    "школа": "проверка/страх несоответствия",

    # доп. транспорт/масштаб/перспектива
    "самолет": "масштаб/перспектива",
    "самолёт": "масштаб/перспектива",
    "полет": "свобода/перспективы",
    "полёт": "свобода/перспективы",
    "лифт": "быстрые переходы/статус",
    "мост": "переход/связь",

    # вода / море / волны / лодка
    "море": "эмоции/подсознание",
    "волна": "эмоции/цикличность",
    "лодка": "управление эмоциями/отношениями",
    "утопление": "эмоции/перегруз",

    # природа/стихии/погода
    "гроза": "напряжение/разрядка",
    "огонь": "энергия/очищение",
    "смерч": "бурные перемены/хаос",
    "лес": "поиск себя/неизвестность",
    "пещера": "погружение в бессознательное",

    # пространство дома
    "подвал": "бессознательное/глубины",
    "чердак": "идеи/архив ума",

    # город/социум
    "город": "социальные правила/сети",
    "деревня": "корни/замедление",

    # животные
    "собака": "доверие/защита",
    "волк": "инстинкты/границы",
    "медведь": "сила/территории",
    "тигр": "агрессия/харизма",
    "кошка": "интуиция/независимость",
    "рыба": "интуиция/новое",

    # «тени», страхи
    "чудовище": "подавленные эмоции/страхи",
    "привидение": "прошлое/непрожитое",
    "оружие": "агрессия/угроза",
    "нападение": "уязвимость/конфликт",
    "насекомые": "мелкие раздражители",
    "паук": "запутанность/отвращение",
    "паутина": "сети/залипание",
    "кровь": "рана/исцеление",
    "бомба": "накопленное напряжение",

    # время/тайминг/правила
    "опоздание": "тайминг/перегруз",
    "запоздание": "тайминг/перегруз",
    "очередь": "терпение/справедливость",
    "телефон": "контакты/перегруз коммуникациями",
    "шум": "перегруз стимулов",

    # ключи/доступ/границы
    "ключи": "доступ/решение",
    "дверь": "границы/порог",
    "замок": "границы/доступ",

    # идентичность/багаж/потери/находки
    "чемодан": "личный багаж/обязательства",
    "паспорт": "идентичность/статус",
    "потеря": "утрата/нехватка",
    "нахождение": "возврат ресурса",

    # путь/ориентация
    "лабиринт": "поиск выхода/сложный путь",
    "карта": "ориентиры/план",
    "заблудиться": "поиск направления",

    # отношения/близость
    "поцелуй": "близость/интеграция",
    "секс": "близость/новые ресурсы",

    # ограничения/контроль
    "тюрьма": "ограничения/вина",
    "драка": "конфликт/границы",
    "зеркало": "самовосприятие/тень",

    "гора": "испытания/препятствие/цель",
    "цветы": "чувства/красота/признание",
    "дерево": "жизнь/рост/связь поколений",
    "сад": "личное пространство/забота",
    "больница": "исцеление/уязвимость",
    "операция": "трансформация/лечение",
    "кольцо": "союз/обязательства",
    "свадьба": "переход/объединение",
    "университет": "знания/развитие",
    "аэропорт": "ожидание/перемены",
    "пляж": "граница сознательного и бессознательного",
    "космос": "бесконечность/вдохновение",
    "звезды": "надежды/планы",
    "церковь": "духовность/ценности",
    "кладбище": "прощание/память",
    "коридор": "переход/неопределенность",
    "окно": "возможности/перспективы",
    "ребёнок": "новое начало/уязвимость",
    "беременность": "созревание/ответственность",
    "часы": "время/ограниченность ресурсов",
    "друг": "отношения/поддержка",
    "подруга": "отношения/поддержка",
    "мать": "забота/корни",
    "отец": "структура/контроль",
    "бабушка": "род/мудрость",
    "дедушка": "род/мудрость",
    "брат": "соперничество/равенство",
    "сестра": "соперничество/равенство",
    "ребёнок": "новое/уязвимость",
    "ребенок": "новое/уязвимость",
    "младенец": "новое/уязвимость",
    "дядя": "социальные связи/поддержка",
    "тётя": "социальные связи/поддержка",
    "тетя": "социальные связи/поддержка",
    "партнёр": "союз/отношения",
    "партнер": "союз/отношения",
    "муж": "союз/отношения",
    "жена": "союз/отношения",
    "родители": "опора/семейные сценарии",
    "семья": "опора/семейные сценарии",
    "лотерея": "удача/риск",
    "ставки": "удача/риск",
    "преступники": "угроза/границы"
}

def infer_archetypes(symbol_keys: List[str]) -> List[str]:
    a, seen = [], set()
    for k in symbol_keys:
        kk = k.lower().replace("ё", "е").strip()
        note = ARCH_RULES.get(kk)
        if note and note not in seen:
            seen.add(note)
            a.append(note)
    return a


def infer_summary(symbol_keys: List[str], emotions_ordered: List[str]) -> str:
    ks = {k.lower() for k in symbol_keys}

    # --- приоритетные сочетания (более точные, чем одиночные темы) ---
    # контроль/управление
    if ("автомобиль" in ks and "авария" in ks) or ("автомобиль" in ks and "тормоза" in ks):
        return "Тема контроля: страх не справиться с управлением в важной сфере."
    if {"автомобиль", "чужая машина"} <= ks:
        return "Тема ответственности: управляете чем-то «не своим», поэтому контроль ощущается слабее."

    # эмоциональное переполнение
    if "вода" in ks and ("наводнение" in ks or "шторм" in ks):
        return "Эмоциональное переполнение — важно мягко разгружать чувства."

    # границы/порог
    if "дом" in ks and "дверь" in ks:
        return "Тема границ и личного пространства."

    # избегание/встреча с задачей
    if "погоня" in ks:
        return "Избегание задачи или сильной эмоции — стоит остановиться и посмотреть, что «преследует»."

    # уверенность/образ
    if "зубы" in ks:
        return "Тема уверенности и самопрезентации — как вы себя показываете миру."

    # --- одиночные эвристики, согласованные с ARCH_RULES ---
    if {"темнота", "ночь", "тьма"} & ks:
        return "Поиск скрытых аспектов и работа с неосознанным; может указывать на чувство неопределённости."

    if {"животное", "змея", "волк", "собака", "медведь"} & ks:
        return "Работа с инстинктами и базовыми эмоциями."

    if {"полет", "полёт", "летать", "взлёт"} & ks:
        return "Желание свободы и расширения перспектив; стремление выйти за рамки."

    if "падение" in ks:
        return "Тема потери контроля или опоры; ощущение уязвимости."

    if {"смерть", "похороны"} & ks:
        return "Завершение цикла и обновление; переход к новому этапу."

    if {"одежда", "нагота"} & ks:
        return "Уязвимость и самопрезентация; страх быть увиденным настоящим."

    if {"экзамен", "учёба", "школа"} & ks:
        return "Проверка на готовность и страх несоответствия."

    # общий мягкий фолбэк
    if emotions_ordered:
        return f"Сон отражает преобладающую эмоцию: {emotions_ordered[0]}."
    return "Сон отражает текущие переживания и процесс адаптации."




# ====================== КРИЗИС ======================

def match_crisis(text: str, items: List[dict]) -> Tuple[bool, List[str], Optional[dict]]:
    """
    Возвращает (is_crisis, совпадения, best_help_dict|None),
    где best_help_dict может содержать поля {"help": "...", "help_url": "..."}.
    Берём элемент с максимальной severity.
    """
    t = _norm(text)
    hits: List[str] = []
    best: Optional[dict] = None
    best_sev = -1

    for it in items:
        phrase = _norm(it.get("phrase", ""))
        if not phrase:
            continue
        if phrase in t:
            hits.append(phrase)
            sev = int(it.get("severity", 1))
            if sev > best_sev:
                best_sev = sev
                best = {"help": it.get("help"), "help_url": it.get("help_url")}
    return (len(hits) > 0), hits, best


# ====================== ОСНОВНОЙ АНАЛИЗ ======================

def analyze_dream(text: str, *, redis_url: Optional[str] = None) -> Analysis:
    # кэш результата (по нормализованному тексту)
    norm_join = " ".join(normalize(text))
    cache_key = "dreambot:analysis:" + hashlib.sha1(norm_join.encode("utf-8")).hexdigest()

    r = None
    if redis_url and redis:
        try:
            r = redis.from_url(redis_url, decode_responses=True)
            cached = r.get(cache_key)
            if cached:
                data = json.loads(cached)
                return Analysis(**data)
        except Exception:
            r = None  # фолбэк без Redis

    # токены/биграммы
    tokens = normalize(text)
    bigrams = make_bigrams(tokens)

    # словари
    symbols_dict = SymbolsCache(redis_url).get()
    emotions_map = EmotionsCache(redis_url).get()

    # 1) символы
    symbols_found = detect_symbols(tokens, bigrams, symbols_dict)

    # 2) эмоции
    emotions_ordered, emotions_counts = detect_emotions(tokens, bigrams, emotions_map)

    # 3) действия (агрегация из символов)
    all_actions: List[str] = []
    for s in symbols_found:
        all_actions.extend(s.get("actions", []))
    # дедуп и обрезка top-5
    seen = set()
    uniq_actions: List[str] = []
    for a in all_actions:
        a = (a or "").strip()
        if a and a not in seen:
            seen.add(a)
            uniq_actions.append(a)
    if len(uniq_actions) > 5:
        uniq_actions = uniq_actions[:5]

    # 4) архетипы + общий смысл
    symbol_keys = [s["key"] for s in symbols_found]  # <-- фикс: убран мусор
    archetypes = infer_archetypes(symbol_keys)
    summary = infer_summary(symbol_keys, emotions_ordered)

    # 5) кризис
    crisis_items = load_crisis_from_json()
    crisis, crisis_list, help_dict = match_crisis(text, crisis_items)
    crisis_help = help_dict.get("help") if help_dict else None
    crisis_help_url = help_dict.get("help_url") if help_dict else None

    analysis = Analysis(
        symbols=symbols_found,
        emotions=emotions_ordered,
        emotions_count=emotions_counts,
        actions=uniq_actions,
        archetypes=archetypes,
        summary=summary,
        crisis=crisis,
        crisis_matches=crisis_list,
        crisis_help=crisis_help,
        crisis_help_url=crisis_help_url,
    )

    # закешировать
    if r:
        try:
            r.setex(cache_key, 3600, json.dumps(asdict(analysis), ensure_ascii=False))
        except Exception:
            pass

    return analysis
