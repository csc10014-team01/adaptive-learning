# N06 — Đọc hiểu hệ thống hiện tại qua `src`

**Đối chiếu code ngày 27/10/2026**, theo sơ đồ mục 1–2 của
[N04_architecture_api.md](N04_architecture_api.md).

## 1. Hệ thống hiện đang làm được gì?

Hệ thống hỗ trợ giáo viên tạo đề ôn tập **Đại số tổ hợp lớp 10**, dựa trên hồ sơ
học sinh và ngân hàng câu hỏi có sẵn. Đề tạo xong được lưu thành bản nháp chờ duyệt.

Mỗi module là một nhóm code phụ trách một việc. Các module Python cùng nằm trong
**một backend FastAPI**; Qwen chạy riêng qua Ollama trên máy.

## 2. Từ các khối trong sơ đồ đến file code

### A. Lớp giao diện — Client / Presentation Layer

Khối **Web Interface** nằm trong `src/ui/`, hiện phục vụ giáo viên.

| File | Nhiệm vụ và liên hệ |
|---|---|
| [static/index.html](../../src/ui/static/index.html), [static/style.css](../../src/ui/static/style.css) | Tạo màn hình và hình thức trình bày. |
| [static/app.js](../../src/ui/static/app.js) | Nhận thao tác, gọi API để xem hồ sơ/kế hoạch, tạo/mở đề, hiển thị lỗi và tải JSON. |
| [routes.py](../../src/ui/routes.py), [__main__.py](../../src/ui/__main__.py) | Gắn giao diện vào backend và khởi động ứng dụng local. |

### B. Lớp nghiệp vụ — Backend / Application Layer

| Khối trong N04 | File chính | Nhiệm vụ và liên hệ |
|---|---|---|
| **FastAPI Backend** | [api/main.py](../../src/api/main.py), [api/schemas.py](../../src/api/schemas.py) | `main.py` nhận yêu cầu, kiểm tra token giáo viên và gọi đúng module. `schemas.py` quy định/kiểm tra cấu trúc dữ liệu, số câu và tổng điểm. |
| **Student Learning Profiles** | `api/main.py` + [api/m3_adapter.py](../../src/api/m3_adapter.py) | Lấy năng lực, số bằng chứng theo từng kỹ năng và lịch sử câu sai để đưa vào bộ tạo đề. Chưa có module hồ sơ riêng. |
| **Intelligent Exam Generation** | [orchestration/exam_service.py](../../src/orchestration/exam_service.py) | Điều phối toàn bộ quá trình chọn câu, viết lại, kiểm tra và ghép đề. API gọi vào đây qua lớp nối [api/real_generator.py](../../src/api/real_generator.py). |
| **Sinh và ghép đề** *(bên trong khối tạo đề)* | [orchestration/question_generation.py](../../src/orchestration/question_generation.py), [orchestration/exam_assembler.py](../../src/orchestration/exam_assembler.py) | File đầu gọi Qwen và bộ kiểm tra, thử lại có giới hạn khi đầu ra sai. File sau ghép câu với **đáp án nguồn** và phân điểm. |
| **Kiểm tra đầu ra** *(bên trong khối tạo đề)* | [validation/question_validator.py](../../src/validation/question_validator.py), [validation/math_validator.py](../../src/validation/math_validator.py) | Kiểm tra định dạng và giữ nguyên số liệu. Trước khi lưu, `main.py` kiểm tra thêm nguồn câu và đề có khớp yêu cầu không. |
| **Exam Review & Release** | [orchestration/review_service.py](../../src/orchestration/review_service.py) | Duyệt toàn bộ đề và kiểm tra phiên bản. Tạo lại câu do `exam_service.py` xử lý; thành công thì đề phải duyệt lại. [orchestration/source_snapshot.py](../../src/orchestration/source_snapshot.py) giúp phát hiện nguồn câu đã đổi. |

Các kiểm tra hiện có **chưa chứng minh tính đúng toán học/ngữ nghĩa**;
giáo viên vẫn cần xem câu hỏi, đáp án và cách cho điểm.

### C. Lớp quyết định đề và AI — AI & Processing Layer

Khối **Assessment Planner** nằm trong `src/adaptation/`:

| File | Nhiệm vụ và liên hệ |
|---|---|
| [planner.py](../../src/adaptation/planner.py) | Đọc hồ sơ, phân bổ câu theo kỹ năng và độ khó, rồi gọi Selector. Có chế độ cá nhân hóa và đề chuẩn. |
| [policy.py](../../src/adaptation/policy.py) | Chứa ngưỡng và tỷ lệ Planner sử dụng: tối thiểu 3 bằng chứng/kỹ năng, mục tiêu 3/4, tối đa 2 kỹ năng yếu được ưu tiên. |
| [question_selector.py](../../src/adaptation/question_selector.py) | Chọn câu nguồn theo kế hoạch, tránh trùng trong đề, ưu tiên tránh câu trong lịch sử sai khi phù hợp. Thiếu câu đáp ứng điều kiện bắt buộc thì báo lỗi. |
| [skill_relationships.py](../../src/adaptation/skill_relationships.py), [contracts.py](../../src/adaptation/contracts.py) | Lần lượt: ưu tiên kỹ năng ôn tập liên quan **khi được cấu hình**; định nghĩa bản phân bổ Planner giao cho Selector. |

Khối **Local Qwen Model** được kết nối qua `src/ai/`:

| File | Nhiệm vụ và liên hệ |
|---|---|
| [expression_planner.py](../../src/ai/expression_planner.py) | Chuẩn bị câu nguồn cho bộ sinh từng câu; hiện giữ bối cảnh gốc. |
| [prompts.py](../../src/ai/prompts.py), [qwen_client.py](../../src/ai/qwen_client.py) | File đầu tạo chỉ dẫn giữ dữ kiện, chỉ sửa câu chữ. File sau gửi đến Ollama và nhận kết quả/lỗi. |
| [contracts.py](../../src/ai/contracts.py) | Quy định dữ liệu trao đổi giữa bước chuẩn bị, Qwen và bộ kiểm tra. |

**Planner chọn câu; Qwen viết lại câu chữ; Assembler giữ đáp án nguồn.**
Hồ sơ học sinh và đáp án không được gửi vào chỉ dẫn cho Qwen.

### D. Lớp dữ liệu — Data / Persistence Layer

Khối **Data Access** và **SQLite Storage** được nối bởi các file trong `src/api/`:

| File | Nhiệm vụ và liên hệ |
|---|---|
| [m3_adapter.py](../../src/api/m3_adapter.py) | Đọc hồ sơ/câu hỏi từ SQLite nguồn, chuyển về dạng các module sử dụng. |
| [data_adapter.py](../../src/api/data_adapter.py) | Phần đọc/kiểm tra dùng chung, được `m3_adapter.py` dùng lại; hỗ trợ JSON cho demo. API dùng nó đối chiếu nguồn câu/kỹ năng trước khi lưu. |
| [exam_store.py](../../src/api/exam_store.py) | Lưu/mở đề và các phiên bản; chặn thao tác từ phiên bản cũ ghi đè thay đổi mới. |

Mặc định có **ba file dữ liệu riêng**; hai file nguồn chỉ được đọc:

- `data/sample/memory/student_profiles_sample.db`: hồ sơ học sinh.
- `data/sample/dataset/question_bank.db`: kỹ năng, câu hỏi và đáp án nguồn.
- `data/runtime/exams.db`: đề do ứng dụng tạo và các phiên bản của đề.

## 3. Một lần bấm “Tạo đề” đi qua đâu?

1. **Giao diện → API:** gửi yêu cầu; API đọc hồ sơ rồi gọi `exam_service.py`.
2. **Bộ điều phối → Planner → Selector:** lập kế hoạch, chọn câu nguồn.
3. **Bộ điều phối → Expression Planner → bộ sinh từng câu:** chuẩn bị câu,
   gọi Qwen và bộ kiểm tra.
4. **Assembler → API → kho đề:** ghép đề, kiểm tra toàn bộ, lưu rồi trả về giao diện.

Tạo đề trả kết quả hoàn chỉnh trong cùng một yêu cầu; thất bại thì không lưu đề dở.
**“Xem kế hoạch”** chỉ lập kế hoạch/chọn câu, chưa gọi Qwen hay lưu đề.

## 4. File phụ và những phần chưa triển khai

- [api/services.py](../../src/api/services.py): bộ tạo đề **fake** không gọi Qwen,
  kho đề tạm mất khi restart và các hàm chia số câu/điểm được luồng thật dùng chung.
- [ai/qwen_spike.py](../../src/ai/qwen_spike.py): chương trình thử nghiệm Qwen,
  đo thời gian/tài nguyên; chạy riêng với luồng tạo đề của ứng dụng.
- **Duyệt/tạo lại câu:** có API, chưa có giao diện. Phát đề cho học sinh chưa có.
- **Submission & AI Grading / Teacher Grade Verification:** chưa triển khai.
  `src/assessment/`, `src/competency/`, `src/knowledge/`, `src/exercise/` mới là
  thư mục giữ chỗ; các file `__init__.py` chưa có xử lý nghiệp vụ.

Vòng “học sinh làm bài → chấm → xác nhận điểm → cập nhật hồ sơ → tạo đề tiếp”
trong N04 vẫn là hướng phát triển, chưa phải luồng đang chạy trong `src`.
