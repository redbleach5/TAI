"""Keyboard Layout Fixer - исправление текста набранного в неправильной раскладке.

Полезно когда пользователь забыл переключить раскладку:
- "ghbdtn" -> "привет"
- "cjplf" -> "создай"
"""


# Таблица соответствия EN -> RU
EN_TO_RU = {
    'q': 'й', 'w': 'ц', 'e': 'у', 'r': 'к', 't': 'е', 'y': 'н',
    'u': 'г', 'i': 'ш', 'o': 'щ', 'p': 'з', '[': 'х', ']': 'ъ',
    'a': 'ф', 's': 'ы', 'd': 'в', 'f': 'а', 'g': 'п', 'h': 'р',
    'j': 'о', 'k': 'л', 'l': 'д', ';': 'ж', "'": 'э',
    'z': 'я', 'x': 'ч', 'c': 'с', 'v': 'м', 'b': 'и', 'n': 'т',
    'm': 'ь', ',': 'б', '.': 'ю', '/': '.',
    '`': 'ё', '~': 'Ё',
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
}


def looks_like_wrong_layout(text: str) -> bool:
    """Проверяет, похож ли текст на набранный в неправильной раскладке.
    
    Эвристика: если текст состоит из латинских букв, но не похож
    на английские слова - вероятно это русский в EN раскладке.
    """
    if not text:
        return False
    
    text = text.strip().lower()
    
    # Если есть русские буквы - раскладка правильная
    if any('\u0400' <= c <= '\u04ff' for c in text):
        return False
    
    # Если только ASCII буквы
    if not all(c.isascii() for c in text):
        return False
    
    # Проверяем известные паттерны
    if text in COMMON_PATTERNS:
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
    
    # 4+ согласных подряд очень необычно для английского
    if max_streak >= 4 and len(text) > 3:
        return True
    
    return False


def fix_layout(text: str, direction: str = "auto") -> str:
    """Исправляет раскладку клавиатуры.
    
    Args:
        text: Текст для исправления
        direction: "en_to_ru", "ru_to_en", или "auto"
    
    Returns:
        Исправленный текст или оригинал если исправление не нужно
    """
    if not text:
        return text
    
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
        f'Please interpret the converted text.'
    )
