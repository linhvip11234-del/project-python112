# FIX_LOG_NGHIEP_VU

Đã sửa các lỗi nghiệp vụ chính:

1. Gắn lại @login_required đúng cho thanh_toan_gio_hang.
2. Bỏ @login_required bị gắn nhầm vào helper _parse_selected_cart_item_ids.
3. Loại bỏ trạng thái cũ Approved/Đã duyệt khỏi runtime code.
4. Chuẩn hóa luồng trạng thái đơn:
   Pending -> Confirmed -> Shipping -> Completed / Cancelled / Rejected
5. Sửa dashboard admin đếm Đang giao và Hoàn thành thay cho Đã duyệt.
6. Sửa điều kiện đánh giá sản phẩm theo trạng thái mới.
7. API tạo đánh giá chỉ cho user đã mua sản phẩm.
8. Sửa giỏ hàng:
   - Cập nhật số lượng kiểm tra tồn kho.
   - Thêm vào giỏ kiểm tra tồn kho theo tổng số lượng cộng dồn.
   - Checkout chỉ tạo đơn cho sản phẩm được tích chọn.
9. Giữ voucher từ giỏ hàng khi chuyển sang trang checkout.
10. Admin không xóa cứng đơn hàng nữa, chuyển sang hủy đơn để giữ lịch sử nghiệp vụ.
11. Chuyển EMAIL_HOST_PASSWORD sang biến môi trường.
12. Dọn ALLOWED_HOSTS bị khai báo trùng.
13. Cập nhật text hướng dẫn trạng thái đơn hàng trong template/chatbot.
