"""КС ИНН/СНИЛС — без Presidio, чтобы гонять на Mac."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "presidio"))

from ru_pdn.checksums import (
    inn10_complete,
    inn10_valid,
    inn12_complete,
    inn12_valid,
    inn_valid,
    passport_digits_plausible,
    snils_complete,
    snils_valid,
)


class TestInn(unittest.TestCase):
    def test_roundtrip_10(self):
        inn = inn10_complete("783000229")
        self.assertEqual(len(inn), 10)
        self.assertTrue(inn10_valid(inn))
        self.assertTrue(inn_valid(inn))
        # ломаем контрольную
        broken = inn[:9] + str((int(inn[9]) + 1) % 10)
        self.assertFalse(inn10_valid(broken))

    def test_roundtrip_12(self):
        inn = inn12_complete("5001007322")
        self.assertEqual(len(inn), 12)
        self.assertTrue(inn12_valid(inn))
        self.assertFalse(inn12_valid(inn[:11] + ("0" if inn[11] != "0" else "1")))

    def test_rejects_junk(self):
        self.assertFalse(inn_valid("0000000000"))
        self.assertFalse(inn_valid("1234567890"))  # почти наверняка без КС
        self.assertFalse(inn_valid("79001234567"))  # 11 цифр — не ИНН


class TestSnils(unittest.TestCase):
    def test_roundtrip(self):
        digits = snils_complete("112233445")
        self.assertEqual(len(digits), 11)
        self.assertTrue(snils_valid(digits))
        broken = digits[:9] + "99"
        if broken != digits:
            self.assertFalse(snils_valid(broken))

    def test_early_issue_requires_00(self):
        self.assertTrue(snils_valid("00100199800"))
        self.assertFalse(snils_valid("00100199812"))

    def test_phone_like_usually_fails(self):
        self.assertFalse(snils_valid("79001234567"))


class TestPassport(unittest.TestCase):
    def test_ok(self):
        self.assertTrue(passport_digits_plausible("4508123456"))

    def test_rejects_zeros(self):
        self.assertFalse(passport_digits_plausible("0000000000"))
        self.assertFalse(passport_digits_plausible("0012000000"))


if __name__ == "__main__":
    unittest.main()
