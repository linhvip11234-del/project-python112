"""
Khai báo URL của app shop.
Tại đây gom toàn bộ route phía khách hàng, admin và API.
"""
from django.urls import path

from . import api_views, views

# Danh sách route của app shop
urlpatterns = [
    path("api/health/", api_views.ApiHealthView.as_view(), name="api_health"),
    path("api/products/", api_views.ProductListApiView.as_view(), name="api_products"),
    path("api/products/<int:pk>/", api_views.ProductDetailApiView.as_view(), name="api_product_detail"),
    path("api/products/<int:pk>/reviews/", api_views.ProductReviewListApiView.as_view(), name="api_product_reviews"),
    path("api/products/<int:pk>/reviews/create/", api_views.ProductReviewCreateApiView.as_view(), name="api_product_review_create"),
    path("api/orders/", api_views.OrderListApiView.as_view(), name="api_orders"),
    path("", views.home, name="home"),
    path("dang-ky/", views.dang_ky, name="dang_ky"),
    path("dang-nhap/", views.dang_nhap, name="dang_nhap"),
    path("flash-sale/", views.flash_sale_products, name="flash_sale_products"),
    path("san-pham/<int:sp_id>/", views.chi_tiet_san_pham, name="chi_tiet_san_pham"),
    path("quen-mat-khau/", views.quen_mat_khau, name="quen_mat_khau"),
    path("quen-mat-khau/chon-phuong-thuc/", views.chon_phuong_thuc_khoi_phuc, name="chon_phuong_thuc_khoi_phuc"),
    path("quen-mat-khau/cau-hoi-bao-mat/", views.khoi_phuc_bang_cau_hoi_bao_mat, name="khoi_phuc_bang_cau_hoi_bao_mat"),
    path("quen-mat-khau/otp/", views.dat_lai_mat_khau_otp, name="dat_lai_mat_khau_otp"),
    path("dang-xuat/", views.dang_xuat, name="dang_xuat"),

    path("gio-hang/", views.gio_hang, name="gio_hang"),
    path("gio-hang/them/<int:sp_id>/", views.add_to_cart, name="add_to_cart"),
    path("gio-hang/cap-nhat/<int:item_id>/", views.cap_nhat_gio_hang, name="cap_nhat_gio_hang"),
    path("gio-hang/xoa/<int:item_id>/", views.xoa_khoi_gio, name="xoa_khoi_gio"),
    path("gio-hang/xoa-tat-ca/", views.xoa_toan_bo_gio_hang, name="xoa_toan_bo_gio_hang"),
    path("gio-hang/thanh-toan/", views.thanh_toan_gio_hang, name="thanh_toan_gio_hang"),
    path("dat-hang/<int:san_pham_id>/", views.dat_hang, name="dat_hang"),
    path("don-hang/", views.ds_don, name="ds_don"),
    path("don-hang/<int:don_id>/thanh-toan-qr/", views.order_payment_qr, name="order_payment_qr"),
    path("don-hang/<int:don_id>/thanh-toan-qr/img/", views.order_payment_qr_image, name="order_payment_qr_image"),
    path("don-hang/<int:don_id>/thanh-toan-qr/callback/", views.order_payment_callback, name="order_payment_callback"),
    path("vi-dien-tu/", views.wallet_view, name="wallet"),
    path("vi-dien-tu/nap-tien/", views.wallet_deposit, name="wallet_deposit"),
    path("vi-dien-tu/nap-tien/<int:topup_id>/", views.wallet_topup_detail, name="wallet_topup_detail"),
    path("vi-dien-tu/nap-tien/<int:topup_id>/qr/", views.wallet_topup_qr, name="wallet_topup_qr"),
    path("vi-dien-tu/nap-tien/<int:topup_id>/callback/", views.wallet_topup_callback, name="wallet_topup_callback"),
    path("don-hang/xac-nhan/<int:don_id>/", views.xac_nhan_don, name="xac_nhan_don"),
    path("don-hang/huy/<int:don_id>/", views.huy_don, name="huy_don"),

    path("admin-don-hang/", views.ds_don_admin, name="ds_don_admin"),
    path("admin-don-hang/<int:don_id>/<str:hanh_dong>/", views.duyet_don, name="duyet_don"),

    path("admin-panel/", views.admin_dashboard, name="admin_dashboard"),
    path("admin-panel/san-pham/", views.admin_sanpham_list, name="admin_sanpham_list"),
    path("admin-panel/san-pham/them/", views.admin_sanpham_create, name="admin_sanpham_create"),
    path("admin-panel/san-pham/<int:sp_id>/", views.admin_sanpham_detail, name="admin_sanpham_detail"),
    path("admin-panel/san-pham/<int:sp_id>/sua/", views.admin_sanpham_edit, name="admin_sanpham_edit"),
    path("admin-panel/san-pham/<int:sp_id>/xoa/", views.admin_sanpham_delete, name="admin_sanpham_delete"),

    path("admin-panel/kho/", views.admin_inventory_list, name="admin_inventory_list"),
    path("admin-panel/kho/<int:sp_id>/", views.admin_inventory_detail, name="admin_inventory_detail"),
    path("admin-panel/kho/<int:sp_id>/cap-nhat/", views.admin_inventory_adjust, name="admin_inventory_adjust"),

    path("admin-panel/nha-cung-cap/", views.admin_supplier_list, name="admin_supplier_list"),
    path("admin-panel/nha-cung-cap/them/", views.admin_supplier_create, name="admin_supplier_create"),
    path("admin-panel/nha-cung-cap/<int:supplier_id>/", views.admin_supplier_detail, name="admin_supplier_detail"),
    path("admin-panel/nha-cung-cap/<int:supplier_id>/sua/", views.admin_supplier_edit, name="admin_supplier_edit"),
    path("admin-panel/nha-cung-cap/<int:supplier_id>/xoa/", views.admin_supplier_delete, name="admin_supplier_delete"),

    path("admin-panel/phieu-nhap-kho/", views.admin_receipt_list, name="admin_receipt_list"),
    path("admin-panel/phieu-nhap-kho/them/", views.admin_receipt_create, name="admin_receipt_create"),
    path("admin-panel/phieu-nhap-kho/<int:receipt_id>/", views.admin_receipt_detail, name="admin_receipt_detail"),
    path("admin-panel/phieu-nhap-kho/<int:receipt_id>/nhap-kho/", views.admin_receipt_receive, name="admin_receipt_receive"),
    path("admin-panel/phieu-nhap-kho/<int:receipt_id>/huy/", views.admin_receipt_cancel, name="admin_receipt_cancel"),

    path("admin-panel/lo-hang/", views.admin_batch_list, name="admin_batch_list"),
    path("admin-panel/lo-hang/<int:batch_id>/", views.admin_batch_detail, name="admin_batch_detail"),

    path("admin-panel/don-hang/", views.admin_donhang_list, name="admin_donhang_list"),
    path("admin-panel/don-hang/them/", views.admin_donhang_create, name="admin_donhang_create"),
    path("admin-panel/don-hang/<int:don_id>/", views.admin_donhang_detail, name="admin_donhang_detail"),
    path("admin-panel/don-hang/<int:don_id>/sua/", views.admin_donhang_edit, name="admin_donhang_edit"),
    path("admin-panel/don-hang/<int:don_id>/xoa/", views.admin_donhang_delete, name="admin_donhang_delete"),
    path("admin-panel/don-hang/<int:don_id>/cap-nhat/", views.admin_donhang_update, name="admin_donhang_update"),

    path("admin-panel/voucher/", views.admin_voucher_list, name="admin_voucher_list"),
    path("admin-panel/voucher/them/", views.admin_voucher_create, name="admin_voucher_create"),
    path("admin-panel/voucher/<int:voucher_id>/", views.admin_voucher_detail, name="admin_voucher_detail"),
    path("admin-panel/voucher/<int:voucher_id>/sua/", views.admin_voucher_edit, name="admin_voucher_edit"),
    path("admin-panel/voucher/<int:voucher_id>/xoa/", views.admin_voucher_delete, name="admin_voucher_delete"),

    path("admin-panel/nap-tien/", views.admin_topup_list, name="admin_topup_list"),
    path("admin-panel/nap-tien/<int:topup_id>/", views.admin_topup_detail, name="admin_topup_detail"),
    path("admin-panel/nap-tien/<int:topup_id>/qr/", views.admin_topup_qr, name="admin_topup_qr"),
    path("admin-panel/nap-tien/<int:topup_id>/duyet/", views.admin_topup_approve, name="admin_topup_approve"),
    path("admin-panel/nap-tien/<int:topup_id>/tu-choi/", views.admin_topup_reject, name="admin_topup_reject"),

    path("admin-panel/users/", views.admin_user_list, name="admin_user_list"),
    path("admin-panel/users/them/", views.admin_user_create, name="admin_user_create"),
    path("admin-panel/users/<int:user_id>/sua/", views.admin_user_edit, name="admin_user_edit"),
    path("admin-panel/users/<int:user_id>/xoa/", views.admin_user_delete, name="admin_user_delete"),
]
