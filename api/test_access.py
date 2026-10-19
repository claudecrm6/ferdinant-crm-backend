"""
Testga kirish uchun majburiy to'lov tekshiruvi (BACKEND).

Qoidalar:
- Oraliq test  : o'quvchining joriy oy uchun barcha to'lov majburiyatlari bajarilgan
                 va qarzi 0 bo'lishi shart.
- Yakuniy test : yuqoridagilarga qo'shimcha ravishda ikkinchi to'lov ham amalga
                 oshirilgan va to'liq yopilgan bo'lishi shart.
- Turi tanlanmagan test (test_type="") oraliq qoidasi bo'yicha tekshiriladi.

Tekshiruv faqat Student maydonlariga (paid_amount/debt_amount) tayanmaydi: ular
frontend tomonidan yoziladi. Haqiqiy holat Payment yozuvlari bilan solishtiriladi.
"""
from django.core import signing
from django.utils import timezone

from .models import Payment

MONTHS_UZ = [
    "Yanvar", "Fevral", "Mart", "Aprel", "May", "Iyun",
    "Iyul", "Avgust", "Sentyabr", "Oktyabr", "Noyabr", "Dekabr",
]

TEST_TYPE_ORALIQ = "oraliq"
TEST_TYPE_YAKUNIY = "yakuniy"
VALID_TEST_TYPES = ("", TEST_TYPE_ORALIQ, TEST_TYPE_YAKUNIY)

ACCESS_TOKEN_SALT = "quiz-access"
ACCESS_TOKEN_MAX_AGE = 2 * 60 * 60  # 2 soat


def _fmt(n):
    return f"{int(n):,}".replace(",", " ")


def evaluate_access(student, test_type):
    """
    O'quvchining testga kirish huquqini tekshiradi.

    Qaytaradi: dict(allowed, code, message, details)
    """
    test_type = test_type or ""
    now = timezone.localtime()
    month_name = MONTHS_UZ[now.month - 1]
    year = now.year

    obligation = int(student.original_debt or 0)
    payments = list(
        Payment.objects.filter(student=student, month=month_name, year=year).order_by("id")
    )
    paid_real = int(sum(p.amount for p in payments))
    debt_real = max(0, obligation - paid_real)
    debt_stored = int(student.debt_amount or 0)
    # Qaysi biri katta bo'lsa, o'sha qarz hisoblanadi (ma'lumotlar bir-biriga
    # mos kelmasa ham, to'lanmagan summa ko'rinib turadi).
    debt = max(debt_real, debt_stored)

    details = {
        "student": student.name,
        "month": month_name,
        "year": year,
        "required_amount": obligation,
        "paid_amount": paid_real,
        "debt_amount": debt,
        "payments_count": len(payments),
        "test_type": test_type,
    }

    def deny(code, message):
        return {"allowed": False, "code": code, "message": message, "details": details}

    # --- Oraliq qoidasi (barcha test turlari uchun asos) ---
    if debt > 0:
        if test_type == TEST_TYPE_YAKUNIY:
            if len(payments) <= 1:
                return deny(
                    "second_payment_required",
                    f"Yakuniy testga kirish uchun {month_name} oyi bo'yicha ikkinchi to'lov "
                    f"amalga oshirilib, to'liq yopilishi shart. Hozircha {len(payments)} ta to'lov "
                    f"qilingan ({_fmt(paid_real)} so'm), qolgan qarz: {_fmt(debt)} so'm.",
                )
            return deny(
                "second_payment_incomplete",
                f"Yakuniy testga kirish uchun ikkinchi to'lov to'liq bo'lishi shart. "
                f"{month_name} oyi bo'yicha to'langan: {_fmt(paid_real)} so'm, "
                f"qolgan qarz: {_fmt(debt)} so'm.",
            )
        return deny(
            "debt_remaining",
            f"Testga kirish uchun {month_name} oyi bo'yicha barcha to'lovlar bajarilgan va "
            f"qarz 0 bo'lishi shart. To'langan: {_fmt(paid_real)} so'm, "
            f"qolgan qarz: {_fmt(debt)} so'm.",
        )

    # Qarz 0 ko'rinadi, lekin majburiyat bor va to'lov yozuvlari uni qoplamasa —
    # holat soxta/eskirgan. Bunday o'quvchi kiritilmaydi.
    if obligation > 0 and paid_real < obligation:
        return deny(
            "payment_records_mismatch",
            f"{month_name} oyi uchun to'lov yozuvlari majburiyatni qoplamaydi "
            f"(to'langan: {_fmt(paid_real)} so'm, kerak: {_fmt(obligation)} so'm). "
            "Iltimos, administrator bilan bog'laning.",
        )

    # --- Yakuniy qoidasi: ikkinchi to'lov mavjud bo'lishi shart ---
    if test_type == TEST_TYPE_YAKUNIY and len(payments) < 2:
        return deny(
            "second_payment_required",
            f"Yakuniy testga kirish uchun {month_name} oyi bo'yicha ikkinchi to'lov "
            "amalga oshirilgan bo'lishi shart. Hozircha faqat "
            f"{len(payments)} ta to'lov qayd etilgan.",
        )

    return {
        "allowed": True,
        "code": "ok",
        "message": "To'lov tasdiqlandi, testga kirish mumkin.",
        "details": details,
    }


# ===================== KIRISH TOKENI =====================
def make_access_token(student, test_type, user):
    payload = {"s": student.id, "t": test_type or "", "u": user.id if user else None}
    return signing.dumps(payload, salt=ACCESS_TOKEN_SALT)


def read_access_token(token):
    """Token to'g'ri va muddati o'tmagan bo'lsa payload, aks holda None."""
    if not token or not isinstance(token, str):
        return None
    try:
        return signing.loads(token, salt=ACCESS_TOKEN_SALT, max_age=ACCESS_TOKEN_MAX_AGE)
    except signing.BadSignature:  # SignatureExpired ham shundan meros
        return None
