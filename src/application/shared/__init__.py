"""Shared application-layer utilities."""

from src.application.shared.llm_fallback import generate_with_fallback, stream_with_fallback

__all__ = ["generate_with_fallback", "stream_with_fallback"]
