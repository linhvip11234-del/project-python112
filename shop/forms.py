"""Form layer: gom validate input, kiểm tra file upload và chuẩn hoá dữ liệu."""

from __future__ import annotations

from django import forms
from django.forms import formset_factory
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError

from .models import DonHang, InventoryBatch, NhaCungCap, PhieuNhapKho, ProductReview, SECURITY_QUESTION_CHOICES, SanPham, SavedAddress, Voucher
from .services import calculate_order_total, can_transition


ALLOWED_IMAGE_EXTENSIONS = {"jpg", "jpeg", "png", "webp", "gif"}
MAX_UPLOAD_SIZE = 2 * 1024 * 1024  # 2MB


class MultipleFileInput(forms.ClearableFileInput):
    allow_multiple_selected = True


class MultipleFileField(forms.FileField):
    widget = MultipleFileInput

    def clean(self, data, initial=None):
        single_clean = super().clean
        if data in self.empty_values:
            return []
        if isinstance(data, (list, tuple)):
            return [single_clean(item, initial) for item in data]
        return [single_clean(data, initial)]


class BaseStyledForm(forms.Form):
    """Form thường dùng class CSS chung."""

    def _apply_common_css(self):
        for field in self.fields.values():
            css = field.widget.attrs.get("class", "")
            field.widget.attrs["class"] = f"input {css}".strip()


# Form đăng ký tài khoản khách hàng
class RegistrationForm(BaseStyledForm):
    username = forms.CharField(max_length=150, label="Tên đăng nhập")
    email = forms.EmailField(required=False, label="Email")
    password = forms.CharField(min_length=6, label="Mật khẩu", widget=forms.PasswordInput(attrs={"placeholder": "******"}))
    password2 = forms.CharField(min_length=6, label="Nhập lại mật khẩu", widget=forms.PasswordInput(attrs={"placeholder": "******"}))
    security_question_1 = forms.ChoiceField(label="Câu hỏi bảo mật 1", choices=SECURITY_QUESTION_CHOICES)
    security_answer_1 = forms.CharField(max_length=255, label="Câu trả lời 1")
    security_question_2 = forms.ChoiceField(label="Câu hỏi bảo mật 2", choices=SECURITY_QUESTION_CHOICES)
    security_answer_2 = forms.CharField(max_length=255, label="Câu trả lời 2")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._apply_common_css()
        for name in ["security_answer_1", "security_answer_2", "username", "email"]:
            self.fields[name].widget.attrs.setdefault("placeholder", "Nhập thông tin")

    def clean_username(self):
        username = (self.cleaned_data.get("username") or "").strip()
        if not username:
            raise ValidationError("Nhập tên đăng nhập.")
        if User.objects.filter(username__iexact=username).exists():
            raise ValidationError("Tên đăng nhập đã tồn tại.")
        return username

    def clean_email(self):
        email = (self.cleaned_data.get("email") or "").strip().lower()
        if email and User.objects.filter(email__iexact=email).exists():
            raise ValidationError("Email này đã được liên kết với tài khoản khác.")
        return email

    def clean_ton_kho(self):
        ton_kho = self.cleaned_data.get("ton_kho")
        if ton_kho in (None, ""):
            return 10
        if int(ton_kho) < 0:
            raise ValidationError("Tồn kho phải là số >= 0.")
        return ton_kho

    def clean(self):
        cleaned_data = super().clean()
        password = (cleaned_data.get("password") or "").strip()
        password2 = (cleaned_data.get("password2") or "").strip()
        q1 = cleaned_data.get("security_question_1")
        q2 = cleaned_data.get("security_question_2")
        a1 = (cleaned_data.get("security_answer_1") or "").strip()
        a2 = (cleaned_data.get("security_answer_2") or "").strip()
        if password and password2 and password != password2:
            self.add_error("password2", ValidationError("Mật khẩu nhập lại không khớp."))
        if q1 and q2 and q1 == q2:
            self.add_error("security_question_2", ValidationError("Vui lòng chọn 2 câu hỏi bảo mật khác nhau."))
        if not a1:
            self.add_error("security_answer_1", ValidationError("Vui lòng nhập câu trả lời cho câu hỏi bảo mật 1."))
        if not a2:
            self.add_error("security_answer_2", ValidationError("Vui lòng nhập câu trả lời cho câu hỏi bảo mật 2."))
        return cleaned_data


# Form quản trị sản phẩm
class SanPhamForm(forms.ModelForm):
    """Form cho CRUD sản phẩm, có validate ảnh upload."""

    anh = forms.FileField(required=False, widget=forms.ClearableFileInput(attrs={"class": "input", "accept": ".jpg,.jpeg,.png,.webp,.gif,image/*"}))
    gallery_images = MultipleFileField(required=False, widget=MultipleFileInput(attrs={"class": "input", "accept": ".jpg,.jpeg,.png,.webp,.gif,image/*", "multiple": True}))

    class Meta:
        model = SanPham
        fields = ["ten", "gia", "gia_khuyen_mai", "flash_sale_price", "flash_sale_start", "flash_sale_end", "ton_kho", "search_tags", "mo_ta", "trang_thai", "anh"]
        widgets = {
            "ten": forms.TextInput(attrs={"class": "input", "placeholder": "Tên sản phẩm"}),
            "gia": forms.NumberInput(attrs={"class": "input", "min": "0", "placeholder": "Giá gốc (VND)"}),
            "gia_khuyen_mai": forms.NumberInput(attrs={"class": "input", "min": "0", "placeholder": "Để trống nếu không giảm giá"}),
            "flash_sale_price": forms.NumberInput(attrs={"class": "input", "min": "0", "placeholder": "Để trống nếu không bật flash sale"}),
            "flash_sale_start": forms.DateTimeInput(attrs={"class": "input", "type": "datetime-local"}, format="%Y-%m-%dT%H:%M"),
            "flash_sale_end": forms.DateTimeInput(attrs={"class": "input", "type": "datetime-local"}, format="%Y-%m-%dT%H:%M"),
            "ton_kho": forms.NumberInput(attrs={"class": "input", "min": "0", "placeholder": "Số lượng tồn kho"}),
            "search_tags": forms.TextInput(attrs={"class": "input", "placeholder": "VD: nhan, vang trang, kim cuong"}),
            "mo_ta": forms.Textarea(attrs={"class": "input", "placeholder": "Mô tả chi tiết sản phẩm", "rows": 5}),
            "trang_thai": forms.Select(attrs={"class": "input"}),
        }

    def clean_gia(self):
        gia = self.cleaned_data["gia"]
        if gia is None or int(gia) < 0:
            raise ValidationError("Giá phải là số >= 0.")
        return gia

    def clean_gia_khuyen_mai(self):
        gia_khuyen_mai = self.cleaned_data.get("gia_khuyen_mai")
        if gia_khuyen_mai in (None, ""):
            return None
        if int(gia_khuyen_mai) < 0:
            raise ValidationError("Giá khuyến mại phải là số >= 0.")
        return gia_khuyen_mai

    def clean_flash_sale_price(self):
        flash_sale_price = self.cleaned_data.get("flash_sale_price")
        if flash_sale_price in (None, ""):
            return None
        if int(flash_sale_price) < 0:
            raise ValidationError("Giá flash sale phải là số >= 0.")
        return flash_sale_price

    def clean(self):
        cleaned_data = super().clean()
        gia = cleaned_data.get("gia")
        gia_khuyen_mai = cleaned_data.get("gia_khuyen_mai")
        flash_sale_price = cleaned_data.get("flash_sale_price")
        flash_sale_start = cleaned_data.get("flash_sale_start")
        flash_sale_end = cleaned_data.get("flash_sale_end")
        if gia is not None and gia_khuyen_mai not in (None, "") and int(gia_khuyen_mai) >= int(gia):
            self.add_error("gia_khuyen_mai", ValidationError("Giá khuyến mại phải nhỏ hơn giá gốc."))
        if gia is not None and flash_sale_price not in (None, "") and int(flash_sale_price) >= int(gia):
            self.add_error("flash_sale_price", ValidationError("Giá flash sale phải nhỏ hơn giá gốc."))
        if flash_sale_price not in (None, "") and not flash_sale_start:
            self.add_error("flash_sale_start", ValidationError("Vui lòng chọn thời gian bắt đầu flash sale."))
        if flash_sale_price not in (None, "") and not flash_sale_end:
            self.add_error("flash_sale_end", ValidationError("Vui lòng chọn thời gian kết thúc flash sale."))
        if (flash_sale_start and not flash_sale_price) or (flash_sale_end and not flash_sale_price):
            self.add_error("flash_sale_price", ValidationError("Vui lòng nhập giá flash sale khi đã chọn thời gian."))
        if flash_sale_start and flash_sale_end and flash_sale_end <= flash_sale_start:
            self.add_error("flash_sale_end", ValidationError("Thời gian kết thúc phải sau thời gian bắt đầu."))
        return cleaned_data

    def clean_search_tags(self):
        return ", ".join([part.strip() for part in (self.cleaned_data.get("search_tags") or "").split(",") if part.strip()])

    def clean_gallery_images(self):
        images = self.cleaned_data.get("gallery_images") or []
        for image in images:
            ten_file = getattr(image, "name", "")
            ext = ten_file.rsplit(".", 1)[-1].lower() if "." in ten_file else ""
            if ext not in ALLOWED_IMAGE_EXTENSIONS:
                raise ValidationError("Ảnh gallery chỉ cho phép JPG, JPEG, PNG, WEBP hoặc GIF.")
            if getattr(image, "size", 0) > MAX_UPLOAD_SIZE:
                raise ValidationError("Mỗi ảnh gallery phải nhỏ hơn 2MB.")
            content_type = getattr(image, "content_type", "")
            if content_type and not content_type.startswith("image/"):
                raise ValidationError("Gallery chỉ nhận tệp ảnh hợp lệ.")
        return images

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["ton_kho"].required = False
        self.fields["ton_kho"].initial = self.initial.get("ton_kho") or getattr(self.instance, "ton_kho", 10) or 10
        for name in ["flash_sale_start", "flash_sale_end"]:
            value = self.initial.get(name) or getattr(self.instance, name, None)
            if value:
                self.initial[name] = value.strftime("%Y-%m-%dT%H:%M")

    def clean_anh(self):
        anh = self.cleaned_data.get("anh")
        if not anh:
            return anh

        ten_file = getattr(anh, "name", "")
        ext = ten_file.rsplit(".", 1)[-1].lower() if "." in ten_file else ""
        if ext not in ALLOWED_IMAGE_EXTENSIONS:
            raise ValidationError("Chỉ cho phép ảnh JPG, JPEG, PNG, WEBP hoặc GIF.")

        if getattr(anh, "size", 0) > MAX_UPLOAD_SIZE:
            raise ValidationError("Ảnh vượt quá 2MB. Vui lòng chọn ảnh nhỏ hơn.")

        content_type = getattr(anh, "content_type", "")
        if content_type and not content_type.startswith("image/"):
            raise ValidationError("Tệp tải lên phải là ảnh hợp lệ.")
        return anh


# Form nhập thông tin đặt hàng / người nhận
class DatHangForm(BaseStyledForm):
    """Form checkout cho người dùng đặt hàng."""

    saved_address_id = forms.ChoiceField(required=False, label="Địa chỉ đã lưu")
    ho_ten = forms.CharField(max_length=100, widget=forms.TextInput(attrs={"placeholder": "Ví dụ: Trần Bình Minh"}))
    sdt = forms.CharField(max_length=20, widget=forms.TextInput(attrs={"placeholder": "Ví dụ: 0987654321"}))
    dia_chi = forms.CharField(max_length=255, widget=forms.TextInput(attrs={"placeholder": "Số nhà, đường, phường/xã, quận/huyện, tỉnh"}))
    ghi_chu = forms.CharField(max_length=255, required=False, widget=forms.TextInput(attrs={"placeholder": "Ví dụ: giao giờ hành chính"}))
    phuong_thuc_tt = forms.ChoiceField(choices=DonHang.PHUONG_THUC_TT, widget=forms.Select())
    so_luong = forms.IntegerField(min_value=1, widget=forms.NumberInput(attrs={"min": "1", "max": "99"}))
    voucher_code = forms.CharField(max_length=30, required=False, widget=forms.TextInput(attrs={"placeholder": "Ví dụ: GIAM10"}))
    save_address = forms.BooleanField(required=False, label="Lưu địa chỉ này cho lần sau")
    set_default_address = forms.BooleanField(required=False, label="Đặt làm địa chỉ mặc định")
    address_label = forms.CharField(max_length=100, required=False, widget=forms.TextInput(attrs={"placeholder": "Ví dụ: Nhà riêng, Công ty"}))

    def __init__(self, *args, user=None, **kwargs):
        self.user = user
        super().__init__(*args, **kwargs)
        self._apply_common_css()
        choices = [("", "-- Chọn địa chỉ đã lưu --")]
        if getattr(user, "is_authenticated", False):
            choices += [(str(addr.id), f"{addr.label or 'Địa chỉ'} - {addr.ho_ten} - {addr.sdt}") for addr in user.saved_addresses.all()[:20]]
        self.fields["saved_address_id"].choices = choices

    def clean_voucher_code(self):
        return (self.cleaned_data.get("voucher_code") or "").strip().upper()

    def clean_saved_address_id(self):
        value = (self.cleaned_data.get("saved_address_id") or "").strip()
        if not value:
            return None
        if not getattr(self.user, "is_authenticated", False):
            raise ValidationError("Bạn cần đăng nhập để dùng địa chỉ đã lưu.")
        try:
            addr = SavedAddress.objects.get(id=int(value), user=self.user)
        except Exception:
            raise ValidationError("Địa chỉ đã lưu không hợp lệ.")
        return addr

    def clean_sdt(self):
        sdt = (self.cleaned_data.get("sdt") or "").strip()
        if not sdt.isdigit() or len(sdt) < 9:
            raise ValidationError("SĐT không hợp lệ (chỉ số, tối thiểu 9 chữ số).")
        return sdt


class AdminDonHangForm(forms.ModelForm):
    """Form cho Admin CRUD đơn hàng."""

    class Meta:
        model = DonHang
        fields = [
            "nguoi_dat",
            "san_pham",
            "ho_ten",
            "sdt",
            "dia_chi",
            "ghi_chu",
            "phuong_thuc_tt",
            "so_luong",
            "trang_thai",
        ]
        widgets = {
            "nguoi_dat": forms.Select(attrs={"class": "input"}),
            "san_pham": forms.Select(attrs={"class": "input"}),
            "ho_ten": forms.TextInput(attrs={"class": "input"}),
            "sdt": forms.TextInput(attrs={"class": "input"}),
            "dia_chi": forms.TextInput(attrs={"class": "input"}),
            "ghi_chu": forms.TextInput(attrs={"class": "input"}),
            "phuong_thuc_tt": forms.Select(attrs={"class": "input"}),
            "so_luong": forms.NumberInput(attrs={"class": "input", "min": "1", "max": "999"}),
            "trang_thai": forms.Select(attrs={"class": "input"}),
        }

    def clean_voucher_code(self):
        return (self.cleaned_data.get("voucher_code") or "").strip().upper()

    def clean_sdt(self):
        sdt = (self.cleaned_data.get("sdt") or "").strip()
        if not sdt.isdigit() or len(sdt) < 9:
            raise ValidationError("SĐT không hợp lệ (chỉ số, tối thiểu 9 chữ số).")
        return sdt

    def clean_so_luong(self):
        so_luong = self.cleaned_data.get("so_luong")
        if so_luong is None or int(so_luong) <= 0:
            raise ValidationError("Số lượng phải lớn hơn 0.")
        return so_luong

    def clean(self):
        cleaned_data = super().clean()
        instance = self.instance
        new_status = cleaned_data.get("trang_thai")

        if instance and instance.pk and new_status and new_status != instance.trang_thai:
            if not can_transition(instance.trang_thai, new_status, actor_role="admin"):
                self.add_error(
                    "trang_thai",
                    ValidationError(
                        f"Không thể chuyển từ {instance.trang_thai} sang {new_status} theo luồng duyệt hiện tại."
                    ),
                )
        return cleaned_data

    def save(self, commit=True):
        order = super().save(commit=False)
        order.tong_tien = calculate_order_total(order.san_pham, order.so_luong)
        if commit:
            order.save()
        return order


# Form quản trị voucher
class VoucherAdminForm(forms.ModelForm):
    class Meta:
        model = Voucher
        fields = [
            "code",
            "title",
            "description",
            "discount_type",
            "value",
            "min_order_value",
            "max_discount",
            "usage_limit",
            "used_count",
            "active",
            "starts_at",
            "ends_at",
        ]
        widgets = {
            "code": forms.TextInput(attrs={"class": "input", "placeholder": "Ví dụ: GIAM10"}),
            "title": forms.TextInput(attrs={"class": "input", "placeholder": "Tên hiển thị voucher"}),
            "description": forms.TextInput(attrs={"class": "input", "placeholder": "Mô tả ngắn voucher"}),
            "discount_type": forms.Select(attrs={"class": "input"}),
            "value": forms.NumberInput(attrs={"class": "input", "min": "0"}),
            "min_order_value": forms.NumberInput(attrs={"class": "input", "min": "0"}),
            "max_discount": forms.NumberInput(attrs={"class": "input", "min": "0"}),
            "usage_limit": forms.NumberInput(attrs={"class": "input", "min": "0"}),
            "used_count": forms.NumberInput(attrs={"class": "input", "min": "0"}),
            "active": forms.CheckboxInput(attrs={"style": "width:18px;height:18px;"}),
            "starts_at": forms.DateTimeInput(attrs={"class": "input", "type": "datetime-local"}, format="%Y-%m-%dT%H:%M"),
            "ends_at": forms.DateTimeInput(attrs={"class": "input", "type": "datetime-local"}, format="%Y-%m-%dT%H:%M"),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name in ["starts_at", "ends_at"]:
            value = self.initial.get(name) or getattr(self.instance, name, None)
            if value:
                self.initial[name] = value.strftime("%Y-%m-%dT%H:%M")

    def clean_code(self):
        code = (self.cleaned_data.get("code") or "").strip().upper()
        if not code:
            raise ValidationError("Vui lòng nhập mã voucher.")
        return code

    def clean_value(self):
        value = self.cleaned_data.get("value")
        if value is None or int(value) < 0:
            raise ValidationError("Giá trị giảm phải >= 0.")
        return value

    def clean_min_order_value(self):
        value = self.cleaned_data.get("min_order_value")
        if value is None or int(value) < 0:
            raise ValidationError("Đơn tối thiểu phải >= 0.")
        return value

    def clean_max_discount(self):
        value = self.cleaned_data.get("max_discount")
        if value is None or int(value) < 0:
            raise ValidationError("Giảm tối đa phải >= 0.")
        return value

    def clean_usage_limit(self):
        value = self.cleaned_data.get("usage_limit")
        if value is None or int(value) < 0:
            raise ValidationError("Giới hạn lượt dùng phải >= 0.")
        return value

    def clean_used_count(self):
        value = self.cleaned_data.get("used_count")
        if value is None or int(value) < 0:
            raise ValidationError("Số lượt đã dùng phải >= 0.")
        return value

    def clean(self):
        cleaned_data = super().clean()
        starts_at = cleaned_data.get("starts_at")
        ends_at = cleaned_data.get("ends_at")
        discount_type = cleaned_data.get("discount_type")
        value = int(cleaned_data.get("value") or 0)
        max_discount = int(cleaned_data.get("max_discount") or 0)
        usage_limit = int(cleaned_data.get("usage_limit") or 0)
        used_count = int(cleaned_data.get("used_count") or 0)

        if starts_at and ends_at and starts_at > ends_at:
            self.add_error("ends_at", ValidationError("Thời gian kết thúc phải sau thời gian bắt đầu."))
        if discount_type == "percent" and value > 100:
            self.add_error("value", ValidationError("Voucher giảm theo % không được vượt quá 100."))
        if discount_type == "fixed" and max_discount and max_discount < value:
            self.add_error("max_discount", ValidationError("Với voucher giảm cố định, giảm tối đa nên >= giá trị giảm."))
        if usage_limit and used_count > usage_limit:
            self.add_error("used_count", ValidationError("Số lượt đã dùng không được lớn hơn giới hạn sử dụng."))
        return cleaned_data


class AdminInventoryAdjustForm(BaseStyledForm):
    ACTION_CHOICES = [
        ("set", "Đặt lại tồn kho"),
        ("increase", "Nhập thêm"),
        ("decrease", "Xuất bớt"),
    ]

    action = forms.ChoiceField(label="Kiểu cập nhật", choices=ACTION_CHOICES, widget=forms.Select(attrs={"class": "input"}))
    quantity = forms.IntegerField(label="Số lượng", min_value=0, widget=forms.NumberInput(attrs={"class": "input", "min": "0"}))
    note = forms.CharField(label="Ghi chú", max_length=255, required=False, widget=forms.TextInput(attrs={"class": "input", "placeholder": "Ví dụ: kiểm kho cuối ngày, nhập thêm hàng mới..."}))

    def clean_quantity(self):
        quantity = self.cleaned_data.get("quantity")
        if quantity is None or int(quantity) < 0:
            raise ValidationError("Số lượng phải >= 0.")
        return int(quantity)

    def clean(self):
        cleaned_data = super().clean()
        action = cleaned_data.get("action")
        quantity = int(cleaned_data.get("quantity") or 0)
        if action in {"increase", "decrease"} and quantity <= 0:
            self.add_error("quantity", ValidationError("Vui lòng nhập số lượng lớn hơn 0 cho thao tác tăng/giảm kho."))
        return cleaned_data


class ForgotPasswordRequestForm(BaseStyledForm):
    """Nhập username hoặc email để khởi tạo luồng quên mật khẩu."""

    username_or_email = forms.CharField(
        label="Tên đăng nhập hoặc email",
        max_length=150,
        widget=forms.TextInput(attrs={"placeholder": "nhập username hoặc email"}),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._apply_common_css()




class ProductReviewForm(BaseStyledForm):
    rating = forms.ChoiceField(choices=[(str(i), f"{i} sao") for i in range(5, 0, -1)], initial="5")
    title = forms.CharField(max_length=120, required=False, widget=forms.TextInput(attrs={"placeholder": "Tiêu đề đánh giá (không bắt buộc)"}))
    comment = forms.CharField(required=False, widget=forms.Textarea(attrs={"placeholder": "Chia sẻ trải nghiệm của bạn về sản phẩm", "rows": 4}))

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._apply_common_css()

    def clean_rating(self):
        rating = int(self.cleaned_data.get("rating") or 0)
        if rating < 1 or rating > 5:
            raise ValidationError("Số sao phải từ 1 đến 5.")
        return rating

    def clean(self):
        cleaned_data = super().clean()
        title = (cleaned_data.get("title") or "").strip()
        comment = (cleaned_data.get("comment") or "").strip()
        if not title and not comment:
            self.add_error("comment", ValidationError("Vui lòng nhập nội dung hoặc tiêu đề đánh giá."))
        cleaned_data["title"] = title
        cleaned_data["comment"] = comment
        return cleaned_data


class ForgotPasswordOTPForm(BaseStyledForm):
    """Nhập OTP và mật khẩu mới."""

    otp = forms.CharField(
        label="Mã OTP",
        max_length=6,
        min_length=6,
        widget=forms.TextInput(attrs={"placeholder": "6 số", "inputmode": "numeric", "autocomplete": "one-time-code"}),
    )
    new_password = forms.CharField(
        label="Mật khẩu mới",
        min_length=6,
        widget=forms.PasswordInput(attrs={"placeholder": "Nhập mật khẩu mới"}),
    )
    new_password2 = forms.CharField(
        label="Nhập lại mật khẩu mới",
        min_length=6,
        widget=forms.PasswordInput(attrs={"placeholder": "Nhập lại mật khẩu mới"}),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._apply_common_css()

    def clean_otp(self):
        otp = (self.cleaned_data.get("otp") or "").strip()
        if not otp.isdigit() or len(otp) != 6:
            raise ValidationError("OTP phải gồm đúng 6 chữ số.")
        return otp

    def clean(self):
        cleaned_data = super().clean()
        p1 = (cleaned_data.get("new_password") or "").strip()
        p2 = (cleaned_data.get("new_password2") or "").strip()
        if p1 and p2 and p1 != p2:
            self.add_error("new_password2", ValidationError("Mật khẩu nhập lại không khớp."))
        return cleaned_data


class ForgotPasswordSecurityForm(BaseStyledForm):
    answer_1 = forms.CharField(max_length=255, label="Câu trả lời câu hỏi 1")
    answer_2 = forms.CharField(max_length=255, label="Câu trả lời câu hỏi 2")
    new_password = forms.CharField(min_length=6, label="Mật khẩu mới", widget=forms.PasswordInput(attrs={"placeholder": "Nhập mật khẩu mới"}))
    new_password2 = forms.CharField(min_length=6, label="Nhập lại mật khẩu mới", widget=forms.PasswordInput(attrs={"placeholder": "Nhập lại mật khẩu mới"}))

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._apply_common_css()

    def clean(self):
        cleaned_data = super().clean()
        p1 = (cleaned_data.get("new_password") or "").strip()
        p2 = (cleaned_data.get("new_password2") or "").strip()
        if p1 and p2 and p1 != p2:
            self.add_error("new_password2", ValidationError("Mật khẩu nhập lại không khớp."))
        return cleaned_data


class AdminUserForm(BaseStyledForm):
    """Form quản lý user với role User/Admin."""

    ROLE_CHOICES = [
        ("user", "User"),
        ("admin", "Admin"),
    ]

    username = forms.CharField(max_length=150)
    email = forms.EmailField(required=False)
    password = forms.CharField(required=False, widget=forms.PasswordInput(render_value=True))
    role = forms.ChoiceField(choices=ROLE_CHOICES, initial="user")
    is_active = forms.BooleanField(required=False, initial=True)

    def __init__(self, *args, instance: User | None = None, **kwargs):
        self.instance = instance
        super().__init__(*args, **kwargs)
        self._apply_common_css()
        self.fields["password"].help_text = "Bỏ trống nếu không đổi mật khẩu."

        if instance:
            self.initial.update(
                {
                    "username": instance.username,
                    "email": instance.email,
                    "role": "admin" if instance.is_staff else "user",
                    "is_active": instance.is_active,
                }
            )

    def clean_username(self):
        username = (self.cleaned_data.get("username") or "").strip()
        qs = User.objects.filter(username=username)
        if self.instance and self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise ValidationError("Username đã tồn tại.")
        return username

    def clean_password(self):
        password = (self.cleaned_data.get("password") or "").strip()
        if not self.instance and not password:
            raise ValidationError("Vui lòng nhập password.")
        return password

    def save(self) -> User:
        if self.instance:
            user = self.instance
        else:
            user = User()

        user.username = self.cleaned_data["username"]
        user.email = self.cleaned_data.get("email", "")
        user.is_staff = self.cleaned_data["role"] == "admin"
        user.is_active = bool(self.cleaned_data.get("is_active"))

        password = self.cleaned_data.get("password", "")
        if password:
            user.set_password(password)
        elif not user.pk:
            raise ValidationError("Password là bắt buộc khi tạo mới.")

        user.save()
        return user


class SupplierForm(forms.ModelForm):
    class Meta:
        model = NhaCungCap
        fields = ["ten", "sdt", "email", "dia_chi", "ghi_chu", "active"]
        widgets = {
            "ten": forms.TextInput(attrs={"class": "input", "placeholder": "Tên nhà cung cấp"}),
            "sdt": forms.TextInput(attrs={"class": "input", "placeholder": "Số điện thoại"}),
            "email": forms.EmailInput(attrs={"class": "input", "placeholder": "Email liên hệ"}),
            "dia_chi": forms.TextInput(attrs={"class": "input", "placeholder": "Địa chỉ"}),
            "ghi_chu": forms.TextInput(attrs={"class": "input", "placeholder": "Ghi chú thêm"}),
            "active": forms.CheckboxInput(attrs={"style": "width:18px;height:18px;"}),
        }

    def clean_ten(self):
        ten = (self.cleaned_data.get("ten") or "").strip()
        if not ten:
            raise ValidationError("Vui lòng nhập tên nhà cung cấp.")
        return ten


class PurchaseReceiptForm(forms.ModelForm):
    class Meta:
        model = PhieuNhapKho
        fields = ["supplier", "note"]
        widgets = {
            "supplier": forms.Select(attrs={"class": "input"}),
            "note": forms.TextInput(attrs={"class": "input", "placeholder": "Ghi chú cho phiếu nhập kho"}),
        }


class PurchaseReceiptItemForm(BaseStyledForm):
    product = forms.ModelChoiceField(
        label="Sản phẩm",
        queryset=SanPham.objects.all().order_by("ten"),
        widget=forms.Select(attrs={"class": "input"}),
        required=False,
    )
    quantity = forms.IntegerField(label="Số lượng", min_value=1, required=False, widget=forms.NumberInput(attrs={"class": "input", "min": "1"}))
    unit_price = forms.IntegerField(label="Đơn giá nhập", min_value=0, required=False, widget=forms.NumberInput(attrs={"class": "input", "min": "0"}))
    batch_code = forms.CharField(label="Mã lô", max_length=50, required=False, widget=forms.TextInput(attrs={"class": "input", "placeholder": "Ví dụ: LO-2026-001"}))
    note = forms.CharField(label="Ghi chú", max_length=255, required=False, widget=forms.TextInput(attrs={"class": "input", "placeholder": "Mô tả thêm cho dòng nhập"}))

    def clean(self):
        cleaned_data = super().clean()
        product = cleaned_data.get("product")
        quantity = cleaned_data.get("quantity")
        unit_price = cleaned_data.get("unit_price")
        batch_code = (cleaned_data.get("batch_code") or "").strip().upper()
        has_any_value = bool(product or quantity or unit_price or batch_code or cleaned_data.get("note"))

        if has_any_value and not product:
            self.add_error("product", ValidationError("Vui lòng chọn sản phẩm cho dòng nhập."))
        if has_any_value and not quantity:
            self.add_error("quantity", ValidationError("Vui lòng nhập số lượng."))
        if quantity is not None and int(quantity) <= 0:
            self.add_error("quantity", ValidationError("Số lượng phải lớn hơn 0."))
        if unit_price is not None and int(unit_price) < 0:
            self.add_error("unit_price", ValidationError("Đơn giá nhập phải >= 0."))
        cleaned_data["batch_code"] = batch_code
        return cleaned_data


PurchaseReceiptItemFormSet = formset_factory(PurchaseReceiptItemForm, extra=3, can_delete=True)
