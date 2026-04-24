"""Business/services layer cho ứng dụng shop."""

from __future__ import annotations

import uuid
from datetime import timedelta
from typing import Iterable

from django.conf import settings
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.core.mail import send_mail
from django.db import models, transaction
from django.db.models import F
from django.utils import timezone

from .models import CartItem, DonHang, InventoryBatch, InventoryHistory, NhaCungCap, OrderStatusHistory, PhieuNhapKho, PhieuNhapKhoItem, SanPham, SavedAddress, Voucher, Wallet, WalletTopUpRequest, WalletTransaction


PRODUCT_SORTS = {
    "newest": ("-id",),
    "oldest": ("id",),
    "name_asc": ("ten", "id"),
    "name_desc": ("-ten", "-id"),
    "price_asc": ("gia", "id"),
    "price_desc": ("-gia", "-id"),
    "rating_desc": ("-id",),
}

ORDER_SORTS = {
    "newest": ("-id",),
    "oldest": ("id",),
    "total_asc": ("tong_tien", "id"),
    "total_desc": ("-tong_tien", "-id"),
    "status_asc": ("trang_thai", "-id"),
    "status_desc": ("-trang_thai", "-id"),
}

USER_SORTS = {
    "newest": ("-date_joined", "-id"),
    "oldest": ("date_joined", "id"),
    "name_asc": ("username", "id"),
    "name_desc": ("-username", "-id"),
}

INVENTORY_SORTS = {
    "lowest": ("ton_kho", "id"),
    "highest": ("-ton_kho", "id"),
    "name_asc": ("ten", "id"),
    "name_desc": ("-ten", "-id"),
    "newest": ("-id",),
}

ORDER_TRANSITIONS = {
    "user": {
        "Pending": {"Confirmed", "Cancelled"},
        "Confirmed": {"Cancelled"},
        "Approved": set(),
        "Rejected": set(),
        "Cancelled": set(),
    },
    "admin": {
        "Pending": {"Confirmed", "Approved", "Rejected", "Cancelled"},
        "Confirmed": {"Approved", "Rejected", "Cancelled"},
        "Approved": set(),
        "Rejected": set(),
        "Cancelled": set(),
    },
}


TOPUP_STATUS_LABELS = {
    "pending": "Chờ thanh toán",
    "paid": "Đã nhận callback",
    "approved": "Đã cộng ví",
    "rejected": "Từ chối",
}


def seed_sample_products() -> None:
    now = timezone.now()
    ds = [
        {
            "ten": "Bông tai Kim cương Vàng trắng 58,5% (14K) PNJ DD00W060198",
            "gia": 46_200_000,
            "gia_khuyen_mai": 41_580_000,
            "flash_sale_price": 39_900_000,
            "flash_sale_start": now - timedelta(hours=2),
            "flash_sale_end": now + timedelta(hours=10),
            "anh": "sanpham/bong_tai_kim_cuong_vang_trang.jpg",
            "mo_ta": "Bông tai dáng hoop nhỏ gọn, đính dãy đá sáng đều, phù hợp đeo hằng ngày hoặc phối cùng trang phục dự tiệc.",
            "ton_kho": 12,
        },
        {
            "ten": "Mặt dây chuyền Vàng 75% (18K) đính Ngọc trai Southsea PNJ PSDDC060001",
            "gia": 24_610_000,
            "anh": "sanpham/mat_day_ngoc_trai_vang_18k.jpg",
            "mo_ta": "Mặt dây chuyền ngọc trai tông vàng sang trọng, thiết kế mềm mại tạo điểm nhấn nổi bật cho vùng cổ.",
            "ton_kho": 8,
        },
        {
            "ten": "Lắc tay Vàng trắng Ý 75% (18K) PNJ 0000W01534",
            "gia": 15_892_000,
            "gia_khuyen_mai": 14_100_000,
            "anh": "sanpham/lac_tay_vang_trang_18k_pnj.jpg",
            "mo_ta": "Lắc tay thanh mảnh với charm hoa tinh tế, phong cách nữ tính, dễ kết hợp cùng đồng hồ và nhẫn mảnh.",
            "ton_kho": 15,
        },
        {
            "ten": "Nhẫn Kim cương Vàng trắng 58,5% (14K) PNJ DD00W060464",
            "gia": 34_620_000,
            "anh": "sanpham/nhan_kim_cuong_vang_trang_14k.jpg",
            "mo_ta": "Nhẫn vàng trắng đính kim cương kiểu baguette hiện đại, tôn vẻ thanh lịch và sang trọng cho người đeo.",
            "ton_kho": 10,
        },
        {
            "ten": "Mặt dây chuyền Vàng trắng 58,5% (14K) đính đá Sapphire PNJ SP00W000028",
            "gia": 8_740_000,
            "anh": "sanpham/mat_day_sapphire_vang_trang.jpg",
            "mo_ta": "Thiết kế mặt dây tròn cổ điển kết hợp đá sapphire xanh đậm, phù hợp làm quà tặng ý nghĩa.",
            "ton_kho": 9,
        },
        {
            "ten": "Nhẫn Vàng trắng 58,5% (14K) đính đá ECZ PNJ XMXMW005643",
            "gia": 10_476_000,
            "gia_khuyen_mai": 9_250_000,
            "flash_sale_price": 8_990_000,
            "flash_sale_start": now - timedelta(hours=1),
            "flash_sale_end": now + timedelta(hours=6),
            "anh": "sanpham/nhan_da_ecz_vang_trang.jpg",
            "mo_ta": "Nhẫn đính đá ECZ xếp tầng trẻ trung, độ sáng nổi bật, phù hợp đeo riêng hoặc chồng nhiều nhẫn.",
            "ton_kho": 20,
        },
        {
            "ten": "Bông tai Vàng trắng 41,6% (10K) đính đá ECZ PNJ XMXMW060874",
            "gia": 13_070_000,
            "anh": "sanpham/bong_tai_hoa_vang_trang_10k.jpg",
            "mo_ta": "Bông tai hoa đính đá lấp lánh, thiết kế cân đối và sang nhã, phù hợp phong cách thanh lịch.",
            "ton_kho": 14,
        },
        {
            "ten": "Lắc tay Vàng 58,5% (14K) PNJ 0000Y060888",
            "gia": 15_370_000,
            "anh": "sanpham/lac_tay_vang_14k_pnj.jpg",
            "mo_ta": "Lắc tay sắc vàng nổi bật với họa tiết xoắn mềm mại, tạo cảm giác đầy đặn nhưng vẫn nữ tính.",
            "ton_kho": 11,
        },
    ]
    for item in ds:
        SanPham.objects.update_or_create(
            ten=item["ten"],
            defaults={"gia": item["gia"], "gia_khuyen_mai": item.get("gia_khuyen_mai"), "flash_sale_price": item.get("flash_sale_price"), "flash_sale_start": item.get("flash_sale_start"), "flash_sale_end": item.get("flash_sale_end"), "anh": item["anh"], "mo_ta": item["mo_ta"], "ton_kho": item.get("ton_kho", 10), "trang_thai": "active"},
        )


def seed_sample_vouchers() -> None:
    ds = [
        {
            "code": "GIAM10",
            "title": "Giảm 10%",
            "description": "Giảm 10% cho đơn từ 500.000đ",
            "discount_type": "percent",
            "value": 10,
            "min_order_value": 500_000,
            "max_discount": 300_000,
        },
        {
            "code": "FREESHIP50",
            "title": "Giảm 50.000đ",
            "description": "Giảm trực tiếp 50.000đ cho đơn từ 1.000.000đ",
            "discount_type": "fixed",
            "value": 50_000,
            "min_order_value": 1_000_000,
            "max_discount": 50_000,
        },
    ]
    for item in ds:
        Voucher.objects.update_or_create(
            code=item["code"],
            defaults={**item, "active": True},
        )


def get_user_role(user) -> str:
    if not getattr(user, "is_authenticated", False):
        return "guest"
    if getattr(user, "is_staff", False) or getattr(user, "is_superuser", False):
        return "admin"
    return "user"


def calculate_order_total(product: SanPham, quantity: int) -> int:
    return int(product.gia_hien_tai) * int(quantity)


def get_or_create_wallet(user: User) -> Wallet:
    wallet, _ = Wallet.objects.get_or_create(user=user)
    return wallet


def get_cart_items(user: User):
    return CartItem.objects.filter(user=user).select_related("san_pham")


def cart_item_count(user: User) -> int:
    if not getattr(user, "is_authenticated", False):
        return 0
    return get_cart_items(user).count()


def get_saved_addresses(user: User):
    if not getattr(user, "is_authenticated", False):
        return SavedAddress.objects.none()
    return SavedAddress.objects.filter(user=user).order_by("-is_default", "-updated_at", "-id")


def get_default_saved_address(user: User) -> SavedAddress | None:
    return get_saved_addresses(user).first()


def save_user_address(*, user: User, cleaned_data: dict) -> SavedAddress | None:
    if not getattr(user, "is_authenticated", False):
        return None
    if not cleaned_data.get("save_address"):
        return None
    is_default = bool(cleaned_data.get("set_default_address"))
    label = (cleaned_data.get("address_label") or "").strip()
    addr, created = SavedAddress.objects.get_or_create(
        user=user,
        ho_ten=cleaned_data["ho_ten"],
        sdt=cleaned_data["sdt"],
        dia_chi=cleaned_data["dia_chi"],
        defaults={"label": label, "is_default": is_default},
    )
    changed = False
    if label and addr.label != label:
        addr.label = label
        changed = True
    if is_default and not addr.is_default:
        addr.is_default = True
        changed = True
    if changed:
        addr.save()
    elif created and is_default:
        addr.save()
    return addr


def create_inventory_history(*, product: SanPham, old_stock: int, new_stock: int, change_type: str, actor: User | None = None, note: str = "", order: DonHang | None = None) -> InventoryHistory:
    return InventoryHistory.objects.create(
        san_pham=product,
        old_stock=int(old_stock or 0),
        quantity_change=int(new_stock or 0) - int(old_stock or 0),
        new_stock=int(new_stock or 0),
        change_type=change_type,
        actor=actor,
        order=order,
        note=note,
    )


def adjust_product_stock(*, product: SanPham, action: str, quantity: int, actor: User | None = None, note: str = "") -> SanPham:
    quantity = int(quantity or 0)
    product = SanPham.objects.select_for_update().get(pk=product.pk)
    old_stock = int(product.ton_kho or 0)

    if action == "set":
        new_stock = quantity
        change_type = "manual_set"
    elif action == "increase":
        if quantity <= 0:
            raise ValidationError("Số lượng nhập kho phải lớn hơn 0.")
        new_stock = old_stock + quantity
        change_type = "manual_in"
    elif action == "decrease":
        if quantity <= 0:
            raise ValidationError("Số lượng xuất kho phải lớn hơn 0.")
        if old_stock < quantity:
            raise ValidationError(f"Không thể xuất {quantity} sản phẩm vì kho hiện chỉ còn {old_stock}.")
        new_stock = old_stock - quantity
        change_type = "manual_out"
    else:
        raise ValidationError("Thao tác kho không hợp lệ.")

    product.ton_kho = new_stock
    product.save(update_fields=["ton_kho"])
    create_inventory_history(product=product, old_stock=old_stock, new_stock=new_stock, change_type=change_type, actor=actor, note=note)
    return product


def ensure_stock_available(*, product: SanPham, quantity: int) -> None:
    if quantity <= 0:
        raise ValidationError("Số lượng phải lớn hơn 0.")
    if product.trang_thai != "active":
        raise ValidationError("Sản phẩm hiện không khả dụng.")
    if int(product.ton_kho or 0) < int(quantity):
        raise ValidationError(f"Sản phẩm {product.ten} chỉ còn {int(product.ton_kho or 0)} trong kho.")


def decrease_stock(*, product: SanPham, quantity: int, actor: User | None = None, note: str = "", order: DonHang | None = None, change_type: str = "order_out") -> None:
    ensure_stock_available(product=product, quantity=quantity)
    old_stock = int(product.ton_kho or 0)
    updated = SanPham.objects.filter(id=product.id, ton_kho__gte=quantity).update(ton_kho=F("ton_kho") - quantity)
    if not updated:
        product.refresh_from_db()
        raise ValidationError(f"Sản phẩm {product.ten} không đủ tồn kho.")
    product.refresh_from_db(fields=["ton_kho"])
    create_inventory_history(product=product, old_stock=old_stock, new_stock=product.ton_kho, change_type=change_type, actor=actor, note=note, order=order)


def increase_stock(*, product: SanPham, quantity: int, actor: User | None = None, note: str = "", order: DonHang | None = None, change_type: str = "order_return") -> None:
    if quantity <= 0:
        return
    old_stock = int(product.ton_kho or 0)
    SanPham.objects.filter(id=product.id).update(ton_kho=F("ton_kho") + quantity)
    product.refresh_from_db(fields=["ton_kho"])
    create_inventory_history(product=product, old_stock=old_stock, new_stock=product.ton_kho, change_type=change_type, actor=actor, note=note, order=order)


def cart_subtotal(user: User) -> int:
    return sum(item.thanh_tien for item in get_cart_items(user))


@transaction.atomic
def add_product_to_cart(*, user: User, product: SanPham, quantity: int = 1) -> CartItem:
    if quantity <= 0:
        raise ValidationError("Số lượng phải lớn hơn 0.")
    ensure_stock_available(product=product, quantity=quantity)
    item, created = CartItem.objects.select_for_update().get_or_create(user=user, san_pham=product, defaults={"quantity": quantity})
    if not created:
        item.quantity += quantity
        item.save(update_fields=["quantity", "updated_at"])
    return item


@transaction.atomic
def update_cart_item_quantity(*, item: CartItem, quantity: int) -> None:
    if quantity <= 0:
        item.delete()
        return
    item.quantity = quantity
    item.save(update_fields=["quantity", "updated_at"])


def _tag(tag: str, value: str) -> str:
    value = value or ""
    return f"{tag}{len(value):02d}{value}"


def _crc16_ccitt_false(payload: str) -> str:
    crc = 0xFFFF
    for ch in payload.encode("utf-8"):
        crc ^= ch << 8
        for _ in range(8):
            if crc & 0x8000:
                crc = (crc << 1) ^ 0x1021
            else:
                crc <<= 1
            crc &= 0xFFFF
    return f"{crc:04X}"


def get_bank_info() -> dict:
    return {
        "bank_bin": getattr(settings, "VIETQR_BANK_BIN", "970422"),
        "bank_name": getattr(settings, "VIETQR_BANK_NAME", "MB Bank"),
        "account_no": getattr(settings, "VIETQR_ACCOUNT_NO", "0123456789"),
        "account_name": getattr(settings, "VIETQR_ACCOUNT_NAME", "TRANG SUC DEMO"),
        "city": getattr(settings, "VIETQR_CITY", "HA NOI"),
    }


def build_vietqr_payload(*, amount: int, description: str) -> str:
    bank = get_bank_info()
    merchant_info = _tag("00", bank["bank_bin"]) + _tag("01", bank["account_no"]) + _tag("02", "QRIBFTTA")
    consumer = _tag("00", "A000000727") + _tag("01", merchant_info)
    payload = (
        _tag("00", "01")
        + _tag("01", "12")
        + _tag("38", consumer)
        + _tag("52", "5812")
        + _tag("53", "704")
        + _tag("54", str(amount))
        + _tag("58", "VN")
        + _tag("59", bank["account_name"][:25])
        + _tag("60", bank["city"][:15])
        + _tag("62", _tag("08", description[:25]))
    )
    payload_for_crc = payload + "6304"
    return payload_for_crc + _crc16_ccitt_false(payload_for_crc)


def make_reference(prefix: str) -> str:
    prefix = (prefix or "REF").upper()[:8]
    return f"{prefix}{uuid.uuid4().hex[:10].upper()}"


@transaction.atomic
def create_topup_request(*, user: User, amount: int) -> WalletTopUpRequest:
    if amount <= 0:
        raise ValidationError("Số tiền nạp phải lớn hơn 0.")

    wallet = get_or_create_wallet(user)
    reference = make_reference("NAP")
    transfer_note = f"NAPVI {reference}"[:25]
    qr_payload = build_vietqr_payload(amount=amount, description=transfer_note)
    return WalletTopUpRequest.objects.create(
        wallet=wallet,
        amount=amount,
        reference=reference,
        transfer_note=transfer_note,
        qr_payload=qr_payload,
        status="pending",
    )


@transaction.atomic
def approve_topup_request(*, topup: WalletTopUpRequest, approved_by: User | None = None) -> tuple[bool, str]:
    if topup.status == "approved":
        return True, "Yêu cầu nạp tiền đã được cộng ví trước đó."
    if topup.status == "rejected":
        return False, "Yêu cầu này đã bị từ chối."

    wallet = topup.wallet
    wallet.balance += topup.amount
    wallet.save(update_fields=["balance", "updated_at"])

    now = timezone.now()
    topup.status = "approved"
    topup.paid_at = topup.paid_at or now
    topup.approved_at = now
    if approved_by is not None:
        topup.approved_by = approved_by
    topup.save(update_fields=["status", "paid_at", "approved_at", "approved_by"])

    WalletTransaction.objects.create(
        wallet=wallet,
        amount=topup.amount,
        transaction_type="deposit",
        note=f"Nạp tiền QR {topup.reference}",
    )
    return True, f"Đã cộng {topup.amount:,} VND vào ví cho yêu cầu {topup.reference}."


@transaction.atomic
def mark_topup_paid(*, topup: WalletTopUpRequest, auto_credit: bool = True) -> tuple[bool, str]:
    if topup.status == "approved":
        return True, "Giao dịch đã hoàn tất và ví đã được cộng tiền."
    if topup.status == "rejected":
        return False, "Giao dịch này đã bị từ chối nên không thể callback."

    if topup.status == "pending":
        topup.status = "paid"
        topup.paid_at = timezone.now()
        topup.save(update_fields=["status", "paid_at"])

    if auto_credit:
        return approve_topup_request(topup=topup)
    return True, "Đã ghi nhận callback thanh toán. Chờ admin duyệt nạp tiền."


@transaction.atomic
def reject_topup_request(*, topup: WalletTopUpRequest, approved_by: User | None = None, reason: str = "") -> tuple[bool, str]:
    if topup.status == "approved":
        return False, "Yêu cầu đã được cộng ví nên không thể từ chối."
    if topup.status == "rejected":
        return True, "Yêu cầu đã ở trạng thái từ chối."

    topup.status = "rejected"
    topup.rejected_reason = reason or "Admin từ chối yêu cầu nạp tiền."
    if approved_by is not None:
        topup.approved_by = approved_by
    topup.save(update_fields=["status", "rejected_reason", "approved_by"])
    return True, f"Đã từ chối yêu cầu {topup.reference}."


@transaction.atomic
def mark_order_paid_by_bank(*, order: DonHang) -> tuple[bool, str]:
    if order.phuong_thuc_tt != "ChuyenKhoan":
        return False, "Đơn hàng này không dùng chuyển khoản ngân hàng."
    if order.da_thanh_toan:
        return True, f"Đơn #{order.id} đã được ghi nhận thanh toán trước đó."

    order.da_thanh_toan = True
    order.thanh_toan_luc = timezone.now()
    order.ma_thanh_toan = order.ma_thanh_toan or f"DH{order.id}"
    order.save(update_fields=["da_thanh_toan", "thanh_toan_luc", "ma_thanh_toan"])
    return True, f"Đã ghi nhận thanh toán chuyển khoản cho đơn #{order.id}."


def get_voucher_by_code(code: str) -> Voucher | None:
    code = (code or "").strip().upper()
    if not code:
        return None
    return Voucher.objects.filter(code__iexact=code).first()


def calculate_voucher_discount(*, voucher: Voucher | None, subtotal: int) -> int:
    if not voucher:
        return 0
    subtotal = max(int(subtotal or 0), 0)
    if subtotal <= 0:
        return 0
    if voucher.discount_type == "percent":
        discount = subtotal * int(voucher.value or 0) // 100
    else:
        discount = int(voucher.value or 0)
    if voucher.max_discount:
        discount = min(discount, int(voucher.max_discount))
    return max(min(discount, subtotal), 0)


def validate_voucher(*, code: str, subtotal: int) -> Voucher | None:
    code = (code or "").strip().upper()
    if not code:
        return None
    voucher = get_voucher_by_code(code)
    if not voucher:
        raise ValidationError("Mã giảm giá không tồn tại.")
    if not voucher.is_available_now():
        raise ValidationError("Mã giảm giá hiện không khả dụng.")
    if subtotal < int(voucher.min_order_value or 0):
        raise ValidationError(f"Đơn hàng cần từ {int(voucher.min_order_value):,} VND để áp dụng mã này.")
    discount = calculate_voucher_discount(voucher=voucher, subtotal=subtotal)
    if discount <= 0:
        raise ValidationError("Mã giảm giá không áp dụng được cho đơn hàng hiện tại.")
    return voucher


def build_checkout_pricing(*, subtotal: int, voucher_code: str = "") -> dict:
    subtotal = max(int(subtotal or 0), 0)
    voucher = validate_voucher(code=voucher_code, subtotal=subtotal) if voucher_code else None
    discount = calculate_voucher_discount(voucher=voucher, subtotal=subtotal)
    return {
        "subtotal": subtotal,
        "discount": discount,
        "total": max(subtotal - discount, 0),
        "voucher": voucher,
        "voucher_code": voucher.code if voucher else (voucher_code or "").strip().upper(),
    }


def _allocate_discount(total_discount: int, amounts: list[int]) -> list[int]:
    if total_discount <= 0 or not amounts:
        return [0 for _ in amounts]
    total_amount = sum(amounts)
    if total_amount <= 0:
        return [0 for _ in amounts]
    allocations = []
    allocated = 0
    for idx, amount in enumerate(amounts):
        if idx == len(amounts) - 1:
            current = total_discount - allocated
        else:
            current = total_discount * amount // total_amount
            allocated += current
        allocations.append(current)
    return allocations


@transaction.atomic
def create_order_from_checkout(*, user: User, product: SanPham, cleaned_data: dict) -> DonHang:
    so_luong = int(cleaned_data["so_luong"])
    product = SanPham.objects.select_for_update().get(pk=product.pk)
    ensure_stock_available(product=product, quantity=so_luong)
    tong_tien_goc = calculate_order_total(product, so_luong)
    voucher = validate_voucher(code=cleaned_data.get("voucher_code", ""), subtotal=tong_tien_goc) if cleaned_data.get("voucher_code") else None
    discount_amount = calculate_voucher_discount(voucher=voucher, subtotal=tong_tien_goc)
    tong_tien = tong_tien_goc - discount_amount
    phuong_thuc_tt = cleaned_data["phuong_thuc_tt"]

    if phuong_thuc_tt == "ViDienTu":
        wallet = get_or_create_wallet(user)
        if wallet.balance < tong_tien:
            raise ValidationError("Số dư ví không đủ để thanh toán đơn hàng này.")
        wallet.balance -= tong_tien
        wallet.save(update_fields=["balance", "updated_at"])
    else:
        wallet = None

    decrease_stock(product=product, quantity=so_luong, actor=user, order=None, note=f"Tạo đơn hàng mới với số lượng {so_luong}")

    order = DonHang.objects.create(
        nguoi_dat=user,
        san_pham=product,
        voucher=voucher,
        ho_ten=cleaned_data["ho_ten"],
        sdt=cleaned_data["sdt"],
        dia_chi=cleaned_data["dia_chi"],
        ghi_chu=cleaned_data.get("ghi_chu", ""),
        phuong_thuc_tt=phuong_thuc_tt,
        so_luong=so_luong,
        tong_tien_goc=tong_tien_goc,
        discount_amount=discount_amount,
        voucher_code=voucher.code if voucher else "",
        tong_tien=tong_tien,
        trang_thai="Pending",
        da_thanh_toan=(phuong_thuc_tt == "ViDienTu"),
    )

    if voucher:
        Voucher.objects.filter(pk=voucher.pk).update(used_count=F("used_count") + 1)

    if phuong_thuc_tt == "ViDienTu":
        order.ma_thanh_toan = make_reference("VIDT")
        order.thanh_toan_luc = timezone.now()
        order.save(update_fields=["ma_thanh_toan", "thanh_toan_luc"])
        WalletTransaction.objects.create(
            wallet=wallet,
            amount=tong_tien,
            transaction_type="payment",
            order=order,
            note=f"Thanh toán đơn hàng #{order.id} bằng ví điện tử",
        )
    elif phuong_thuc_tt == "ChuyenKhoan":
        order.ma_thanh_toan = f"DH{order.id}"
        order.save(update_fields=["ma_thanh_toan"])

    return order


@transaction.atomic
def create_orders_from_cart(*, user: User, cleaned_data: dict) -> list[DonHang]:
    items = list(get_cart_items(user).select_for_update())
    for item in items:
        item.san_pham = SanPham.objects.select_for_update().get(pk=item.san_pham_id)
        ensure_stock_available(product=item.san_pham, quantity=item.quantity)
    if not items:
        raise ValidationError("Giỏ hàng của bạn đang trống.")
    subtotals = [item.thanh_tien for item in items]
    subtotal = sum(subtotals)
    voucher = validate_voucher(code=cleaned_data.get("voucher_code", ""), subtotal=subtotal) if cleaned_data.get("voucher_code") else None
    total_discount = calculate_voucher_discount(voucher=voucher, subtotal=subtotal)
    discount_allocations = _allocate_discount(total_discount, subtotals)
    total_payable = subtotal - total_discount
    phuong_thuc_tt = cleaned_data["phuong_thuc_tt"]

    if phuong_thuc_tt == "ViDienTu":
        wallet = get_or_create_wallet(user)
        if wallet.balance < total_payable:
            raise ValidationError("Số dư ví không đủ để thanh toán toàn bộ giỏ hàng.")
        wallet.balance -= total_payable
        wallet.save(update_fields=["balance", "updated_at"])
    else:
        wallet = None

    orders = []
    for item in items:
        decrease_stock(product=item.san_pham, quantity=item.quantity, actor=user, order=None, note=f"Checkout giỏ hàng với số lượng {item.quantity}")

    for item, item_discount in zip(items, discount_allocations):
        order = DonHang.objects.create(
            nguoi_dat=user,
            san_pham=item.san_pham,
            voucher=voucher,
            ho_ten=cleaned_data["ho_ten"],
            sdt=cleaned_data["sdt"],
            dia_chi=cleaned_data["dia_chi"],
            ghi_chu=cleaned_data.get("ghi_chu", ""),
            phuong_thuc_tt=phuong_thuc_tt,
            so_luong=item.quantity,
            tong_tien_goc=item.thanh_tien,
            discount_amount=item_discount,
            voucher_code=voucher.code if voucher else "",
            tong_tien=max(item.thanh_tien - item_discount, 0),
            trang_thai="Pending",
            da_thanh_toan=(phuong_thuc_tt == "ViDienTu"),
        )
        if phuong_thuc_tt == "ViDienTu":
            order.ma_thanh_toan = make_reference("VIDT")
            order.thanh_toan_luc = timezone.now()
            order.save(update_fields=["ma_thanh_toan", "thanh_toan_luc"])
            WalletTransaction.objects.create(
                wallet=wallet,
                amount=order.tong_tien,
                transaction_type="payment",
                order=order,
                note=f"Thanh toán đơn hàng #{order.id} bằng ví điện tử từ giỏ hàng",
            )
        elif phuong_thuc_tt == "ChuyenKhoan":
            order.ma_thanh_toan = f"DH{order.id}"
            order.save(update_fields=["ma_thanh_toan"])
        orders.append(order)

    if voucher:
        Voucher.objects.filter(pk=voucher.pk).update(used_count=F("used_count") + 1)
    CartItem.objects.filter(id__in=[item.id for item in items]).delete()
    return orders


def can_transition(current_status: str, new_status: str, actor_role: str) -> bool:
    if current_status == new_status:
        return True
    role_key = "admin" if actor_role == "admin" else "user"
    allowed = ORDER_TRANSITIONS.get(role_key, {}).get(current_status, set())
    return new_status in allowed


def get_allowed_statuses(order: DonHang, actor_role: str, *, include_current: bool = True) -> list[tuple[str, str]]:
    allowed_codes: Iterable[str] = ORDER_TRANSITIONS.get(
        "admin" if actor_role == "admin" else "user", {}
    ).get(order.trang_thai, set())

    choices = []
    for code, label in DonHang.TRANG_THAI:
        if code == order.trang_thai and include_current:
            choices.append((code, label))
        elif code in allowed_codes:
            choices.append((code, label))
    return choices


def send_order_status_email(*, order: DonHang, old_status: str, new_status: str) -> None:
    email = (order.nguoi_dat.email or "").strip()
    if not email:
        return
    subject = f"[Trang suc] Don hang #{order.id} da chuyen sang {order.get_trang_thai_display()}"
    body = (
        f"Xin chao {order.ho_ten or order.nguoi_dat.username},\n\n"
        f"Don hang #{order.id} cua ban vua duoc cap nhat trang thai.\n"
        f"- San pham: {order.san_pham.ten}\n"
        f"- Trang thai cu: {old_status or 'Moi tao'}\n"
        f"- Trang thai moi: {new_status}\n"
        f"- Tong thanh toan: {order.tong_tien:,} VND\n\n"
        f"Cam on ban da mua sam tai he thong demo."
    )
    send_mail(subject, body, getattr(settings, "DEFAULT_FROM_EMAIL", None), [email], fail_silently=True)


@transaction.atomic
def update_order_status(*, order: DonHang, new_status: str, actor_role: str, actor: User | None = None) -> tuple[bool, str]:
    valid_codes = {code for code, _ in DonHang.TRANG_THAI}
    if new_status not in valid_codes:
        return False, "Trạng thái không hợp lệ."

    if order.trang_thai == new_status:
        return True, "Trạng thái đơn hàng không thay đổi."

    if not can_transition(order.trang_thai, new_status, actor_role):
        return False, f"Không thể chuyển từ {order.trang_thai} sang {new_status}."

    previous_status = order.trang_thai
    order.trang_thai = new_status

    needs_refund = (
        new_status in {"Cancelled", "Rejected"}
        and not order.da_hoan_tien
        and (
            order.phuong_thuc_tt == "ViDienTu"
            or (order.phuong_thuc_tt == "ChuyenKhoan" and order.da_thanh_toan)
        )
    )

    if new_status in {"Cancelled", "Rejected"} and previous_status not in {"Cancelled", "Rejected"}:
        increase_stock(product=order.san_pham, quantity=order.so_luong, actor=actor, order=order, note=f"Hoàn kho do đơn #{order.id} chuyển sang {new_status}")

    if needs_refund:
        wallet = get_or_create_wallet(order.nguoi_dat)
        wallet.balance += order.tong_tien
        wallet.save(update_fields=["balance", "updated_at"])
        order.da_hoan_tien = True

        refund_note = (
            f"Hoàn tiền đơn ví điện tử #{order.id}"
            if order.phuong_thuc_tt == "ViDienTu"
            else f"Hoàn tiền tự động cho đơn chuyển khoản #{order.id}"
        )
        WalletTransaction.objects.create(
            wallet=wallet,
            amount=order.tong_tien,
            transaction_type="refund",
            order=order,
            note=refund_note,
        )
        refund_suffix = " Đã hoàn tiền vào ví điện tử."
    else:
        refund_suffix = ""

    order.save(update_fields=["trang_thai", "da_hoan_tien"])
    OrderStatusHistory.objects.create(order=order, old_status=previous_status, new_status=new_status, actor=actor, note=f"Cập nhật bởi {'admin' if actor_role == 'admin' else 'user'}")
    send_order_status_email(order=order, old_status=previous_status, new_status=new_status)
    return True, f"Đã cập nhật trạng thái đơn #{order.id} thành {order.get_trang_thai_display()}.{refund_suffix}"



SUPPLIER_SORTS = {
    "name_asc": ("ten", "id"),
    "name_desc": ("-ten", "-id"),
    "newest": ("-created_at", "-id"),
    "oldest": ("created_at", "id"),
}

RECEIPT_SORTS = {
    "newest": ("-created_at", "-id"),
    "oldest": ("created_at", "id"),
    "code_asc": ("code", "id"),
    "code_desc": ("-code", "-id"),
}

BATCH_SORTS = {
    "newest": ("-imported_at", "-id"),
    "oldest": ("imported_at", "id"),
    "qty_desc": ("-so_luong_nhap", "-id"),
    "qty_asc": ("so_luong_nhap", "id"),
}


def make_receipt_code() -> str:
    return make_reference("PNK")[:18]


@transaction.atomic
def create_purchase_receipt(*, supplier: NhaCungCap | None, created_by: User | None, note: str = "", items: list[dict] | None = None) -> PhieuNhapKho:
    items = items or []
    if not items:
        raise ValidationError("Phiếu nhập kho cần ít nhất 1 dòng sản phẩm.")

    receipt = PhieuNhapKho.objects.create(
        code=make_receipt_code(),
        supplier=supplier,
        created_by=created_by,
        note=note or "",
        status="draft",
    )
    for item in items:
        product = item.get("product")
        quantity = int(item.get("quantity") or 0)
        unit_price = int(item.get("unit_price") or 0)
        if not product or quantity <= 0:
            continue
        batch_code = (item.get("batch_code") or "").strip().upper() or f"{receipt.code}-{product.id}"
        PhieuNhapKhoItem.objects.create(
            receipt=receipt,
            san_pham=product,
            so_luong=quantity,
            don_gia_nhap=unit_price,
            batch_code=batch_code,
            ghi_chu=(item.get("note") or "").strip(),
        )
    if not receipt.items.exists():
        raise ValidationError("Không có dòng nhập kho hợp lệ để lưu phiếu.")
    return receipt


@transaction.atomic
def receive_purchase_receipt(*, receipt: PhieuNhapKho, actor: User | None = None) -> tuple[bool, str]:
    receipt = PhieuNhapKho.objects.select_for_update().select_related("supplier").get(pk=receipt.pk)
    if receipt.status == "received":
        return True, f"Phiếu {receipt.code} đã được nhập kho trước đó."
    if receipt.status == "cancelled":
        return False, f"Phiếu {receipt.code} đã bị huỷ nên không thể nhập kho."

    items = list(receipt.items.select_related("san_pham"))
    if not items:
        return False, "Phiếu nhập kho chưa có dòng sản phẩm."

    imported_at = timezone.now()
    for item in items:
        increase_stock(
            product=item.san_pham,
            quantity=item.so_luong,
            actor=actor,
            note=f"Nhập kho theo phiếu {receipt.code} - lô {item.batch_code}",
            change_type="receipt_in",
        )
        InventoryBatch.objects.create(
            san_pham=item.san_pham,
            supplier=receipt.supplier,
            receipt=receipt,
            receipt_item=item,
            batch_code=item.batch_code or f"{receipt.code}-{item.san_pham_id}",
            so_luong_nhap=item.so_luong,
            so_luong_con_lai=item.so_luong,
            don_gia_nhap=item.don_gia_nhap,
            imported_at=imported_at,
            created_by=actor,
            note=item.ghi_chu or receipt.note,
        )

    receipt.status = "received"
    receipt.imported_at = imported_at
    receipt.save(update_fields=["status", "imported_at", "updated_at"])
    return True, f"Đã nhập kho thành công cho phiếu {receipt.code}."


@transaction.atomic
def cancel_purchase_receipt(*, receipt: PhieuNhapKho) -> tuple[bool, str]:
    receipt = PhieuNhapKho.objects.select_for_update().get(pk=receipt.pk)
    if receipt.status == "received":
        return False, f"Phiếu {receipt.code} đã nhập kho nên không thể huỷ."
    if receipt.status == "cancelled":
        return True, f"Phiếu {receipt.code} đã ở trạng thái huỷ."
    receipt.status = "cancelled"
    receipt.save(update_fields=["status", "updated_at"])
    return True, f"Đã huỷ phiếu nhập kho {receipt.code}."


def apply_supplier_filters(queryset, *, q: str = "", active: str = "", sort: str = "name_asc"):
    if q:
        queryset = queryset.filter(
            models.Q(ten__icontains=q)
            | models.Q(sdt__icontains=q)
            | models.Q(email__icontains=q)
            | models.Q(dia_chi__icontains=q)
        )
    if active == "active":
        queryset = queryset.filter(active=True)
    elif active == "inactive":
        queryset = queryset.filter(active=False)
    return queryset.order_by(*SUPPLIER_SORTS.get(sort, SUPPLIER_SORTS["name_asc"]))


def apply_receipt_filters(queryset, *, q: str = "", status: str = "", sort: str = "newest"):
    if q:
        queryset = queryset.filter(
            models.Q(code__icontains=q)
            | models.Q(supplier__ten__icontains=q)
            | models.Q(note__icontains=q)
            | models.Q(items__san_pham__ten__icontains=q)
            | models.Q(items__batch_code__icontains=q)
        ).distinct()
    if status in {code for code, _ in PhieuNhapKho.STATUS_CHOICES}:
        queryset = queryset.filter(status=status)
    return queryset.order_by(*RECEIPT_SORTS.get(sort, RECEIPT_SORTS["newest"]))


def apply_batch_filters(queryset, *, q: str = "", sort: str = "newest"):
    if q:
        queryset = queryset.filter(
            models.Q(batch_code__icontains=q)
            | models.Q(san_pham__ten__icontains=q)
            | models.Q(receipt__code__icontains=q)
            | models.Q(supplier__ten__icontains=q)
        )
    return queryset.order_by(*BATCH_SORTS.get(sort, BATCH_SORTS["newest"]))

def build_order_transfer_qr(order: DonHang) -> str:
    return build_vietqr_payload(amount=order.tong_tien, description=(order.ma_thanh_toan or f"DH{order.id}")[:25])


def apply_product_filters(queryset, *, q: str = "", status: str = "", sort: str = "newest"):
    if q:
        queryset = queryset.filter(
            models.Q(ten__icontains=q)
            | models.Q(mo_ta__icontains=q)
            | models.Q(search_tags__icontains=q)
        )
    if status in {code for code, _ in SanPham.TRANG_THAI}:
        queryset = queryset.filter(trang_thai=status)
    return queryset.order_by(*PRODUCT_SORTS.get(sort, PRODUCT_SORTS["newest"]))


def apply_order_filters(queryset, *, q: str = "", status: str = "", payment: str = "", sort: str = "newest"):
    if status in {code for code, _ in DonHang.TRANG_THAI}:
        queryset = queryset.filter(trang_thai=status)
    if payment in {code for code, _ in DonHang.PHUONG_THUC_TT}:
        queryset = queryset.filter(phuong_thuc_tt=payment)
    if q:
        queryset = queryset.filter(
            models.Q(nguoi_dat__username__icontains=q)
            | models.Q(ho_ten__icontains=q)
            | models.Q(sdt__icontains=q)
            | models.Q(san_pham__ten__icontains=q)
            | models.Q(dia_chi__icontains=q)
            | models.Q(ma_thanh_toan__icontains=q)
            | models.Q(voucher_code__icontains=q)
        )
    return queryset.order_by(*ORDER_SORTS.get(sort, ORDER_SORTS["newest"]))


def apply_user_filters(queryset, *, q: str = "", role: str = "", active: str = "", sort: str = "newest"):
    if q:
        queryset = queryset.filter(models.Q(username__icontains=q) | models.Q(email__icontains=q))
    if role == "admin":
        queryset = queryset.filter(is_staff=True)
    elif role == "user":
        queryset = queryset.filter(is_staff=False)
    if active == "active":
        queryset = queryset.filter(is_active=True)
    elif active == "inactive":
        queryset = queryset.filter(is_active=False)
    return queryset.order_by(*USER_SORTS.get(sort, USER_SORTS["newest"]))
