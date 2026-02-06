"""Keyboard Layout Fixer - исправление текста набранного в неправильной раскладке.

Полезно когда пользователь забыл переключить раскладку:
- "ghbdtn" -> "привет"
- "cjplfq" -> "создай"

Production-ready with:
- Whitelist of common English/tech terms to avoid false positives
- Improved consonant streak heuristic
- Input validation
"""

# Таблица соответствия EN -> RU
EN_TO_RU = {
    "q": "й",
    "w": "ц",
    "e": "у",
    "r": "к",
    "t": "е",
    "y": "н",
    "u": "г",
    "i": "ш",
    "o": "щ",
    "p": "з",
    "[": "х",
    "]": "ъ",
    "a": "ф",
    "s": "ы",
    "d": "в",
    "f": "а",
    "g": "п",
    "h": "р",
    "j": "о",
    "k": "л",
    "l": "д",
    ";": "ж",
    "'": "э",
    "z": "я",
    "x": "ч",
    "c": "с",
    "v": "м",
    "b": "и",
    "n": "т",
    "m": "ь",
    ",": "б",
    ".": "ю",
    "/": ".",
    "`": "ё",
    "~": "Ё",
}

# Таблица соответствия RU -> EN
RU_TO_EN = {v: k for k, v in EN_TO_RU.items()}

# Добавляем заглавные буквы
EN_TO_RU_UPPER = {k.upper(): v.upper() for k, v in EN_TO_RU.items() if k.isalpha()}
RU_TO_EN_UPPER = {v.upper(): k.upper() for k, v in EN_TO_RU.items() if k.isalpha()}
EN_TO_RU.update(EN_TO_RU_UPPER)
RU_TO_EN.update(RU_TO_EN_UPPER)

# Частые паттерны неправильной раскладки (EN -> RU)
COMMON_PATTERNS = {
    "ghbdtn": "привет",
    "cjplfq": "создай",
    "yfgbib": "напиши",
    "ntcn": "тест",
    "aeyrwbz": "функция",
    "rjl": "код",
    "ghjuhfvvf": "программа",
    "gjvjom": "помощь",
    "gjbcr": "поиск",
    "dsgjkyb": "выполни",
    "pfghjc": "запрос",
    "jnrhjq": "открой",
    "pfrhjq": "закрой",
}

# Common English words and tech terms to NOT convert (whitelist)
ENGLISH_WHITELIST = {
    # Common short words
    "the",
    "and",
    "for",
    "not",
    "but",
    "you",
    "all",
    "can",
    "had",
    "her",
    "was",
    "one",
    "our",
    "out",
    "has",
    "his",
    "how",
    "man",
    "new",
    "now",
    "old",
    "see",
    "two",
    "way",
    "who",
    "boy",
    "did",
    "get",
    "let",
    "put",
    "say",
    "she",
    "too",
    "use",
    "are",
    "its",
    # Tech terms (often have consonant clusters)
    "http",
    "https",
    "html",
    "css",
    "json",
    "xml",
    "api",
    "url",
    "uri",
    "npm",
    "git",
    "ssh",
    "ftp",
    "sql",
    "php",
    "cli",
    "gui",
    "sdk",
    "jwt",
    "test",
    "tests",
    "code",
    "help",
    "file",
    "type",
    "sync",
    "async",
    "script",
    "function",
    "class",
    "method",
    "string",
    "print",
    "return",
    "python",
    "javascript",
    "typescript",
    "react",
    "node",
    "docker",
    "linux",
    "nginx",
    "mysql",
    "redis",
    "mongodb",
    "postgres",
    # Common programming words
    "import",
    "export",
    "const",
    "let",
    "var",
    "def",
    "func",
    "struct",
}


def looks_like_wrong_layout(text: str) -> bool:
    """Проверяет, похож ли текст на набранный в неправильной раскладке.

    Эвристика: если текст состоит из латинских букв, но не похож
    на английские слова - вероятно это русский в EN раскладке.

    Uses whitelist of common English/tech terms to reduce false positives.
    """
    if not text or not isinstance(text, str):
        return False

    text = text.strip().lower()

    # Too short - skip
    if len(text) < 3:
        return False

    # Если есть русские буквы - раскладка правильная
    if any("\u0400" <= c <= "\u04ff" for c in text):
        return False

    # Если есть неASCII символы - не конвертируем
    if not all(c.isascii() for c in text):
        return False

    # Если текст полностью числа - не конвертируем
    if text.isdigit():
        return False

    # Check whitelist - if any word is a known English/tech term, skip
    words = text.split()
    for word in words:
        # Remove common punctuation for comparison
        clean_word = word.strip(".,!?;:'\"()[]{}").lower()
        if clean_word in ENGLISH_WHITELIST:
            return False

    # Проверяем известные паттерны
    if text in COMMON_PATTERNS:
        return True

    # Check each word for patterns
    for word in words:
        if word.lower() in COMMON_PATTERNS:
            return True

    # Эвристика: много согласных подряд без гласных
    # (типично для русского в EN раскладке)
    en_vowels = set("aeiou")
    consonant_streak = 0
    max_streak = 0

    for c in text:
        if c.isalpha() and c not in en_vowels:
            consonant_streak += 1
            max_streak = max(max_streak, consonant_streak)
        else:
            consonant_streak = 0

    # 5+ согласных подряд (raised from 4) очень необычно для английского
    # Except for some words like "strengths"
    if max_streak >= 5 and len(text) > 4:
        return True

    # Additional heuristic: high ratio of 'j', 'b', 'n' which are common in RU->EN
    # but less common in normal English
    suspicious_chars = set("jbnfghpx")  # Common in Russian, less in English starts
    alpha_chars = [c for c in text if c.isalpha()]
    if len(alpha_chars) >= 4:
        suspicious_ratio = sum(1 for c in alpha_chars if c in suspicious_chars) / len(alpha_chars)
        if suspicious_ratio > 0.5:
            return True

    return False


def fix_layout(text: str, direction: str = "auto") -> str:
    """Исправляет раскладку клавиатуры.

    Args:
        text: Текст для исправления
        direction: "en_to_ru", "ru_to_en", или "auto"

    Returns:
        Исправленный текст или оригинал если исправление не нужно

    Raises:
        ValueError: If direction is invalid

    """
    if not text or not isinstance(text, str):
        return text or ""

    valid_directions = {"auto", "en_to_ru", "ru_to_en"}
    if direction not in valid_directions:
        raise ValueError(f"direction must be one of {valid_directions}")

    # Автоопределение направления
    if direction == "auto":
        if looks_like_wrong_layout(text):
            direction = "en_to_ru"
        else:
            return text  # Не похоже на неправильную раскладку

    # Конвертация
    mapping = EN_TO_RU if direction == "en_to_ru" else RU_TO_EN

    result = []
    for char in text:
        result.append(mapping.get(char, char))

    return "".join(result)


def maybe_fix_query(query: str) -> tuple[str, bool]:
    """Пытается исправить запрос если он в неправильной раскладке.

    Returns:
        (исправленный_текст, был_исправлен)

    """
    if looks_like_wrong_layout(query):
        fixed = fix_layout(query, "en_to_ru")
        return fixed, True
    return query, False


def get_layout_hint(original: str, fixed: str) -> str:
    """Создаёт подсказку о исправлении раскладки для промпта."""
    return (
        f'NOTE: Input "{original}" appears to be typed in wrong keyboard layout.\n'
        f'Converted to Russian: "{fixed}"\n'
        f"Please interpret the converted text."
    )
