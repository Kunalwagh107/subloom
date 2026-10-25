"""Small deterministic Hindi-span transliterator. Latin text is never changed.

Hindi schwa deletion and spelling have exceptions; this is editable romanization,
not a semantic translation or a claim of perfect language identification.
"""
from dataclasses import replace
import re
import unicodedata

from .subtitles import SubtitleSegment

VOWELS = dict(zip("अआइईउऊऋॠऌएऐओऔऑऍ", ["a", "aa", "i", "ee", "u", "oo", "ri", "ri", "li", "e", "ai", "o", "au", "o", "e"]))
MATRAS = dict(zip("ािीुूृॄॢेैोौॉॅ", ["aa", "i", "ee", "u", "oo", "ri", "ri", "li", "e", "ai", "o", "au", "o", "e"]))
CONSONANTS = dict(zip("कखगघङचछजझञटठडढणतथदधनपफबभमयरलवशषसहळक़ख़ग़ज़ड़ढ़फ़य़", [
    "k", "kh", "g", "gh", "ng", "ch", "chh", "j", "jh", "ny", "t", "th", "d", "dh", "n",
    "t", "th", "d", "dh", "n", "p", "ph", "b", "bh", "m", "y", "r", "l", "v", "sh", "sh", "s", "h", "l",
    "q", "kh", "gh", "z", "r", "rh", "f", "y"]))
# Common readable spellings and schwa exceptions. General conversion remains functional for unseen words.
COMMON = {"आज": "aaj", "हम": "hum", "समझेंगे": "samjhenge", "है": "hai", "हैं": "hain", "मैं": "main",
          "में": "mein", "और": "aur", "यह": "yeh", "वह": "woh", "नहीं": "nahin", "बहुत": "bahut",
          "करना": "karna", "करते": "karte", "करेंगे": "karenge", "आप": "aap", "हिंदी": "Hindi",
          "हिन्दी": "Hindi", "नमस्ते": "namaste", "दुनिया": "duniya", "कंप्यूटर": "computer",
          "क्या": "kya", "क्यों": "kyon", "लिए": "liye", "सीखेंगे": "seekhenge", "हूँ": "hoon",
          "यहाँ": "yahaan", "यहां": "yahaan", "आपका": "aapka", "स्वागत": "swagat", "पढ़ाई": "padhaai",
          "पढ़ना": "padhna", "मशीन": "machine", "लर्निंग": "learning", "पाइथन": "Python",
          "पायथन": "Python", "कोड": "code", "नेटवर्क": "network", "नेटवर्क्स": "networks"}


def script_warning(items: list[SubtitleSegment]) -> str:
    if any(re.search(r"[\u0600-\u06ff]", item.text) for item in items):
        return ("Whisper returned Arabic/Urdu script for some speech. Roman Hindi converts Devanagari only. "
                "Select Hindi / Hinglish and try Small or Medium, or correct the text manually.")
    return ""


def _word(word: str) -> str:
    if word in COMMON:
        return COMMON[word]
    word = unicodedata.normalize("NFC", word)
    # Normalize Devanagari nukta pairs to their dedicated consonant tokens. NFC
    # intentionally decomposes these letters, so recognize the pairs explicitly.
    nukta = {"क़": "q", "ख़": "kh", "ग़": "gh", "ज़": "z", "ड़": "r", "ढ़": "rh", "फ़": "f", "य़": "y"}
    tokens: list[str] = []
    for i, char in enumerate(word):
        following = word[i + 1] if i + 1 < len(word) else ""
        if char in CONSONANTS:
            consonant = CONSONANTS[char]
            if following == "़":
                consonant = nukta.get(char + following, consonant)
                following = word[i + 2] if i + 2 < len(word) else ""
            implicit = "a" if following and following not in MATRAS and following not in {"्", "़"} else ""
            tokens.append(consonant + implicit)
        elif char in MATRAS:
            tokens.append(MATRAS[char])
        elif char in VOWELS:
            tokens.append(VOWELS[char])
        elif char in {"ं", "ँ"}:
            tokens.append("m" if following in "पबभमफ" and following else "n")
        elif char == "ः":
            tokens.append("h")
        elif char in "०१२३४५६७८९":
            tokens.append(str(ord(char) - ord("०")))
        elif char not in {"्", "़"}:
            tokens.append(char)
    text = "".join(tokens)
    # Delete an internal schwa in the common V-C-a-C-V environment, right to left.
    text = re.sub(r"([aeiou])([kgcjtdnpbmyrlvsh]+)a([kgcjtdnpbmyrlvsh]+)([aeiou])", r"\1\2\3\4", text)
    return text


def romanize(text: str) -> str:
    text = re.sub(r"[\u0900-\u0963\u0966-\u097f]+", lambda m: _word(m.group()), text)
    return text.replace("।", ".").replace("॥", ".")


def hinglish(items: list[SubtitleSegment]) -> list[SubtitleSegment]:
    return [replace(item, text=romanize(item.text)) for item in items]
