import tempfile
from datetime import timedelta

from django.contrib.auth.models import User
from django.core import mail
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from .forms import SanPhamForm
from .models import CartItem, DonHang, InventoryBatch, InventoryHistory, NhaCungCap, PhieuNhapKho, ProductImage, ProductReview, SanPham, UserSecurityProfile, Voucher, Wallet, WalletTransaction


@override_settings(MEDIA_ROOT=tempfile.gettempdir())
class ShopFeatureTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(username="user1", password="123456")
        UserSecurityProfile.objects.create(
            user=self.user,
            question_1="first_school",
            answer_1="pbkdf2_sha256$1000000$dummy$g5xv3A4/jqk5oE0Lk2WJn2XhQ9eF2b1oP42H/V3FZ9E=",
            question_2="first_pet",
            answer_2="pbkdf2_sha256$1000000$dummy$g5xv3A4/jqk5oE0Lk2WJn2XhQ9eF2b1oP42H/V3FZ9E=",
        )
        self.user.security_profile.set_answers("Le Quy Don", "Milu")
        self.user.security_profile.save()
        self.admin = User.objects.create_user(username="admin1", password="123456", is_staff=True)
        self.sp_active = SanPham.objects.create(ten="Nhan A", gia=100000, trang_thai="active")
        self.sp_inactive = SanPham.objects.create(ten="Nhan B", gia=200000, trang_thai="inactive")

    def test_guest_cannot_access_admin_panel(self):
        response = self.client.get(reverse("admin_dashboard"), follow=True)
        self.assertContains(response, "Vui lòng đăng nhập để tiếp tục")

    def test_search_filter_sort_products_in_admin_list(self):
        self.client.login(username="admin1", password="123456")
        SanPham.objects.create(ten="Nhan C", gia=50000, trang_thai="active")
        response = self.client.get(
            reverse("admin_sanpham_list"),
            {"q": "Nhan", "trang_thai": "active", "sort": "price_asc"},
        )
        ds = list(response.context["ds"])
        self.assertTrue(all(sp.trang_thai == "active" for sp in ds))
        self.assertEqual(ds[0].gia, 50000)

    def test_product_image_validation_rejects_bad_extension(self):
        bad_file = SimpleUploadedFile("bad.txt", b"abc", content_type="text/plain")
        form = SanPhamForm(data={"ten": "SP loi", "gia": 1000, "trang_thai": "active"}, files={"anh": bad_file})
        self.assertFalse(form.is_valid())
        self.assertIn("Chỉ cho phép ảnh", str(form.errors))

    def test_order_business_flow_user_and_admin(self):
        self.client.login(username="user1", password="123456")
        response = self.client.post(
            reverse("dat_hang", args=[self.sp_active.id]),
            {
                "ho_ten": "Nguyen Van A",
                "sdt": "0987654321",
                "dia_chi": "Ha Noi",
                "ghi_chu": "Giao nhanh",
                "phuong_thuc_tt": "COD",
                "so_luong": 2,
            },
            follow=True,
        )
        self.assertContains(response, "Đặt hàng thành công")
        don = DonHang.objects.get()
        self.assertEqual(don.tong_tien, 200000)
        self.assertEqual(don.trang_thai, "Pending")

        response = self.client.get(reverse("xac_nhan_don", args=[don.id]), follow=True)
        self.assertContains(response, "Đã cập nhật trạng thái đơn")
        don.refresh_from_db()
        self.assertEqual(don.trang_thai, "Confirmed")

        self.client.logout()
        self.client.login(username="admin1", password="123456")
        response = self.client.post(
            reverse("admin_donhang_update", args=[don.id]),
            {"trang_thai": "Approved"},
            follow=True,
        )
        self.assertContains(response, "Đã cập nhật trạng thái đơn")
        don.refresh_from_db()
        self.assertEqual(don.trang_thai, "Approved")

        self.client.logout()
        self.client.login(username="user1", password="123456")
        response = self.client.get(reverse("xac_nhan_don", args=[don.id]), follow=True)
        self.assertContains(response, "Không thể chuyển")
        don.refresh_from_db()
        self.assertEqual(don.trang_thai, "Approved")

    def test_cannot_delete_product_that_has_orders(self):
        DonHang.objects.create(
            nguoi_dat=self.user,
            san_pham=self.sp_active,
            ho_ten="Nguyen Van A",
            sdt="0987654321",
            dia_chi="Thai Nguyen",
            ghi_chu="",
            phuong_thuc_tt="COD",
            so_luong=1,
            tong_tien=100000,
            trang_thai="Pending",
        )
        self.client.login(username="admin1", password="123456")
        response = self.client.post(reverse("admin_sanpham_delete", args=[self.sp_active.id]), follow=True)
        self.assertContains(response, "Không thể xoá sản phẩm đã phát sinh đơn hàng")
        self.assertTrue(SanPham.objects.filter(id=self.sp_active.id).exists())

    def test_wallet_payment_deducts_balance_and_creates_transaction(self):
        wallet = Wallet.objects.get(user=self.user)
        wallet.balance = 500000
        wallet.save()

        self.client.login(username="user1", password="123456")
        response = self.client.post(
            reverse("dat_hang", args=[self.sp_active.id]),
            {
                "ho_ten": "Nguyen Van A",
                "sdt": "0987654321",
                "dia_chi": "Ha Noi",
                "ghi_chu": "",
                "phuong_thuc_tt": "ViDienTu",
                "so_luong": 2,
            },
            follow=True,
        )

        self.assertContains(response, "Đặt hàng thành công")
        wallet.refresh_from_db()
        self.assertEqual(wallet.balance, 300000)
        self.assertEqual(WalletTransaction.objects.filter(wallet=wallet, transaction_type="payment").count(), 1)

    def test_wallet_order_refunds_when_cancelled(self):
        wallet = Wallet.objects.get(user=self.user)
        wallet.balance = 500000
        wallet.save()

        order = DonHang.objects.create(
            nguoi_dat=self.user,
            san_pham=self.sp_active,
            ho_ten="Nguyen Van A",
            sdt="0987654321",
            dia_chi="Thai Nguyen",
            ghi_chu="",
            phuong_thuc_tt="ViDienTu",
            so_luong=1,
            tong_tien=100000,
            trang_thai="Pending",
        )
        WalletTransaction.objects.create(
            wallet=wallet,
            amount=100000,
            transaction_type="payment",
            order=order,
            note="Thanh toán đơn hàng",
        )
        wallet.balance = 400000
        wallet.save()

        self.client.login(username="user1", password="123456")
        response = self.client.get(reverse("huy_don", args=[order.id]), follow=True)
        self.assertContains(response, "Đã hoàn tiền vào ví điện tử")

        wallet.refresh_from_db()
        order.refresh_from_db()
        self.assertEqual(wallet.balance, 500000)
        self.assertTrue(order.da_hoan_tien)
        self.assertEqual(WalletTransaction.objects.filter(wallet=wallet, transaction_type="refund", order=order).count(), 1)

    def test_bank_transfer_order_refunds_when_cancelled_after_payment(self):
        wallet = Wallet.objects.get(user=self.user)
        wallet.balance = 500000
        wallet.save()

        order = DonHang.objects.create(
            nguoi_dat=self.user,
            san_pham=self.sp_active,
            ho_ten="Nguyen Van A",
            sdt="0987654321",
            dia_chi="Thai Nguyen",
            ghi_chu="",
            phuong_thuc_tt="ChuyenKhoan",
            so_luong=1,
            tong_tien=100000,
            trang_thai="Pending",
            da_thanh_toan=True,
            ma_thanh_toan="DH123",
        )

        self.client.login(username="user1", password="123456")
        response = self.client.get(reverse("huy_don", args=[order.id]), follow=True)
        self.assertContains(response, "Đã hoàn tiền vào ví điện tử")

        wallet.refresh_from_db()
        order.refresh_from_db()
        self.assertEqual(wallet.balance, 600000)
        self.assertTrue(order.da_hoan_tien)
        refund = WalletTransaction.objects.get(wallet=wallet, transaction_type="refund", order=order)
        self.assertEqual(refund.note, f"Hoàn tiền tự động cho đơn chuyển khoản #{order.id}")

    def test_bank_transfer_order_cancelled_without_payment_does_not_refund(self):
        wallet = Wallet.objects.get(user=self.user)
        wallet.balance = 500000
        wallet.save()

        order = DonHang.objects.create(
            nguoi_dat=self.user,
            san_pham=self.sp_active,
            ho_ten="Nguyen Van A",
            sdt="0987654321",
            dia_chi="Thai Nguyen",
            ghi_chu="",
            phuong_thuc_tt="ChuyenKhoan",
            so_luong=1,
            tong_tien=100000,
            trang_thai="Pending",
            da_thanh_toan=False,
            ma_thanh_toan="DH124",
        )

        self.client.login(username="user1", password="123456")
        response = self.client.get(reverse("huy_don", args=[order.id]), follow=True)
        self.assertContains(response, "Đã cập nhật trạng thái đơn")

        wallet.refresh_from_db()
        order.refresh_from_db()
        self.assertEqual(wallet.balance, 500000)
        self.assertFalse(order.da_hoan_tien)
        self.assertEqual(WalletTransaction.objects.filter(wallet=wallet, transaction_type="refund", order=order).count(), 0)

    @override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
    def test_forgot_password_email_flow_sends_otp_and_resets_password(self):
        self.user.email = "user1@gmail.com"
        self.user.save(update_fields=["email"])

        response = self.client.post(reverse("quen_mat_khau"), {"username_or_email": "user1@gmail.com"}, follow=True)
        self.assertRedirects(response, reverse("chon_phuong_thuc_khoi_phuc"))

        response = self.client.post(reverse("chon_phuong_thuc_khoi_phuc"), {"method": "email"}, follow=True)
        self.assertContains(response, "Đã gửi OTP")
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("OTP dat lai mat khau", mail.outbox[0].subject)

        session = self.client.session
        otp = session["password_reset_otp"]["otp"]

        response = self.client.post(
            reverse("dat_lai_mat_khau_otp"),
            {"otp": otp, "new_password": "654321abc", "new_password2": "654321abc"},
            follow=True,
        )
        self.assertContains(response, "Đổi mật khẩu thành công")
        self.assertTrue(self.client.login(username="user1", password="654321abc"))



    def test_discounted_product_uses_sale_price_for_order(self):
        self.sp_active.gia = 200000
        self.sp_active.gia_khuyen_mai = 150000
        self.sp_active.save()

        self.client.login(username="user1", password="123456")
        response = self.client.post(
            reverse("dat_hang", args=[self.sp_active.id]),
            {
                "ho_ten": "Nguyen Van A",
                "sdt": "0987654321",
                "dia_chi": "Ha Noi",
                "ghi_chu": "",
                "phuong_thuc_tt": "COD",
                "so_luong": 2,
            },
            follow=True,
        )

        self.assertContains(response, "Đặt hàng thành công")
        don = DonHang.objects.latest("id")
        self.assertEqual(don.tong_tien_goc, 300000)
        self.assertEqual(don.tong_tien, 300000)

    def test_home_shows_discounted_products_section(self):
        SanPham.objects.create(ten="Nhan sale", gia=300000, gia_khuyen_mai=210000, trang_thai="active")
        response = self.client.get(reverse("home"))
        self.assertContains(response, "Sản phẩm giảm giá")
        self.assertContains(response, "Nhan sale")
        self.assertContains(response, "210,000")

    def test_voucher_reduces_single_order_total(self):
        Voucher.objects.create(code="TEST10", discount_type="percent", value=10, min_order_value=50000, active=True)
        self.client.login(username="user1", password="123456")
        response = self.client.post(
            reverse("dat_hang", args=[self.sp_active.id]),
            {
                "ho_ten": "Nguyen Van A",
                "sdt": "0987654321",
                "dia_chi": "Ha Noi",
                "ghi_chu": "",
                "phuong_thuc_tt": "COD",
                "so_luong": 2,
                "voucher_code": "TEST10",
            },
            follow=True,
        )
        self.assertContains(response, "Đặt hàng thành công")
        don = DonHang.objects.latest("id")
        self.assertEqual(don.tong_tien_goc, 200000)
        self.assertEqual(don.discount_amount, 20000)
        self.assertEqual(don.tong_tien, 180000)
        self.assertEqual(don.voucher_code, "TEST10")

    def test_cart_checkout_creates_multiple_orders_and_clears_cart(self):
        Voucher.objects.create(code="CART50", discount_type="fixed", value=50000, min_order_value=100000, active=True)
        self.client.login(username="user1", password="123456")
        self.client.post(reverse("add_to_cart", args=[self.sp_active.id]), {"quantity": 1}, follow=True)
        sp2 = SanPham.objects.create(ten="Day chuyen C", gia=150000, trang_thai="active")
        self.client.post(reverse("add_to_cart", args=[sp2.id]), {"quantity": 2}, follow=True)

        response = self.client.post(
            reverse("thanh_toan_gio_hang"),
            {
                "ho_ten": "Nguyen Van A",
                "sdt": "0987654321",
                "dia_chi": "Ha Noi",
                "ghi_chu": "",
                "phuong_thuc_tt": "COD",
                "so_luong": 1,
                "voucher_code": "CART50",
            },
            follow=True,
        )
        self.assertContains(response, "Đã tạo thành công 2 đơn hàng từ giỏ hàng")
        self.assertEqual(DonHang.objects.count(), 2)
        self.assertEqual(CartItem.objects.filter(user=self.user).count(), 0)
        self.assertEqual(sum(d.tong_tien for d in DonHang.objects.all()), 350000)
    @override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
    def test_forgot_password_rejects_unlinked_email(self):
        response = self.client.post(reverse("quen_mat_khau"), {"username_or_email": "nouser@example.com"}, follow=True)
        self.assertContains(response, "Email chưa được tạo hoặc chưa có tài khoản nào liên kết với email này")
        self.assertEqual(len(mail.outbox), 0)

    def test_forgot_password_security_question_flow(self):
        response = self.client.post(reverse("quen_mat_khau"), {"username_or_email": "user1"}, follow=True)
        self.assertRedirects(response, reverse("chon_phuong_thuc_khoi_phuc"))

        response = self.client.post(reverse("chon_phuong_thuc_khoi_phuc"), {"method": "security"}, follow=True)
        self.assertRedirects(response, reverse("khoi_phuc_bang_cau_hoi_bao_mat"))

        response = self.client.post(
            reverse("khoi_phuc_bang_cau_hoi_bao_mat"),
            {
                "answer_1": "Le Quy Don",
                "answer_2": "Milu",
                "new_password": "newpass123",
                "new_password2": "newpass123",
            },
            follow=True,
        )
        self.assertContains(response, "Đổi mật khẩu thành công bằng câu hỏi bảo mật")
        self.assertTrue(self.client.login(username="user1", password="newpass123"))


    def test_admin_can_create_and_edit_voucher(self):
        self.client.login(username="admin1", password="123456")
        response = self.client.post(
            reverse("admin_voucher_create"),
            {
                "code": "SUMMER20",
                "title": "Khuyen mai he",
                "description": "Giam 20% toan don",
                "discount_type": "percent",
                "value": 20,
                "min_order_value": 100000,
                "max_discount": 50000,
                "usage_limit": 10,
                "used_count": 0,
                "active": "on",
                "starts_at": "",
                "ends_at": "",
            },
            follow=True,
        )
        self.assertContains(response, "Đã tạo voucher SUMMER20")
        voucher = Voucher.objects.get(code="SUMMER20")
        response = self.client.post(
            reverse("admin_voucher_edit", args=[voucher.id]),
            {
                "code": "SUMMER20",
                "title": "Khuyen mai he moi",
                "description": "Giam 20% toan don",
                "discount_type": "percent",
                "value": 15,
                "min_order_value": 100000,
                "max_discount": 30000,
                "usage_limit": 15,
                "used_count": 1,
                "active": "on",
                "starts_at": "",
                "ends_at": "",
            },
            follow=True,
        )
        self.assertContains(response, "Đã cập nhật voucher SUMMER20")
        voucher.refresh_from_db()
        self.assertEqual(voucher.value, 15)
        self.assertEqual(voucher.used_count, 1)

    def test_admin_voucher_list_filters_by_status(self):
        Voucher.objects.create(code="ON1", discount_type="fixed", value=10000, active=True)
        Voucher.objects.create(code="OFF1", discount_type="fixed", value=10000, active=False)
        self.client.login(username="admin1", password="123456")
        response = self.client.get(reverse("admin_voucher_list"), {"active": "1"})
        ds = list(response.context["ds"])
        self.assertTrue(ds)
        self.assertTrue(all(v.active for v in ds))


    def test_flash_sale_price_is_prioritized_over_discount_price(self):
        now = timezone.now()
        self.sp_active.gia = 200000
        self.sp_active.gia_khuyen_mai = 170000
        self.sp_active.flash_sale_price = 150000
        self.sp_active.flash_sale_start = now - timedelta(hours=1)
        self.sp_active.flash_sale_end = now + timedelta(hours=2)
        self.sp_active.save()

        self.client.login(username="user1", password="123456")
        response = self.client.post(
            reverse("dat_hang", args=[self.sp_active.id]),
            {
                "ho_ten": "Nguyen Van A",
                "sdt": "0987654321",
                "dia_chi": "Ha Noi",
                "ghi_chu": "",
                "phuong_thuc_tt": "COD",
                "so_luong": 2,
            },
            follow=True,
        )

        self.assertContains(response, "Đặt hàng thành công")
        don = DonHang.objects.latest("id")
        self.assertEqual(don.tong_tien_goc, 300000)
        self.assertEqual(don.tong_tien, 300000)

    def test_home_shows_flash_sale_section(self):
        now = timezone.now()
        SanPham.objects.create(
            ten="Nhan flash",
            gia=300000,
            gia_khuyen_mai=250000,
            flash_sale_price=199000,
            flash_sale_start=now - timedelta(hours=1),
            flash_sale_end=now + timedelta(hours=5),
            trang_thai="active",
        )
        response = self.client.get(reverse("home"))
        self.assertContains(response, "Flash Sale")
        self.assertContains(response, "Nhan flash")
        self.assertContains(response, "199,000")

    def test_admin_can_create_product_with_flash_sale(self):
        self.client.login(username="admin1", password="123456")
        start = (timezone.now() + timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M")
        end = (timezone.now() + timedelta(hours=5)).strftime("%Y-%m-%dT%H:%M")
        response = self.client.post(
            reverse("admin_sanpham_create"),
            {
                "ten": "Day chuyen flash",
                "gia": 500000,
                "gia_khuyen_mai": 450000,
                "flash_sale_price": 399000,
                "flash_sale_start": start,
                "flash_sale_end": end,
                "mo_ta": "San pham flash sale",
                "trang_thai": "active",
            },
            follow=True,
        )
        self.assertContains(response, "Day chuyen flash")
        sp = SanPham.objects.get(ten="Day chuyen flash")
        self.assertEqual(sp.flash_sale_price, 399000)
        self.assertIsNotNone(sp.flash_sale_start)
        self.assertIsNotNone(sp.flash_sale_end)

    def test_stock_prevents_order_when_not_enough(self):
        self.sp_active.ton_kho = 1
        self.sp_active.save()
        self.client.login(username="user1", password="123456")
        response = self.client.post(
            reverse("dat_hang", args=[self.sp_active.id]),
            {
                "ho_ten": "Nguyen Van A",
                "sdt": "0987654321",
                "dia_chi": "Ha Noi",
                "ghi_chu": "",
                "phuong_thuc_tt": "COD",
                "so_luong": 2,
            },
            follow=True,
        )
        self.assertContains(response, "chỉ còn 1 trong kho", status_code=200)

    def test_stock_decreases_and_returns_on_cancel(self):
        self.sp_active.ton_kho = 5
        self.sp_active.save()
        self.client.login(username="user1", password="123456")
        self.client.post(
            reverse("dat_hang", args=[self.sp_active.id]),
            {
                "ho_ten": "Nguyen Van A",
                "sdt": "0987654321",
                "dia_chi": "Ha Noi",
                "ghi_chu": "",
                "phuong_thuc_tt": "COD",
                "so_luong": 2,
            },
            follow=True,
        )
        self.sp_active.refresh_from_db()
        self.assertEqual(self.sp_active.ton_kho, 3)
        order = DonHang.objects.latest("id")
        self.client.get(reverse("huy_don", args=[order.id]), follow=True)
        self.sp_active.refresh_from_db()
        self.assertEqual(self.sp_active.ton_kho, 5)

    def test_can_save_and_reuse_shipping_address(self):
        self.client.login(username="user1", password="123456")
        response = self.client.post(
            reverse("dat_hang", args=[self.sp_active.id]),
            {
                "ho_ten": "Nguyen Van A",
                "sdt": "0987654321",
                "dia_chi": "Ha Noi",
                "ghi_chu": "",
                "phuong_thuc_tt": "COD",
                "so_luong": 1,
                "save_address": "on",
                "set_default_address": "on",
                "address_label": "Nha rieng",
            },
            follow=True,
        )
        self.assertContains(response, "Đặt hàng thành công")
        self.assertEqual(self.user.saved_addresses.count(), 1)
        addr = self.user.saved_addresses.first()
        self.assertEqual(addr.label, "Nha rieng")
        response = self.client.get(reverse("dat_hang", args=[self.sp_active.id]))
        self.assertContains(response, "Nha rieng")
        self.assertContains(response, "Ha Noi")

    def test_order_status_history_created(self):
        self.client.login(username="user1", password="123456")
        self.client.post(
            reverse("dat_hang", args=[self.sp_active.id]),
            {
                "ho_ten": "Nguyen Van A",
                "sdt": "0987654321",
                "dia_chi": "Ha Noi",
                "ghi_chu": "",
                "phuong_thuc_tt": "COD",
                "so_luong": 1,
            },
            follow=True,
        )
        order = DonHang.objects.latest("id")
        self.assertEqual(order.status_histories.count(), 1)
        self.client.get(reverse("xac_nhan_don", args=[order.id]), follow=True)
        order.refresh_from_db()
        self.assertEqual(order.status_histories.count(), 2)
        self.assertEqual(order.status_histories.last().new_status, "Confirmed")

    def test_admin_can_adjust_inventory(self):
        self.sp_active.ton_kho = 4
        self.sp_active.save()
        self.client.login(username="admin1", password="123456")
        response = self.client.post(
            reverse("admin_inventory_adjust", args=[self.sp_active.id]),
            {"action": "increase", "quantity": 6, "note": "Nhap them lo hang moi"},
            follow=True,
        )
        self.assertContains(response, "Đã cập nhật tồn kho")
        self.sp_active.refresh_from_db()
        self.assertEqual(self.sp_active.ton_kho, 10)
        history = InventoryHistory.objects.filter(san_pham=self.sp_active).first()
        self.assertIsNotNone(history)
        self.assertEqual(history.change_type, "manual_in")
        self.assertEqual(history.new_stock, 10)

    def test_inventory_list_filters_low_stock(self):
        self.sp_active.ton_kho = 3
        self.sp_active.save()
        SanPham.objects.create(ten="Het hang", gia=100000, ton_kho=0, trang_thai="active")
        SanPham.objects.create(ten="Con nhieu", gia=100000, ton_kho=20, trang_thai="active")
        self.client.login(username="admin1", password="123456")
        response = self.client.get(reverse("admin_inventory_list"), {"stock_status": "low"})
        self.assertContains(response, self.sp_active.ten)
        self.assertNotContains(response, "Het hang")
        self.assertNotContains(response, "Con nhieu")

    def test_order_stock_changes_create_inventory_history(self):
        self.sp_active.ton_kho = 5
        self.sp_active.save()
        self.client.login(username="user1", password="123456")
        self.client.post(
            reverse("dat_hang", args=[self.sp_active.id]),
            {
                "ho_ten": "Nguyen Van A",
                "sdt": "0987654321",
                "dia_chi": "Ha Noi",
                "ghi_chu": "",
                "phuong_thuc_tt": "COD",
                "so_luong": 2,
            },
            follow=True,
        )
        order = DonHang.objects.latest("id")
        logs = InventoryHistory.objects.filter(san_pham=self.sp_active).order_by("created_at", "id")
        self.assertTrue(logs.filter(change_type="order_out").exists())
        self.client.get(reverse("huy_don", args=[order.id]), follow=True)
        self.assertTrue(InventoryHistory.objects.filter(san_pham=self.sp_active, change_type="order_return", order=order).exists())


    def test_admin_can_create_supplier(self):
        self.client.login(username="admin1", password="123456")
        response = self.client.post(
            reverse("admin_supplier_create"),
            {
                "ten": "Cong ty ABC",
                "sdt": "0909999999",
                "email": "abc@example.com",
                "dia_chi": "Ha Noi",
                "ghi_chu": "NCC nhap vang",
                "active": "on",
            },
            follow=True,
        )
        self.assertContains(response, "Đã thêm nhà cung cấp")
        self.assertTrue(NhaCungCap.objects.filter(ten="Cong ty ABC").exists())

    def test_admin_can_create_and_receive_purchase_receipt(self):
        supplier = NhaCungCap.objects.create(ten="NCC A")
        old_stock = self.sp_active.ton_kho
        self.client.login(username="admin1", password="123456")
        response = self.client.post(
            reverse("admin_receipt_create"),
            {
                "supplier": supplier.id,
                "note": "Nhap them cho showroom",
                "items-TOTAL_FORMS": "3",
                "items-INITIAL_FORMS": "0",
                "items-MIN_NUM_FORMS": "0",
                "items-MAX_NUM_FORMS": "1000",
                "items-0-product": self.sp_active.id,
                "items-0-quantity": "5",
                "items-0-unit_price": "70000",
                "items-0-batch_code": "LO-001",
                "items-0-note": "Lo dau tien",
                "items-1-product": "",
                "items-1-quantity": "",
                "items-1-unit_price": "",
                "items-1-batch_code": "",
                "items-1-note": "",
                "items-2-product": "",
                "items-2-quantity": "",
                "items-2-unit_price": "",
                "items-2-batch_code": "",
                "items-2-note": "",
            },
            follow=True,
        )
        self.assertContains(response, "Đã tạo phiếu nhập kho")
        receipt = PhieuNhapKho.objects.get()

        response = self.client.post(reverse("admin_receipt_receive", args=[receipt.id]), follow=True)
        self.assertContains(response, "Đã nhập kho thành công")
        receipt.refresh_from_db()
        self.sp_active.refresh_from_db()

        self.assertEqual(receipt.status, "received")
        self.assertEqual(self.sp_active.ton_kho, old_stock + 5)
        self.assertEqual(InventoryBatch.objects.filter(receipt=receipt, batch_code="LO-001").count(), 1)
        self.assertTrue(InventoryHistory.objects.filter(san_pham=self.sp_active, change_type="receipt_in").exists())

    def test_batch_list_can_filter_by_batch_code(self):
        supplier = NhaCungCap.objects.create(ten="NCC Batch")
        receipt = PhieuNhapKho.objects.create(code="PNKTEST001", supplier=supplier, created_by=self.admin, status="received", imported_at=timezone.now())
        InventoryBatch.objects.create(
            san_pham=self.sp_active,
            supplier=supplier,
            receipt=receipt,
            receipt_item=receipt.items.create(san_pham=self.sp_active, so_luong=2, don_gia_nhap=50000, batch_code="BATCH-XYZ"),
            batch_code="BATCH-XYZ",
            so_luong_nhap=2,
            so_luong_con_lai=2,
            don_gia_nhap=50000,
            created_by=self.admin,
        )
        self.client.login(username="admin1", password="123456")
        response = self.client.get(reverse("admin_batch_list"), {"q": "BATCH-XYZ"})
        self.assertContains(response, "BATCH-XYZ")


    @override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
    def test_order_status_change_sends_email_notification(self):
        self.user.email = "buyer@example.com"
        self.user.save(update_fields=["email"])
        order = DonHang.objects.create(
            nguoi_dat=self.user,
            san_pham=self.sp_active,
            ho_ten="Nguyen Van A",
            sdt="0987654321",
            dia_chi="Thai Nguyen",
            ghi_chu="",
            phuong_thuc_tt="COD",
            so_luong=1,
            tong_tien=100000,
            trang_thai="Pending",
        )
        self.client.login(username="user1", password="123456")
        response = self.client.get(reverse("xac_nhan_don", args=[order.id]), follow=True)
        self.assertContains(response, "Đã cập nhật trạng thái đơn")
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("Don hang", mail.outbox[0].subject)
        self.assertIn("Confirmed", mail.outbox[0].body)

    def test_home_advanced_price_filter(self):
        SanPham.objects.create(ten="Nhan Gia Re", gia=50000, gia_khuyen_mai=45000, trang_thai="active")
        SanPham.objects.create(ten="Nhan Cao Cap", gia=250000, trang_thai="active")
        response = self.client.get(reverse("home"), {"min_price": 40000, "max_price": 100000, "sale_only": 1})
        body = response.content.decode()
        self.assertIn("Nhan Gia Re", body)
        self.assertNotIn("Nhan Cao Cap", body)

    def test_product_detail_shows_gallery_and_reviews(self):
        ProductImage.objects.create(san_pham=self.sp_active, image=SimpleUploadedFile("g1.jpg", b"filecontent", content_type="image/jpeg"), caption="Goc 1")
        ProductReview.objects.create(san_pham=self.sp_active, user=self.user, rating=5, title="Rat dep", comment="Mau dep")
        response = self.client.get(reverse("chi_tiet_san_pham", args=[self.sp_active.id]))
        self.assertContains(response, "Goc 1")
        self.assertContains(response, "Rat dep")
        self.assertContains(response, "Mau dep")

    def test_api_products_and_create_review(self):
        response = self.client.get(reverse("api_products"))
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(any(item["ten"] == self.sp_active.ten for item in payload))

        self.client.login(username="user1", password="123456")
        response = self.client.post(
            reverse("api_product_review_create", args=[self.sp_active.id]),
            data={"rating": 4, "title": "On", "comment": "Dep"},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 201)
        self.assertTrue(ProductReview.objects.filter(san_pham=self.sp_active, user=self.user, rating=4).exists())

        response = self.client.get(reverse("api_product_detail", args=[self.sp_active.id]))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["id"], self.sp_active.id)
