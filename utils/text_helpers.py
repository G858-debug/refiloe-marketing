"""Text helper utilities for content processing."""

# Words to avoid in generated content (not suitable for target audience)
BANNED_WORDS = [
    'gnaw', 'gnaws', 'gnawing', 'gnawed',
]

# Replacements for banned words (maps lowercase banned word to replacement)
WORD_REPLACEMENTS = {
    'gnaw': 'eat away',
    'gnaws': 'eats away',
    'gnawing': 'eating away',
    'gnawed': 'ate away',
}


def filter_banned_words(text: str) -> str:
    """Remove or replace banned words from text.

    Args:
        text: Input text to filter

    Returns:
        Filtered text with banned words replaced
    """
    if not text:
        return text

    result = text

    # Replace each banned word (case-insensitive)
    for banned, replacement in WORD_REPLACEMENTS.items():
        # Handle different cases
        import re
        # Replace lowercase
        result = re.sub(rf'\b{banned}\b', replacement, result, flags=re.IGNORECASE)

    return result


def add_banned_words(words: list) -> None:
    """Add additional words to the banned list.

    Args:
        words: List of words to ban
    """
    global BANNED_WORDS
    BANNED_WORDS.extend(words)
