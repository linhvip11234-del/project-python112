# FIX LOG - Bật ChatGPT AI OpenAI

Đã chỉnh dự án để dùng được OpenAI API cho chatbot:

- Thêm `openai>=1.0.0` vào `requirements.txt`.
- Bổ sung cấu hình OpenAI trong `config/settings.py`.
- Cập nhật `.env.example` và `.env` với `OPENAI_TIMEOUT`.
- Nâng cấp hàm `_call_openai_chatbot` trong `shop/views.py`:
  - Ưu tiên dùng OpenAI SDK chính thức nếu đã cài package `openai`.
  - Có fallback HTTP thuần tới Chat Completions API nếu SDK chưa dùng được.
  - Nếu API key trống/lỗi mạng/hết quota, chatbot tự chuyển về fallback nội bộ.
- Thêm file `HUONG_DAN_BAT_CHATGPT_AI.md` để hướng dẫn bật API.

Lưu ý: Không đặt API key trong JavaScript/frontend. API key chỉ đặt trong `.env`.
