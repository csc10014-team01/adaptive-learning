# W06 Exam Quality Gate — triển khai tối thiểu

## Phạm vi và quyết định được phê duyệt

Ngày 14/11/2026, chủ dự án phê duyệt:

- Đề thích ứng: cộng điểm C1/C2/C3/C4 theo tối đa 35/25/20/20.
- Structured Assessment (`default_blueprint`): C4 không áp dụng; tối đa 45/35/20.
- Giữ duyệt thủ công toàn đề với báo cáo `NEEDS_REVIEW`. Đề có thể `approved`
  nhưng báo cáo vẫn `NEEDS_REVIEW`, không tự cấp điểm hoặc tuyên bố đạt W06.

Rubric chi tiết vẫn là bản nháp. Không đặt ngưỡng mới cho mức độ trùng lặp,
lệch độ khó, chất lượng ngôn ngữ hoặc điểm đạt riêng từng tiêu chí.

## Luồng và tương thích

API sinh đề kiểm tra contract, allocation và nguồn như trước. Sau đó
`ExamQualityEvaluator` chạy trên DTO đầy đủ, trước khi lưu bản nháp. Cả nhánh
adaptive, default và fake đều đi qua ranh giới này. Không thay đổi planner,
nguồn câu, thứ tự chọn câu, tham số, ID hoặc seed.

`quality_report` là trường tùy chọn mới trên ExamResponse công khai và core.
JSON cũ vẫn đọc được. Không thêm endpoint hoặc bảng database. Báo cáo nằm trong
JSON snapshot của đề, được lưu nguyên tử bởi SQLiteExamStore/InMemoryExamStore
hiện có. Database nguồn không được ghi. Student view không chứa báo cáo.

Trước khi duyệt, backend đánh giá lại từ nguồn hiện hành và snapshot hồ sơ/yêu
cầu đã dùng khi sinh đề. Không thay bằng mastery mới trong database. Bản nháp
cũ chưa có snapshot được ghi thiếu bằng chứng. Fingerprint nội dung, revision
và policy version phải khớp; điểm thủ công cũ không được kế thừa qua policy mới.

Duyệt thành công tăng revision như trước và liên kết báo cáo với revision mới;
fingerprint không đổi vì thông tin duyệt không phải nội dung đề. Regenerate xóa
đánh giá thủ công, chạy lại đánh giá toàn đề, giữ snapshot đầu vào và tạo báo cáo
mới cùng revision mới. Thất bại hoặc xung đột revision không lưu đè bản hiện tại.

## Báo cáo và quy tắc chấm

Mỗi C1-C4 có status, score nullable, max_score, evidence, warnings, method và
các checks gắn question_ids. Check tự động thành công chỉ chứng minh phạm vi
ghi trong evidence, không cấp toàn bộ điểm rubric.

- C1: tái sử dụng schema về số câu/điểm/bước giải, kiểm tra tham chiếu nguồn,
  TemplateInstantiator và verified_count. Đáp án nguyên khác kết quả tính được
  xác nhận là HARD_FAIL. Nguồn văn bản tự do không được coi là đúng toán chỉ vì
  đáp án/lời giải khớp nguồn.
- C2: kiểm tra lớp/chủ đề/catalogue, kỹ năng và nhãn độ khó với nguồn, quota cứng
  của giáo viên. Metadata đúng không chứng minh nội dung đo đúng kỹ năng.
- C3: tái sử dụng near_duplicate và bổ sung so sánh câu chỉ đổi số, trên toàn đề
  kể cả sau regenerate. Chỉ cảnh báo NEEDS_REVIEW vì chưa có ngưỡng nghiêm trọng.
  Tiếng Việt, tính độc lập giữa câu và hiển thị công thức cần giáo viên xem.
- C4: lưu snapshot, kiểm tra classification bằng policy planner hiện hành khi
  version tương thích, đối chiếu số câu thực tế với summary, ghi quota và lịch
  sử câu sai liên quan. Không suy ra danh sách câu đã làm đúng/thành thạo hoặc
  nhãn lỗi tư duy từ dữ liệu không có.

Method RULE là kiểm tra tự động hữu hạn; HUMAN là đánh giá giáo viên được gửi
tường minh. LLM_ASSISTED chỉ là gợi ý. Evaluator không tự gọi Qwen hoặc dịch vụ
ngoài; callback advisory tùy chọn chỉ dùng khi caller chủ động cung cấp. Timeout
hoặc output sai contract được ghi RETRYABLE_FAIL, không biến thành PASS.

Điểm chỉ nhận từ đánh giá HUMAN có bằng chứng cho tiêu chí, trong mức tối đa đã
phê duyệt. Đánh giá HUMAN xác nhận đã xem toàn bộ các mục con và finding của
tiêu chí; không chỉ xác nhận metadata. Những check tự động ban đầu còn ghi
NEEDS_REVIEW được giữ để truy vết; đánh giá HUMAN nằm ở cấp tiêu chí. Bằng chứng
RULE về lỗi xác nhận được không bị điểm HUMAN ghi đè.

Tổng chỉ có khi mọi tiêu chí áp dụng được đánh giá và có điểm. Cộng các điểm
thành phần đúng một lần. Không đặt ngưỡng đạt riêng cho C1-C4: status PASS tại
cấp tiêu chí có nghĩa đánh giá đã hoàn tất; điểm vẫn có thể thấp. Báo cáo PASS
cần tổng >=80 và không có lỗi chặn hoặc tiêu chí chưa được đánh giá.

## Kết quả và duyệt đề

| Kết quả | Hành vi |
|---|---|
| PASS | Đủ bằng chứng HUMAN, tổng >=80, không có lỗi chặn; vẫn cần hành động giáo viên duyệt |
| HARD_FAIL | Sai đáp án đã kiểm chứng hoặc ngoài phạm vi lớp/chủ đề được hỗ trợ; chặn duyệt |
| QUALITY_FAIL | Vi phạm contract/nguồn/quota cứng hoặc tổng đã đánh giá <80; chặn duyệt |
| NEEDS_REVIEW | Thiếu bằng chứng/phán xét chuyên môn; cho duyệt thủ công theo quyết định trên, giữ nguyên trạng thái báo cáo |
| RETRYABLE_FAIL | Nguồn/kiểm tra RULE bắt buộc chưa sẵn sàng thì phải phục hồi và chạy lại; điểm HUMAN không thay thế kiểm tra này. Nếu chỉ đánh giá LLM hỗ trợ lỗi, HUMAN có thể đánh giá tiêu chí đó. |

`create_app(quality_policy=QualityPolicy(...))` hỗ trợ cấu hình chặt hơn, ví dụ
`allow_manual_needs_review=False`. Chính sách mặc định là các quyết định đã
phê duyệt ở trên, version `w06-approved-integration-v1`.

## Gửi điểm thủ công qua API hiện có

POST `/api/v1/exams/{id}/approve` vẫn nhận request cũ với expected_revision.
Trường tùy chọn mới `quality_review` dùng fingerprint trong quality_report:

```json
{
  "expected_revision": 1,
  "quality_review": {
    "content_fingerprint": "<chép fingerprint 64 ký tự từ quality_report>",
    "criteria": [
      {"criterion_id": "C1", "score": 35, "evidence": "Đã kiểm tra giả thiết, đáp án, lời giải và barem từng ý."},
      {"criterion_id": "C2", "score": 25, "evidence": "Đã đối chiếu nội dung với kỹ năng và độ khó thực tế."},
      {"criterion_id": "C3", "score": 18, "evidence": "Đã xem ngôn ngữ, công thức, trùng lặp và quan hệ giữa các câu."},
      {"criterion_id": "C4", "score": 18, "evidence": "Đã đối chiếu hồ sơ, phân phối câu và giới hạn lịch sử học tập."}
    ]
  }
}
```

Default Blueprint chỉ gửi C1-C3 theo mức tối đa 45/35/20. Có thể gửi một phần
đánh giá; tổng vẫn null nếu chưa đủ. Fingerprint cũ, điểm vượt mức, tiêu chí trùng
hoặc chấm C4 không áp dụng trả 422. Lỗi gate trả 409 `EXAM_QUALITY_*`.
Đánh giá được lưu cùng revision duyệt thành công; yêu cầu duyệt bị từ chối
không lưu đánh giá nháp riêng. UI hiển thị báo cáo và khóa lỗi chặn; chưa có form
nhập điểm W06, nên việc nhập điểm có cấu trúc hiện qua API.

## Giới hạn

Chưa tự động xác minh toàn bộ toán học/ngữ nghĩa của nguồn ngân hàng và
experimental Indirect. Chưa có ngưỡng tự động cho trùng lặp hay lệch độ khó
nghiêm trọng. Chưa tích hợp LLM chấm rubric hoặc benchmark chất lượng chuyên môn.
Teacher token hiện là token dùng chung; bằng chứng HUMAN tin cậy người dùng đã
xác thực, chưa xác định cá nhân giáo viên hoặc tự kiểm chứng nội dung nhận xét.
Không triển khai chấm bài học sinh hoặc cập nhật Student Profile.

## Kiểm thử

```powershell
.\.venv\Scripts\python.exe -B -m pytest -q -p no:cacheprovider
node --test tests/ui/teacher_review.test.cjs
```

Test evaluator dùng nguồn giả lập; test API dùng nguồn chỉ đọc và database
runtime tạm. Không dùng kết quả test để khẳng định đề thật đạt chất lượng W06.

Kết quả xác nhận sau rà soát ngày 14/11/2026: **582 test Python đạt**, bao gồm bộ gọi
**20 tình huống UI** qua Node. Không có test thất bại. Có một cảnh báo deprecation
từ Starlette TestClient/httpx hiện có; không đổi dependency trong phạm vi này.
Rà soát mở rộng: 600 ca sinh đề offline, 20 lần chạy lại cùng seed và 20 lần
regenerate đạt. Xem [báo cáo preflight](../report/exam_generation_preflight.md).

## Tệp thay đổi và trách nhiệm

| Tệp | Mục đích |
|---|---|
| `src/exam_generator/validation/quality_contracts.py` | Contract báo cáo, kiểm tra tính nhất quán, đánh giá HUMAN và fingerprint dùng chung |
| `src/exam_generator/validation/exam_quality.py` | Tổng hợp bằng chứng C1-C4, tính tổng một lần, xử lý outcome và gate |
| `src/exam_generator/api/schemas.py` | Thêm quality_report tùy chọn và quality_review trong approve request |
| `src/api/schemas.py` | Cho phép báo cáo trên DTO công khai, giữ student allowlist |
| `src/api/main.py` | Đánh giá sau kiểm tra nguồn, đánh giá lại trước duyệt và sau regenerate; cấu hình policy |
| `src/exam_generator/orchestration/review_service.py` | Kiểm tra gate trước duyệt, chuyển revision báo cáo khi duyệt thành công |
| `src/exam_generator/orchestration/exam_service.py` | Xóa báo cáo cũ khi regenerate để không kế thừa điểm |
| `src/ui/static/app.js` | Hiển thị kết quả/bằng chứng còn thiếu và khóa nút duyệt khi gate chặn |
| `docs/notes/W06_Rubric.md` | Ghi quyết định đã phê duyệt và sửa công thức bị nhân trọng số hai lần |
| `docs/design/W06_Exam_Quality_Gate.md` | Hướng dẫn luồng, interface, policy, kiểm thử và giới hạn |
| `tests/generator/unit/test_exam_quality.py` | Kiểm tra rubric, toán học, nguồn, trùng lặp, hồ sơ, advisory và báo cáo cũ |
| `tests/generator/test_quality_api.py` | Kiểm tra tích hợp, điểm HUMAN, gate, snapshot, regenerate và persistence |
| `tests/generator/api_helpers.py` | Cho phép test truyền policy chặt hơn qua cấu hình app |
| `tests/ui/teacher_review.test.cjs` | Thêm tình huống UI cho báo cáo bị chặn và duyệt thủ công NEEDS_REVIEW |
| `tests/generator/test_teacher_javascript.py` | Cập nhật số tình huống UI kỳ vọng từ 18 thành 20 |
| `src/exam_generator/ai/qwen_client.py` | Chặn timeout không hữu hạn, ngân sách thử sai kiểu và response không kết thúc bình thường |
| `tools/check_exam_readiness.py` | Kiểm tra ma trận sinh đề chỉ đọc, replay, regenerate và khả năng kết nối Ollama |
| `tests/generator/unit/test_qwen_transport.py` | Hồi quy cấu hình tài nguyên và completion envelope Qwen |
| `tests/generator/test_exam_readiness.py` | Kiểm tra công cụ preflight giữ lỗi, không suy diễn chất lượng Qwen từ fake |
