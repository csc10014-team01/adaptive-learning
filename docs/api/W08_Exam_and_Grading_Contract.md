# W08 — Contract luồng sinh, duyệt và chấm bài trên UI giáo viên

Cập nhật 21/11/2026. Integration: `W08-2026-11-21-teacher-workflow-v2`.
Engine: `R2026-11-17-scoped-skill-guidance-v11`, giữ nguyên prompt và thuật toán.

Bản bàn giao luồng giáo viên V1: xem [ghi chú phạm vi, kiểm chứng và giới hạn](../report/W08_Teacher_Workflow_V1_Handoff.md).
V1 là phiên bản bàn giao luồng UI; mã integration `teacher-workflow-v2` phân biệt
với bản tích hợp backend ngày 20/11, không phải phiên bản model.

## Chạy local

Từ repository root, dùng terminal PowerShell:

```powershell
$env:QWEN_MODEL = 'qwen3:4b-q4_K_M'
$env:GRADING_MODEL = 'qwen3:4b-q4_K_M'
.\.venv\Scripts\python.exe -m src.ui
```

Ollama phải chạy và đã có đúng model được cấu hình. Không tự tải hoặc đổi model.
Để sinh đề không gọi Qwen, dùng `python -m src.ui --fake`; chấm bài không rỗng
vẫn gọi model thật. Có thể thêm `--port 8001` nếu port mặc định đang được dùng.
`python -m src.ui --grading` mở trực tiếp trang chấm. Launcher tạo token tạm;
`--no-browser` yêu cầu đặt `API_TEACHER_TOKEN` trong process. Không tự load `.env`.

Launcher luôn dùng SQLite `EXAM_DB` (mặc định `data/runtime/exams.db`), kể cả fake.
API `create_app(backend="fake")` vẫn giữ tương thích memory store nếu không chỉ
định `exam_db` hoặc `EXAM_DB`. Memory store giữ revision trong vòng đời process;
muốn mở lại đề sau restart phải chọn SQLite.

## Thao tác qua UI mới

1. Kết nối, chọn học sinh và mở hồ sơ chi tiết.
2. Mở cấu hình, xem phân phối và sinh đề. Xem đáp án/lời giải; có thể thay câu
   template hoặc tạo đề mới. Mỗi lần thay câu làm tăng revision và cần duyệt lại.
3. Xem các tiêu chí chấm gợi ý từ lời giải; sửa mô tả và chọn kỹ năng cho từng
   tiêu chí. Giáo viên chịu trách nhiệm xác nhận chúng phù hợp câu đang xem.
4. Bấm **Duyệt đề và rubric chấm**. Kiểm tra quality gate và revision vẫn được
   thực hiện; lỗi chặn không bị thao tác duyệt bỏ qua. `NEEDS_REVIEW` có thể được
   duyệt thủ công theo policy hiện hành, nhưng không tự trở thành `PASS` W06.
5. Bấm **Nhập bài làm và chấm**. Trang chấm tự lấy đúng snapshot đã duyệt, tự
   điền học sinh và tạo ô nhập cho tất cả câu. Không phải nhập lại context JSON.
6. Nhập bài nguyên văn. Nếu có dữ liệu giả lập, mở phần nhập JSON tùy chọn,
   dán đầy đủ bản ghi cho từng câu và bấm áp dụng. Nội dung trống là bài để trống;
   bản ghi thiếu hoặc ID lạ/trùng bị từ chối.
7. Bắt đầu chấm, theo dõi kết quả từng câu và tải kết quả JSON khi job hoàn tất.
   Có thể mở lại bằng mã job hoặc xem lịch sử chấm. Link quay lại đề giữ phiên
   làm việc trong fragment; token không nằm trong query HTTP hoặc localStorage.

Snapshot cũ đã duyệt nhưng chưa có context chấm không được tự sửa. Với những
đề đó, tạo bản nháp mới và duyệt rubric trước khi dùng luồng này.

## API và định danh

Tất cả endpoint dưới đây cần `Authorization: Bearer <teacher_token>`.

| API | Hành vi |
|---|---|
| `GET /api/v1/students` | Danh sách học sinh |
| `GET /api/v1/students/{id}/profile` | Hồ sơ hiện có |
| `GET /api/v1/topics` | Catalogue kỹ năng |
| `POST /api/v1/exams/plan` | Xem kế hoạch |
| `POST /api/v1/exams/generate` | Sinh và lưu bản nháp |
| `GET /api/v1/exams/{id}` | Bản mới nhất của đề |
| `POST /api/v1/exams/{id}/questions/{question_id}/regenerate` | Thay câu template, dùng `expected_revision` |
| `POST /api/v1/exams/{id}/approve` | Duyệt đề/rubric trong revision mới |
| `GET /api/v1/exams/{id}/grading-context?revision=N` | Đọc đúng bản đã duyệt, chuẩn bị ô nhập |
| `POST /api/v1/grading/jobs` | Ghi bài nộp/context và trả HTTP 202 |
| `GET /api/v1/grading/jobs?exam_id=...&limit=20` | Lịch sử; limit từ 1 đến 50, bỏ exam_id để xem cả experimental |
| `GET /api/v1/grading/jobs/{job_id}` | Metadata tiến độ và kết quả đã lưu |
| `GET /api/v1/grading/jobs/{job_id}/result` | Kết quả hoàn tất; trả 409 nếu job chưa xong |

`exam_id` là đề; `revision` là phiên bản bất biến; `question_id` là câu trong
snapshot, có thể khác ID ngân hàng; `job_id` là một lần chấm. Một đề có thể có
nhiều bài nộp, nhưng retry cùng bài phải dùng lại `idempotency_key`.

## Duyệt rubric

Ví dụ một đề một câu; thay mã câu và revision bằng giá trị thật vừa đọc:

```json
{
  "expected_revision": 1,
  "grading_contexts": [
    {
      "question_id": "Q_instance",
      "reference_answer": "5",
      "rubric": [
        {"id": "R1", "description": "Hai nhóm có 2 và 3 đối tượng, chọn đúng một đối tượng nên dùng quy tắc cộng.", "skill_ids": ["A001"]},
        {"id": "R2", "description": "Tính 2 + 3 = 5 và kết luận có 5 cách.", "skill_ids": ["A001", "A008"]}
      ]
    }
  ]
}
```

Nếu gửi `grading_contexts`, phải có đúng một mục cho mỗi câu. ID tiêu chí không
trùng; mỗi mục có mô tả và kỹ năng hợp lệ của câu (A008 được engine cho phép cho
lỗi số học). Backend tự gắn nội dung câu và lời giải nguồn, rồi lưu context cùng
revision được duyệt. Không dùng barem `criteria/sub_score` hoặc rubric chất lượng
W06 làm mapping chấm bài ngầm định. API duyệt cũ không gửi context vẫn được hỗ trợ,
nhưng chưa đảm bảo đề có thể dùng bộ chấm mới.

Đáp án biểu thức phải thuộc tập số học hữu hạn của engine. Bộ nối hỗ trợ chuyển
định dạng xác định như `53 cách chọn` → `53`, hoặc `C(20,2) = 190` → `190` sau
khi kiểm tra hai vế bằng nhau. Không lấy số cuối từ văn xuôi tùy ý. Đáp án chấm
phải bằng đáp án nguồn nếu nguồn nằm trong tập biểu thức kiểm chứng được;
đẳng thức sai bị từ chối. Văn bản ngoài tập hỗ trợ cần giáo viên nhập biểu thức
rõ ràng và xác nhận chuyên môn. Bản đáp án nguồn vẫn được giữ nguyên.

## Nộp bài và đọc kết quả

```json
{
  "mode": "approved_snapshot",
  "idempotency_key": "submission-example-001",
  "exam_id": "EX_example",
  "exam_revision": 2,
  "student_id": "ST001",
  "answers": [
    {"question_id": "Q_instance", "student_answer": "Hai nhóm không giao nhau nên có 2 + 3 = 5 cách chọn."}
  ]
}
```

Client không gửi đáp án/rubric thay thế trong chế độ approved. Snapshot server
phải có đúng học sinh, trạng thái duyệt và đủ grading context. Một revision đã
duyệt vẫn dùng được sau khi có bản nháp mới; không tự đổi sang revision mới nhất.

Response giữ envelope `{metadata, result}`. Metadata có `job_id`, trạng thái,
revision, số câu xử lý và số câu chưa xác định. `result.submissions[]` giữ ID câu,
các hành động đã đánh giá, verdict và lỗi; `result.feedback` có khi xử lý xong.
Verdict là `CORRECT`, `INCORRECT` hoặc `UNCERTAIN`. `COMPLETED` là xử lý và lưu
xong tất cả câu, không chứng minh mọi câu đã có kết luận xác định.

Retry cùng key/nội dung trả đúng job cũ, kể cả sau restart; đổi nội dung nhưng
giữ key trả 409. Job mới cần key mới. Lỗi provider không biến thành lỗi học sinh.
Job đang chạy khi process dừng sẽ thành `INTERRUPTED`; không tự chạy lại.

## Lưu trữ và lỗi

- `exams.db`: giữ nội dung đề và grading context trong từng revision.
- `grading.db`: giữ request nguyên văn, context snapshot, tiến độ và kết quả.
- Không ghi hai database mẫu hoặc hồ sơ học sinh. Không có PCM/EAP, điểm số,
  sửa kết quả AI hay student delivery trong phạm vi lần nối luồng này.
- Lỗi chính: 401/403 về token; `EXAM_REVISION_CONFLICT` khi duyệt/thay câu cũ;
  `INVALID_GRADING_REVIEW` khi reference/mapping không hợp lệ;
  `GRADING_EXAM_NOT_APPROVED`, `GRADING_SNAPSHOT_NOT_FOUND`,
  `GRADING_CONTEXT_NOT_READY` khi snapshot không dùng được;
  `GRADING_QUESTION_MEMBERSHIP` khi danh sách bài làm không khớp;
  `GRADING_IDEMPOTENCY_CONFLICT` khi gửi nội dung khác cùng key.

## Kiểm chứng

`tests/integration/test_teacher_grading_workflow.py` chạy sinh/duyệt/chấm,
retry chống trùng, revision cũ và đọc lại sau restart với transport Qwen giả lập.
`tests/ui/teacher_workflow.test.cjs` và `tests/ui/grading.test.cjs` chạy handler
JavaScript thật với HTTP giả lập. Engine/prompt tiếp tục được kiểm tra provenance.
Những kiểm tra này không đo độ chính xác của model thật.

Kết quả kiểm chứng ngày 21/11/2026: toàn repo **879 test đạt**, 14 subtest đạt,
một cảnh báo deprecation Starlette hiện có. Chrome headless đã chạy UI thật với
backend local: hồ sơ → cấu hình → sinh đề → thay câu template → duyệt rubric →
chuyển sang nhập bài → chấm → restart backend → mở lịch sử/kết quả → quay lại đề.
Không ghi nhận JavaScript exception. Lượt browser này dùng bộ sinh fake với
SQL readers thật và transport Qwen giả lập, nhưng đi qua engine, API và SQLite
thật. Hai database mẫu giữ nguyên byte; engine và transport Qwen v11 không đổi.
Ollama theo cấu hình hiện tại từ chối kết nối trong môi trường kiểm tra, nên
chưa chạy inference thật cho bản nối luồng này. Lượt smoke model thật ngày 20/11
trong báo cáo cũ thuộc bản tích hợp trước, không thay thế kiểm chứng model mới.
