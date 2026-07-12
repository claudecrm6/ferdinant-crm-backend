"""
Qarzdorlik eslatmalarini Telegramga yuborish uchun yordamchi funksiyalar.

Alohida kutubxona (masalan `python-telegram-bot`) qo'shmaslik uchun
standart `urllib` yordamida to'g'ridan-to'g'ri Telegram Bot API'ga
so'rov yuboriladi — xuddi frontenddagi OTP/sertifikat yuborish
kodida qilingani kabi.
"""
import json
import time
import urllib.request
import urllib.error

from django.conf import settings

# Oxirgi muvaffaqiyatsiz urinishning aniq sababini saqlab turadi (masalan,
# Telegram'ning o'zi qaytargan "chat not found" yoki "bot was kicked" kabi
# xabarlari) — shu orqali admin panelida yoki loglarda haqiqiy sababni
# ko'rsatish mumkin bo'ladi.
_last_error = {"message": None}


def get_last_error():
    """Eng oxirgi yuborish xatosining Telegram'dan kelgan aniq matnini qaytaradi."""
    return _last_error["message"]


def send_telegram_message(text, chat_id=None):
    """
    Telegramga oddiy matnli xabar yuboradi.
    Xato yuz bersa, dasturni to'xtatmasdan False qaytaradi, xatoni logga
    yozadi va get_last_error() orqali olish uchun saqlab qo'yadi.
    """
    token = getattr(settings, 'TELEGRAM_BOT_TOKEN', '')
    target_chat_id = chat_id or getattr(settings, 'TELEGRAM_GROUP_CHAT_ID', '')

    if not token or not target_chat_id:
        _last_error["message"] = "BOT_TOKEN yoki CHAT_ID sozlanmagan"
        print(f"[telegram] {_last_error['message']} — xabar yuborilmadi.")
        return False

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = json.dumps({
        "chat_id": target_chat_id,
        "text": text,
        "parse_mode": "HTML",
    }).encode("utf-8")

    request = urllib.request.Request(
        url,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            response.read()
        _last_error["message"] = None
        return True
    except urllib.error.HTTPError as exc:
        # Telegram HTTP xato bilan birga JSON tanasida aniq sababni qaytaradi
        # (masalan {"ok":false,"error_code":400,"description":"Bad Request: chat not found"}).
        # Bu — eng foydali qism, shuning uchun uni o'qib, saqlab qo'yamiz.
        try:
            body = exc.read().decode("utf-8", errors="replace")
            parsed = json.loads(body)
            description = parsed.get("description", body)
        except Exception:
            description = str(exc)
        _last_error["message"] = f"Telegram xatosi ({exc.code}): {description}"
        print(f"[telegram] {_last_error['message']}")
        return False
    except urllib.error.URLError as exc:
        _last_error["message"] = f"Ulanish xatosi: {exc.reason}"
        print(f"[telegram] Xabar yuborishda xato: {exc}")
        return False


def send_to_admins(text):
    """
    Guruhga emas, faqat settings.TELEGRAM_ADMIN_CHAT_IDS ro'yxatidagi shaxsiy
    chat'larga xabar yuboradi (login/logout kabi tizim eventlari uchun).
    Ro'yxatdagi barcha chat'larga urinib ko'radi; hech bo'lmasa bittasiga
    muvaffaqiyatli yuborilsa True qaytaradi.
    """
    admin_ids = getattr(settings, 'TELEGRAM_ADMIN_CHAT_IDS', [])
    if not admin_ids:
        _last_error["message"] = "TELEGRAM_ADMIN_CHAT_IDS sozlanmagan"
        print(f"[telegram] {_last_error['message']} — xabar yuborilmadi.")
        return False

    ok = False
    for admin_chat_id in admin_ids:
        if send_telegram_message(text, chat_id=admin_chat_id):
            ok = True
    return ok

# To'lov kiritilganda xabar boradigan ALOHIDA guruh chat'i.
# Faqat to'lov eventi uchun ishlatiladi — boshqa barcha xabarlar
# (guruh/kurs/o'quvchi qo'shish, login/logout va h.k.) eskicha
# faqat TELEGRAM_ADMIN_CHAT_IDS'ga boradi (send_activity_notice orqali).
PAYMENT_GROUP_CHAT_ID = "1827066150"


def send_payment_group_notice(username, student_name, amount):
    """
    To'lov kiritilganda, faqat shu event uchun, yuqoridagi
    PAYMENT_GROUP_CHAT_ID guruhiga xabar yuboradi. Shablon
    send_activity_notice bilan bir xil, lekin manzil boshqa.
    """
    text = (
        "🔵 <b>To'lov kiritildi</b>\n\n"
        f"👤 Foydalanuvchi: <b>{username}</b>\n"
        f"🧑‍🎓 O'quvchi: {student_name}\n"
        f"💵 Summa: {format_money(amount)} so'm\n"
        f"🕒 Vaqt: {timezone_now_str()}"
    )
    return send_telegram_message(text, chat_id=PAYMENT_GROUP_CHAT_ID)

def send_activity_notice(username, title, details=""):
    """
    Saytdan foydalanish paytidagi harakatlar (guruh qo'shish, o'quvchi
    qo'shish, to'lov kiritish va h.k.) haqida shaxsiy admin chat(lar)iga
    real-time xabar yuboradi. Kim (`username`) qanday harakat (`title`)
    qilgani va qo'shimcha tafsilotlar (`details`) ko'rsatiladi.
    """
    text = f"🔵 <b>{title}</b>\n\n👤 Foydalanuvchi: <b>{username}</b>"
    if details:
        text += f"\n{details}"
    text += f"\n🕒 Vaqt: {timezone_now_str()}"
    return send_to_admins(text)


def send_user_login_notice(user, device_id="", is_trusted=False, ip_address=""):
    """
    CRM foydalanuvchisi tizimga kirganda shaxsiy admin chat(lar)iga xabar yuboradi.
    """
    device_line = f"\n📱 Qurilma: <code>{device_id}</code>" if device_id else ""
    ip_line = f"\n🌐 IP: <code>{ip_address}</code>" if ip_address else ""
    trust_line = "\n✅ Ishonchli qurilma" if is_trusted else "\n🆕 Yangi qurilma (OTP talab qilinishi mumkin)"
    text = (
        "🟢 <b>Tizimga kirish</b>\n\n"
        f"👤 Foydalanuvchi: <b>{user.username}</b>"
        f"{device_line}{ip_line}{trust_line}\n"
        f"🕒 Vaqt: {timezone_now_str()}"
    )
    return send_to_admins(text)


def send_user_logout_notice(username):
    """
    CRM foydalanuvchisi tizimdan chiqqanda shaxsiy admin chat(lar)iga xabar yuboradi.
    """
    text = (
        "🔴 <b>Tizimdan chiqish</b>\n\n"
        f"👤 Foydalanuvchi: <b>{username}</b>\n"
        f"🕒 Vaqt: {timezone_now_str()}"
    )
    return send_to_admins(text)


def send_site_enter_notice(user, device_id="", ip_address=""):
    """
    Foydalanuvchi saytni Chrome/brauzerda ochganda (token orqali avtomatik
    kirganda ham) shaxsiy admin chat(lar)iga xabar yuboradi. Bu parol bilan
    kirishdan (send_user_login_notice) farqli — har safar sayt ochilganda ishlaydi.
    """
    device_line = f"\n📱 Qurilma: <code>{device_id}</code>" if device_id else ""
    ip_line = f"\n🌐 IP: <code>{ip_address}</code>" if ip_address else ""
    text = (
        "🌐 <b>Saytga kirdi</b>\n\n"
        f"👤 Foydalanuvchi: <b>{user.username}</b>"
        f"{device_line}{ip_line}\n"
        f"🕒 Vaqt: {timezone_now_str()}"
    )
    return send_to_admins(text)


def send_site_leave_notice(username):
    """
    Foydalanuvchi brauzer/tabni yopganda yoki saytdan chiqib ketganda
    (navigator.sendBeacon orqali) shaxsiy admin chat(lar)iga xabar yuboradi.
    """
    text = (
        "🚪 <b>Saytdan chiqdi</b>\n\n"
        f"👤 Foydalanuvchi: <b>{username}</b>\n"
        f"🕒 Vaqt: {timezone_now_str()}"
    )
    return send_to_admins(text)


def timezone_now_str():
    from django.utils import timezone as _tz
    return _tz.now().strftime("%d.%m.%Y %H:%M")


MONTHS_UZ = [
    "Yanvar", "Fevral", "Mart", "Aprel", "May", "Iyun",
    "Iyul", "Avgust", "Sentyabr", "Oktyabr", "Noyabr", "Dekabr",
]


def month_name_uz(period):
    """
    "2026-07" -> "Iyul". Format noto'g'ri bo'lsa, period'ning o'zini qaytaradi.
    """
    try:
        year_str, month_str = period.split("-")
        return MONTHS_UZ[int(month_str) - 1]
    except (ValueError, IndexError, AttributeError):
        return period


def format_money(amount):
    try:
        return f"{int(amount):,}".replace(",", " ")
    except (TypeError, ValueError):
        return str(amount)


def _split_into_chunks(lines, header, max_len=3500):
    """
    Telegram xabar uzunligi cheklovidan (4096 belgi) xavfsiz masofada
    qolish uchun uzun ro'yxatlarni bir nechta xabarga bo'lib chiqadi.
    """
    chunks = []
    current = header
    for line in lines:
        candidate = current + "\n" + line
        if len(candidate) > max_len:
            chunks.append(current)
            current = header + " (davomi)\n" + line
        else:
            current = candidate
    chunks.append(current)
    return chunks


def send_general_reminder(period):
    """
    Har oyning 5-sanasida (va shundan keyin har 5 kunda) BARCHA o'quvchilarga
    umumiy to'lov eslatmasini umumiy chatga yuboradi. Bu qarzdorlar ro'yxati
    emas — barchaga qaratilgan bitta qisqa, chiroyli eslatma xabari.
    """
    month = month_name_uz(period)
    text = (
        "🔔 <b>To'lov eslatmasi</b>\n\n"
        "Salom, hurmatli o'quvchilar!\n"
        f"<b>{month}</b> oyi uchun to'lovni amalga oshirishingizni so'raymiz.\n\n"
        "Vaqtida to'lov qilganingiz uchun rahmat!"
    )
    return send_telegram_message(text)


def send_group_lesson_debtors(group, debtor_students):
    """
    Guruh darsi boshlanganda chaqiriladi: shu GURUHGA tegishli qarzdorlar
    ro'yxatini (faqat o'sha guruhdagi o'quvchilar), umumiy Telegram chatiga
    (settings.TELEGRAM_GROUP_CHAT_ID) yuboradi. Xabar sarlavhasida qaysi
    guruh ekani aniq ko'rsatiladi, shunda bitta umumiy chatda ham har bir
    guruhning qarzdorlari alohida-alohida ajralib turadi.
    """
    if not debtor_students:
        return False

    lines = [
        f"• {s.name} — <b>{format_money(s.debt_amount)} so'm</b>"
        for s in debtor_students
    ]
    header = (
        f"📚 <b>{group.name}</b> guruhi darsi boshlandi\n\n"
        f"⚠️ Qarzdorlar ro'yxati ({len(debtor_students)} ta):\n"
    )
    chunks = _split_into_chunks(lines, header)

    ok = True
    for chunk in chunks:
        if not send_telegram_message(chunk):
            ok = False
    return ok


def send_current_lesson_warnings_batched(students, message_pause_seconds=0.3):
    """
    Hozir darsi davom etayotgan guruh(lar)dagi BARCHA o'quvchilarga (qarzdorligidan
    qat'i nazar) alohida, shaxsiylashtirilgan ogohlantirish xabarini yuboradi.

    "Telegram ogohlantirish" bo'limidagi 3-tugma shu funksiyani chaqiradi:
    tugma bosilgan payt joriy vaqtga qarab darsi davom etayotgan guruhlar
    aniqlanadi (reminders.get_current_lesson_students orqali), so'ng shu
    ro'yxat shu yerga uzatiladi.

    Individual oylik qarzdorlik ogohlantirishidan farqli o'laroq, bu yerda
    guruhlar orasida 5 daqiqalik kutish YO'Q — barcha o'quvchilarga bir
    vaqtda (ketma-ket, deyarli kutilmasdan) yuboriladi, chunki bu "hozir dars
    boshlangan guruh" haqida bo'lib, xabar kechiktirilmasdan yetib borishi
    kerak. Telegramning tezlik chekloviga tegib ketmaslik uchun faqat har bir
    xabar orasida qisqa (`message_pause_seconds`) tanaffus qo'yiladi.
    """
    ok = True

    for student in students:
        group_name = student.group.name if student.group else ""
        text = (
            "⚠️ <b>Ogohlantirish</b>\n\n"
            f"Salom, hurmatli <b>{student.name}</b>!\n"
            f"Hozir <b>{group_name}</b> guruhidagi darsingiz davom etmoqda.\n\n"
            "Iltimos, to'lovlaringizni o'z vaqtida amalga oshirishni unutmang."
        )
        if not send_telegram_message(text):
            ok = False
        time.sleep(message_pause_seconds)

    return ok


def send_individual_debt_warnings_batched(
    debtor_students, period, batch_size=4, batch_pause_seconds=300, message_pause_seconds=0.5
):
    """
    15-sanadan keyin — har bir qarzdor o'quvchi uchun alohida, shaxsiylashtirilgan
    ogohlantirish xabarini umumiy chatga yuboradi.

    Telegramning tezlik cheklovlariga (rate limit) tegib ketmaslik uchun
    xabarlar 4 talik guruhlarga (batch) bo'lib yuboriladi: bitta guruh ketma-ket
    jo'natiladi, so'ng keyingi guruhga o'tishdan oldin `batch_pause_seconds`
    (standart holatda 5 daqiqa) kutiladi.

    DIQQAT: bu funksiya uzoq davom etishi mumkin (masalan 12 ta qarzdor bo'lsa,
    ~10 daqiqa), shu sababli har doim alohida fon oqimida (background thread)
    chaqirilishi kerak — asosiy scheduler tsiklini bloklab qo'ymasligi uchun.
    """
    month = month_name_uz(period)
    ok = True

    for i in range(0, len(debtor_students), batch_size):
        batch = debtor_students[i:i + batch_size]
        for student in batch:
            text = (
                "⚠️ <b>Qarzdorlik haqida ogohlantirish</b>\n\n"
                f"Salom, hurmatli <b>{student.name}</b>!\n"
                f"<b>{month}</b> oyi uchun "
                f"<b>{format_money(student.debt_amount)} so'm</b> qarzdorligingizni "
                "to'lab qo'yishingizni so'raymiz.\n\n"
                "Tushunganingiz uchun rahmat!"
            )
            if not send_telegram_message(text):
                ok = False
            time.sleep(message_pause_seconds)

        is_last_batch = (i + batch_size) >= len(debtor_students)
        if not is_last_batch:
            time.sleep(batch_pause_seconds)

    return ok

def send_document_to_admins(file_bytes, filename, caption=""):
    """
    Berilgan faylni (masalan sertifikat PDF) barcha admin chat'lariga
    hujjat sifatida yuboradi. Standart kutubxona bilan (urllib) multipart
    so'rov quriladi — qo'shimcha kutubxona (masalan requests) shart emas.
    """
    import mimetypes
    import uuid

    token = getattr(settings, 'TELEGRAM_BOT_TOKEN', '')
    admin_ids = getattr(settings, 'TELEGRAM_ADMIN_CHAT_IDS', [])

    if not token or not admin_ids:
        _last_error["message"] = "BOT_TOKEN yoki TELEGRAM_ADMIN_CHAT_IDS sozlanmagan"
        print(f"[telegram] {_last_error['message']} — hujjat yuborilmadi.")
        return False

    content_type = mimetypes.guess_type(filename)[0] or "application/octet-stream"
    boundary = uuid.uuid4().hex

    ok_any = False
    for chat_id in admin_ids:
        url = f"https://api.telegram.org/bot{token}/sendDocument"

        parts = []
        for field_name, field_value in (("chat_id", str(chat_id)), ("caption", caption)):
            parts.append(f"--{boundary}\r\n".encode())
            parts.append(f'Content-Disposition: form-data; name="{field_name}"\r\n\r\n'.encode())
            parts.append(f"{field_value}\r\n".encode())

        parts.append(f"--{boundary}\r\n".encode())
        parts.append(
            f'Content-Disposition: form-data; name="document"; filename="{filename}"\r\n'.encode()
        )
        parts.append(f"Content-Type: {content_type}\r\n\r\n".encode())
        parts.append(file_bytes)
        parts.append(b"\r\n")
        parts.append(f"--{boundary}--\r\n".encode())

        body = b"".join(parts)

        request = urllib.request.Request(
            url,
            data=body,
            headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
            method="POST",
        )

        try:
            with urllib.request.urlopen(request, timeout=20) as response:
                response.read()
            ok_any = True
        except urllib.error.HTTPError as exc:
            try:
                body_resp = exc.read().decode("utf-8", errors="replace")
                parsed = json.loads(body_resp)
                description = parsed.get("description", body_resp)
            except Exception:
                description = str(exc)
            _last_error["message"] = f"Telegram xatosi ({exc.code}): {description}"
            print(f"[telegram] {_last_error['message']}")
        except urllib.error.URLError as exc:
            _last_error["message"] = f"Ulanish xatosi: {exc.reason}"
            print(f"[telegram] Hujjat yuborishda xato: {exc}")

    return ok_any