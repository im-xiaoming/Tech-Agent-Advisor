# Tech Agent Advisor

Tech Agent Advisor là ứng dụng chatbot tư vấn sản phẩm công nghệ sử dụng Django, Qdrant, LangGraph và LLM. Người dùng nhập câu hỏi, hệ thống phân loại ý định, truy xuất tài liệu liên quan, xếp hạng lại kết quả, kiểm tra căn cứ và trả lời theo luồng SSE.

## Tổng quan

- `landing`: trang giới thiệu tại `/`.
- `chat`: giao diện hỏi đáp, streaming token và lưu lịch sử theo tài khoản.
- `accounts`: đăng nhập, đăng ký, đăng xuất và quản lý lịch sử hội thoại của người dùng.
- `manager`: quản lý `.config/config.yaml` và theo dõi log hội thoại.
- `rag_engine`: xử lý RAG, bao gồm ingestion, vector store, retriever, agents và guardrails.
- `crawler`: thu thập dữ liệu sản phẩm từ CellphoneS vào `data/cellphones_mobile.jsonl`.
- `data`: thư mục dữ liệu; một phần dữ liệu lớn được quản lý bằng DVC.

## Kiến trúc

Luồng xử lý chính:

1. Người dùng đăng nhập và truy cập `/chat/`.
2. Frontend gửi câu hỏi tới `/message/`.
3. `supervisor_agent` phân loại câu hỏi thành `smalltalk`, `product_advice` hoặc `invalid`.
4. Nếu là câu hỏi tư vấn sản phẩm, `retrieval_agent` truy xuất tài liệu từ Qdrant.
5. Reranker và các bộ kiểm tra citation/groundedness đánh giá lại căn cứ.
6. `advisor_agent` sinh câu trả lời theo token stream.
7. `manager.ChatLog` ghi lại query, answer, sources, latency và groundedness.
8. `accounts.ChatConversation` lưu lịch sử hội thoại theo từng user.

## Cài đặt

Tạo môi trường:

```powershell
python -m venv venv
.\venv\Scripts\activate
pip install -r requirements.txt
```

Thiết lập biến môi trường trong `.env` hoặc shell:

```env
QDRANT_URL=...
QDRANT_API_KEY=...
QDRANT_COLLECTION=tech_products

LLM_PROVIDER=ollama
LLM_MODEL=jaahas/qwen3.5-uncensored

# Nếu dùng Gemini
GOOGLE_API_KEY=...
# hoặc
GEMINI_API_KEY=...
```

Khởi tạo cơ sở dữ liệu:

```powershell
python manage.py migrate
```

Tạo tài khoản admin:

```powershell
python manage.py createsuperuser
```

Chạy server:

```powershell
python manage.py runserver
```

## Cấu hình

File cấu hình chính:

```text
.config/config.yaml
```

Các nhóm cấu hình quan trọng:

- `chunking`: thiết lập phân mảnh văn bản.
- `retriever`: ngưỡng truy xuất, hybrid dense+sparse và self-query filter.
- `reranker`: xếp hạng lại kết quả, kiểm tra groundedness và sinh lại câu trả lời khi căn cứ yếu.
- `chat_history`: số lượt hội thoại được giữ lại và độ dài lịch sử.
- `embedding`: provider, model và dimension.
- `loader`: định dạng dữ liệu đầu vào, hiện hỗ trợ `jsonl` hoặc `csv`.

Có thể chỉnh cấu hình trực tiếp qua:

```text
/manager/config/
```

Lưu ý: cấu hình được đọc khi runtime import module. Sau khi sửa `.config/config.yaml`, nên restart server để ứng dụng nhận cấu hình mới.

## Dữ liệu và chỉ mục RAG

Thu thập dữ liệu CellphoneS:

```powershell
python crawler/crawler.py
```

Xây lại chỉ mục RAG trong Qdrant:

```powershell
python manage.py build_rag_index
```

Nếu dữ liệu lớn được quản lý bằng DVC:

```powershell
dvc pull
```

Đẩy dữ liệu lên Dagshub remote:

```powershell
git push dagshub minh:main
```

## Đường dẫn chính

- `/`: landing page.
- `/accounts/login/`: đăng nhập.
- `/accounts/register/`: đăng ký.
- `/accounts/logout/`: đăng xuất.
- `/chat/`: giao diện chatbot.
- `/history/`: API lịch sử chat của user.
- `/admin/`: Django admin.
- `/manager/config/`: quản lý file cấu hình.
- `/manager/logs/`: theo dõi chat log và hallucination flag.

## RAG engine

Các phần chính trong `rag_engine`:

- `core/config.py`: đọc `.config/config.yaml` và biến môi trường.
- `core/llm.py`: kết nối Ollama hoặc Gemini, hỗ trợ stream.
- `core/embedding.py`: khởi tạo embedding theo provider.
- `rag/loader.py`: nạp dữ liệu `jsonl` hoặc `csv`.
- `rag/chunking.py`: chia văn bản thành chunk.
- `rag/vector_store_qdrant.py`: tạo và nạp Qdrant collection.
- `rag/retriever.py`: similarity search, filter và threshold.
- `rag/tools`: reranker, citation, groundedness và filter.
- `agents`: supervisor, retrieval, advisor và guardrails.

## Manager

Manager cung cấp hai nhóm chức năng:

- Config manager: sửa `.config/config.yaml` bằng form và vùng YAML, ghi trực tiếp vào file, không lưu trong database.
- Chat log manager: xem query, answer, context, retrieved docs, sources, latency, groundedness và đánh dấu trạng thái `ok`, `suspicious`, `confirmed`.

Để truy cập phần manager trong Django admin, đăng nhập bằng tài khoản staff/superuser rồi vào:

```text
/admin/
```

## Lịch sử hội thoại

Chat history được lưu theo tài khoản:

- Frontend tải lịch sử từ `/history/`.
- Khi thêm, xóa hoặc clear hội thoại, frontend đồng bộ dữ liệu về server.
- Server lưu dữ liệu vào model `accounts.ChatConversation`.
- Nếu server lỗi tạm thời, frontend fallback bằng `localStorage`.

## Chạy nhanh

```powershell
.\venv\Scripts\activate
python manage.py migrate
python manage.py build_rag_index
python manage.py runserver
```

Sau đó mở:

```text
http://127.0.0.1:8000/
```

## Lỗi thường gặp

- Qdrant chưa có collection: chạy lại `python manage.py build_rag_index`.
- Đổi embedding model nhưng dimension không khớp: sửa `.config/config.yaml`, sau đó xóa hoặc rebuild collection.
- Bật hybrid search: cần rebuild index để có dense và sparse vectors.
- Đổi config nhưng app chưa nhận: restart Django server.
- Dùng Gemini: cần có `GOOGLE_API_KEY` hoặc `GEMINI_API_KEY`.
- Dùng Ollama: local Ollama server phải đang chạy và đã có model tương ứng.
