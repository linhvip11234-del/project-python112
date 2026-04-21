# Jewelry Django Demo v7 (CRUD + Roles + Workflow)

Demo website bán trang sức bằng Django, đã bổ sung thêm các yêu cầu thường gặp của đồ án CRUD.

## Tính năng đã có

### 1) CRUD cho 2 bảng chính
- **Sản phẩm (`SanPham`)**: Thêm / Xem / Sửa / Xóa trong Admin Panel
- **Đơn hàng (`DonHang`)**: Thêm / Xem / Sửa / Xóa trong Admin Panel
- Người dùng thường vẫn có luồng **đặt hàng** riêng ở giao diện ngoài

### 2) Tìm kiếm, lọc, sắp xếp
- Trang chủ: tìm kiếm + sắp xếp sản phẩm
- Admin sản phẩm: tìm kiếm + lọc trạng thái + sắp xếp
- Admin đơn hàng: tìm kiếm + lọc trạng thái / thanh toán + sắp xếp
- Admin users: tìm kiếm + lọc vai trò / active + sắp xếp
- Đơn hàng của tôi: lọc trạng thái + sắp xếp

### 3) Phân quyền Guest / User / Admin
- **Guest**: chỉ xem sản phẩm
- **User**: đăng nhập, đặt hàng, xem đơn của mình, xác nhận / huỷ đơn hợp lệ
- **Admin**: truy cập Admin Panel, CRUD sản phẩm / đơn hàng / user

### 4) Luồng nghiệp vụ đặc thù
- User đặt hàng → **Pending**
- User có thể chuyển **Pending → Confirmed** hoặc **Pending/Confirmed → Cancelled**
- Admin có thể duyệt theo luồng hợp lệ như:
  - `Pending -> Confirmed / Approved / Rejected / Cancelled`
  - `Confirmed -> Approved / Rejected / Cancelled`
- Hệ thống chặn các chuyển trạng thái sai nghiệp vụ

### 5) Trạng thái dữ liệu
- Sản phẩm: `active / inactive`
- Đơn hàng: `Pending / Confirmed / Approved / Rejected / Cancelled`
- User: `active / inactive`

### 6) Upload file/ảnh có validate
- Upload ảnh sản phẩm
- Kiểm tra định dạng: `JPG/JPEG/PNG/WEBP/GIF`
- Kiểm tra kích thước tối đa: **2MB**

### 7) Thông báo rõ ràng
- Dùng **Django messages** để hiển thị thông báo thành công / lỗi / cảnh báo dạng alert/toast

### 8) Tổ chức code kiểu Layered/MVC-lite
- `views.py`: điều phối request/response
- `forms.py`: validate input và upload
- `services.py`: luật nghiệp vụ và lọc/sắp xếp
- `decorators.py`: phân quyền admin
- `models.py`: dữ liệu + đồng bộ tổng tiền

### 9) Kiểm thử sơ bộ
- Có test tự động trong `shop/tests.py`
- Đã kiểm tra pass bằng `python manage.py test`

## Cài đặt & chạy
```bash
python -m pip install -r requirements.txt
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

## Chạy test
```bash
python manage.py test
```

## Link
- Trang chủ: http://127.0.0.1:8000/
- Django Admin: http://127.0.0.1:8000/admin/
- Admin Panel custom: http://127.0.0.1:8000/admin-panel/

## Ghi chú triển khai
- Ảnh sản phẩm nằm trong `media/sanpham/`
- Không thể xoá sản phẩm nếu đã phát sinh đơn hàng; nên chuyển sang `inactive`
- Không thể xoá user nếu user đó đã có đơn hàng
- Time zone đang dùng: `Asia/Ho_Chi_Minh`
