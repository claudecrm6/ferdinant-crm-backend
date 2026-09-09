from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0017_course'),
    ]

    operations = [
        migrations.AddField(
            model_name='student',
            name='has_discount',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='student',
            name='discounted_price',
            field=models.IntegerField(blank=True, null=True),
        ),
    ]
