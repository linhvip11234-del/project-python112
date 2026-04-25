# views.py: chứa toàn bộ controller/view của website bán trang sức, gồm luồng khách hàng, thanh toán, ví điện tử và trang quản trị.

import datetime as dt
import io
import random

import qrcode
from django.conf import settings
from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.core.mail import send_mail
from django.db import models
from django.db.models import Avg, Count, Sum
from django.db.models.deletion import ProtectedError
from django.db.models.functions import TruncDate
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone

from .decorators import admin_required
from .forms import (
    AdminDonHangForm,
    AdminInventoryAdjustForm,
    AdminUserForm,
    DatHangForm,
    ProductReviewForm,
    ForgotPasswordOTPForm,
    ForgotPasswordRequestForm,
    ForgotPasswordSecurityForm,
    PurchaseReceiptForm,
    PurchaseReceiptItemFormSet,
    RegistrationForm,
    SanPhamForm,
    SupplierForm,
    VoucherAdminForm,
)
from .models import CartItem, DonHang, InventoryBatch, InventoryHistory, NhaCungCap, PhieuNhapKho, ProductImage, ProductReview, SECURITY_QUESTION_MAP, OrderStatusHistory, SanPham, SavedAddress, UserSecurityProfile, Voucher, WalletTopUpRequest, WalletTransaction
from .services import (
    BATCH_SORTS,
    INVENTORY_SORTS,
    ORDER_SORTS,
    PRODUCT_SORTS,
    RECEIPT_SORTS,
    SUPPLIER_SORTS,
    USER_SORTS,
    adjust_product_stock,
    apply_batch_filters,
    apply_order_filters,
    apply_product_filters,
    apply_receipt_filters,
    apply_supplier_filters,
    apply_user_filters,
    add_product_to_cart,
    approve_topup_request,
    build_checkout_pricing,
    build_order_transfer_qr,
    cart_item_count,
    cart_subtotal,
    cancel_purchase_receipt,
    create_order_from_checkout,
    create_orders_from_cart,
    create_purchase_receipt,
    get_default_saved_address,
    get_saved_addresses,
    save_user_address,
    create_topup_request,
    get_allowed_statuses,
    get_bank_info,
    get_cart_items,
    get_or_create_wallet,
    get_user_role,
    mark_order_paid_by_bank,
    mark_topup_paid,
    receive_purchase_receipt,
    reject_topup_request,
    seed_sample_products,
    seed_sample_vouchers,
    update_cart_item_quantity,
    update_order_status,
    validate_voucher,
)




PASSWORD_RESET_SESSION_KEY = "password_reset_otp"
PASSWORD_RESET_USER_SESSION_KEY = "password_reset_user"
PASSWORD_RESET_OTP_EXPIRE_SECONDS = 300


# Helper: ép tham số query string về kiểu int; nếu lỗi thì trả về giá trị mặc định.
def _parse_int_param(value: str, default=None):
    value = (value or "").strip()
    if not value:
        return default
    try:
        return int(value)
    except Exception:
        return default


# Helper: lọc danh sách sản phẩm theo giá, khuyến mãi, tồn kho và điểm đánh giá để phục vụ catalog/trang chủ.
def _filter_products_for_catalog(products, *, min_price=None, max_price=None, sale_only=False, in_stock=False, min_rating=0):
    filtered = []
    for product in products:
        current_price = int(product.gia_hien_tai or 0)
        if min_price is not None and current_price < int(min_price):
            continue
        if max_price is not None and current_price > int(max_price):
            continue
        if sale_only and not (product.dang_flash_sale or product.dang_giam_gia):
            continue
        if in_stock and not product.con_hang:
            continue
        if min_rating and float(product.average_rating or 0) < float(min_rating):
            continue
        filtered.append(product)
    return filtered


# Helper: lưu nhiều ảnh phụ cho 1 sản phẩm khi admin tạo hoặc sửa sản phẩm.
def _save_gallery_images(product: SanPham, images):
    for index, image in enumerate(images or [], start=1):
        ProductImage.objects.create(
            san_pham=product,
            image=image,
            sort_order=product.images.count() + index,
            caption=f"{product.ten} - góc {product.images.count() + index}",
        )


# Helper: annotate thêm điểm đánh giá trung bình và số lượt đánh giá cho queryset sản phẩm.
def _annotated_catalog_queryset(queryset):
    return queryset.annotate(
        average_rating_value=Avg("reviews__rating", filter=models.Q(reviews__is_visible=True)),
        review_count_value=Count("reviews", filter=models.Q(reviews__is_visible=True), distinct=True),
    )


# Helper: ẩn bớt ký tự email khi hiển thị cho người dùng ở luồng quên mật khẩu.
def _mask_email(email: str) -> str:
    email = (email or "").strip()
    if "@" not in email:
        return email
    name, domain = email.split("@", 1)
    if len(name) <= 2:
        masked = name[0] + "*" * max(len(name) - 1, 1)
    else:
        masked = name[:2] + "*" * (len(name) - 2)
    return f"{masked}@{domain}"


# Helper: sinh mã OTP 6 chữ số cho chức năng đặt lại mật khẩu.
def _generate_otp() -> str:
    return f"{random.randint(0, 999999):06d}"


# Helper: lưu thông tin OTP đặt lại mật khẩu vào session, kèm thời gian hết hạn.
def _set_password_reset_session(request, *, user_id: int, otp: str, email: str):
    request.session[PASSWORD_RESET_SESSION_KEY] = {
        "user_id": user_id,
        "otp": otp,
        "email": email,
        "expires_at": (timezone.now() + dt.timedelta(seconds=PASSWORD_RESET_OTP_EXPIRE_SECONDS)).isoformat(),
        "attempts": 0,
    }
    request.session.modified = True


# Helper: đọc và kiểm tra session OTP; tự xóa nếu hết hạn hoặc sai định dạng.
def _get_password_reset_session(request):
    data = request.session.get(PASSWORD_RESET_SESSION_KEY) or {}
    expires_at = data.get("expires_at")
    if not expires_at:
        return None
    try:
        expires_dt = dt.datetime.fromisoformat(expires_at)
    except ValueError:
        request.session.pop(PASSWORD_RESET_SESSION_KEY, None)
        return None
    if timezone.is_naive(expires_dt):
        expires_dt = timezone.make_aware(expires_dt, timezone.get_current_timezone())
    if timezone.now() > expires_dt:
        request.session.pop(PASSWORD_RESET_SESSION_KEY, None)
        return None
    return data


# Helper: xóa session OTP sau khi dùng xong hoặc khi cần hủy luồng đặt lại mật khẩu.
def _clear_password_reset_session(request):
    request.session.pop(PASSWORD_RESET_SESSION_KEY, None)
    request.session.modified = True




# Helper: đánh dấu user đã xác minh thành công để cho phép nhập mật khẩu mới.
def _set_password_reset_user_session(request, *, user_id: int):
    request.session[PASSWORD_RESET_USER_SESSION_KEY] = {"user_id": user_id}
    request.session.modified = True


# Helper: lấy user đang được phép đặt lại mật khẩu từ session.
def _get_password_reset_user(request):
    data = request.session.get(PASSWORD_RESET_USER_SESSION_KEY) or {}
    user_id = data.get("user_id")
    if not user_id:
        return None
    return User.objects.filter(id=user_id).first()


# Helper: xóa session user của luồng đặt lại mật khẩu.
def _clear_password_reset_user_session(request):
    request.session.pop(PASSWORD_RESET_USER_SESSION_KEY, None)
    request.session.modified = True


# Helper: gửi OTP qua email cho người dùng để xác minh yêu cầu đặt lại mật khẩu.
def _send_password_reset_otp(*, user: User, otp: str):
    subject = "OTP dat lai mat khau"
    message = (
        f"Xin chao {user.username},\n\n"
        f"Ma OTP dat lai mat khau cua ban la: {otp}\n"
        f"Ma co hieu luc trong {PASSWORD_RESET_OTP_EXPIRE_SECONDS // 60} phut.\n\n"
        "Neu ban khong yeu cau dat lai mat khau, hay bo qua email nay.\n"
    )
    send_mail(
        subject=subject,
        message=message,
        from_email=getattr(settings, "DEFAULT_FROM_EMAIL", None),
        recipient_list=[user.email],
        fail_silently=False,
    )


PRODUCT_SORT_CHOICES = [
    ("newest", "Mới nhất"),
    ("oldest", "Cũ nhất"),
    ("name_asc", "Tên A-Z"),
    ("name_desc", "Tên Z-A"),
    ("price_asc", "Giá tăng dần"),
    ("price_desc", "Giá giảm dần"),
]

ORDER_SORT_CHOICES = [
    ("newest", "Mới nhất"),
    ("oldest", "Cũ nhất"),
    ("total_desc", "Tổng tiền giảm dần"),
    ("total_asc", "Tổng tiền tăng dần"),
    ("status_asc", "Trạng thái A-Z"),
]

USER_SORT_CHOICES = [
    ("newest", "Mới nhất"),
    ("oldest", "Cũ nhất"),
    ("name_asc", "Username A-Z"),
    ("name_desc", "Username Z-A"),
]


TOPUP_SORT_CHOICES = [
    ("newest", "Mới nhất"),
    ("oldest", "Cũ nhất"),
    ("amount_desc", "Số tiền giảm dần"),
    ("amount_asc", "Số tiền tăng dần"),
]


TOPUP_SORTS = {
    "newest": ("-created_at", "-id"),
    "oldest": ("created_at", "id"),
    "amount_desc": ("-amount", "-id"),
    "amount_asc": ("amount", "id"),
}


# Helper: tạo ảnh QR từ nội dung text/chuỗi thanh toán rồi trả về trực tiếp cho trình duyệt.
def _render_qr_image(payload: str) -> HttpResponse:
    qr = qrcode.QRCode(version=1, box_size=8, border=2)
    qr.add_data(payload)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    buffer.seek(0)
    return HttpResponse(buffer.getvalue(), content_type="image/png")


# Helper: gom dữ liệu trang checkout (địa chỉ, tổng tiền, voucher, ngân hàng, ví...) dùng chung cho mua ngay và thanh toán giỏ hàng.
def _build_checkout_context(*, user, form, items, source: str, product=None):
    items = list(items)
    subtotal = sum(item["subtotal"] for item in items)
    voucher_code = ""
    voucher_preview = None
    discount_preview = 0
    if getattr(form, "is_bound", False) and form.is_valid():
        voucher_code = form.cleaned_data.get("voucher_code", "")
        try:
            pricing = build_checkout_pricing(subtotal=subtotal, voucher_code=voucher_code)
        except ValidationError as exc:
            form.add_error("voucher_code", exc.message if hasattr(exc, "message") else str(exc))
            pricing = {"subtotal": subtotal, "discount": 0, "total": subtotal, "voucher": None, "voucher_code": voucher_code}
        voucher_preview = pricing["voucher"]
        discount_preview = pricing["discount"]
    else:
        voucher_code = form.initial.get("voucher_code", "") if hasattr(form, "initial") else ""
        if voucher_code:
            try:
                pricing = build_checkout_pricing(subtotal=subtotal, voucher_code=voucher_code)
                voucher_preview = pricing["voucher"]
                discount_preview = pricing["discount"]
            except ValidationError:
                voucher_preview = None
                discount_preview = 0

    return {
        "form": form,
        "wallet": get_or_create_wallet(user),
        "bank_info": get_bank_info(),
        "checkout_items": items,
        "checkout_source": source,
        "sp": product,
        "subtotal": subtotal,
        "discount_preview": discount_preview,
        "total_preview": max(subtotal - discount_preview, 0),
        "voucher_preview": voucher_preview,
        "cart_count": cart_item_count(user),
        "available_vouchers": Voucher.objects.filter(active=True).order_by("code")[:5],
        "saved_addresses": get_saved_addresses(user),
    }


# Trang chủ: hiển thị banner, sản phẩm mới, sản phẩm giảm giá, flash sale và các bộ lọc catalog ngoài trang chủ.
def home(request):
    seed_sample_products()
    seed_sample_vouchers()
    q = request.GET.get("q", "").strip()
    sort = request.GET.get("sort", "newest").strip()
    min_price = _parse_int_param(request.GET.get("min_price"), None)
    max_price = _parse_int_param(request.GET.get("max_price"), None)
    sale_only = request.GET.get("sale_only") == "1"
    in_stock = request.GET.get("in_stock") == "1"
    min_rating = _parse_int_param(request.GET.get("min_rating"), 0) or 0
    if sort not in PRODUCT_SORTS:
        sort = "newest"
    now = timezone.now()
    ds_qs = _annotated_catalog_queryset(apply_product_filters(SanPham.objects.filter(trang_thai="active"), q=q, sort=sort))
    ds = list(ds_qs)
    if sort == "rating_desc":
        ds.sort(key=lambda p: (float(p.average_rating or 0), int(p.review_count or 0), p.id), reverse=True)
    ds = _filter_products_for_catalog(ds, min_price=min_price, max_price=max_price, sale_only=sale_only, in_stock=in_stock, min_rating=min_rating)

    flash_sale_products = list(_annotated_catalog_queryset(SanPham.objects.filter(
        trang_thai="active",
        flash_sale_price__isnull=False,
        flash_sale_price__gt=0,
        flash_sale_price__lt=models.F("gia"),
        flash_sale_start__lte=now,
        flash_sale_end__gte=now,
    ).order_by("flash_sale_end", "-id")[:4]))
    discounted_products = list(_annotated_catalog_queryset(SanPham.objects.filter(
        trang_thai="active",
        gia_khuyen_mai__isnull=False,
        gia_khuyen_mai__gt=0,
    ).exclude(gia_khuyen_mai__gte=models.F("gia")).exclude(id__in=[p.id for p in flash_sale_products]).order_by("-id")[:4]))
    return render(request, "home.html", {
        "ds": ds,
        "q": q,
        "sort": sort,
        "min_price": request.GET.get("min_price", ""),
        "max_price": request.GET.get("max_price", ""),
        "sale_only": sale_only,
        "in_stock": in_stock,
        "min_rating": int(min_rating or 0),
        "product_sort_choices": PRODUCT_SORT_CHOICES + [("rating_desc", "Đánh giá cao nhất")],
        "cart_count": cart_item_count(request.user),
        "available_vouchers": Voucher.objects.filter(active=True).order_by("code")[:5],
        "discounted_products": discounted_products,
        "flash_sale_products": flash_sale_products,
        "now": now,
    })


# Danh sách flash sale: lọc và hiển thị riêng các sản phẩm đang trong chương trình flash sale.
def flash_sale_products(request):
    seed_sample_products()
    seed_sample_vouchers()
    now = timezone.now()
    ds = SanPham.objects.filter(
        trang_thai="active",
        flash_sale_price__isnull=False,
        flash_sale_price__gt=0,
        flash_sale_price__lt=models.F("gia"),
        flash_sale_start__lte=now,
        flash_sale_end__gte=now,
    ).order_by("flash_sale_end", "-id")
    return render(request, "flash_sale_products.html", {
        "ds": ds,
        "cart_count": cart_item_count(request.user),
        "now": now,
    })


<<<<<<< HEAD
# Chi tiết sản phẩm: hiển thị thông tin đầy đủ, ảnh phụ, đánh giá và xử lý gửi đánh giá mới từ khách hàng.
=======
# Chi tiết sản phẩm: hiển thị thông tin đầy đủ, ảnh phụ, đánh giá và chỉ cho khách đã mua viết đánh giá.
>>>>>>> 2c81230 (sua giao dien mua hang)
def chi_tiet_san_pham(request, sp_id):
    seed_sample_products()
    seed_sample_vouchers()
    sp = get_object_or_404(_annotated_catalog_queryset(SanPham.objects.all()), id=sp_id)

    can_review = False
    existing_review = None
    if request.user.is_authenticated:
        existing_review = ProductReview.objects.filter(san_pham=sp, user=request.user).first()
        can_review = DonHang.objects.filter(
            nguoi_dat=request.user,
            san_pham=sp,
        ).exclude(trang_thai__in=["pending", "cancelled", "rejected"]).exists()

    if request.method == "POST":
        if not request.user.is_authenticated:
            messages.error(request, "Vui lòng đăng nhập và mua sản phẩm để gửi đánh giá.")
            return redirect("dang_nhap")
        if not can_review:
            messages.error(request, "Chỉ khách đã mua sản phẩm mới có thể viết đánh giá.")
            return redirect("chi_tiet_san_pham", sp_id=sp.id)

        review_form = ProductReviewForm(request.POST)
        if review_form.is_valid():
            review, created = ProductReview.objects.update_or_create(
                san_pham=sp,
                user=request.user,
                defaults={
                    "rating": review_form.cleaned_data["rating"],
                    "title": review_form.cleaned_data.get("title", ""),
                    "comment": review_form.cleaned_data.get("comment", ""),
                    "is_visible": True,
                },
            )
            messages.success(request, "Đã gửi đánh giá sản phẩm." if created else "Đã cập nhật đánh giá của bạn.")
            return redirect("chi_tiet_san_pham", sp_id=sp.id)
    else:
        initial = {}
        if existing_review:
            initial = {"rating": existing_review.rating, "title": existing_review.title, "comment": existing_review.comment}
        review_form = ProductReviewForm(initial=initial)

    reviews = sp.reviews.filter(is_visible=True).select_related("user")
    san_pham_goi_y = list(_annotated_catalog_queryset(SanPham.objects.filter(trang_thai="active").exclude(id=sp.id).order_by("-id")[:4]))
    gallery_images = list(sp.gallery_images)
    return render(request, "chi_tiet_san_pham.html", {
        "sp": sp,
        "san_pham_goi_y": san_pham_goi_y,
        "gallery_images": gallery_images,
        "reviews": reviews,
        "review_form": review_form,
        "can_review": can_review,
        "cart_count": cart_item_count(request.user),
        "now": timezone.now(),
    })


# Đăng ký tài khoản khách hàng mới; kiểm tra form hợp lệ rồi tạo user trong hệ thống.
def dang_ky(request):
    if request.user.is_authenticated:
        return redirect("home")

    form = RegistrationForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = User.objects.create_user(
            username=form.cleaned_data["username"],
            email=form.cleaned_data.get("email", ""),
            password=form.cleaned_data["password"],
        )
        profile = UserSecurityProfile(
            user=user,
            question_1=form.cleaned_data["security_question_1"],
            question_2=form.cleaned_data["security_question_2"],
        )
        profile.set_answers(
            form.cleaned_data["security_answer_1"],
            form.cleaned_data["security_answer_2"],
        )
        profile.save()
        messages.success(request, "Đăng ký thành công. Bạn có thể đăng nhập ngay bây giờ.")
        return redirect("dang_nhap")

    return render(request, "dang_ky.html", {"form": form})



# Đăng nhập: xác thực tài khoản và điều hướng theo vai trò người dùng.
def dang_nhap(request):
    if request.user.is_authenticated:
        return redirect("home")

    if request.method == "POST":
        username = request.POST.get("username", "").strip()
        password = request.POST.get("password", "").strip()
        user = authenticate(request, username=username, password=password)
        if user is None:
            user_obj = User.objects.filter(username=username).first()
            if user_obj and not user_obj.is_active:
                return render(request, "dang_nhap.html", {"loi": "Tài khoản đang bị khóa (inactive)."})
            return render(request, "dang_nhap.html", {"loi": "Sai tên đăng nhập hoặc mật khẩu."})

        login(request, user)
        messages.success(request, f"Đăng nhập thành công với vai trò {get_user_role(user).title()}.")
        return redirect("home")

    return render(request, "dang_nhap.html")



# Bước 1 quên mật khẩu: nhập username/email, kiểm tra tài khoản và chuẩn bị chọn phương thức khôi phục.
def quen_mat_khau(request):
    if request.user.is_authenticated:
        return redirect("home")

    _clear_password_reset_session(request)
    _clear_password_reset_user_session(request)
    form = ForgotPasswordRequestForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        username_or_email = (form.cleaned_data.get("username_or_email") or "").strip()
        user = User.objects.filter(models.Q(username__iexact=username_or_email) | models.Q(email__iexact=username_or_email)).first()

        if not user:
            if "@" in username_or_email:
                form.add_error("username_or_email", "Email chưa được tạo hoặc chưa có tài khoản nào liên kết với email này.")
            else:
                form.add_error("username_or_email", "Không tìm thấy tài khoản tương ứng.")
        elif not user.is_active:
            form.add_error("username_or_email", "Tài khoản đang bị khóa nên không thể đặt lại mật khẩu.")
        else:
            _set_password_reset_user_session(request, user_id=user.id)
            return redirect("chon_phuong_thuc_khoi_phuc")

    return render(request, "quen_mat_khau.html", {"form": form})


# Bước 2 quên mật khẩu: cho người dùng chọn khôi phục bằng email OTP hoặc câu hỏi bảo mật.
def chon_phuong_thuc_khoi_phuc(request):
    if request.user.is_authenticated:
        return redirect("home")

    user = _get_password_reset_user(request)
    if not user:
        messages.error(request, "Vui lòng nhập lại tài khoản cần khôi phục mật khẩu.")
        return redirect("quen_mat_khau")

    profile = getattr(user, "security_profile", None)
    has_email = bool((user.email or "").strip())
    has_security = profile is not None

    if request.method == "POST":
        method = (request.POST.get("method") or "").strip()
        if method == "email":
            if not has_email:
                messages.error(request, "Email chưa được tạo hoặc chưa có tài khoản nào liên kết với email này.")
            else:
                otp = _generate_otp()
                try:
                    _send_password_reset_otp(user=user, otp=otp)
                except Exception:
                    messages.error(request, "Không gửi được OTP qua Gmail. Hãy kiểm tra cấu hình EMAIL_HOST_USER, EMAIL_HOST_PASSWORD và App Password.")
                else:
                    _set_password_reset_session(request, user_id=user.id, otp=otp, email=user.email)
                    messages.success(request, f"Đã gửi OTP về email {_mask_email(user.email)}.")
                    return redirect("dat_lai_mat_khau_otp")
        elif method == "security":
            if not has_security:
                messages.error(request, "Tài khoản này chưa cài câu hỏi bảo mật.")
            else:
                return redirect("khoi_phuc_bang_cau_hoi_bao_mat")
        else:
            messages.error(request, "Vui lòng chọn phương thức khôi phục hợp lệ.")

    return render(request, "chon_phuong_thuc_khoi_phuc.html", {
        "reset_user": user,
        "masked_email": _mask_email(user.email) if has_email else "Chưa liên kết email",
        "has_email": has_email,
        "has_security": has_security,
    })


# Khôi phục mật khẩu bằng câu hỏi bảo mật: đối chiếu câu trả lời rồi cấp quyền đổi mật khẩu.
def khoi_phuc_bang_cau_hoi_bao_mat(request):
    if request.user.is_authenticated:
        return redirect("home")

    user = _get_password_reset_user(request)
    if not user:
        messages.error(request, "Vui lòng nhập lại tài khoản cần khôi phục mật khẩu.")
        return redirect("quen_mat_khau")

    profile = getattr(user, "security_profile", None)
    if not profile:
        messages.error(request, "Tài khoản này chưa cài câu hỏi bảo mật.")
        return redirect("chon_phuong_thuc_khoi_phuc")

    form = ForgotPasswordSecurityForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        if profile.check_answers(form.cleaned_data["answer_1"], form.cleaned_data["answer_2"]):
            user.set_password(form.cleaned_data["new_password"])
            user.save(update_fields=["password"])
            _clear_password_reset_session(request)
            _clear_password_reset_user_session(request)
            messages.success(request, "Đổi mật khẩu thành công bằng câu hỏi bảo mật.")
            return redirect("dang_nhap")
        form.add_error(None, "Câu trả lời bảo mật không đúng.")

    return render(request, "khoi_phuc_bang_cau_hoi_bao_mat.html", {
        "form": form,
        "reset_user": user,
        "question_1": SECURITY_QUESTION_MAP.get(profile.question_1, profile.question_1),
        "question_2": SECURITY_QUESTION_MAP.get(profile.question_2, profile.question_2),
    })


# Khôi phục mật khẩu bằng OTP: xác minh mã OTP và cho phép người dùng đặt mật khẩu mới.
def dat_lai_mat_khau_otp(request):
    if request.user.is_authenticated:
        return redirect("home")

    session_data = _get_password_reset_session(request)
    if not session_data:
        messages.error(request, "Phiên đặt lại mật khẩu đã hết hạn. Vui lòng yêu cầu OTP mới.")
        return redirect("quen_mat_khau")

    form = ForgotPasswordOTPForm(request.POST or None)
    user = User.objects.filter(id=session_data.get("user_id")).first()
    if not user:
        _clear_password_reset_session(request)
        messages.error(request, "Không tìm thấy tài khoản để đặt lại mật khẩu.")
        return redirect("quen_mat_khau")

    if request.method == "POST" and form.is_valid():
        attempts = int(session_data.get("attempts") or 0)
        if attempts >= 5:
            _clear_password_reset_session(request)
            messages.error(request, "Bạn đã nhập sai OTP quá nhiều lần. Vui lòng yêu cầu OTP mới.")
            return redirect("quen_mat_khau")

        otp = form.cleaned_data["otp"]
        if otp != str(session_data.get("otp")):
            session_data["attempts"] = attempts + 1
            request.session[PASSWORD_RESET_SESSION_KEY] = session_data
            request.session.modified = True
            form.add_error("otp", "OTP không đúng.")
        else:
            user.set_password(form.cleaned_data["new_password"])
            user.save(update_fields=["password"])
            _clear_password_reset_session(request)
            _clear_password_reset_user_session(request)
            messages.success(request, "Đổi mật khẩu thành công. Bạn có thể đăng nhập bằng mật khẩu mới.")
            return redirect("dang_nhap")

    remaining_seconds = max(0, int((dt.datetime.fromisoformat(session_data["expires_at"]).astimezone(timezone.get_current_timezone()) - timezone.now()).total_seconds()))
    return render(
        request,
        "dat_lai_mat_khau_otp.html",
        {
            "form": form,
            "masked_email": _mask_email(session_data.get("email") or user.email),
            "remaining_seconds": remaining_seconds,
        },
    )


# Đăng xuất khỏi hệ thống và quay về trang chủ.
def dang_xuat(request):
    if request.user.is_authenticated:
        logout(request)
        messages.success(request, "Bạn đã đăng xuất.")
    return redirect("home")


@login_required
# Giỏ hàng: thêm 1 sản phẩm vào giỏ, có kiểm tra tồn kho và cộng dồn số lượng nếu sản phẩm đã tồn tại.
def add_to_cart(request, sp_id):
    if request.method != "POST":
        return redirect("home")
    seed_sample_products()
    seed_sample_vouchers()
    sp = get_object_or_404(SanPham, id=sp_id)
    try:
        quantity = int((request.POST.get("quantity") or "1").strip())
    except ValueError:
        quantity = 1
    try:
        item = add_product_to_cart(user=request.user, product=sp, quantity=quantity)
    except ValidationError as exc:
        messages.error(request, exc.message if hasattr(exc, "message") else str(exc))
    else:
        messages.success(request, f"Đã thêm {item.san_pham.ten} vào giỏ hàng.")
    next_url = request.POST.get("next") or reverse("gio_hang")
    return redirect(next_url)


@login_required
# Trang giỏ hàng: hiển thị toàn bộ item người dùng đã chọn cùng tổng tiền tạm tính.
def gio_hang(request):
    seed_sample_products()
    seed_sample_vouchers()
    items = list(get_cart_items(request.user))
    subtotal = sum(item.thanh_tien for item in items)
    voucher_code = (request.GET.get("voucher") or "").strip().upper()
    voucher = None
    discount = 0
    voucher_error = ""
    if voucher_code:
        try:
            pricing = build_checkout_pricing(subtotal=subtotal, voucher_code=voucher_code)
            voucher = pricing["voucher"]
            discount = pricing["discount"]
        except ValidationError as exc:
            voucher_error = exc.message if hasattr(exc, "message") else str(exc)
    return render(request, "gio_hang.html", {"items": items, "subtotal": subtotal, "discount": discount, "total": max(subtotal - discount, 0), "voucher": voucher, "voucher_code": voucher_code, "voucher_error": voucher_error, "cart_count": cart_item_count(request.user), "available_vouchers": Voucher.objects.filter(active=True).order_by("code")[:5]})


@login_required
# Giỏ hàng: cập nhật số lượng 1 item, đồng thời kiểm tra giới hạn tồn kho.
def cap_nhat_gio_hang(request, item_id):
    if request.method != "POST":
        return redirect("gio_hang")
    item = get_object_or_404(CartItem.objects.select_related("user", "san_pham"), id=item_id, user=request.user)
    try:
        quantity = int((request.POST.get("quantity") or "1").strip())
    except ValueError:
        quantity = item.quantity
    update_cart_item_quantity(item=item, quantity=quantity)
    messages.success(request, "Đã cập nhật giỏ hàng.")
    return redirect("gio_hang")


@login_required
# Giỏ hàng: xóa 1 sản phẩm khỏi giỏ.
def xoa_khoi_gio(request, item_id):
    if request.method != "POST":
        return redirect("gio_hang")
    item = get_object_or_404(CartItem, id=item_id, user=request.user)
    item.delete()
    messages.success(request, "Đã xoá sản phẩm khỏi giỏ hàng.")
    return redirect("gio_hang")


@login_required
# Giỏ hàng: xóa toàn bộ sản phẩm hiện có trong giỏ của người dùng.
def xoa_toan_bo_gio_hang(request):
    if request.method != "POST":
        return redirect("gio_hang")
    CartItem.objects.filter(user=request.user).delete()
    messages.success(request, "Đã xoá toàn bộ giỏ hàng.")
    return redirect("gio_hang")


@login_required
# Checkout mua ngay: tạo đơn hàng từ 1 sản phẩm được mua trực tiếp tại trang chi tiết.
def dat_hang(request, san_pham_id):
    seed_sample_products()
    seed_sample_vouchers()
    sp = get_object_or_404(SanPham, id=san_pham_id)

    if not sp.co_the_dat_hang and not request.user.is_staff:
        messages.error(request, "Sản phẩm này đang inactive nên không thể đặt hàng.")
        return redirect("home")

    default_address = get_default_saved_address(request.user)
    initial = {"ho_ten": request.user.get_full_name() or request.user.username, "so_luong": 1, "phuong_thuc_tt": "COD"}
    if default_address:
        initial.update({"saved_address_id": str(default_address.id), "ho_ten": default_address.ho_ten, "sdt": default_address.sdt, "dia_chi": default_address.dia_chi})
    form = DatHangForm(request.POST or None, initial=initial if request.method == "GET" else None, user=request.user)

    preview_qty = 1
    try:
        preview_qty = max(int(form["so_luong"].value() or 1), 1)
    except Exception:
        preview_qty = 1
    item_preview = [{"product": sp, "quantity": preview_qty, "subtotal": sp.gia_hien_tai * preview_qty}]

    if request.method == "POST" and form.is_valid():
        item_preview = [{"product": sp, "quantity": form.cleaned_data["so_luong"], "subtotal": sp.gia_hien_tai * form.cleaned_data["so_luong"]}]
        selected_address = form.cleaned_data.get("saved_address_id")
        if selected_address:
            form.cleaned_data["ho_ten"] = selected_address.ho_ten
            form.cleaned_data["sdt"] = selected_address.sdt
            form.cleaned_data["dia_chi"] = selected_address.dia_chi
        try:
            don = create_order_from_checkout(user=request.user, product=sp, cleaned_data=form.cleaned_data)
        except ValidationError as exc:
            form.add_error(None, exc.message if hasattr(exc, "message") else str(exc))
        else:
            save_user_address(user=request.user, cleaned_data=form.cleaned_data)
            if don.phuong_thuc_tt == "ChuyenKhoan":
                messages.success(request, f"Đã tạo đơn #{don.id}. Vui lòng quét QR để thanh toán chuyển khoản.")
                return redirect("order_payment_qr", don_id=don.id)
            messages.success(request, f"Đặt hàng thành công. Mã đơn của bạn là #{don.id}.")
            return redirect("ds_don")

    return render(request, "dat_hang.html", _build_checkout_context(user=request.user, form=form, items=item_preview, source="single", product=sp))


@login_required
# Checkout từ giỏ hàng: tạo đơn hàng từ các item trong giỏ của người dùng.
def thanh_toan_gio_hang(request):
    seed_sample_products()
    seed_sample_vouchers()
    cart_items = list(get_cart_items(request.user))
    if not cart_items:
        messages.error(request, "Giỏ hàng của bạn đang trống.")
        return redirect("gio_hang")

    default_address = get_default_saved_address(request.user)
    initial = {"ho_ten": request.user.get_full_name() or request.user.username, "so_luong": 1, "phuong_thuc_tt": "COD"}
    if default_address:
        initial.update({"saved_address_id": str(default_address.id), "ho_ten": default_address.ho_ten, "sdt": default_address.sdt, "dia_chi": default_address.dia_chi})
    form = DatHangForm(request.POST or None, initial=initial if request.method == "GET" else None, user=request.user)
    checkout_items = [{"product": item.san_pham, "quantity": item.quantity, "subtotal": item.thanh_tien} for item in cart_items]

    if request.method == "POST" and form.is_valid():
        selected_address = form.cleaned_data.get("saved_address_id")
        if selected_address:
            form.cleaned_data["ho_ten"] = selected_address.ho_ten
            form.cleaned_data["sdt"] = selected_address.sdt
            form.cleaned_data["dia_chi"] = selected_address.dia_chi
        try:
            orders = create_orders_from_cart(user=request.user, cleaned_data=form.cleaned_data)
        except ValidationError as exc:
            form.add_error(None, exc.message if hasattr(exc, "message") else str(exc))
        else:
            save_user_address(user=request.user, cleaned_data=form.cleaned_data)
            if orders and orders[0].phuong_thuc_tt == "ChuyenKhoan":
                messages.success(request, f"Đã tạo {len(orders)} đơn hàng từ giỏ hàng. Hãy thanh toán lần lượt bằng QR cho từng đơn.")
            else:
                messages.success(request, f"Đã tạo thành công {len(orders)} đơn hàng từ giỏ hàng.")
            return redirect("ds_don")

    return render(request, "dat_hang.html", _build_checkout_context(user=request.user, form=form, items=checkout_items, source="cart"))


@login_required
# Ví điện tử: hiển thị số dư, lịch sử giao dịch và các thao tác liên quan đến ví.
def wallet_view(request):
    wallet = get_or_create_wallet(request.user)
    transactions = WalletTransaction.objects.filter(wallet=wallet).select_related("order").order_by("-created_at", "-id")
    topups = WalletTopUpRequest.objects.filter(wallet=wallet).order_by("-created_at", "-id")[:10]
    return render(
        request,
        "wallet.html",
        {
            "wallet": wallet,
            "transactions": transactions,
            "topups": topups,
            "bank_info": get_bank_info(),
        },
    )


@login_required
# Ví điện tử: tạo yêu cầu nạp tiền mới để chờ admin xác nhận.
def wallet_deposit(request):
    if request.method != "POST":
        return redirect("wallet")

    try:
        amount = int((request.POST.get("amount") or "0").strip())
    except ValueError:
        amount = 0

    if amount <= 0:
        messages.error(request, "Số tiền nạp phải lớn hơn 0.")
        return redirect("wallet")

    try:
        topup = create_topup_request(user=request.user, amount=amount)
    except ValidationError as exc:
        messages.error(request, str(exc))
        return redirect("wallet")

    messages.success(request, f"Đã tạo yêu cầu nạp tiền {topup.reference}. Vui lòng quét QR để thanh toán.")
    return redirect("wallet_topup_detail", topup_id=topup.id)


@login_required
# Chi tiết yêu cầu nạp ví: hiển thị trạng thái, số tiền, mã tham chiếu và thông tin chuyển khoản.
def wallet_topup_detail(request, topup_id):
    topup = get_object_or_404(WalletTopUpRequest.objects.select_related("wallet__user", "approved_by"), id=topup_id)
    if topup.wallet.user != request.user and not request.user.is_staff:
        messages.error(request, "Bạn không có quyền xem yêu cầu nạp tiền này.")
        return redirect("wallet")
    return render(
        request,
        "wallet_topup_detail.html",
        {
            "topup": topup,
            "bank_info": get_bank_info(),
            "auto_seconds": getattr(settings, "BANK_CALLBACK_AUTO_SECONDS", 5),
            "auto_approve": getattr(settings, "AUTO_APPROVE_TOPUP_CALLBACK", True),
        },
    )


@login_required
# Sinh QR nạp ví cho người dùng quét nhanh khi chuyển khoản.
def wallet_topup_qr(request, topup_id):
    topup = get_object_or_404(WalletTopUpRequest.objects.select_related("wallet__user"), id=topup_id)
    if topup.wallet.user != request.user and not request.user.is_staff:
        return HttpResponse(status=403)
    return _render_qr_image(topup.qr_payload)


@login_required
# Callback/mô phỏng xác nhận đã chuyển khoản nạp ví để cập nhật trạng thái yêu cầu.
def wallet_topup_callback(request, topup_id):
    if request.method != "POST":
        return redirect("wallet")
    topup = get_object_or_404(WalletTopUpRequest.objects.select_related("wallet__user"), id=topup_id)
    if topup.wallet.user != request.user and not request.user.is_staff:
        messages.error(request, "Bạn không có quyền thực hiện thao tác này.")
        return redirect("wallet")
    ok, message = mark_topup_paid(topup=topup, auto_credit=getattr(settings, "AUTO_APPROVE_TOPUP_CALLBACK", True))
    if ok:
        messages.success(request, message)
    else:
        messages.error(request, message)
    return redirect("wallet")


@login_required
# Danh sách đơn hàng của khách: xem lịch sử mua, lọc theo trạng thái và tra cứu chi tiết.
def ds_don(request):
    q = request.GET.get("q", "").strip()
    trang_thai = request.GET.get("trang_thai", "").strip()
    sort = request.GET.get("sort", "newest").strip()

    if sort not in ORDER_SORTS:
        sort = "newest"

    ds = apply_order_filters(
        DonHang.objects.filter(nguoi_dat=request.user).select_related("san_pham").prefetch_related("status_histories__actor"),
        q=q,
        status=trang_thai,
        sort=sort,
    )

    return render(
        request,
        "don_hang.html",
        {
            "ds": ds,
            "q": q,
            "trang_thai": trang_thai,
            "sort": sort,
            "sort_choices": ORDER_SORT_CHOICES,
            "trang_thai_choices": DonHang.TRANG_THAI,
            "saved_addresses": get_saved_addresses(request.user),
        },
    )


@login_required
# Hiển thị QR chuyển khoản cho 1 đơn hàng chưa thanh toán.
def order_payment_qr(request, don_id):
    don = get_object_or_404(DonHang.objects.select_related("nguoi_dat", "san_pham"), id=don_id, nguoi_dat=request.user)
    if don.phuong_thuc_tt != "ChuyenKhoan":
        messages.error(request, "Đơn hàng này không dùng chuyển khoản ngân hàng.")
        return redirect("ds_don")
    return render(
        request,
        "order_payment_qr.html",
        {
            "don": don,
            "bank_info": get_bank_info(),
            "auto_seconds": getattr(settings, "BANK_CALLBACK_AUTO_SECONDS", 5),
        },
    )


@login_required
# Trả về ảnh QR của đơn hàng để nhúng trực tiếp lên giao diện.
def order_payment_qr_image(request, don_id):
    don = get_object_or_404(DonHang.objects.select_related("nguoi_dat"), id=don_id, nguoi_dat=request.user)
    if don.phuong_thuc_tt != "ChuyenKhoan":
        return HttpResponse(status=400)
    return _render_qr_image(build_order_transfer_qr(don))


@login_required
# Callback/mô phỏng xác nhận đơn hàng đã được chuyển khoản thành công.
def order_payment_callback(request, don_id):
    if request.method != "POST":
        return redirect("ds_don")
    don = get_object_or_404(DonHang.objects.select_related("nguoi_dat"), id=don_id, nguoi_dat=request.user)
    ok, message = mark_order_paid_by_bank(order=don)
    if ok:
        messages.success(request, message)
    else:
        messages.error(request, message)
    return redirect("ds_don")


@login_required
# Khách xác nhận đơn trong các trạng thái cho phép theo nghiệp vụ.
def xac_nhan_don(request, don_id):
    don = get_object_or_404(DonHang, id=don_id, nguoi_dat=request.user)
    if don.phuong_thuc_tt == "ChuyenKhoan" and not don.da_thanh_toan:
        messages.error(request, "Đơn hàng chuyển khoản chưa được ghi nhận thanh toán nên chưa thể xác nhận.")
        return redirect("ds_don")
    ok, message = update_order_status(order=don, new_status="Confirmed", actor_role="user", actor=request.user)
    if ok:
        messages.success(request, message)
    else:
        messages.error(request, message)
    return redirect("ds_don")


@login_required
# Hủy đơn hàng: đổi trạng thái, hoàn tiền ví (nếu có) và cập nhật tồn kho theo service.
def huy_don(request, don_id):
    don = get_object_or_404(DonHang, id=don_id, nguoi_dat=request.user)
    ok, message = update_order_status(order=don, new_status="Cancelled", actor_role="user", actor=request.user)
    if ok:
        messages.success(request, message)
    else:
        messages.error(request, message)
    return redirect("ds_don")


@admin_required
# Chuyển hướng nhanh từ route cũ sang danh sách đơn hàng admin mới.
def ds_don_admin(request):
    return redirect("admin_donhang_list")


@admin_required
# Admin thao tác nhanh với đơn hàng: duyệt, từ chối hoặc đổi trạng thái theo action truyền vào.
def duyet_don(request, don_id, hanh_dong):
    don = get_object_or_404(DonHang, id=don_id)
    new_status = "Approved" if hanh_dong == "approve" else "Rejected"
    ok, message = update_order_status(order=don, new_status=new_status, actor_role="admin", actor=request.user)
    if ok:
        messages.success(request, message)
    else:
        messages.error(request, message)
    return redirect("admin_donhang_list")


@admin_required
# Dashboard quản trị: tổng hợp số liệu đơn hàng, doanh thu, top sản phẩm và biểu đồ thống kê.
def admin_dashboard(request):
    tong_sp = SanPham.objects.count()
    tong_sp_active = SanPham.objects.filter(trang_thai="active").count()
    tong_sp_inactive = SanPham.objects.filter(trang_thai="inactive").count()
    tong_don = DonHang.objects.count()
    cho_xac_nhan = DonHang.objects.filter(trang_thai="Pending").count()
    da_duyet = DonHang.objects.filter(trang_thai="Approved").count()
    da_huy = DonHang.objects.filter(trang_thai="Cancelled").count()
    nap_cho_duyet = WalletTopUpRequest.objects.filter(status__in=["pending", "paid"]).count()
    nap_hoan_tat = WalletTopUpRequest.objects.filter(status="approved").count()
    tong_voucher = Voucher.objects.count()
    voucher_dang_bat = Voucher.objects.filter(active=True).count()
    flash_sale_dang_bat = SanPham.objects.filter(trang_thai="active", flash_sale_price__isnull=False, flash_sale_price__gt=0, flash_sale_price__lt=models.F("gia"), flash_sale_start__lte=timezone.now(), flash_sale_end__gte=timezone.now()).count()
    sap_het_hang = SanPham.objects.filter(ton_kho__gt=0, ton_kho__lte=5).count()
    het_hang = SanPham.objects.filter(ton_kho__lte=0).count()
    tong_nha_cung_cap = NhaCungCap.objects.count()
    phieu_nhap_nhap = PhieuNhapKho.objects.filter(status="received").count()
    phieu_nhap_nhap_nhap = InventoryBatch.objects.count()
    phieu_nhap_cho = PhieuNhapKho.objects.filter(status="draft").count()

    status_rows = DonHang.objects.values("trang_thai").annotate(c=Count("id")).order_by("trang_thai")
    status_labels = [r["trang_thai"] for r in status_rows]
    status_counts = [r["c"] for r in status_rows]

    today = timezone.localdate()
    start = today - dt.timedelta(days=6)
    daily_rows = (
        DonHang.objects.filter(tao_luc__date__gte=start, tao_luc__date__lte=today)
        .annotate(d=TruncDate("tao_luc"))
        .values("d")
        .annotate(orders=Count("id"), revenue=Sum("tong_tien"))
        .order_by("d")
    )
    daily_map = {r["d"]: r for r in daily_rows}
    days = [start + dt.timedelta(days=i) for i in range(7)]
    daily_labels = [d.strftime("%d/%m") for d in days]
    daily_orders = [int(daily_map.get(d, {}).get("orders") or 0) for d in days]
    daily_revenue = [int(daily_map.get(d, {}).get("revenue") or 0) for d in days]
    top_products = DonHang.objects.values("san_pham__ten").annotate(c=Count("id")).order_by("-c")[:10]

    return render(
        request,
        "admin_dashboard.html",
        {
            "tong_sp": tong_sp,
            "tong_sp_active": tong_sp_active,
            "tong_sp_inactive": tong_sp_inactive,
            "tong_don": tong_don,
            "cho_xac_nhan": cho_xac_nhan,
            "da_duyet": da_duyet,
            "da_huy": da_huy,
            "nap_cho_duyet": nap_cho_duyet,
            "nap_hoan_tat": nap_hoan_tat,
            "tong_voucher": tong_voucher,
            "voucher_dang_bat": voucher_dang_bat,
            "flash_sale_dang_bat": flash_sale_dang_bat,
            "sap_het_hang": sap_het_hang,
            "het_hang": het_hang,
            "tong_nha_cung_cap": tong_nha_cung_cap,
            "phieu_nhap_nhap": phieu_nhap_nhap,
            "phieu_nhap_nhap_nhap": phieu_nhap_nhap_nhap,
            "phieu_nhap_cho": phieu_nhap_cho,
            "status_labels": status_labels,
            "status_counts": status_counts,
            "daily_labels": daily_labels,
            "daily_orders": daily_orders,
            "daily_revenue": daily_revenue,
            "top_products": top_products,
        },
    )


@admin_required
# Admin sản phẩm: danh sách sản phẩm có lọc, tìm kiếm và sắp xếp.
def admin_sanpham_list(request):
    q = request.GET.get("q", "").strip()
    trang_thai = request.GET.get("trang_thai", "").strip()
    sort = request.GET.get("sort", "newest").strip()
    if sort not in PRODUCT_SORTS:
        sort = "newest"

    ds = apply_product_filters(SanPham.objects.all(), q=q, status=trang_thai, sort=sort)
    return render(
        request,
        "admin_sanpham_list.html",
        {"ds": ds, "q": q, "trang_thai": trang_thai, "sort": sort, "sort_choices": PRODUCT_SORT_CHOICES, "trang_thai_choices": SanPham.TRANG_THAI},
    )


@admin_required
# Admin sản phẩm: xem chi tiết 1 sản phẩm và các thông tin liên quan.
def admin_sanpham_detail(request, sp_id):
    sp = get_object_or_404(_annotated_catalog_queryset(SanPham.objects.all()), id=sp_id)
    return render(request, "admin_sanpham_detail.html", {
        "sp": sp,
        "gallery_images": sp.gallery_images,
        "reviews": sp.reviews.select_related("user")[:10],
    })



@admin_required
# Admin sản phẩm: tạo mới sản phẩm, lưu ảnh chính và ảnh phụ.
def admin_sanpham_create(request):
    form = SanPhamForm(request.POST or None, request.FILES or None)
    if request.method == "POST" and form.is_valid():
        sp = form.save()
        _save_gallery_images(sp, form.cleaned_data.get("gallery_images"))
        messages.success(request, f"Đã thêm sản phẩm #{sp.id} thành công.")
        return redirect("admin_sanpham_detail", sp_id=sp.id)
    return render(request, "admin_sanpham_form.html", {"mode": "create", "form": form})



@admin_required
# Admin sản phẩm: chỉnh sửa thông tin sản phẩm hiện có.
def admin_sanpham_edit(request, sp_id):
    sp = get_object_or_404(SanPham, id=sp_id)
    form = SanPhamForm(request.POST or None, request.FILES or None, instance=sp)
    if request.method == "POST" and form.is_valid():
        sp = form.save()
        delete_ids = [int(i) for i in request.POST.getlist("delete_gallery_ids") if str(i).isdigit()]
        if delete_ids:
            sp.images.filter(id__in=delete_ids).delete()
        _save_gallery_images(sp, form.cleaned_data.get("gallery_images"))
        messages.success(request, f"Đã cập nhật sản phẩm #{sp.id}.")
        return redirect("admin_sanpham_detail", sp_id=sp.id)
    return render(request, "admin_sanpham_form.html", {"sp": sp, "mode": "edit", "form": form, "gallery_images": sp.gallery_images})



@admin_required
# Admin sản phẩm: xóa hoặc ngừng hoạt động sản phẩm tùy ràng buộc dữ liệu.
def admin_sanpham_delete(request, sp_id):
    sp = get_object_or_404(SanPham, id=sp_id)
    if request.method == "POST":
        try:
            sp.delete()
            messages.success(request, "Đã xoá sản phẩm thành công.")
            return redirect("admin_sanpham_list")
        except ProtectedError:
            messages.error(request, "Không thể xoá sản phẩm đã phát sinh đơn hàng. Hãy chuyển trạng thái sang inactive để ngừng bán.")
            return redirect("admin_sanpham_detail", sp_id=sp.id)
    return render(request, "admin_sanpham_delete.html", {"sp": sp})


@admin_required
# Admin kho: xem danh sách tồn kho sản phẩm kèm bộ lọc và tìm kiếm.
def admin_inventory_list(request):
    q = request.GET.get("q", "").strip()
    stock_status = request.GET.get("stock_status", "").strip()
    sort = request.GET.get("sort", "lowest").strip()
    if sort not in INVENTORY_SORTS:
        sort = "lowest"

    ds = SanPham.objects.all()
    if q:
        ds = ds.filter(ten__icontains=q)
    if stock_status == "out":
        ds = ds.filter(ton_kho__lte=0)
    elif stock_status == "low":
        ds = ds.filter(ton_kho__gt=0, ton_kho__lte=5)
    elif stock_status == "available":
        ds = ds.filter(ton_kho__gt=5)
    ds = ds.order_by(*INVENTORY_SORTS[sort])

    return render(request, "admin_inventory_list.html", {
        "ds": ds,
        "q": q,
        "stock_status": stock_status,
        "sort": sort,
        "sort_choices": [
            ("lowest", "Tồn kho thấp nhất"),
            ("highest", "Tồn kho cao nhất"),
            ("name_asc", "Tên A-Z"),
            ("name_desc", "Tên Z-A"),
            ("newest", "Mới nhất"),
        ],
        "total_products": SanPham.objects.count(),
        "low_stock_count": SanPham.objects.filter(ton_kho__gt=0, ton_kho__lte=5).count(),
        "out_stock_count": SanPham.objects.filter(ton_kho__lte=0).count(),
    })


@admin_required
# Admin kho: xem lịch sử biến động kho của 1 sản phẩm cụ thể.
def admin_inventory_detail(request, sp_id):
    sp = get_object_or_404(SanPham, id=sp_id)
    histories = sp.inventory_histories.select_related("actor", "order")[:20]
    return render(request, "admin_inventory_detail.html", {"sp": sp, "histories": histories})


@admin_required
# Admin kho: điều chỉnh thủ công số lượng tồn và ghi log lịch sử kho.
def admin_inventory_adjust(request, sp_id):
    sp = get_object_or_404(SanPham, id=sp_id)
    form = AdminInventoryAdjustForm(request.POST or None, initial={"action": "set", "quantity": sp.ton_kho})
    if request.method == "POST" and form.is_valid():
        try:
            updated = adjust_product_stock(
                product=sp,
                action=form.cleaned_data["action"],
                quantity=form.cleaned_data["quantity"],
                actor=request.user,
                note=form.cleaned_data.get("note", ""),
            )
        except ValidationError as exc:
            form.add_error(None, exc.message if hasattr(exc, "message") else str(exc))
        else:
            messages.success(request, f"Đã cập nhật tồn kho cho sản phẩm #{updated.id}. Tồn kho hiện tại: {updated.ton_kho}.")
            return redirect("admin_inventory_detail", sp_id=updated.id)
    return render(request, "admin_inventory_adjust.html", {"sp": sp, "form": form})


@admin_required
# Admin nhà cung cấp: danh sách nhà cung cấp có lọc và sắp xếp.
def admin_supplier_list(request):
    q = request.GET.get("q", "").strip()
    active = request.GET.get("active", "").strip()
    sort = request.GET.get("sort", "name_asc").strip()
    if sort not in SUPPLIER_SORTS:
        sort = "name_asc"
    ds = apply_supplier_filters(NhaCungCap.objects.all(), q=q, active=active, sort=sort)
    return render(request, "admin_supplier_list.html", {
        "ds": ds,
        "q": q,
        "active": active,
        "sort": sort,
        "sort_choices": [("name_asc", "Tên A-Z"), ("name_desc", "Tên Z-A"), ("newest", "Mới nhất"), ("oldest", "Cũ nhất")],
        "supplier_count": NhaCungCap.objects.count(),
        "active_count": NhaCungCap.objects.filter(active=True).count(),
    })


@admin_required
# Admin nhà cung cấp: tạo mới nhà cung cấp.
def admin_supplier_create(request):
    form = SupplierForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        supplier = form.save()
        messages.success(request, f"Đã thêm nhà cung cấp #{supplier.id}.")
        return redirect("admin_supplier_detail", supplier_id=supplier.id)
    return render(request, "admin_supplier_form.html", {"form": form, "mode": "create"})


@admin_required
# Admin nhà cung cấp: xem chi tiết thông tin 1 nhà cung cấp.
def admin_supplier_detail(request, supplier_id):
    supplier = get_object_or_404(NhaCungCap, id=supplier_id)
    recent_receipts = supplier.purchase_receipts.all()[:10]
    recent_batches = supplier.inventory_batches.select_related("san_pham", "receipt")[:10]
    return render(request, "admin_supplier_detail.html", {"supplier": supplier, "recent_receipts": recent_receipts, "recent_batches": recent_batches})


@admin_required
# Admin nhà cung cấp: chỉnh sửa thông tin nhà cung cấp.
def admin_supplier_edit(request, supplier_id):
    supplier = get_object_or_404(NhaCungCap, id=supplier_id)
    form = SupplierForm(request.POST or None, instance=supplier)
    if request.method == "POST" and form.is_valid():
        supplier = form.save()
        messages.success(request, f"Đã cập nhật nhà cung cấp #{supplier.id}.")
        return redirect("admin_supplier_detail", supplier_id=supplier.id)
    return render(request, "admin_supplier_form.html", {"form": form, "mode": "edit", "supplier": supplier})


@admin_required
# Admin nhà cung cấp: xóa nhà cung cấp nếu không vi phạm ràng buộc dữ liệu.
def admin_supplier_delete(request, supplier_id):
    supplier = get_object_or_404(NhaCungCap, id=supplier_id)
    if request.method == "POST":
        supplier.delete()
        messages.success(request, "Đã xoá nhà cung cấp.")
        return redirect("admin_supplier_list")
    return render(request, "admin_supplier_delete.html", {"supplier": supplier})


@admin_required
# Admin phiếu nhập: xem danh sách phiếu nhập kho và trạng thái nhập hàng.
def admin_receipt_list(request):
    q = request.GET.get("q", "").strip()
    status = request.GET.get("status", "").strip()
    sort = request.GET.get("sort", "newest").strip()
    if sort not in RECEIPT_SORTS:
        sort = "newest"
    ds = apply_receipt_filters(PhieuNhapKho.objects.select_related("supplier", "created_by").prefetch_related("items__san_pham"), q=q, status=status, sort=sort)
    return render(request, "admin_receipt_list.html", {
        "ds": ds,
        "q": q,
        "status": status,
        "sort": sort,
        "sort_choices": [("newest", "Mới nhất"), ("oldest", "Cũ nhất"), ("code_asc", "Mã A-Z"), ("code_desc", "Mã Z-A")],
        "status_choices": PhieuNhapKho.STATUS_CHOICES,
        "draft_count": PhieuNhapKho.objects.filter(status="draft").count(),
        "received_count": PhieuNhapKho.objects.filter(status="received").count(),
    })


@admin_required
# Admin phiếu nhập: tạo phiếu nhập mới cùng nhiều dòng sản phẩm nhập kho.
def admin_receipt_create(request):
    form = PurchaseReceiptForm(request.POST or None)
    item_formset = PurchaseReceiptItemFormSet(request.POST or None, prefix="items")
    if request.method == "POST" and form.is_valid() and item_formset.is_valid():
        item_payloads = []
        for item_form in item_formset:
            data = getattr(item_form, "cleaned_data", None) or {}
            if not data or data.get("DELETE"):
                continue
            if not data.get("product"):
                continue
            item_payloads.append({
                "product": data.get("product"),
                "quantity": data.get("quantity"),
                "unit_price": data.get("unit_price") or 0,
                "batch_code": data.get("batch_code") or "",
                "note": data.get("note") or "",
            })
        if not item_payloads:
            form.add_error(None, "Vui lòng nhập ít nhất 1 dòng sản phẩm.")
        else:
            try:
                receipt = create_purchase_receipt(
                    supplier=form.cleaned_data.get("supplier"),
                    created_by=request.user,
                    note=form.cleaned_data.get("note") or "",
                    items=item_payloads,
                )
            except ValidationError as exc:
                form.add_error(None, exc.message if hasattr(exc, "message") else str(exc))
            else:
                if request.POST.get("receive_now") == "1":
                    ok, message = receive_purchase_receipt(receipt=receipt, actor=request.user)
                    if ok:
                        messages.success(request, message)
                    else:
                        messages.warning(request, message)
                else:
                    messages.success(request, f"Đã tạo phiếu nhập kho {receipt.code}.")
                return redirect("admin_receipt_detail", receipt_id=receipt.id)
    return render(request, "admin_receipt_form.html", {"form": form, "item_formset": item_formset})


@admin_required
# Admin phiếu nhập: xem chi tiết 1 phiếu nhập kho.
def admin_receipt_detail(request, receipt_id):
    receipt = get_object_or_404(PhieuNhapKho.objects.select_related("supplier", "created_by"), id=receipt_id)
    items = receipt.items.select_related("san_pham")
    batches = receipt.batches.select_related("san_pham", "supplier")
    return render(request, "admin_receipt_detail.html", {"receipt": receipt, "items": items, "batches": batches})


@admin_required
# Admin phiếu nhập: xác nhận đã nhận hàng để cộng tồn kho và sinh lô hàng.
def admin_receipt_receive(request, receipt_id):
    receipt = get_object_or_404(PhieuNhapKho, id=receipt_id)
    if request.method != "POST":
        return redirect("admin_receipt_detail", receipt_id=receipt.id)
    ok, message = receive_purchase_receipt(receipt=receipt, actor=request.user)
    if ok:
        messages.success(request, message)
    else:
        messages.error(request, message)
    return redirect("admin_receipt_detail", receipt_id=receipt.id)


@admin_required
# Admin phiếu nhập: hủy phiếu nhập khi còn ở trạng thái cho phép.
def admin_receipt_cancel(request, receipt_id):
    receipt = get_object_or_404(PhieuNhapKho, id=receipt_id)
    if request.method != "POST":
        return redirect("admin_receipt_detail", receipt_id=receipt.id)
    ok, message = cancel_purchase_receipt(receipt=receipt)
    if ok:
        messages.success(request, message)
    else:
        messages.error(request, message)
    return redirect("admin_receipt_detail", receipt_id=receipt.id)


@admin_required
# Admin lô hàng: xem danh sách các batch nhập kho để quản lý tồn theo lô.
def admin_batch_list(request):
    q = request.GET.get("q", "").strip()
    sort = request.GET.get("sort", "newest").strip()
    if sort not in BATCH_SORTS:
        sort = "newest"
    ds = apply_batch_filters(InventoryBatch.objects.select_related("san_pham", "supplier", "receipt", "created_by"), q=q, sort=sort)
    return render(request, "admin_batch_list.html", {
        "ds": ds,
        "q": q,
        "sort": sort,
        "sort_choices": [("newest", "Mới nhất"), ("oldest", "Cũ nhất"), ("qty_desc", "Số lượng giảm dần"), ("qty_asc", "Số lượng tăng dần")],
        "batch_count": InventoryBatch.objects.count(),
    })


@admin_required
# Admin lô hàng: xem chi tiết 1 batch/lô hàng.
def admin_batch_detail(request, batch_id):
    batch = get_object_or_404(InventoryBatch.objects.select_related("san_pham", "supplier", "receipt", "created_by"), id=batch_id)
    return render(request, "admin_batch_detail.html", {"batch": batch})


@admin_required
# Admin đơn hàng: danh sách đơn với bộ lọc, tìm kiếm, sắp xếp và phân trang logic trong service.
def admin_donhang_list(request):
    trang_thai = request.GET.get("trang_thai", "").strip()
    q = request.GET.get("q", "").strip()
    payment = request.GET.get("payment", "").strip()
    sort = request.GET.get("sort", "newest").strip()
    if sort not in ORDER_SORTS:
        sort = "newest"

    ds = apply_order_filters(DonHang.objects.select_related("nguoi_dat", "san_pham").all(), q=q, status=trang_thai, payment=payment, sort=sort)
    return render(
        request,
        "admin_donhang_list.html",
        {
            "ds": ds,
            "q": q,
            "trang_thai": trang_thai,
            "payment": payment,
            "sort": sort,
            "sort_choices": ORDER_SORT_CHOICES,
            "trang_thai_choices": DonHang.TRANG_THAI,
            "payment_choices": DonHang.PHUONG_THUC_TT,
        },
    )


@admin_required
# Admin đơn hàng: xem chi tiết 1 đơn hàng.
def admin_donhang_detail(request, don_id):
    don = get_object_or_404(DonHang.objects.select_related("nguoi_dat", "san_pham").prefetch_related("status_histories__actor"), id=don_id)
    return render(request, "admin_donhang_detail.html", {"don": don, "allowed_statuses": get_allowed_statuses(don, actor_role="admin"), "status_histories": don.status_histories.all()})


@admin_required
# Admin đơn hàng: tạo thủ công 1 đơn mới từ trang quản trị.
def admin_donhang_create(request):
    form = AdminDonHangForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        don = form.save()
        messages.success(request, f"Đã tạo đơn hàng #{don.id}.")
        return redirect("admin_donhang_detail", don_id=don.id)
    return render(request, "admin_donhang_form.html", {"mode": "create", "form": form})


@admin_required
# Admin đơn hàng: chỉnh sửa thông tin cơ bản của đơn hàng.
def admin_donhang_edit(request, don_id):
    don = get_object_or_404(DonHang, id=don_id)
    form = AdminDonHangForm(request.POST or None, instance=don)
    if request.method == "POST" and form.is_valid():
        don = form.save()
        messages.success(request, f"Đã cập nhật đơn hàng #{don.id}.")
        return redirect("admin_donhang_detail", don_id=don.id)
    return render(request, "admin_donhang_form.html", {"mode": "edit", "form": form, "don": don})


@admin_required
# Admin đơn hàng: xóa đơn hàng nếu được phép.
def admin_donhang_delete(request, don_id):
    don = get_object_or_404(DonHang.objects.select_related("nguoi_dat", "san_pham"), id=don_id)
    if request.method == "POST":
        don.delete()
        messages.success(request, f"Đã xoá đơn hàng #{don.id}.")
        return redirect("admin_donhang_list")
    return render(request, "admin_donhang_delete.html", {"don": don})


@admin_required
# Admin đơn hàng: cập nhật trạng thái đơn bằng form quản trị.
def admin_donhang_update(request, don_id):
    don = get_object_or_404(DonHang, id=don_id)
    if request.method == "POST":
        new_status = request.POST.get("trang_thai", "").strip()
        ok, message = update_order_status(order=don, new_status=new_status, actor_role="admin", actor=request.user)
        if ok:
            messages.success(request, message)
        else:
            messages.error(request, message)
    return redirect(request.META.get("HTTP_REFERER", "admin_donhang_list"))


@admin_required
# Admin nạp ví: xem tất cả yêu cầu nạp tiền, lọc theo trạng thái và số tiền.
def admin_topup_list(request):
    status = request.GET.get("status", "").strip()
    q = request.GET.get("q", "").strip()
    sort = request.GET.get("sort", "newest").strip()
    if sort not in TOPUP_SORTS:
        sort = "newest"

    ds = WalletTopUpRequest.objects.select_related("wallet__user", "approved_by")
    if status in {code for code, _ in WalletTopUpRequest.STATUS_CHOICES}:
        ds = ds.filter(status=status)
    if q:
        ds = ds.filter(
            models.Q(reference__icontains=q)
            | models.Q(transfer_note__icontains=q)
            | models.Q(wallet__user__username__icontains=q)
        )
    ds = ds.order_by(*TOPUP_SORTS[sort])
    return render(
        request,
        "admin_topup_list.html",
        {
            "ds": ds,
            "q": q,
            "status": status,
            "sort": sort,
            "sort_choices": TOPUP_SORT_CHOICES,
            "status_choices": WalletTopUpRequest.STATUS_CHOICES,
        },
    )


@admin_required
# Admin nạp ví: xem chi tiết 1 yêu cầu nạp tiền.
def admin_topup_detail(request, topup_id):
    topup = get_object_or_404(WalletTopUpRequest.objects.select_related("wallet__user", "approved_by"), id=topup_id)
    return render(request, "admin_topup_detail.html", {"topup": topup, "bank_info": get_bank_info()})


@admin_required
# Admin nạp ví: sinh QR chuyển khoản cho yêu cầu nạp cụ thể.
def admin_topup_qr(request, topup_id):
    topup = get_object_or_404(WalletTopUpRequest, id=topup_id)
    return _render_qr_image(topup.qr_payload)


@admin_required
# Admin nạp ví: duyệt yêu cầu nạp tiền và cộng số dư ví cho khách.
def admin_topup_approve(request, topup_id):
    if request.method != "POST":
        return redirect("admin_topup_detail", topup_id=topup_id)
    topup = get_object_or_404(WalletTopUpRequest.objects.select_related("wallet__user"), id=topup_id)
    ok, message = approve_topup_request(topup=topup, approved_by=request.user)
    if ok:
        messages.success(request, message)
    else:
        messages.error(request, message)
    return redirect("admin_topup_detail", topup_id=topup.id)


@admin_required
# Admin nạp ví: từ chối yêu cầu nạp tiền.
def admin_topup_reject(request, topup_id):
    if request.method != "POST":
        return redirect("admin_topup_detail", topup_id=topup_id)
    topup = get_object_or_404(WalletTopUpRequest.objects.select_related("wallet__user"), id=topup_id)
    reason = (request.POST.get("reason") or "").strip()
    ok, message = reject_topup_request(topup=topup, approved_by=request.user, reason=reason)
    if ok:
        messages.success(request, message)
    else:
        messages.error(request, message)
    return redirect("admin_topup_detail", topup_id=topup.id)


@admin_required
# Admin người dùng: danh sách tài khoản hệ thống có lọc, tìm kiếm và thống kê theo vai trò.
def admin_user_list(request):
    q = request.GET.get("q", "").strip()
    role = request.GET.get("role", "").strip()
    active = request.GET.get("active", "").strip()
    sort = request.GET.get("sort", "newest").strip()
    if sort not in USER_SORTS:
        sort = "newest"

    users = apply_user_filters(User.objects.all(), q=q, role=role, active=active, sort=sort)
    return render(
        request,
        "admin_user_list.html",
        {
            "users": users,
            "q": q,
            "role": role,
            "active": active,
            "sort": sort,
            "sort_choices": USER_SORT_CHOICES,
            "role_choices": [("user", "User"), ("admin", "Admin")],
        },
    )


@admin_required
# Admin người dùng: tạo mới tài khoản người dùng từ trang quản trị.
def admin_user_create(request):
    form = AdminUserForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = form.save()
        messages.success(request, f"Đã tạo user {user.username}.")
        return redirect("admin_user_list")
    return render(request, "admin_user_form.html", {"mode": "create", "form": form})


@admin_required
# Admin người dùng: chỉnh sửa tài khoản, vai trò hoặc trạng thái hoạt động.
def admin_user_edit(request, user_id):
    u = get_object_or_404(User, id=user_id)
    form = AdminUserForm(request.POST or None, instance=u)
    if request.method == "POST" and form.is_valid():
        if request.user == u and form.cleaned_data["role"] != "admin":
            form.add_error("role", "Bạn không thể tự hạ quyền chính mình xuống User.")
        if request.user == u and not form.cleaned_data["is_active"]:
            form.add_error("is_active", "Bạn không thể tự khóa tài khoản đang đăng nhập.")
        if not form.errors:
            password_changed = bool(form.cleaned_data.get("password"))
            saved_user = form.save()
            if request.user == u and password_changed:
                update_session_auth_hash(request, saved_user)
            messages.success(request, f"Đã cập nhật user {saved_user.username}.")
            return redirect("admin_user_list")
    return render(request, "admin_user_form.html", {"mode": "edit", "form": form, "u": u})


@admin_required
# Admin người dùng: xóa tài khoản khi phù hợp nghiệp vụ.
def admin_user_delete(request, user_id):
    u = get_object_or_404(User, id=user_id)
    if request.method == "POST":
        if request.user == u:
            messages.error(request, "Bạn không thể xoá chính tài khoản đang đăng nhập.")
            return redirect("admin_user_list")
        if DonHang.objects.filter(nguoi_dat=u).exists():
            messages.error(request, "Không thể xoá user đã phát sinh đơn hàng.")
            return redirect("admin_user_list")
        username = u.username
        u.delete()
        messages.success(request, f"Đã xoá user {username}.")
        return redirect("admin_user_list")
    return render(request, "admin_user_delete.html", {"u": u})


@admin_required
# Admin voucher: danh sách mã giảm giá với lọc, sắp xếp và tìm kiếm.
def admin_voucher_list(request):
    q = request.GET.get("q", "").strip()
    active = request.GET.get("active", "").strip()
    discount_type = request.GET.get("discount_type", "").strip()
    sort = request.GET.get("sort", "code_asc").strip()

    sort_map = {
        "code_asc": ["code"],
        "code_desc": ["-code"],
        "newest": ["-created_at", "-id"],
        "most_used": ["-used_count", "code"],
        "ending_soon": ["ends_at", "code"],
    }
    if sort not in sort_map:
        sort = "code_asc"

    ds = Voucher.objects.all()
    if q:
        ds = ds.filter(models.Q(code__icontains=q) | models.Q(title__icontains=q) | models.Q(description__icontains=q))
    if active == "1":
        ds = ds.filter(active=True)
    elif active == "0":
        ds = ds.filter(active=False)
    if discount_type in {code for code, _ in Voucher.DISCOUNT_TYPES}:
        ds = ds.filter(discount_type=discount_type)
    ds = ds.order_by(*sort_map[sort])

    return render(request, "admin_voucher_list.html", {
        "ds": ds,
        "q": q,
        "active": active,
        "discount_type": discount_type,
        "sort": sort,
        "sort_choices": [
            ("code_asc", "Mã A-Z"),
            ("code_desc", "Mã Z-A"),
            ("newest", "Mới nhất"),
            ("most_used", "Dùng nhiều nhất"),
            ("ending_soon", "Sắp hết hạn"),
        ],
        "discount_type_choices": Voucher.DISCOUNT_TYPES,
    })


@admin_required
# Admin voucher: xem chi tiết 1 voucher.
def admin_voucher_detail(request, voucher_id):
    voucher = get_object_or_404(Voucher, id=voucher_id)
    return render(request, "admin_voucher_detail.html", {"voucher": voucher})


@admin_required
# Admin voucher: tạo mới mã giảm giá.
def admin_voucher_create(request):
    form = VoucherAdminForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        voucher = form.save()
        messages.success(request, f"Đã tạo voucher {voucher.code}.")
        return redirect("admin_voucher_detail", voucher_id=voucher.id)
    return render(request, "admin_voucher_form.html", {"mode": "create", "form": form})


@admin_required
# Admin voucher: chỉnh sửa thông tin voucher.
def admin_voucher_edit(request, voucher_id):
    voucher = get_object_or_404(Voucher, id=voucher_id)
    form = VoucherAdminForm(request.POST or None, instance=voucher)
    if request.method == "POST" and form.is_valid():
        voucher = form.save()
        messages.success(request, f"Đã cập nhật voucher {voucher.code}.")
        return redirect("admin_voucher_detail", voucher_id=voucher.id)
    return render(request, "admin_voucher_form.html", {"mode": "edit", "form": form, "voucher": voucher})


@admin_required
# Admin voucher: xóa voucher nếu không vi phạm ràng buộc.
def admin_voucher_delete(request, voucher_id):
    voucher = get_object_or_404(Voucher, id=voucher_id)
    if request.method == "POST":
        code = voucher.code
        voucher.delete()
        messages.success(request, f"Đã xoá voucher {code}.")
        return redirect("admin_voucher_list")
    return render(request, "admin_voucher_delete.html", {"voucher": voucher})
