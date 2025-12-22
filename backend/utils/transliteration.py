"""
Macedonian Latin-Cyrillic Transliteration Utilities

Provides bidirectional search support for Macedonian text,
allowing users to search using either Latin or Cyrillic characters.
"""


def latin_to_cyrillic(text: str) -> str:
    """
    Convert Latin transliteration to Macedonian Cyrillic.
    Used for searching Cyrillic names with Latin input.

    Examples:
        - "Bitola" -> "Битола"
        - "Skopje" -> "Скопје"
        - "alkaloid" -> "алкалоид"
    """
    # Multi-character mappings must be processed first
    latin_to_macedonian = {
        'dzh': 'џ', 'Dzh': 'Џ', 'DZH': 'Џ',
        'gj': 'ѓ', 'Gj': 'Ѓ', 'GJ': 'Ѓ',
        'kj': 'ќ', 'Kj': 'Ќ', 'KJ': 'Ќ',
        'lj': 'љ', 'Lj': 'Љ', 'LJ': 'Љ',
        'nj': 'њ', 'Nj': 'Њ', 'NJ': 'Њ',
        'dz': 'ѕ', 'Dz': 'Ѕ', 'DZ': 'Ѕ',
        'zh': 'ж', 'Zh': 'Ж', 'ZH': 'Ж',
        'ch': 'ч', 'Ch': 'Ч', 'CH': 'Ч',
        'sh': 'ш', 'Sh': 'Ш', 'SH': 'Ш',
    }

    # Single character mappings
    single_char = {
        'a': 'а', 'b': 'б', 'v': 'в', 'g': 'г', 'd': 'д', 'e': 'е',
        'z': 'з', 'i': 'и', 'j': 'ј', 'k': 'к', 'l': 'л', 'm': 'м',
        'n': 'н', 'o': 'о', 'p': 'п', 'r': 'р', 's': 'с', 't': 'т',
        'u': 'у', 'f': 'ф', 'h': 'х', 'c': 'ц',
        'A': 'А', 'B': 'Б', 'V': 'В', 'G': 'Г', 'D': 'Д', 'E': 'Е',
        'Z': 'З', 'I': 'И', 'J': 'Ј', 'K': 'К', 'L': 'Л', 'M': 'М',
        'N': 'Н', 'O': 'О', 'P': 'П', 'R': 'Р', 'S': 'С', 'T': 'Т',
        'U': 'У', 'F': 'Ф', 'H': 'Х', 'C': 'Ц'
    }

    # Process multi-character combinations first
    result = text
    for latin, cyrillic in latin_to_macedonian.items():
        result = result.replace(latin, cyrillic)

    # Then process single characters
    output = ''
    for char in result:
        output += single_char.get(char, char)

    return output


def has_cyrillic(text: str) -> bool:
    """Check if text contains any Cyrillic characters."""
    return any('\u0400' <= c <= '\u04FF' for c in text)


def get_search_variants(search_term: str) -> list[str]:
    """
    Get all search variants for a term (both Latin and Cyrillic).

    Returns:
        List of search patterns to use in ILIKE queries.
        For Cyrillic input: returns just the original.
        For Latin input: returns both original and Cyrillic conversion.
    """
    if not search_term:
        return []

    if has_cyrillic(search_term):
        # Already Cyrillic, return as-is
        return [search_term]
    else:
        # Latin input - return both original and Cyrillic version
        cyrillic = latin_to_cyrillic(search_term)
        if cyrillic != search_term:
            return [search_term, cyrillic]
        return [search_term]


def build_bilingual_search_pattern(search_term: str) -> str:
    """
    Build a combined search pattern for SQL ILIKE with ~ regex.

    For use with PostgreSQL regex: column ~* 'pattern1|pattern2'

    Returns:
        Regex pattern string that matches either Latin or Cyrillic variant.
    """
    variants = get_search_variants(search_term)
    if len(variants) == 1:
        return variants[0]
    return '|'.join(variants)
