![Hongkongdoll](tech_chatbot_rag_multiagent_app\images\image.png)

# Vạn Tượng Thiên Cơ

Tech Chatbot RAG Multi-Agent App là một pháp đàn vấn đáp công nghệ, lấy Django làm thân, Qdrant làm linh mạch tri thức, LangGraph làm trận đồ điều phối, LLM làm nguyên thần sinh đáp. Người dùng nhập vấn, hệ thống phân ý, triệu hồi tư liệu, tái xếp hạng, kiểm chứng căn cứ, rồi xuất đáp theo dòng SSE.

## Tông Môn Tổng Lược

- `landing`: tiên hiệp môn hộ, mở đầu tại `/`.
- `chat`: chính điện vấn đáp, streaming token, lưu lịch sử theo tài khoản.
- `accounts`: đăng nhập, đăng ký, đăng xuất, bảo hộ lịch sử hội thoại.
- `manager`: quản trị `.config/config.yaml` và giám sát log hội thoại.
- `rag_engine`: nội công RAG, gồm ingestion, vector store, retriever, agents, guardrails.
- `crawler`: thu thập pháp liệu sản phẩm từ CellphoneS về `data/cellphones_mobile.jsonl`.
- `data`: kho nguyên liệu; một phần dữ liệu lớn được quản bằng DVC.

## Linh Mạch Kiến Trúc

Luồng vấn đáp:

1. Người dùng vào `/chat/` sau khi đăng nhập.
2. Frontend gửi câu hỏi tới `/message/`.
3. `supervisor_agent` phân đạo: `smalltalk`, `product_advice`, hoặc `invalid`.
4. Nếu là tư vấn sản phẩm, `retrieval_agent` truy hồi tài liệu từ Qdrant.
5. Reranker và bộ kiểm chứng citation/groundedness thẩm định căn cứ.
6. `advisor_agent` sinh đáp theo token stream.
7. `manager.ChatLog` ghi lại query, answer, sources, latency, groundedness.
8. `accounts.ChatConversation` lưu lịch sử hội thoại theo user.

## Khai Sơn Lập Đạo

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

Tạo admin:

```powershell
python manage.py createsuperuser
```

Khai mở pháp đàn:

```powershell
python manage.py runserver
```

## Trúc Cơ Tri Thức

Config chính nằm tại:

```text
.config/config.yaml
```

Các mục trọng yếu:

- `chunking`: phân mảnh văn bản.
- `retriever`: ngưỡng truy hồi, hybrid dense+sparse, self-query filter.
- `reranker`: tái xếp hạng, groundedness, tái sinh đáp khi căn cứ yếu.
- `chat_history`: số lượt giữ lại, độ dài lịch sử.
- `embedding`: provider, model, dimension.
- `loader`: `jsonl` hoặc `csv`.

Có thể chỉnh trực tiếp qua admin:

```text
/manager/config/
```

Lưu ý: config được đọc lúc import runtime, sau khi đổi `.config/config.yaml` nên restart server để linh khí mới nhập toàn cục.

## Luyện Khí Dữ Liệu

Thu thập dữ liệu CellphoneS:

```powershell
python crawler/crawler.py
```

Xây lại chỉ mục RAG vào Qdrant:

```powershell
python manage.py build_rag_index
```

Nếu dữ liệu lớn đi qua DVC:

```powershell
dvc pull
```

Đẩy pháp liệu lên Dagshub remote:

```powershell
git push dagshub minh:main
```

## Đạo Môn Truy Cập

- `/`: Landing page tiên hiệp.
- `/accounts/login/`: Đăng nhập.
- `/accounts/register/`: Đăng ký.
- `/accounts/logout/`: Xuất môn.
- `/chat/`: Chính điện chatbot.
- `/history/`: API lịch sử chat của user.
- `/admin/`: Django admin.
- `/manager/config/`: Quản lý file cấu hình.
- `/manager/logs/`: Giám sát chat log và hallucination flag.

## Nội Công RAG

Các tầng chính trong `rag_engine`:

- `core/config.py`: đọc `.config/config.yaml` và biến môi trường.
- `core/llm.py`: kết nối Ollama hoặc Gemini, hỗ trợ stream.
- `core/embedding.py`: khởi tạo embedding theo provider.
- `rag/loader.py`: nạp `jsonl` hoặc `csv`.
- `rag/chunking.py`: phân chunk.
- `rag/vector_store_qdrant.py`: dựng và nạp Qdrant collection.
- `rag/retriever.py`: similarity search, filter, threshold.
- `rag/tools`: reranker, citation, groundedness, filter.
- `agents`: supervisor, retrieval, advisor, guardrails.

## Hộ Pháp Quản Trị

Manager có hai pháp khí:

- Config manager: sửa `.config/config.yaml` bằng form rộng và vùng YAML lớn, ghi thẳng file, không lưu database.
- Chat log manager: xem query, answer, context, retrieved docs, sources, latency, groundedness và đánh dấu `ok`, `suspicious`, `confirmed`.

Muốn thấy mục manager trong Django admin, đăng nhập bằng staff/superuser rồi vào:

```text
/admin/
```

## Hội Thoại Và Lưu Ảnh

Chat history được lưu theo tài khoản:

- Frontend tải lịch sử từ `/history/`.
- Khi thêm/xóa/clear hội thoại, frontend đồng bộ về server.
- Server lưu vào model `accounts.ChatConversation`.
- Nếu server lỗi tạm thời, frontend còn fallback bằng `localStorage`.

## Pháp Chú Vận Hành Nhanh

```powershell
.\venv\Scripts\activate
python manage.py migrate
python manage.py build_rag_index
python manage.py runserver
```

Sau đó nhập cảnh:

```text
http://127.0.0.1:8000/
```

## Cấm Kỵ Thường Gặp

- Qdrant chưa có collection: chạy lại `python manage.py build_rag_index`.
- Đổi embedding model nhưng dimension không khớp: sửa `.config/config.yaml`, xóa/rebuild collection.
- Bật hybrid search: cần rebuild index để có dense + sparse vectors.
- Đổi config nhưng app chưa nhận: restart Django server.
- Dùng Gemini: phải có `GOOGLE_API_KEY` hoặc `GEMINI_API_KEY`.
- Dùng Ollama: local Ollama server phải đang chạy và đã có model tương ứng.
