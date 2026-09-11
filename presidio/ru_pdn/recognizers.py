"""Кастомные Presidio recognizers: ИНН, СНИЛС, паспорт РФ, ФИО.

LiteLLM v1.100.0 шлёт в Analyzer language=en, даже если текст русский.
spaCy-en русские ФИО не видит — ловим паттернами. ИНН/СНИЛС — только с КС,
чтобы не маскировать телефоны и номера заказов.
"""
from __future__ import annotations

import re

from presidio_analyzer import Pattern, PatternRecognizer, RecognizerResult

from ru_pdn.checksums import (
    inn_valid,
    only_digits,
    passport_digits_plausible,
    snils_valid,
)

INN_CONTEXT = ["инн", "inn", "налогоплател", "идентификационн"]
SNILS_CONTEXT = ["снилс", "snils", "пенсион", "страх"]
PASSPORT_CONTEXT = ["паспорт", "паспорта", "серия", "выдан", "удостоверен"]
FIO_CONTEXT = [
    "фио",
    "зовут",
    "фамилия",
    "имя",
    "отчество",
    "гражданин",
    "гражданка",
    "заявител",
    "клиент",
    "студент",
    "паспорт",
]

_PATRONYMIC = re.compile(
    r"(?:ович|евич|ич|овна|евна|ична|ычна|ьич)\b", re.IGNORECASE
)


def _window(text: str, start: int, end: int, size: int = 48) -> str:
    return text[max(0, start - size) : min(len(text), end + size)].lower()


def _has_any(haystack: str, needles: list[str]) -> bool:
    return any(n in haystack for n in needles)


class RuInnRecognizer(PatternRecognizer):
    """ИНН 10/12. Без валидной КС кандидат выкидываем."""

    def __init__(self, supported_language: str = "en"):
        patterns = [
            Pattern("inn12", r"(?<!\d)\d{12}(?!\d)", 0.4),
            Pattern("inn10", r"(?<!\d)\d{10}(?!\d)", 0.3),
        ]
        super().__init__(
            supported_entity="INN_RU",
            patterns=patterns,
            context=INN_CONTEXT,
            supported_language=supported_language,
            name=f"RuInnRecognizer_{supported_language}",
        )

    def validate_result(self, pattern_text: str):
        return True if inn_valid(only_digits(pattern_text)) else False


class RuSnilsRecognizer(PatternRecognizer):
    """СНИЛС XXX-XXX-XXX YY или 11 цифр. КС обязательна."""

    def __init__(self, supported_language: str = "en"):
        patterns = [
            Pattern("snils_fmt", r"\b\d{3}-\d{3}-\d{3}[ \u00a0]?\d{2}\b", 0.6),
            Pattern("snils_bare", r"(?<!\d)\d{11}(?!\d)", 0.2),
        ]
        super().__init__(
            supported_entity="SNILS_RU",
            patterns=patterns,
            context=SNILS_CONTEXT,
            supported_language=supported_language,
            name=f"RuSnilsRecognizer_{supported_language}",
        )

    def validate_result(self, pattern_text: str):
        return True if snils_valid(only_digits(pattern_text)) else False


class RuPassportRecognizer(PatternRecognizer):
    """Паспорт: 4 (серия) + 6 (номер). КС нет — только рядом со словом «паспорт»/«серия»."""

    def __init__(self, supported_language: str = "en"):
        patterns = [
            Pattern("passport_spaced", r"\b\d{2}\s\d{2}\s\d{6}\b", 0.6),
            Pattern("passport_series_num", r"\b\d{4}\s\d{6}\b", 0.55),
            Pattern("passport_compact", r"(?<!\d)\d{10}(?!\d)", 0.2),
        ]
        super().__init__(
            supported_entity="PASSPORT_RF",
            patterns=patterns,
            context=PASSPORT_CONTEXT,
            supported_language=supported_language,
            name=f"RuPassportRecognizer_{supported_language}",
        )

    def validate_result(self, pattern_text: str):
        return True if passport_digits_plausible(only_digits(pattern_text)) else False

    def analyze(self, text, entities, nlp_artifacts=None):
        results = super().analyze(text, entities, nlp_artifacts)
        kept: list[RecognizerResult] = []
        for item in results:
            if _has_any(_window(text, item.start, item.end), PASSPORT_CONTEXT):
                kept.append(item)
        return kept


class RuFioRecognizer(PatternRecognizer):
    """Русские ФИО без spaCy-ru (запрос к Analyzer идёт как en).

    Берём тройку с отчеством всегда; два/три слова — только с контекстом
    («фио», «зовут», …). Иначе замаскируется «Российская Федерация».
    """

    def __init__(self, supported_language: str = "en"):
        name = r"[А-ЯЁ][а-яё]{1,30}(?:-[А-ЯЁ][а-яё]{1,30})?"
        patronymic = (
            r"[А-ЯЁ][а-яё]{1,20}(?:ович|евич|ич|овна|евна|ична|ычна|ьич)"
        )
        patterns = [
            Pattern(
                "fio_patronymic",
                rf"\b{name}\s+{name}\s+{patronymic}\b",
                0.9,
            ),
            Pattern(
                "fio_two_or_three",
                rf"\b{name}\s+{name}(?:\s+{name})?\b",
                0.35,
            ),
        ]
        super().__init__(
            supported_entity="PERSON",
            patterns=patterns,
            context=FIO_CONTEXT,
            supported_language=supported_language,
            name=f"RuFioRecognizer_{supported_language}",
        )

    def analyze(self, text, entities, nlp_artifacts=None):
        results = super().analyze(text, entities, nlp_artifacts)
        kept: list[RecognizerResult] = []
        for item in results:
            span = text[item.start : item.end]
            if _PATRONYMIC.search(span):
                kept.append(item)
                continue
            if _has_any(_window(text, item.start, item.end), FIO_CONTEXT):
                kept.append(item)
        return kept


def register_ru_recognizers(engine) -> None:
    """Повесить RU-recognizers на language=en — так их видит LiteLLM."""
    registry = engine.registry
    existing = {r.name for r in registry.recognizers}
    for cls in (
        RuInnRecognizer,
        RuSnilsRecognizer,
        RuPassportRecognizer,
        RuFioRecognizer,
    ):
        rec = cls(supported_language="en")
        if rec.name not in existing:
            registry.add_recognizer(rec)
            existing.add(rec.name)
