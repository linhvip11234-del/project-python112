# LOG_GOP_ADMIN_REVIEW_NANG_CAO

Đã gộp riêng nghiệp vụ từ `tram sua.zip` vào bản cuối:

1. Thêm model ProductReviewImage để mỗi đánh giá có nhiều ảnh.
2. Thêm migration shop/migrations/0015_productreviewimage.py.
3. Cập nhật db.sqlite3, tạo bảng shop_productreviewimage và ghi nhận migration.
4. Thêm ProductReviewForm hỗ trợ upload tối đa 5 ảnh.
5. Thêm AdminProductReviewForm để admin sửa đánh giá và thêm ảnh.
6. Thêm view admin:
   - admin_review_list
   - admin_review_detail
   - admin_review_edit
   - admin_review_toggle
   - admin_review_image_delete
   - admin_review_delete
7. Thêm URL admin quản lý đánh giá.
8. Thêm template:
   - admin_review_list.html
   - admin_review_detail.html
   - admin_review_form.html
   - admin_review_delete.html
9. Thêm menu Đánh giá trong admin.
10. Cập nhật chi tiết sản phẩm để hiển thị ảnh đánh giá và cho user upload ảnh đánh giá.
11. Cập nhật popup đánh giá nhanh sau thanh toán để upload ảnh.
12. Giữ nguyên các nghiệp vụ mới của bản cuối:
   - Chatbot
   - Hóa đơn PDF
   - QR động đúng số tiền
   - Trạng thái Đang giao / Hoàn thành
   - Thông báo chuông
   - Fix trùng ảnh sản phẩm
   - Seed sản phẩm từ media
