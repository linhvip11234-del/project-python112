from django.contrib import admin

from .models import CartItem, DonHang, InventoryBatch, InventoryHistory, NhaCungCap, OrderStatusHistory, PhieuNhapKho, PhieuNhapKhoItem, ProductImage, ProductReview, SanPham, SavedAddress, UserSecurityProfile, Voucher, Wallet, WalletTopUpRequest, WalletTransaction


@admin.register(SanPham)
class SanPhamAdmin(admin.ModelAdmin):
    list_display = ("id", "ten", "gia", "gia_khuyen_mai", "flash_sale_price", "ton_kho", "flash_sale_start", "flash_sale_end", "trang_thai")
    list_filter = ("trang_thai",)
    search_fields = ("ten",)
    ordering = ("-id",)


@admin.register(UserSecurityProfile)
class UserSecurityProfileAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "question_1", "question_2", "updated_at")
    search_fields = ("user__username", "user__email")
    ordering = ("-updated_at", "-id")


@admin.register(DonHang)
class DonHangAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "nguoi_dat",
        "san_pham",
        "so_luong",
        "tong_tien",
        "trang_thai",
        "phuong_thuc_tt",
        "tao_luc",
    )
    list_filter = ("trang_thai", "phuong_thuc_tt", "tao_luc")
    search_fields = (
        "nguoi_dat__username",
        "san_pham__ten",
        "ho_ten",
        "sdt",
        "dia_chi",
    )
    ordering = ("-id",)


@admin.register(Wallet)
class WalletAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "balance", "updated_at")
    search_fields = ("user__username", "user__email")
    ordering = ("-updated_at",)


@admin.register(WalletTransaction)
class WalletTransactionAdmin(admin.ModelAdmin):
    list_display = ("id", "wallet", "transaction_type", "amount", "order", "created_at")
    list_filter = ("transaction_type", "created_at")
    search_fields = ("wallet__user__username", "note")
    ordering = ("-created_at", "-id")


@admin.register(WalletTopUpRequest)
class WalletTopUpRequestAdmin(admin.ModelAdmin):
    list_display = ("id", "wallet", "amount", "reference", "status", "created_at", "approved_at")
    list_filter = ("status", "created_at", "approved_at")
    search_fields = ("wallet__user__username", "reference", "transfer_note")
    ordering = ("-created_at", "-id")


@admin.register(Voucher)
class VoucherAdmin(admin.ModelAdmin):
    list_display = ("id", "code", "title", "discount_type", "value", "used_count", "usage_limit", "active")
    list_filter = ("discount_type", "active")
    search_fields = ("code", "title", "description")
    ordering = ("code",)


@admin.register(CartItem)
class CartItemAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "san_pham", "quantity", "updated_at")
    search_fields = ("user__username", "san_pham__ten")
    ordering = ("-updated_at", "-id")


@admin.register(SavedAddress)
class SavedAddressAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "label", "ho_ten", "sdt", "is_default", "updated_at")
    search_fields = ("user__username", "label", "ho_ten", "sdt", "dia_chi")
    list_filter = ("is_default",)
    ordering = ("-is_default", "-updated_at", "-id")


@admin.register(OrderStatusHistory)
class OrderStatusHistoryAdmin(admin.ModelAdmin):
    list_display = ("id", "order", "old_status", "new_status", "actor", "created_at")
    list_filter = ("new_status", "created_at")
    search_fields = ("order__id", "actor__username", "note")
    ordering = ("-created_at", "-id")


@admin.register(InventoryHistory)
class InventoryHistoryAdmin(admin.ModelAdmin):
    list_display = ("id", "san_pham", "change_type", "quantity_change", "old_stock", "new_stock", "actor", "created_at")
    list_filter = ("change_type", "created_at")
    search_fields = ("san_pham__ten", "actor__username", "note")
    ordering = ("-created_at", "-id")


@admin.register(NhaCungCap)
class NhaCungCapAdmin(admin.ModelAdmin):
    list_display = ("id", "ten", "sdt", "email", "active", "updated_at")
    list_filter = ("active",)
    search_fields = ("ten", "sdt", "email", "dia_chi")
    ordering = ("ten", "id")


class PhieuNhapKhoItemInline(admin.TabularInline):
    model = PhieuNhapKhoItem
    extra = 0


@admin.register(PhieuNhapKho)
class PhieuNhapKhoAdmin(admin.ModelAdmin):
    list_display = ("id", "code", "supplier", "status", "created_by", "imported_at", "created_at")
    list_filter = ("status", "created_at", "imported_at")
    search_fields = ("code", "supplier__ten", "note")
    ordering = ("-created_at", "-id")
    inlines = [PhieuNhapKhoItemInline]


@admin.register(InventoryBatch)
class InventoryBatchAdmin(admin.ModelAdmin):
    list_display = ("id", "batch_code", "san_pham", "supplier", "so_luong_nhap", "so_luong_con_lai", "don_gia_nhap", "imported_at")
    list_filter = ("imported_at",)
    search_fields = ("batch_code", "san_pham__ten", "supplier__ten", "receipt__code")
    ordering = ("-imported_at", "-id")


@admin.register(ProductImage)
class ProductImageAdmin(admin.ModelAdmin):
    list_display = ("id", "san_pham", "caption", "sort_order", "is_active", "created_at")
    list_filter = ("is_active", "created_at")
    search_fields = ("san_pham__ten", "caption")
    ordering = ("san_pham", "sort_order", "id")


@admin.register(ProductReview)
class ProductReviewAdmin(admin.ModelAdmin):
    list_display = ("id", "san_pham", "user", "rating", "is_visible", "created_at")
    list_filter = ("rating", "is_visible", "created_at")
    search_fields = ("san_pham__ten", "user__username", "title", "comment")
    ordering = ("-created_at", "-id")
