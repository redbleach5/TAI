"""Tests for Keyboard Layout Fixer."""

from src.infrastructure.services.keyboard_layout import (
    EN_TO_RU,
    RU_TO_EN,
    COMMON_PATTERNS,
    looks_like_wrong_layout,
    fix_layout,
    maybe_fix_query,
    get_layout_hint,
)


class TestEnToRuMapping:
    """Tests for EN to RU character mapping."""

    def test_basic_letters(self):
        """Basic letter mappings should be correct."""
        assert EN_TO_RU["q"] == "й"
        assert EN_TO_RU["w"] == "ц"
        assert EN_TO_RU["e"] == "у"
        assert EN_TO_RU["a"] == "ф"
        assert EN_TO_RU["s"] == "ы"

    def test_uppercase_letters(self):
        """Uppercase letters should be mapped."""
        assert EN_TO_RU["Q"] == "Й"
        assert EN_TO_RU["A"] == "Ф"

    def test_ru_to_en_reverse(self):
        """RU to EN should be reverse of EN to RU."""
        assert RU_TO_EN["й"] == "q"
        assert RU_TO_EN["ц"] == "w"


class TestLooksLikeWrongLayout:
    """Tests for looks_like_wrong_layout function."""

    def test_common_patterns(self):
        """Common patterns should be detected."""
        assert looks_like_wrong_layout("ghbdtn") is True  # привет
        assert looks_like_wrong_layout("cjplfq") is True   # создай
        assert looks_like_wrong_layout("ntcn") is True    # тест

    def test_russian_text_not_detected(self):
        """Russian text should not be flagged."""
        assert looks_like_wrong_layout("привет") is False
        assert looks_like_wrong_layout("создай код") is False

    def test_normal_english(self):
        """Normal English should not be detected."""
        assert looks_like_wrong_layout("hello") is False
        assert looks_like_wrong_layout("create function") is False

    def test_empty_string(self):
        """Empty string should return False."""
        assert looks_like_wrong_layout("") is False

    def test_consonant_streak_heuristic(self):
        """Long consonant streaks should be detected."""
        # Russian "программа" in EN layout has many consonants
        assert looks_like_wrong_layout("ghjuhfvvf") is True

    def test_mixed_text(self):
        """Mixed text with Russian should not be flagged."""
        assert looks_like_wrong_layout("hello привет") is False


class TestFixLayout:
    """Tests for fix_layout function."""

    def test_en_to_ru_conversion(self):
        """EN to RU conversion should work."""
        assert fix_layout("ghbdtn", "en_to_ru") == "привет"
        assert fix_layout("cjplfq", "en_to_ru") == "создай"

    def test_ru_to_en_conversion(self):
        """RU to EN conversion should work."""
        assert fix_layout("привет", "ru_to_en") == "ghbdtn"

    def test_auto_detection(self):
        """Auto detection should work for wrong layout."""
        assert fix_layout("ghbdtn", "auto") == "привет"
        # Normal text should not be changed
        assert fix_layout("hello", "auto") == "hello"

    def test_preserves_spaces(self):
        """Spaces should be preserved."""
        assert fix_layout("ghbdtn vbh", "en_to_ru") == "привет мир"

    def test_preserves_numbers(self):
        """Numbers should be preserved."""
        assert fix_layout("ghbdtn123", "en_to_ru") == "привет123"

    def test_empty_string(self):
        """Empty string should return empty."""
        assert fix_layout("", "auto") == ""


class TestMaybeFixQuery:
    """Tests for maybe_fix_query function."""

    def test_fixes_wrong_layout(self):
        """Should fix text in wrong layout."""
        fixed, was_fixed = maybe_fix_query("ghbdtn")
        assert fixed == "привет"
        assert was_fixed is True

    def test_leaves_correct_text(self):
        """Should not modify correct text."""
        fixed, was_fixed = maybe_fix_query("hello")
        assert fixed == "hello"
        assert was_fixed is False

    def test_leaves_russian_text(self):
        """Should not modify Russian text."""
        fixed, was_fixed = maybe_fix_query("привет")
        assert fixed == "привет"
        assert was_fixed is False


class TestGetLayoutHint:
    """Tests for get_layout_hint function."""

    def test_generates_hint(self):
        """Should generate layout hint."""
        hint = get_layout_hint("ghbdtn", "привет")
        assert "ghbdtn" in hint
        assert "привет" in hint
        assert "wrong keyboard layout" in hint.lower()


class TestCommonPatterns:
    """Tests for common pattern recognition."""

    def test_all_common_patterns_convert_correctly(self):
        """All common patterns should convert to expected Russian."""
        for en_pattern, ru_expected in COMMON_PATTERNS.items():
            fixed = fix_layout(en_pattern, "en_to_ru")
            assert fixed == ru_expected, f"{en_pattern} -> {fixed} != {ru_expected}"
