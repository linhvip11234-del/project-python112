# LOG_THÊM_SẢN_PHẨM_TỪ_MEDIA

Đã lấy toàn bộ ảnh trong thư mục `media/sanpham` và `media/sanpham/catalog` để tạo sản phẩm trong database.

Kết quả:
- Tổng sản phẩm hiện có trong database: 104
- Ảnh thiếu: 0
- Đã thêm logic seed trong `shop/services.py`, khi chạy trang chủ hệ thống sẽ tự đảm bảo các sản phẩm từ ảnh tồn tại.
- Phân loại theo tên file:
  - bt / bong-tai: Bông tai
  - dc: Dây chuyền
  - md / mat-day: Mặt dây chuyền
  - lt / lac-tay: Lắc tay
  - n / nhan: Nhẫn
  - v / vong: Vòng tay
  - bo / bo-trang-suc: Bộ trang sức

Lưu ý:
- Không ghi đè code nghiệp vụ.
- Các sản phẩm được tạo với tên, giá, tồn kho, mô tả và search_tags tự động.
