from django.contrib.auth.hashers import check_password, make_password
from django.contrib.auth.models import User
from django.db import models
from django.utils import timezone
from django.db.models import Avg, Sum


SECURITY_QUESTION_CHOICES = [
    ("childhood_name", "Tên người bạn thân thời thơ ấu của bạn là gì?"),
    ("first_school", "Tên trường tiểu học đầu tiên của bạn là gì?"),
    ("favorite_teacher", "Tên giáo viên bạn nhớ nhất là gì?"),
    ("first_pet", "Tên thú cưng đầu tiên của bạn là gì?"),
    ("birth_city", "Bạn sinh ra ở thành phố nào?"),
    ("favorite_book", "Tên cuốn sách yêu thích thời nhỏ của bạn là gì?"),
]
SECURITY_QUESTION_MAP = dict(SECURITY_QUESTION_CHOICES)


class SanPham(models.Model):
    """Bảng sản phẩm chính."""

    TRANG_THAI = [
        ("active", "Hoạt động"),
        ("inactive", "Ngừng kinh doanh"),
    ]

    ten = models.CharField(max_length=100)
    gia = models.IntegerField(default=0)
    gia_khuyen_mai = models.IntegerField(blank=True, null=True)
    flash_sale_price = models.IntegerField(blank=True, null=True)
    flash_sale_start = models.DateTimeField(blank=True, null=True)
    flash_sale_end = models.DateTimeField(blank=True, null=True)
    anh = models.ImageField(upload_to="sanpham/", blank=True, null=True)
    search_tags = models.CharField(max_length=255, blank=True, default="")
    mo_ta = models.TextField(blank=True, default="")
    ton_kho = models.IntegerField(default=10)
    trang_thai = models.CharField(max_length=20, choices=TRANG_THAI, default="active")

    def __str__(self):
        return self.ten

    @property
    def co_the_dat_hang(self) -> bool:
        return self.trang_thai == "active" and int(self.ton_kho or 0) > 0

    @property
    def con_hang(self) -> bool:
        return int(self.ton_kho or 0) > 0

    @property
    def sap_het_hang(self) -> bool:
        return 0 < int(self.ton_kho or 0) <= 5

    @property
    def dang_giam_gia(self) -> bool:
        return self.gia_khuyen_mai is not None and int(self.gia_khuyen_mai or 0) > 0 and int(self.gia_khuyen_mai) < int(self.gia or 0)

    @property
    def dang_flash_sale(self) -> bool:
        now = timezone.now()
        return (
            self.flash_sale_price is not None
            and int(self.flash_sale_price or 0) > 0
            and int(self.flash_sale_price) < int(self.gia or 0)
            and self.flash_sale_start is not None
            and self.flash_sale_end is not None
            and self.flash_sale_start <= now <= self.flash_sale_end
        )

    @property
    def co_flash_sale_cai_dat(self) -> bool:
        return (
            self.flash_sale_price is not None
            and int(self.flash_sale_price or 0) > 0
            and int(self.flash_sale_price) < int(self.gia or 0)
            and self.flash_sale_start is not None
            and self.flash_sale_end is not None
        )

    @property
    def sap_dien_ra_flash_sale(self) -> bool:
        return self.co_flash_sale_cai_dat and timezone.now() < self.flash_sale_start

    @property
    def da_ket_thuc_flash_sale(self) -> bool:
        return self.co_flash_sale_cai_dat and timezone.now() > self.flash_sale_end

    @property
    def gia_hien_tai(self) -> int:
        if self.dang_flash_sale:
            return int(self.flash_sale_price)
        return int(self.gia_khuyen_mai) if self.dang_giam_gia else int(self.gia or 0)

    @property
    def so_tien_giam(self) -> int:
        return max(int(self.gia or 0) - self.gia_hien_tai, 0)

    @property
    def phan_tram_giam(self) -> int:
        gia = int(self.gia or 0)
        if gia <= 0 or not self.dang_giam_gia:
            return 0
        return max((self.so_tien_giam * 100) // gia, 0)

    @property
    def mo_ta_ngan(self) -> str:
        mo_ta = (self.mo_ta or "").strip()
        if not mo_ta:
            return "Trang sức cao cấp, thiết kế thanh lịch và phù hợp làm quà tặng."
        return mo_ta[:120] + ("..." if len(mo_ta) > 120 else "")

    @property
    def review_count(self) -> int:
        return int(getattr(self, "review_count_value", None) or self.reviews.filter(is_visible=True).count())

    @property
    def average_rating(self) -> float:
        annotated = getattr(self, "average_rating_value", None)
        if annotated is not None:
            return float(annotated or 0)
        return float(self.reviews.filter(is_visible=True).aggregate(avg=Avg("rating")).get("avg") or 0)

    @property
    def rating_stars(self) -> str:
        avg = self.average_rating
        full = int(round(avg))
        full = max(min(full, 5), 0)
        return "★" * full + "☆" * (5 - full)

    @property
    def gallery_images(self):
        return self.images.filter(is_active=True).order_by("sort_order", "id")


class UserSecurityProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="security_profile")
    question_1 = models.CharField(max_length=50, choices=SECURITY_QUESTION_CHOICES)
    answer_1 = models.CharField(max_length=255)
    question_2 = models.CharField(max_length=50, choices=SECURITY_QUESTION_CHOICES)
    answer_2 = models.CharField(max_length=255)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Bao mat - {self.user.username}"

    def set_answers(self, answer_1: str, answer_2: str):
        self.answer_1 = make_password((answer_1 or "").strip().lower())
        self.answer_2 = make_password((answer_2 or "").strip().lower())

    def check_answers(self, answer_1: str, answer_2: str) -> bool:
        return check_password((answer_1 or "").strip().lower(), self.answer_1) and check_password((answer_2 or "").strip().lower(), self.answer_2)

    @property
    def question_1_text(self):
        return SECURITY_QUESTION_MAP.get(self.question_1, self.question_1)

    @property
    def question_2_text(self):
        return SECURITY_QUESTION_MAP.get(self.question_2, self.question_2)


class Wallet(models.Model):
    """Ví điện tử cho mỗi người dùng."""

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="wallet")
    balance = models.IntegerField(default=0)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Ví - {self.user.username}"


class Voucher(models.Model):
    DISCOUNT_TYPES = [
        ("percent", "Giảm theo %"),
        ("fixed", "Giảm số tiền cố định"),
    ]

    code = models.CharField(max_length=30, unique=True)
    title = models.CharField(max_length=100, default="")
    description = models.CharField(max_length=255, blank=True, default="")
    discount_type = models.CharField(max_length=20, choices=DISCOUNT_TYPES, default="percent")
    value = models.IntegerField(default=0)
    min_order_value = models.IntegerField(default=0)
    max_discount = models.IntegerField(default=0)
    usage_limit = models.IntegerField(default=0)
    used_count = models.IntegerField(default=0)
    active = models.BooleanField(default=True)
    starts_at = models.DateTimeField(blank=True, null=True)
    ends_at = models.DateTimeField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["code"]

    def __str__(self):
        return self.code

    def is_available_now(self) -> bool:
        now = timezone.now()
        if not self.active:
            return False
        if self.starts_at and now < self.starts_at:
            return False
        if self.ends_at and now > self.ends_at:
            return False
        if self.usage_limit and self.used_count >= self.usage_limit:
            return False
        return True


class DonHang(models.Model):
    """Bảng đơn hàng chính."""

    TRANG_THAI = [
        ("Pending", "Chờ xác nhận"),
        ("Confirmed", "Đã xác nhận"),
        ("Cancelled", "Đã huỷ"),
        ("Approved", "Đã duyệt"),
        ("Rejected", "Từ chối"),
    ]

    PHUONG_THUC_TT = [
        ("COD", "COD (Thanh toán khi nhận hàng)"),
        ("ChuyenKhoan", "Chuyển khoản ngân hàng"),
        ("ViDienTu", "Ví điện tử"),
    ]

    nguoi_dat = models.ForeignKey(User, on_delete=models.CASCADE, related_name="don_hangs")
    san_pham = models.ForeignKey(SanPham, on_delete=models.PROTECT, related_name="don_hangs")
    voucher = models.ForeignKey("Voucher", on_delete=models.SET_NULL, null=True, blank=True, related_name="orders")

    ho_ten = models.CharField(max_length=100, default="")
    sdt = models.CharField(max_length=20, default="")
    dia_chi = models.CharField(max_length=255, default="")
    ghi_chu = models.CharField(max_length=255, blank=True, default="")
    phuong_thuc_tt = models.CharField(max_length=50, choices=PHUONG_THUC_TT, default="COD")

    so_luong = models.IntegerField(default=1)
    tong_tien_goc = models.IntegerField(default=0)
    discount_amount = models.IntegerField(default=0)
    voucher_code = models.CharField(max_length=30, blank=True, default="")
    tong_tien = models.IntegerField(default=0)
    trang_thai = models.CharField(max_length=20, choices=TRANG_THAI, default="Pending")
    da_hoan_tien = models.BooleanField(default=False)
    da_thanh_toan = models.BooleanField(default=False)
    ma_thanh_toan = models.CharField(max_length=50, blank=True, default="")
    thanh_toan_luc = models.DateTimeField(blank=True, null=True)
    tao_luc = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Don #{self.id} - {self.nguoi_dat.username}"

    def tinh_tong_tien(self) -> int:
        return max(int(self.so_luong or 0), 0) * max(int(self.san_pham.gia_hien_tai or 0), 0)

    def save(self, *args, **kwargs):
        if self.san_pham_id:
            self.tong_tien_goc = self.tinh_tong_tien()
            self.discount_amount = max(int(self.discount_amount or 0), 0)
            self.discount_amount = min(self.discount_amount, self.tong_tien_goc)
            self.tong_tien = max(self.tong_tien_goc - self.discount_amount, 0)
        super().save(*args, **kwargs)


class SavedAddress(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="saved_addresses")
    label = models.CharField(max_length=100, blank=True, default="")
    ho_ten = models.CharField(max_length=100)
    sdt = models.CharField(max_length=20)
    dia_chi = models.CharField(max_length=255)
    is_default = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-is_default", "-updated_at", "-id"]

    def __str__(self):
        return self.label or f"{self.user.username} - {self.dia_chi[:30]}"

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        if self.is_default:
            SavedAddress.objects.filter(user=self.user).exclude(pk=self.pk).update(is_default=False)


class OrderStatusHistory(models.Model):
    order = models.ForeignKey("DonHang", on_delete=models.CASCADE, related_name="status_histories")
    old_status = models.CharField(max_length=20, blank=True, default="")
    new_status = models.CharField(max_length=20)
    actor = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name="order_status_actions")
    note = models.CharField(max_length=255, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at", "id"]

    def __str__(self):
        return f"Don #{self.order_id}: {self.old_status} -> {self.new_status}"


class InventoryHistory(models.Model):
    CHANGE_TYPES = [
        ("manual_set", "Admin đặt lại tồn kho"),
        ("manual_in", "Admin nhập kho"),
        ("manual_out", "Admin xuất kho"),
        ("receipt_in", "Nhập kho theo phiếu nhập"),
        ("order_out", "Trừ kho theo đơn hàng"),
        ("order_return", "Hoàn kho do huỷ / từ chối đơn"),
    ]

    san_pham = models.ForeignKey(SanPham, on_delete=models.CASCADE, related_name="inventory_histories")
    old_stock = models.IntegerField(default=0)
    quantity_change = models.IntegerField(default=0)
    new_stock = models.IntegerField(default=0)
    change_type = models.CharField(max_length=30, choices=CHANGE_TYPES, default="manual_set")
    actor = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name="inventory_actions")
    order = models.ForeignKey("DonHang", on_delete=models.SET_NULL, null=True, blank=True, related_name="inventory_histories")
    note = models.CharField(max_length=255, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-id"]

    def __str__(self):
        sign = "+" if int(self.quantity_change or 0) >= 0 else ""
        return f"Kho {self.san_pham.ten}: {sign}{self.quantity_change}"


class NhaCungCap(models.Model):
    ten = models.CharField(max_length=150)
    sdt = models.CharField(max_length=20, blank=True, default="")
    email = models.EmailField(blank=True, default="")
    dia_chi = models.CharField(max_length=255, blank=True, default="")
    ghi_chu = models.CharField(max_length=255, blank=True, default="")
    active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["ten", "id"]

    def __str__(self):
        return self.ten


class PhieuNhapKho(models.Model):
    STATUS_CHOICES = [
        ("draft", "Nháp"),
        ("received", "Đã nhập kho"),
        ("cancelled", "Đã huỷ"),
    ]

    code = models.CharField(max_length=20, unique=True)
    supplier = models.ForeignKey("NhaCungCap", on_delete=models.SET_NULL, null=True, blank=True, related_name="purchase_receipts")
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name="created_purchase_receipts")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="draft")
    note = models.CharField(max_length=255, blank=True, default="")
    imported_at = models.DateTimeField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at", "-id"]

    def __str__(self):
        return self.code

    @property
    def tong_so_luong(self) -> int:
        return int(self.items.aggregate(total=Sum("so_luong")).get("total") or 0)

    @property
    def tong_gia_tri(self) -> int:
        total = 0
        for item in self.items.all():
            total += item.thanh_tien
        return int(total)


class PhieuNhapKhoItem(models.Model):
    receipt = models.ForeignKey("PhieuNhapKho", on_delete=models.CASCADE, related_name="items")
    san_pham = models.ForeignKey(SanPham, on_delete=models.PROTECT, related_name="purchase_receipt_items")
    so_luong = models.IntegerField(default=0)
    don_gia_nhap = models.IntegerField(default=0)
    batch_code = models.CharField(max_length=50, blank=True, default="")
    ghi_chu = models.CharField(max_length=255, blank=True, default="")

    class Meta:
        ordering = ["id"]

    def __str__(self):
        return f"{self.receipt.code} - {self.san_pham.ten}"

    @property
    def thanh_tien(self) -> int:
        return max(int(self.so_luong or 0), 0) * max(int(self.don_gia_nhap or 0), 0)


class InventoryBatch(models.Model):
    san_pham = models.ForeignKey(SanPham, on_delete=models.CASCADE, related_name="inventory_batches")
    supplier = models.ForeignKey("NhaCungCap", on_delete=models.SET_NULL, null=True, blank=True, related_name="inventory_batches")
    receipt = models.ForeignKey("PhieuNhapKho", on_delete=models.CASCADE, related_name="batches")
    receipt_item = models.ForeignKey("PhieuNhapKhoItem", on_delete=models.CASCADE, related_name="batches")
    batch_code = models.CharField(max_length=50)
    so_luong_nhap = models.IntegerField(default=0)
    so_luong_con_lai = models.IntegerField(default=0)
    don_gia_nhap = models.IntegerField(default=0)
    imported_at = models.DateTimeField(default=timezone.now)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name="created_inventory_batches")
    note = models.CharField(max_length=255, blank=True, default="")

    class Meta:
        ordering = ["-imported_at", "-id"]

    def __str__(self):
        return f"{self.batch_code} - {self.san_pham.ten}"


class ProductImage(models.Model):
    san_pham = models.ForeignKey(SanPham, on_delete=models.CASCADE, related_name="images")
    image = models.ImageField(upload_to="sanpham/gallery/")
    caption = models.CharField(max_length=120, blank=True, default="")
    sort_order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["sort_order", "id"]

    def __str__(self):
        return self.caption or f"Ảnh phụ #{self.pk} - {self.san_pham.ten}"


class ProductReview(models.Model):
    san_pham = models.ForeignKey(SanPham, on_delete=models.CASCADE, related_name="reviews")
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="product_reviews")
    rating = models.PositiveSmallIntegerField(default=5)
    title = models.CharField(max_length=120, blank=True, default="")
    comment = models.TextField(blank=True, default="")
    is_visible = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        unique_together = ("san_pham", "user")

    def __str__(self):
        return f"{self.san_pham.ten} - {self.user.username} ({self.rating}/5)"

    @property
    def stars(self) -> str:
        rating = max(min(int(self.rating or 0), 5), 0)
        return "★" * rating + "☆" * (5 - rating)


class CartItem(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="cart_items")
    san_pham = models.ForeignKey(SanPham, on_delete=models.CASCADE, related_name="cart_items")
    quantity = models.IntegerField(default=1)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("user", "san_pham")
        ordering = ["-updated_at", "-id"]

    def __str__(self):
        return f"{self.user.username} - {self.san_pham.ten}"

    @property
    def thanh_tien(self) -> int:
        return max(int(self.quantity or 0), 0) * max(int(self.san_pham.gia_hien_tai or 0), 0)


class WalletTopUpRequest(models.Model):
    """Yêu cầu nạp tiền bằng QR/VietQR."""

    STATUS_CHOICES = [
        ("pending", "Chờ thanh toán"),
        ("paid", "Đã nhận callback"),
        ("approved", "Đã cộng ví"),
        ("rejected", "Từ chối"),
    ]

    wallet = models.ForeignKey(Wallet, on_delete=models.CASCADE, related_name="topup_requests")
    amount = models.IntegerField(default=0)
    reference = models.CharField(max_length=32, unique=True)
    transfer_note = models.CharField(max_length=64, default="", blank=True)
    qr_payload = models.TextField(blank=True, default="")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")
    approved_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name="approved_topups")
    rejected_reason = models.CharField(max_length=255, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    paid_at = models.DateTimeField(blank=True, null=True)
    approved_at = models.DateTimeField(blank=True, null=True)

    def __str__(self):
        return f"Nạp ví {self.reference} - {self.wallet.user.username}"

    @property
    def user(self):
        return self.wallet.user


class WalletTransaction(models.Model):
    """Lịch sử giao dịch ví."""

    TRANSACTION_TYPES = [
        ("deposit", "Nạp tiền"),
        ("payment", "Thanh toán đơn hàng"),
        ("refund", "Hoàn tiền"),
    ]

    wallet = models.ForeignKey(Wallet, on_delete=models.CASCADE, related_name="transactions")
    amount = models.IntegerField()
    transaction_type = models.CharField(max_length=20, choices=TRANSACTION_TYPES)
    order = models.ForeignKey("DonHang", on_delete=models.SET_NULL, null=True, blank=True, related_name="wallet_transactions")
    note = models.CharField(max_length=255, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.wallet.user.username} - {self.transaction_type} - {self.amount}"


from django.db.models.signals import post_save
from django.dispatch import receiver


@receiver(post_save, sender=User)
def create_wallet_for_user(sender, instance, created, **kwargs):
    if created:
        Wallet.objects.get_or_create(user=instance)



@receiver(post_save, sender=DonHang)
def create_initial_order_history(sender, instance, created, **kwargs):
    if created and not instance.status_histories.exists():
        OrderStatusHistory.objects.create(order=instance, old_status="", new_status=instance.trang_thai, actor=instance.nguoi_dat, note="Tạo đơn hàng")
