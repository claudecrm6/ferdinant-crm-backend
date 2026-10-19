from django.db import models
from django.utils import timezone
import secrets


class Group(models.Model):
    user = models.ForeignKey(
        'CRMUser',
        on_delete=models.CASCADE,
        related_name='groups',
        null=True,
        blank=True
    )
    name = models.CharField(max_length=100)
    time = models.CharField(max_length=10, default="15:00")
    days = models.CharField(max_length=20, default="DCHJ")
    course_type = models.CharField(max_length=100, blank=True)
    teacher = models.CharField(max_length=100, blank=True)
    price = models.IntegerField(default=500000)
    max_students = models.IntegerField(default=17)

    def __str__(self):
        return self.name


class Course(models.Model):
    user = models.ForeignKey(
        'CRMUser',
        on_delete=models.CASCADE,
        related_name='courses',
        null=True,
        blank=True
    )
    name = models.CharField(max_length=100)
    price = models.IntegerField(default=500000)

    def __str__(self):
        return self.name


class Student(models.Model):
    name = models.CharField(max_length=200)
    group = models.ForeignKey(Group, on_delete=models.SET_NULL, null=True, blank=True)
    original_debt = models.IntegerField(default=500000)
    debt_amount = models.IntegerField(default=500000)
    paid_amount = models.IntegerField(default=0)
    payment_status = models.CharField(max_length=20, default="debt")
    # Joriy to'lov holati qaysi oyga tegishli ekanini belgilaydi, masalan "2026-07".
    # Yangi oy boshlanganda shu maydon eskirgan hisoblanib, holat reset qilinadi.
    period = models.CharField(max_length=7, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    # ===== CHEGIRMA (INDIVIDUAL OYLIK NARX) =====
    # has_discount=True bo'lsa, bu o'quvchi uchun oylik to'lov guruh/kurs
    # narxidan emas, balki discounted_price maydonidagi individual summadan
    # olinadi. Bu qiymat guruh narxi keyinchalik o'zgarsa ham o'zgarmaydi va
    # har oy (ensure_monthly_reset) shu summa asosida qarzdorlik ochiladi.
    has_discount = models.BooleanField(default=False)
    discounted_price = models.IntegerField(null=True, blank=True)

    def save(self, *args, **kwargs):

        self.debt_amount = max(
            0,
            self.original_debt - self.paid_amount
        )

        if self.debt_amount == 0:
            self.payment_status = "paid"

        elif self.paid_amount > 0:
            self.payment_status = "partial"

        else:
            self.payment_status = "debt"

        if not self.period:
            self.period = timezone.localtime().strftime("%Y-%m")

        super().save(*args, **kwargs)


class Payment(models.Model):
    owner = models.ForeignKey(
        'CRMUser',
        on_delete=models.PROTECT,   # user o'chsa ham payment yo'qolmasin
        related_name='payments'
    )
    student = models.ForeignKey(
        Student,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='payments'
    )
    # Student o'chib ketsa ham, kim to'lagani ko'rinib tursin
    student_name_snapshot = models.CharField(max_length=255, blank=True)

    amount = models.IntegerField()
    month = models.CharField(max_length=20)
    year = models.IntegerField()
    date = models.CharField(max_length=20)

    # ===== TO'LOV BOSQICHI (ORALIQ / YAKUNIY) =====
    # Shu oy uchun o'quvchining birinchi to'lovi "oraliq", keyingisi "yakuniy".
    # Bu maydonlar faqat qayd uchun — qarzdorlik hisobiga (Student) ta'sir qilmaydi.
    STAGE_ORALIQ = 'oraliq'
    STAGE_YAKUNIY = 'yakuniy'
    STAGE_CHOICES = [
        (STAGE_ORALIQ, 'Oraliq'),
        (STAGE_YAKUNIY, 'Yakuniy'),
    ]
    STATUS_PARTIAL = 'partial'
    STATUS_PAID = 'paid'
    STATUS_CHOICES = [
        (STATUS_PARTIAL, 'Qisman'),
        (STATUS_PAID, "To'liq to'langan"),
    ]
    stage = models.CharField(max_length=10, choices=STAGE_CHOICES, blank=True, default='')
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, blank=True, default='')

    def save(self, *args, **kwargs):
        if self.student and not self.student_name_snapshot:
            # Yangi to'lov yoki student hali mavjud bo'lgan holat — ismini "suratga olamiz"
            self.student_name_snapshot = self.student.name
        elif not self.student_name_snapshot and self.pk:
            # Himoya: agar kimdir (masalan eski frontend so'rovi) snapshot maydonini
            # bo'sh jo'natib, uni PUT/PATCH orqali ustidan yozib yuborsa —
            # bazada avval saqlangan ismni yo'qotmasligimiz kerak.
            existing = Payment.objects.filter(pk=self.pk).values_list(
                'student_name_snapshot', flat=True
            ).first()
            if existing:
                self.student_name_snapshot = existing
        super().save(*args, **kwargs)


class Trash(models.Model):
    owner = models.ForeignKey(
        'CRMUser',
        on_delete=models.CASCADE,
        related_name='trash_items',
        null=True,
        blank=True
    )
    student_data = models.JSONField()
    deleted_at = models.DateTimeField(auto_now_add=True)
    from_group = models.CharField(max_length=100, blank=True)


# ===================== CRM FOYDALANUVCHILAR =====================
def generate_token():
    return secrets.token_hex(32)


class CRMUser(models.Model):
    ROLE_ADMIN = 'admin'
    ROLE_TEACHER = 'teacher'
    ROLE_CHOICES = [
        (ROLE_ADMIN, 'Admin'),
        (ROLE_TEACHER, 'Teacher'),
    ]

    username = models.CharField(max_length=100, unique=True)
    password_hash = models.CharField(max_length=200)
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default=ROLE_TEACHER)
    name = models.CharField(max_length=200, blank=True)
    phone = models.CharField(max_length=50, blank=True)
    address = models.CharField(max_length=200, blank=True)
    avatar = models.TextField(blank=True)  # base64
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.username


class CRMSession(models.Model):
    user = models.ForeignKey(CRMUser, on_delete=models.CASCADE, related_name='sessions')
    token = models.CharField(max_length=200, unique=True, default=generate_token)
    device_id = models.CharField(max_length=200, blank=True)
    is_trusted = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    last_used = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.user.username} - {self.token[:10]}..."


# ===================== QARZDORLIK ESLATMALARI (TELEGRAM) =====================
class ReminderLog(models.Model):
    """
    Har bir oy uchun qaysi turdagi Telegram eslatmasi allaqachon yuborilganini
    qayd qiladi. Shu orqali eslatma bir necha marta (masalan bir nechta
    gunicorn worker fon jarayoni tomonidan) qayta yuborilmasligi kafolatlanadi.
    """
    GENERAL = 'general'
    INDIVIDUAL = 'individual'
    GROUP_LESSON = 'group_lesson'
    TYPE_CHOICES = [
        (GENERAL, "Barcha o'quvchilar uchun umumiy to'lov eslatmasi (har 5 kunda)"),
        (INDIVIDUAL, "15-sanadan keyingi har bir qarzdorga alohida ogohlantirish"),
        (GROUP_LESSON, "Guruh darsi boshlanganda shu guruh qarzdorlari ro'yxati"),
    ]

    # Guruh-asosli eslatmalar uchun "period" maydoniga
    # "YYYY-MM-DD-group-<id>" ko'rinishida noyob kalit yoziladi (masalan
    # "2026-07-08-group-3"), shu orqali bir xil guruhga bir kunda faqat bitta
    # marta xabar yuborilishi kafolatlanadi.
    period = models.CharField(max_length=40)  # masalan "2026-07" yoki "2026-07-05"
    reminder_type = models.CharField(max_length=20, choices=TYPE_CHOICES)
    sent_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('period', 'reminder_type')

    def __str__(self):
        return f"{self.period} - {self.reminder_type}"

class RegistrationOTP(models.Model):
    """
    Ro'yxatdan o'tishda Telegram orqali tasdiqlash kodi — endi to'liq
    backendda saqlanadi va tekshiriladi (frontendda emas), shuning uchun
    brauzer konsoli orqali chetlab o'tib bo'lmaydi.
    """
    verification_id = models.CharField(max_length=64, unique=True)
    code = models.CharField(max_length=4)
    verified = models.BooleanField(default=False)
    used = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()

    def __str__(self):
        return f"OTP {self.verification_id[:8]}... ({'verified' if self.verified else 'pending'})"