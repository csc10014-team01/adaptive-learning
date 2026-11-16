# ADR-001: Định lượng ngưỡng phân loại năng lực và cơ chế Rẽ nhánh / Fallback

- **Trạng thái:** Chấp thuận; phần quyết định ban đầu được cập nhật bằng policy hiện hành ở mục 2–4.
- **Ngày quyết định ban đầu:** 19/10/2026
- **Người ra quyết định ban đầu:** Nhất Nghi (Project Lead)
- **Tham vấn ban đầu:** Yến Trân (AI Lead), Ánh Dương (Data Lead)
- **Ngày đồng bộ tài liệu với implementation:** 16/11/2026
- **Policy mặc định được đối chiếu:** `mvp-personalization-v4-coordinated-difficulty`.

## 1. Bối cảnh và vấn đề

Hệ thống cần chọn trọng tâm kỹ năng và độ khó dựa trên hồ sơ học sinh, đồng thời xử lý được trường hợp thiếu bằng chứng, thiếu nguồn câu hỏi hoặc lỗi diễn đạt từ Qwen.

Quyết định ngày 19/10/2026 dùng ba nhóm `no_data`, `partial`, `sufficient`, với ngưỡng đủ dữ liệu từ 2 bằng chứng và cách rẽ nhánh Default/Personalized cho cả đề. Mô tả đó đã được thay thế bởi policy hiện hành dưới đây. Lịch sử quyết định được giữ tại mục 7; bản cập nhật này ghi nhận implementation đang có, không thay đổi thuật toán hoặc dữ liệu học sinh.

## 2. Phân loại theo từng kỹ năng

### 2.1. Dữ liệu và ngưỡng mặc định

- **`evidence_count`:** Số kết quả đánh giá hợp lệ được tính vào hồ sơ của **một kỹ năng**. Planner chỉ đọc giá trị này, không tự tăng bằng chứng hoặc suy ra bằng chứng từ lịch sử câu sai.
- **`mastery_score`:** Điểm thành thạo của kỹ năng trên thang **0–4**; điểm có giá trị phải hữu hạn và nằm trong miền này.
- **`min_evidence = 3`:** Mốc đủ bằng chứng để sử dụng mastery cho cá nhân hóa độ khó.
- **`mastery_target = 2.0`:** Mốc phân biệt kỹ năng yếu và đạt khi đã đủ bằng chứng.

### 2.2. Bốn trạng thái

| Trạng thái | Điều kiện của từng kỹ năng | Cách sử dụng |
|---|---|---|
| `NO_DATA` | Không có bản ghi kỹ năng trong hồ sơ, hoặc `evidence_count == 0` | Chưa có mastery được đo; thuộc nhóm chẩn đoán. |
| `PARTIAL` | `1 <= evidence_count < 3`, với mastery hợp lệ | Có dữ liệu nhưng chưa dùng mastery để phân loại yếu/đạt; thuộc nhóm chẩn đoán. |
| `WEAK` | `evidence_count >= 3` và `mastery_score < 2.0` | Có thể được chọn làm kỹ năng trọng tâm luyện tập. |
| `ACHIEVED` | `evidence_count >= 3` và `mastery_score >= 2.0` | Dùng mastery để phân bổ độ khó cho phần ôn tập. |

Các điều kiện được áp dụng độc lập cho từng mã kỹ năng trong danh mục. Một học sinh có thể đồng thời có cả bốn trạng thái.
Không có bản ghi kỹ năng hoặc evidence bằng 0 được xem là `NO_DATA`. Bản ghi có evidence > 0 nhưng thiếu mastery hợp lệ là lỗi dữ liệu, không được tự chuyển thành `NO_DATA` hoặc `PARTIAL`.

## 3. Rẽ nhánh và phân bổ đề

Planner xét toàn bộ kỹ năng trong danh mục sau khi phân loại, theo thứ tự sau:

| Điều kiện | `strategy` | Phân bổ mục tiêu mặc định |
|---|---|---|
| Có ít nhất một kỹ năng `WEAK` | `focused_practice` | Chọn tối đa hai kỹ năng yếu nhất, sắp theo mastery tăng dần, hòa điểm theo mã kỹ năng. Một trọng tâm nhận khoảng 40% số câu; hai trọng tâm nhận tổng khoảng 60%. Phần còn lại dành cho các kỹ năng ôn tập khác. |
| Không có `WEAK`, còn kỹ năng `NO_DATA` hoặc `PARTIAL` | `diagnostic_review` | Nếu có cả kỹ năng `ACHIEVED`, dành khoảng 60% số câu cho nhóm chẩn đoán và phần còn lại cho nhóm duy trì; nếu không có `ACHIEVED`, toàn bộ câu dành cho chẩn đoán. |
| Tất cả kỹ năng là `ACHIEVED` | `advanced_review` | Ôn tập các kỹ năng đã đạt, với độ khó theo mastery từng kỹ năng. |

## 4. Cơ chế xử lý lỗi và fallback

| Tình huống | Hệ thống xử lý thế nào? |
|---|---|
| Hồ sơ học sinh hoặc nguồn câu hỏi chứa dữ liệu sai | Dừng xử lý và báo lỗi dữ liệu. Không tự điền điểm năng lực hay số bằng chứng để tiếp tục sinh đề. |
| Mẫu câu hỏi (Template) không dùng được cho yêu cầu hiện tại | Ghi cảnh báo, rồi tìm mẫu khác hoặc câu có sẵn trong ngân hàng câu hỏi. |
| Qwen trả sai định dạng JSON hoặc câu hỏi không qua bước kiểm tra | Gửi lại yêu cầu kèm lỗi cần sửa. Mặc định tối đa **2 lần gọi cho mỗi cách diễn đạt**, gồm lần đầu; vẫn lỗi thì chuyển sang bước thay cách diễn đạt hoặc thay nguồn bên dưới. |
| Câu Indirect vẫn lỗi sau các lần thử | Nhờ Qwen diễn đạt lại theo dạng Direct, giữ nguyên dữ kiện và đáp án của bài toán. Các lần thử Direct vẫn chịu giới hạn thời gian chung của đề. |
| Khi sinh đề mới, Qwen bị quá thời gian, đang bận hoặc vẫn không tạo được câu hợp lệ | Bỏ mẫu đang lỗi và chọn lại nguồn để ráp đề. Có thể dùng mẫu khác hoặc câu có sẵn; chỉ trả đề khi tìm đủ câu hợp lệ. |
| Không tìm đủ câu để tạo đề hợp lệ | Báo không đủ nguồn câu hỏi (`INSUFFICIENT_QUESTION_BANK`, HTTP 409). Không lưu đề còn thiếu câu. |
| Câu hỏi có trạng thái `needs_review` | Yêu cầu giáo viên kiểm tra nội dung và duyệt. Trạng thái này chưa xác nhận câu hỏi đúng nghĩa toán học hoặc đạt rubric. |
| Sinh lại một câu thất bại | Báo lỗi của lần sinh lại. Không tự chọn lại nguồn cho toàn bộ đề như khi sinh đề mới. |

**Giới hạn thời gian và số lần thử:**

- Mỗi lần gọi Qwen có giới hạn mặc định **45 giây**.
- Mỗi cách diễn đạt được thử tối đa **2 lần mặc định**, gồm lần gọi đầu tiên. Có thể cấu hình từ 1 đến 3 lần.
- Các lần gọi Qwen trong cùng một đề dùng chung ngân sách **180 giây**. Thử lại hoặc chuyển từ Indirect sang Direct không làm thời gian này tính lại từ đầu.
- Đây là giới hạn cấu hình. Tổng thời gian xử lý yêu cầu còn gồm đọc dữ liệu, chọn câu và kiểm tra đề nên có thể dài hơn.

**Khi một mẫu câu hỏi bị lỗi:**

Hệ thống bỏ mẫu đó khỏi các lần chọn nguồn tiếp theo trong cùng yêu cầu và tìm nguồn thay thế. Chỉ khi có đủ câu và đề vượt qua bước kiểm tra hợp lệ, hệ thống mới trả về và lưu bản nháp. Nếu không tạo được đề hoàn chỉnh, hệ thống báo lỗi.

Giáo viên vẫn cần kiểm tra và duyệt bản nháp trước khi sử dụng.

## 5. Nguồn đối chiếu implementation

- [PlannerPolicyConfig](../../src/exam_generator/adaptation/policy.py): phiên bản, ngưỡng evidence/mastery và các tỷ lệ mặc định.
- [RuleBasedPlanner](../../src/exam_generator/adaptation/planner.py): phân loại từng kỹ năng, chọn chiến lược, phân bổ quota và diagnostics.
- [SkillMastery và StudentProfileResponse](../../src/exam_generator/api/schemas.py): miền dữ liệu, chuẩn hóa mastery khi evidence bằng 0 và validation hồ sơ.
- [SourceSelector](../../src/exam_generator/adaptation/source_selector.py): chọn/thay nguồn và giới hạn an toàn.
- [QuestionGenerationService](../../src/exam_generator/orchestration/question_generation.py), [ExamService](../../src/exam_generator/orchestration/exam_service.py) và [QwenClient](../../src/exam_generator/ai/qwen_client.py): retry, Direct fallback, lập lại lựa chọn nguồn và ngân sách thời gian.
- [Test policy mastery 0–4](../../tests/generator/unit/test_mastery_2of4_policy.py): ngưỡng 2,0, evidence tối thiểu 3, hồ sơ hỗn hợp và giới hạn L4.

## 6. Lịch sử quyết định

| Mốc | Nội dung | Trạng thái |
|---|---|---|
| 19/10/2026 — quyết định ban đầu | `no_data = 0`, `partial = 1`, `sufficient >= 2`; chọn Default/Personalized theo bằng chứng; dự kiến fallback chung về Default và khóa adaptive khi thiếu dữ liệu. | Đã được thay thế; giữ để truy vết. |
| 16/11/2026 — đồng bộ tài liệu theo #63 | Ghi nhận policy `mvp-personalization-v4-coordinated-difficulty`: evidence tối thiểu 3, mastery mục tiêu 2,0/4, phân loại từng kỹ năng thành bốn trạng thái; mô tả chiến lược và fallback theo implementation hiện hành. | Áp dụng cho tài liệu và expected result của đợt chạy thử mới; không đổi code. |
