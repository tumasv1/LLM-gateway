"""Живой прогон Analyzer (нужен контейнер). На Mac без образа — skip."""
from __future__ import annotations

import os
import unittest
import urllib.error
import urllib.request
import json

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "presidio"))
from ru_pdn.checksums import inn10_complete, inn12_complete, snils_complete

ANALYZER = os.environ.get("PRESIDIO_ANALYZER_URL", "http://127.0.0.1:3000")


def _analyze(text: str) -> list[dict]:
    req = urllib.request.Request(
        f"{ANALYZER}/analyze",
        data=json.dumps({"text": text, "language": "en"}).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode())


def _types(text: str) -> set[str]:
    return {hit["entity_type"] for hit in _analyze(text)}


class TestRuAnalyzerLive(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            urllib.request.urlopen(f"{ANALYZER}/health", timeout=3)
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            raise unittest.SkipTest(f"analyzer недоступен: {exc}") from exc

    def test_inn_snils_passport_fio(self):
        inn10 = inn10_complete("783000229")
        inn12 = inn12_complete("5001007322")
        snils = snils_complete("112233445")
        snils_fmt = f"{snils[:3]}-{snils[3:6]}-{snils[6:9]} {snils[9:]}"
        text = (
            f"ФИО Иван Петрович Сидоров, ИНН {inn10} / {inn12}, "
            f"СНИЛС {snils_fmt}, паспорт 45 08 123456"
        )
        types = _types(text)
        self.assertIn("PERSON", types)
        self.assertIn("INN_RU", types)
        self.assertIn("SNILS_RU", types)
        self.assertIn("PASSPORT_RF", types)

    def test_no_false_positives_on_prose(self):
        text = (
            "Российская Федерация, Министерство образования. "
            "Заказ 1234567890, телефон 79001234567, счёт 40817810099910004312."
        )
        types = _types(text)
        self.assertNotIn("INN_RU", types)
        self.assertNotIn("SNILS_RU", types)
        self.assertNotIn("PASSPORT_RF", types)
        self.assertNotIn("PERSON", types)

    def test_two_word_name_needs_context(self):
        self.assertNotIn("PERSON", _types("Вчера Иван Иванов ходил в магазин."))
        self.assertIn("PERSON", _types("Клиента зовут Иван Иванов"))


if __name__ == "__main__":
    unittest.main()
