# Kế hoạch hai người — tiếp nối code hiện tại

Ngày cập nhật: 26/10/2026. Điều chỉnh từ
`Ke_hoach_trien_khai_AI_Exam_Assistant_2_nguoi.docx`; giữ kiến trúc modular monolith
và public API hiện tại. Chi tiết quyết định: [ADR-004](../decisions/ADR-004-modular-generation-and-review.md).

## Phần đã chuyển sang pipeline mới

- AllocationPlan có kiểu Pydantic, phân bổ trước khi chọn ID bài.
- QuestionSelector tách riêng, giữ quota giáo viên và kiểm tra thiếu ngân hàng.
- ExpressionPlanner tách riêng; dữ liệu hiện tại dùng direct/preserve_source.
- Model transport, candidate validation, retry orchestration và assembler tách riêng.
- Một ngân sách retry, deadline toàn đề, lỗi xác định không hạ thành needs_review.
- API approve/regenerate, revision conflict và lịch sử snapshot trong SQLite.
- Policy P3/P2/P1 cấu hình riêng, kiểm tra trên fixture 9 kỹ năng; không áp dụng
  nhầm lên catalogue 7 kỹ năng M3.

## Ownership tiếp tục phát triển

| Nhóm module | AI & Algorithms Lead | Backend Lead |
|---|---|---|
| `src/adaptation/` | Owner allocation, relationships, selection và unit tests | Review contract, constraints và integration |
| `src/ai/expression_planner.py`, `prompts.py` | Owner expression policy và prompt | Review input/privacy/deadline |
| `src/ai/qwen_client.py` | Owner model transport | Review configuration và integration |
| `src/validation/` | Owner semantic/math checks và bộ case | Review schema/error integration |
| `src/orchestration/` | Review nghiệp vụ | Owner retry, assembly, review lifecycle |
| `src/api/`, adapters, stores | Cung cấp yêu cầu dữ liệu | Owner API, persistence và integration tests |
| Shared contracts, fixtures, policy | Cùng review | Cùng review |

Không chuyển tất cả file sang `backend/app/` chỉ để khớp cây thư mục mẫu.
Các module Python truyền model trực tiếp; JSON dùng tại API, Ollama và fixtures.

## Các đợt tiếp theo

1. **Chốt dữ liệu với Data:** chọn catalogue vận hành 7 hay 9 kỹ năng; nếu đổi,
   cung cấp mapping có chủ đích, primary annotations và kế hoạch xử lý mastery.
   Fixture 9 kỹ năng chỉ là dữ liệu thử, không phải hồ sơ học sinh thật.
2. **ProblemSpec có kiểm chứng:** chuẩn bị tập bài nhỏ có operation/parameters,
   order/replacement/constraints và đáp án đã duyệt. Không suy các trường đó từ
   prose bằng heuristic rồi coi là nguồn sự thật.
3. **Expression và semantic checks:** triển khai context/indirect trên phạm vi
   ProblemSpec đã hỗ trợ. Có case lỗi thay điều kiện nhưng giữ nguyên số liệu;
   phần chưa đủ chắc giữ needs_review. Chạy Qwen thật và ghi nhận kết quả thực tế.
4. **Teacher workflow:** nối giao diện approve/regenerate theo revision hiện có;
   chốt identity/ownership trước khi thêm student delivery hoặc nhiều giáo viên.
5. **Assessment milestone riêng:** student submissions, preliminary grading,
   xác minh điểm và cập nhật mastery; chưa tính các phần này là đã hoàn thành.

## Tiêu chí tích hợp

- Giữ `/api/v1/exams/generate` đồng bộ và các tên field hiện có.
- Changes ở shared contracts phải kèm fixture, expected outputs và tests hai phía.
- M3 databases vẫn read-only qua ứng dụng. Dữ liệu vận hành nằm trong exam store.
- Dùng `python -m pytest -q`; dependencies hiện quản lý bằng `requirements.txt`.
  Ruff và tự nạp `.env` chưa được thêm; không ghi chúng như công cụ đã có sẵn.
- Unit/HTTP-double tests chứng minh contract và control flow; đánh giá model thật
  là bước riêng, không suy ra từ số lượng tests pass.
