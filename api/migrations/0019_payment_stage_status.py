from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0018_student_discount_fields'),
    ]

    operations = [
        migrations.AddField(
            model_name='payment',
            name='stage',
            field=models.CharField(blank=True, choices=[('oraliq', 'Oraliq'), ('yakuniy', 'Yakuniy')], default='', max_length=10),
        ),
        migrations.AddField(
            model_name='payment',
            name='status',
            field=models.CharField(blank=True, choices=[('partial', 'Qisman'), ("paid", "To'liq to'langan")], default='', max_length=10),
        ),
    ]
