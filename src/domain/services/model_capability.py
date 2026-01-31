"""Universal model capability scoring for Ollama and LM Studio.

Uses parameter size when available (Ollama details.parameter_size), else parses from name.
Higher score = more capable model.
"""

import re

# Regex: 4.3B, 7b, 8B, 13b, 20B, 70b, 72B
_PARAM_PATTERN = re.compile(r"(\d+(?:\.\d+)?)\s*[bB]\b")
# Millions: 137M (embeddings)
_PARAM_M_PATTERN = re.compile(r"(\d+(?:\.\d+)?)\s*[mM]\b")


def parse_capability_from_param_size(param_size: str) -> float:
    """Parse capability from Ollama details.parameter_size (e.g. '4.3B', '7B', '137M').

    Returns billions as float. M = millions (0.137B). Unknown format -> 0.
    """
    if not param_size or not isinstance(param_size, str):
        return 0.0
    s = param_size.strip()
    m = _PARAM_PATTERN.search(s)
    if m:
        try:
            return float(m.group(1))
        except ValueError:
            pass
    m = _PARAM_M_PATTERN.search(s)
    if m:
        try:
            return float(m.group(1)) / 1000  # 137M -> 0.137B
        except ValueError:
            pass
    return 0.0


def parse_capability_from_name(name: str) -> float:
    """Parse capability from model name when API doesn't provide parameter_size.

    Matches: qwen2.5-coder:7b, llama3.2:3b, gpt-oss:20b, mistral-7b, phi-3-mini.
    Returns billions as float. Unknown -> 5.0 (middle tier).
    """
    if not name or not isinstance(name, str):
        return 5.0
    m = _PARAM_PATTERN.search(name)
    if m:
        try:
            return float(m.group(1))
        except ValueError:
            pass
    return 5.0


def compute_capability(name: str, param_size: str | None = None) -> float:
    """Compute capability score. Prefer param_size when available (Ollama)."""
    if param_size:
        score = parse_capability_from_param_size(param_size)
        if score > 0:
            return score
    return parse_capability_from_name(name)
