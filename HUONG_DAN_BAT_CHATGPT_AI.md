# HƯỚNG DẪN BẬT CHATGPT AI CHO WEBSITE LUMIÈRE

## 1. Cài thư viện

```powershell
python -m pip install -r requirements.txt
```

Trong `requirements.txt` đã có thêm:

```txt
openai>=1.0.0
```

## 2. Thêm API key vào `.env`

Mở file `.env` ở thư mục chứa `manage.py`, điền key vào dòng:

```env
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-4o-mini
OPENAI_CHAT_COMPLETIONS_URL=https://api.openai.com/v1/chat/completions
OPENAI_TIMEOUT=20
```

Không đưa API key lên GitHub. Nếu không có API key, chatbot tự dùng chế độ fallback nội bộ.

## 3. Chạy lại server

```powershell
python manage.py check
python manage.py runserver
```

Sau đó mở website và hỏi thử chatbot ở góc phải dưới.

## 4. Câu hỏi test nhanh

- Tư vấn cho tôi nhẫn làm quà sinh nhật
- Website có thanh toán QR không?
- Cách dùng voucher?
- Tôi muốn tìm lắc tay còn hàng

## 5. Cách hoạt động

Giao diện chatbot gửi câu hỏi về Django qua URL `chatbot/api/`. Django lấy ngữ cảnh từ database như sản phẩm, giỏ hàng, ví, đơn hàng rồi gọi OpenAI API. Nếu API lỗi, hết quota hoặc chưa có key, hệ thống vẫn trả lời bằng fallback nội bộ để demo không bị gián đoạn.
