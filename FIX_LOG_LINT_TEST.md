# FIX LOG - Lint & Test

Ngày sửa: 2026-05-04

## Vấn đề đã xử lý

1. VS Code/Pylint báo nhiều lỗi giả trong `shop/tests.py`:
   - `Class 'SanPham' has no 'objects' member`
   - `Class 'DonHang' has no 'objects' member`
   - `Class 'Voucher' has no 'objects' member`
   - `Class 'Wallet' has no 'objects' member`
   - `Missing module/class/function docstring`
   - `Line too long`

   Nguyên nhân: Pylint không nhận diện đầy đủ Django ORM tự sinh thuộc tính `.objects` cho model.

2. Test chạy chậm do Django dùng hasher mặc định khi tạo user trong test.

## Cách đã sửa

- Thêm dòng cấu hình Pylint ở đầu `shop/tests.py` để bỏ qua các cảnh báo giả trong file test.
- Sửa `@override_settings` trong `shop/tests.py`:
  - dùng `MD5PasswordHasher` trong môi trường test để tăng tốc chạy test;
  - dùng email backend in-memory để test OTP/email không gửi Gmail thật.
- Thêm file `.pylintrc` ở thư mục gốc để VS Code/Pylint giảm báo lỗi giả.
- Thêm `.vscode/settings.json` để VS Code nhận đúng cấu hình lint trong dự án.

## Kết quả kiểm tra

- `python manage.py check`: OK
- `python manage.py test -v 2`: OK
- Tổng số test: 35
- Kết quả: 35/35 passed
