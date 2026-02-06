"""Tests for keyboard_layout — pure layout detection and fixing, zero mocks."""

import pytest

from src.infrastructure.services.keyboard_layout import (
    fix_layout,
    get_layout_hint,
    looks_like_wrong_layout,
    maybe_fix_query,
)


class TestLooksLikeWrongLayout:
    """Detect wrong keyboard layout (EN typed instead of RU)."""

    def test_common_patterns(self):
        assert looks_like_wrong_layout("ghbdtn") is True  # привет
        assert looks_like_wrong_layout("cjplfq") is True  # создай
        assert looks_like_wrong_layout("yfgbib") is True  # напиши

    def test_russian_text_not_wrong(self):
        assert looks_like_wrong_layout("привет") is False
        assert looks_like_wrong_layout("создай функцию") is False

    def test_english_text_not_wrong(self):
        assert looks_like_wrong_layout("hello world") is False
        assert looks_like_wrong_layout("python code") is False
        assert looks_like_wrong_layout("test function") is False

    def test_short_text_skipped(self):
        assert looks_like_wrong_layout("hi") is False
        assert looks_like_wrong_layout("ab") is False

    def test_empty_and_none(self):
        assert looks_like_wrong_layout("") is False
        assert looks_like_wrong_layout(None) is False  # type: ignore[arg-type]

    def test_digits_not_wrong(self):
        assert looks_like_wrong_layout("12345") is False

    def test_whitelist_prevents_false_positive(self):
        # English tech terms should not be detected
        assert looks_like_wrong_layout("json") is False
        assert looks_like_wrong_layout("api") is False
        assert looks_like_wrong_layout("git") is False
        assert looks_like_wrong_layout("async") is False
        assert looks_like_wrong_layout("python") is False

    def test_consonant_streak_detection(self):
        # 5+ consonants in a row is suspicious
        assert looks_like_wrong_layout("bcdfghjkl") is True

    def test_suspicious_char_ratio(self):
        # High ratio of j, b, n, f, g, h, p, x
        assert looks_like_wrong_layout("jbnfgh") is True


class TestFixLayout:
    """fix_layout: convert between EN and RU layouts."""

    def test_en_to_ru_known(self):
        result = fix_layout("ghbdtn", direction="en_to_ru")
        assert result == "привет"

    def test_en_to_ru_code(self):
        result = fix_layout("rjl", direction="en_to_ru")
        assert result == "код"

    def test_auto_fixes_wrong_layout(self):
        result = fix_layout("ghbdtn", direction="auto")
        assert result == "привет"

    def test_auto_leaves_english(self):
        result = fix_layout("hello", direction="auto")
        assert result == "hello"

    def test_empty_string(self):
        assert fix_layout("") == ""

    def test_none_returns_empty(self):
        assert fix_layout(None) == ""  # type: ignore[arg-type]

    def test_invalid_direction_raises(self):
        with pytest.raises(ValueError, match="direction must be"):
            fix_layout("test", direction="invalid")

    def test_preserves_unknown_chars(self):
        result = fix_layout("123", direction="en_to_ru")
        assert result == "123"


class TestMaybeFixQuery:
    """maybe_fix_query: attempt auto-fix, report if fixed."""

    def test_fixes_wrong_layout(self):
        fixed, was_fixed = maybe_fix_query("ghbdtn")
        assert was_fixed is True
        assert fixed == "привет"

    def test_leaves_correct_text(self):
        fixed, was_fixed = maybe_fix_query("hello world")
        assert was_fixed is False
        assert fixed == "hello world"

    def test_leaves_russian(self):
        fixed, was_fixed = maybe_fix_query("привет")
        assert was_fixed is False
        assert fixed == "привет"


class TestGetLayoutHint:
    """get_layout_hint: format hint for prompt."""

    def test_contains_both_texts(self):
        hint = get_layout_hint("ghbdtn", "привет")
        assert "ghbdtn" in hint
        assert "привет" in hint

    def test_contains_note(self):
        hint = get_layout_hint("abc", "фис")
        assert "wrong keyboard layout" in hint
