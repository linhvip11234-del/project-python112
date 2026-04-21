from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("shop", "0006_usersecurityprofile"),
    ]

    operations = [
        migrations.AddField(
            model_name="sanpham",
            name="mo_ta",
            field=models.TextField(blank=True, default=""),
        ),
    ]
