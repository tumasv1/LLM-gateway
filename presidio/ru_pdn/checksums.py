"""Контрольные суммы российских идентификаторов (публичные алгоритмы ФНС/ПФР).

Чистые функции без Presidio — так их можно гонять pytest-ом даже без образа.
"""
from __future__ import annotations


def only_digits(text: str) -> str:
    return "".join(ch for ch in text if ch.isdigit())


def inn10_valid(digits: str) -> bool:
    """ИНН юрлица: 10 цифр, одна контрольная."""
    if len(digits) != 10 or not digits.isdigit() or digits == "0" * 10:
        return False
    weights = (2, 4, 10, 3, 5, 9, 4, 6, 8)
    total = sum(int(digits[i]) * weights[i] for i in range(9))
    return (total % 11 % 10) == int(digits[9])


def inn12_valid(digits: str) -> bool:
    """ИНН физлица/ИП: 12 цифр, две контрольные."""
    if len(digits) != 12 or not digits.isdigit() or digits == "0" * 12:
        return False
    w11 = (7, 2, 4, 10, 3, 5, 9, 4, 6, 8)
    w12 = (3, 7, 2, 4, 10, 3, 5, 9, 4, 6, 8)
    n11 = sum(int(digits[i]) * w11[i] for i in range(10)) % 11 % 10
    n12 = sum(int(digits[i]) * w12[i] for i in range(11)) % 11 % 10
    return n11 == int(digits[10]) and n12 == int(digits[11])


def inn_valid(digits: str) -> bool:
    if len(digits) == 10:
        return inn10_valid(digits)
    if len(digits) == 12:
        return inn12_valid(digits)
    return False


def inn10_complete(body9: str) -> str:
    if len(body9) != 9 or not body9.isdigit():
        raise ValueError("нужно ровно 9 цифр")
    weights = (2, 4, 10, 3, 5, 9, 4, 6, 8)
    n10 = sum(int(body9[i]) * weights[i] for i in range(9)) % 11 % 10
    return body9 + str(n10)


def inn12_complete(body10: str) -> str:
    if len(body10) != 10 or not body10.isdigit():
        raise ValueError("нужно ровно 10 цифр")
    w11 = (7, 2, 4, 10, 3, 5, 9, 4, 6, 8)
    w12 = (3, 7, 2, 4, 10, 3, 5, 9, 4, 6, 8)
    n11 = sum(int(body10[i]) * w11[i] for i in range(10)) % 11 % 10
    body11 = body10 + str(n11)
    n12 = sum(int(body11[i]) * w12[i] for i in range(11)) % 11 % 10
    return body11 + str(n12)


def snils_valid(digits: str) -> bool:
    """СНИЛС: 11 цифр, контрольная пара по правилам ПФР (включая ранние номера)."""
    if len(digits) != 11 or not digits.isdigit() or digits == "0" * 11:
        return False
    number = int(digits[:9])
    checksum = int(digits[9:11])
    # номера ≤ 001-001-998 выпускались без расчёта КС — всегда 00
    if number <= 1_001_998:
        return checksum == 0
    total = sum(int(digits[i]) * (9 - i) for i in range(9))
    if total < 100:
        expected = total
    elif total in (100, 101):
        expected = 0
    else:
        expected = total % 101
        if expected in (100, 101):
            expected = 0
    return checksum == expected


def snils_complete(body9: str) -> str:
    if len(body9) != 9 or not body9.isdigit():
        raise ValueError("нужно ровно 9 цифр")
    number = int(body9)
    if number <= 1_001_998:
        chk = 0
    else:
        total = sum(int(body9[i]) * (9 - i) for i in range(9))
        if total < 100:
            chk = total
        elif total in (100, 101):
            chk = 0
        else:
            chk = total % 101
            if chk in (100, 101):
                chk = 0
    return body9 + f"{chk:02d}"


def passport_digits_plausible(digits: str) -> bool:
    """Паспорт РФ: 4 (серия) + 6 (номер). КС нет — только грубый sanity-check."""
    if len(digits) != 10 or not digits.isdigit():
        return False
    if digits == "0" * 10:
        return False
    series_region = int(digits[:2])
    number = int(digits[4:])
    # 00 как регион не бывает; номер 000000 — мусор
    return series_region >= 1 and number >= 1
