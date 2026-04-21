# Manual test checklist

## Guest
- [ ] Vào trang chủ xem được sản phẩm active
- [ ] Không vào được Admin Panel nếu chưa đăng nhập

## User
- [ ] Đăng ký / đăng nhập thành công
- [ ] Đặt hàng với dữ liệu hợp lệ
- [ ] Không đặt được nếu số lượng <= 0 hoặc SĐT sai
- [ ] Đơn mới ở trạng thái Pending
- [ ] Có thể Confirm đơn Pending
- [ ] Có thể Cancel đơn Pending/Confirmed
- [ ] Không thể đổi trạng thái sai luồng

## Admin
- [ ] CRUD sản phẩm hoạt động
- [ ] Upload ảnh đúng định dạng/kích thước hoạt động
- [ ] Tìm kiếm / lọc / sắp xếp sản phẩm hoạt động
- [ ] CRUD đơn hàng hoạt động
- [ ] Lọc trạng thái / thanh toán / sắp xếp đơn hàng hoạt động
- [ ] Cập nhật trạng thái đơn đúng luồng
- [ ] CRUD user hoạt động
- [ ] Phân role User/Admin hoạt động
