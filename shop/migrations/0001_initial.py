from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="SanPham",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("ten", models.CharField(max_length=100)),
                ("gia", models.IntegerField(default=0)),
                ("anh", models.ImageField(blank=True, null=True, upload_to="sanpham/")),
            ],
        ),
        migrations.CreateModel(
            name="DonHang",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("so_luong", models.IntegerField(default=1)),
                ("tong_tien", models.IntegerField(default=0)),
                ("trang_thai", models.CharField(default="Pending", max_length=20)),
                ("tao_luc", models.DateTimeField(auto_now_add=True)),
                (
                    "nguoi_dat",
                    models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL),
                ),
                (
                    "san_pham",
                    models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to="shop.sanpham"),
                ),
            ],
        ),
    ]
