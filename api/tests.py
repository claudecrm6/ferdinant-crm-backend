from unittest import mock

from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from .models import CRMUser, CRMSession, Group, Student, Payment
from .test_access import MONTHS_UZ, evaluate_access, make_access_token


class TestAccessTests(TestCase):
    """Testga kirish uchun majburiy to'lov tekshiruvi (backend)."""

    def setUp(self):
        self.user = CRMUser.objects.create(username="teacher", password_hash="x")
        self.session = CRMSession.objects.create(user=self.user)
        self.other = CRMUser.objects.create(username="other", password_hash="x")
        self.group = Group.objects.create(user=self.user, name="G1", price=500000)
        now = timezone.localtime()
        self.month = MONTHS_UZ[now.month - 1]
        self.year = now.year
        self.student = Student.objects.create(
            name="Ali", group=self.group, original_debt=500000, paid_amount=0
        )
        self.client = APIClient()
        self.client.cookies["crm_session"] = self.session.token

    # --- yordamchi ---
    def pay(self, amount, stage=""):
        # Frontend kabi: Payment yozuvi + Student qarzi yangilanadi
        Payment.objects.create(
            owner=self.user, student=self.student, amount=amount,
            month=self.month, year=self.year, date="2026-01-01", stage=stage,
        )
        self.student.paid_amount += amount
        self.student.save()

    def check(self, test_type):
        return self.client.post(
            "/api/tests/check-access/",
            {"student_id": self.student.id, "test_type": test_type},
            format="json",
        )

    # --- oraliq ---
    def test_oraliq_denied_when_nothing_paid(self):
        r = self.check("oraliq")
        self.assertEqual(r.status_code, 403)
        self.assertFalse(r.data["allowed"])
        self.assertEqual(r.data["code"], "debt_remaining")
        self.assertIn("500 000", r.data["message"])
        self.assertNotIn("access_token", r.data)

    def test_oraliq_denied_when_partial(self):
        self.pay(200000, "oraliq")
        r = self.check("oraliq")
        self.assertEqual(r.status_code, 403)
        self.assertIn("300 000", r.data["message"])

    def test_oraliq_allowed_when_fully_paid(self):
        self.pay(500000, "oraliq")
        r = self.check("oraliq")
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.data["allowed"])
        self.assertIn("access_token", r.data)

    def test_untyped_test_uses_oraliq_rule(self):
        self.assertEqual(self.check("").status_code, 403)
        self.pay(500000, "oraliq")
        self.assertEqual(self.check("").status_code, 200)

    # --- yakuniy ---
    def test_yakuniy_denied_with_only_first_payment_partial(self):
        self.pay(200000, "oraliq")
        r = self.check("yakuniy")
        self.assertEqual(r.status_code, 403)
        self.assertEqual(r.data["code"], "second_payment_required")

    def test_yakuniy_denied_when_second_payment_partial(self):
        self.pay(200000, "oraliq")
        self.pay(100000, "yakuniy")
        r = self.check("yakuniy")
        self.assertEqual(r.status_code, 403)
        self.assertEqual(r.data["code"], "second_payment_incomplete")

    def test_yakuniy_allowed_when_second_payment_complete(self):
        self.pay(200000, "oraliq")
        self.pay(300000, "yakuniy")
        r = self.check("yakuniy")
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.data["allowed"])

    def test_yakuniy_denied_when_paid_in_single_payment(self):
        self.pay(500000, "oraliq")
        r = self.check("yakuniy")
        self.assertEqual(r.status_code, 403)
        self.assertEqual(r.data["code"], "second_payment_required")

    # --- soxta holatga qarshi ---
    def test_forged_student_record_is_rejected(self):
        # Frontend orqali Student.paid_amount qo'lda to'liq qilingan, to'lov yozuvi yo'q
        self.student.paid_amount = 500000
        self.student.save()
        self.assertEqual(self.student.debt_amount, 0)
        r = self.check("oraliq")
        self.assertEqual(r.status_code, 403)
        self.assertEqual(r.data["code"], "debt_remaining")

    def test_payment_records_without_student_update_is_rejected(self):
        Payment.objects.create(
            owner=self.user, student=self.student, amount=500000,
            month=self.month, year=self.year, date="2026-01-01",
        )
        # Student qarzi yangilanmagan (debt hali 500000)
        self.assertEqual(self.check("oraliq").status_code, 403)

    def test_previous_month_payment_does_not_count(self):
        Payment.objects.create(
            owner=self.user, student=self.student, amount=500000,
            month="Yanvar" if self.month != "Yanvar" else "Fevral",
            year=self.year, date="2026-01-01",
        )
        self.student.paid_amount = 500000
        self.student.save()
        self.assertEqual(self.check("oraliq").status_code, 403)

    # --- kirish huquqlari ---
    def test_requires_login(self):
        c = APIClient()
        r = c.post("/api/tests/check-access/", {"student_id": self.student.id}, format="json")
        self.assertEqual(r.status_code, 401)

    def test_other_teachers_student_forbidden(self):
        s2 = CRMSession.objects.create(user=self.other)
        c = APIClient()
        c.cookies["crm_session"] = s2.token
        self.pay(500000, "oraliq")
        r = c.post("/api/tests/check-access/", {"student_id": self.student.id}, format="json")
        self.assertEqual(r.status_code, 403)
        self.assertEqual(r.data["code"], "forbidden")

    def test_bad_test_type(self):
        self.assertEqual(self.check("final").status_code, 400)

    # --- natija endpointi ---
    @mock.patch("api.views.telegram_service.send_to_admins", return_value=True)
    def test_quiz_result_requires_token(self, send):
        r = APIClient().post(
            "/api/telegram/send-quiz-result/",
            {"test_name": "T", "name": "Ali", "score": 5, "total": 10},
            format="json",
        )
        self.assertEqual(r.status_code, 403)
        send.assert_not_called()

    @mock.patch("api.views.telegram_service.send_to_admins", return_value=True)
    def test_quiz_result_rejects_forged_token(self, send):
        r = APIClient().post(
            "/api/telegram/send-quiz-result/",
            {"name": "Ali", "access_token": "fake"}, format="json",
        )
        self.assertEqual(r.status_code, 403)
        send.assert_not_called()

    @mock.patch("api.views.telegram_service.send_to_admins", return_value=True)
    def test_quiz_result_accepted_with_valid_token(self, send):
        self.pay(500000, "oraliq")
        token = self.check("oraliq").data["access_token"]
        r = APIClient().post(
            "/api/telegram/send-quiz-result/",
            {"test_name": "T", "name": "Ali", "score": 5, "total": 10, "access_token": token},
            format="json",
        )
        self.assertEqual(r.status_code, 200)
        send.assert_called_once()

    @mock.patch("api.views.telegram_service.send_to_admins", return_value=True)
    def test_quiz_result_rechecks_payment_state(self, send):
        # Token olingan, keyin to'lov bekor qilingan (o'chirilgan) bo'lsa — rad etiladi
        self.pay(500000, "oraliq")
        token = self.check("oraliq").data["access_token"]
        Payment.objects.all().delete()
        r = APIClient().post(
            "/api/telegram/send-quiz-result/",
            {"name": "Ali", "access_token": token}, format="json",
        )
        self.assertEqual(r.status_code, 403)
        send.assert_not_called()

    @mock.patch("api.views.telegram_service.send_to_admins", return_value=True)
    def test_oraliq_token_cannot_be_used_for_yakuniy(self, send):
        self.pay(500000, "oraliq")
        # yakuniy uchun token qo'lda yasalgan, lekin to'lov yetarli emas
        token = make_access_token(self.student, "yakuniy", self.user)
        r = APIClient().post(
            "/api/telegram/send-quiz-result/",
            {"name": "Ali", "access_token": token}, format="json",
        )
        self.assertEqual(r.status_code, 403)
        send.assert_not_called()
