# W07 Checklist nghiệm thu và kịch bản demo

**Phụ trách:** Ngô Nhất Nghi · [Issue #55](https://github.com/csc10014-team01/adaptive-learning/issues/55)

**Trạng thái:** Checklist và kịch bản sơ bộ. Cấu hình và kết quả demo sẽ được điền sau khi chạy thử.

W07 kiểm chứng luồng sinh và duyệt đề MVP1 đã tích hợp vào `main`, xây dựng giao diện và nối backend AI chấm điểm. Demo đi từ đề vừa duyệt đến bài nộp mẫu có cả câu AI chấm được và câu cần giáo viên chấm.

## Quyết định đánh giá từ cuộc họp W06

Nhóm thống nhất dùng phương pháp đánh giá trong [W06 Grading Data Model](../design/W06_Grading_Data_Model.md), mục 2–7.

- **Chấm từng câu:** Ghi mức rubric quan sát được (`observed_level`) từ 0 đến mức tối đa của rubric đã duyệt. Ví dụ với rubric 0–4, mức 0 là kết quả đánh giá hợp lệ. Với câu chuyển chấm tay, giáo viên đối chiếu bài làm với rubric có sẵn trong phiên bản đề đã duyệt, rồi chọn mức đạt và ghi nhận xét. `observed_level` để trống cho đến khi giáo viên lưu kết quả. Mỗi câu chỉ ghi mức đánh giá cho kỹ năng chính nếu có đủ căn cứ.
- **Tính năng lực:** Dùng Partial Credit Model (PCM) và độ khó từng bước chuyển mức để ước lượng `theta_eap`. Quy đổi qua bộ tham chiếu chung thành `question_mastery_score`. Mastery của một kỹ năng là trung bình các điểm câu hợp lệ thuộc kỹ năng đó. `evidence_count` là số kết quả được tính vào trung bình.
- **Bàn giao W07**
  - Lưu mức rubric, nhận xét và nguồn chấm. Gắn kết quả với bài nộp, câu hỏi, kỹ năng và phiên bản đề đã duyệt.
  - Ánh Dương, Yến Trân và Khánh Như đối chiếu rubric tính điểm hiện có của MVP1 với rubric theo mức dùng để chấm bài.
  - Đề demo có tiêu chí rõ cho từng mức rubric để QA đối chiếu kết quả.
  - Nghiệm thu phần tính PCM/EAP và cập nhật hồ sơ trong W08.

## Checklist nghiệm thu W07

### Sinh và duyệt đề

- [ ] **GEN-01** — Trên giao diện giáo viên của nhóm, chọn học sinh và sinh đề. Xem trước được câu hỏi, đáp án và lời giải. Kiểm tra đáp án và lời giải khớp với yêu cầu thực tế của từng câu trong đề demo.
- [ ] **GEN-02** — Sinh lại một câu từ template và thấy phiên bản đề thay đổi. Duyệt phiên bản mới nhất và đọc lại đúng nội dung đã duyệt. Thao tác gửi với phiên bản cũ được báo xung đột.
- [ ] **GEN-03** — Thử sinh đề lỗi và ca hết lượt thử lại. Giao diện báo rõ trạng thái và backend chỉ trả đề hoàn chỉnh hoặc phương án thay thế hợp lệ.
- [ ] **GEN-04** — Khi có Ollama, chạy ít nhất một đề adaptive đầy đủ với Qwen thật. Ghi model, cấu hình, thời gian và kết quả đối chiếu câu hỏi với đáp án/lời giải. Kiểm tra ca Indirect EA0004 từng đổi yêu cầu đếm số cách chọn thành hỏi số lượng tối thiểu. Ghi riêng kết quả Qwen thật và giả lập.

### Chấm AI từng câu

- [ ] **GRD-01** — API nhận bài nộp mẫu với đúng học sinh, mã đề, phiên bản đã duyệt và ID từng câu. Từ chối đề chưa duyệt, sai phiên bản, thiếu bản ghi câu hoặc ID lạ/trùng.
- [ ] **GRD-02** — Câu có căn cứ xác minh trả `observed_level` trong miền rubric, nhận xét và nguồn chấm. QA đối chiếu với mức kỳ vọng trong dữ liệu mẫu.
- [ ] **GRD-03** — Câu AI chưa xác minh được có cờ cần giáo viên và lý do, với `observed_level` chưa có. Mức sai miền hoặc đầu ra lỗi không được lưu thành kết quả hợp lệ. Kết quả của câu đã chấm được vẫn đọc lại được.
- [ ] **GRD-04** — Gửi lại cùng bài nộp rồi đọc lại kết quả sau khi khởi động lại backend. Kết quả từng câu được giữ và không có bản ghi trùng. Bài demo còn câu cần giáo viên được hiển thị là chưa hoàn tất chấm.

## Kịch bản demo sơ bộ

| Bước | Thao tác | Kết quả cần thấy |
|---|---|---|
| 1 | Mở giao diện giáo viên. Chọn học sinh mẫu và sinh đề theo cấu hình đã chạy thử. | Có bản nháp đề kèm đáp án và lời giải. Người demo nêu rõ đang dùng Qwen thật hay bộ sinh giả lập. |
| 2 | Xem trước, sinh lại một câu từ template và duyệt bản mới nhất. | Câu thay đổi, phiên bản tăng và bản mới được duyệt. Ghi `exam_id` và `revision` đã duyệt. |
| 3 | Qua API theo contract của Khánh Như, gửi bài nộp mẫu gắn với đúng phiên bản và các ID câu vừa duyệt. | Một câu trả mức rubric và nhận xét như kỳ vọng. Một câu khác trả cờ cần giáo viên và lý do, chưa có mức. |
| 4 | Đọc lại kết quả rồi gửi lại cùng bài nộp. | Kết quả hai nhánh được giữ, không thêm bản ghi trùng. Bài còn chờ giáo viên. |

**Chuẩn bị bài mẫu khi chạy thử:** Chọn một câu có lời giải dễ xác minh và một câu có câu trả lời không rỗng nhưng thiếu căn cứ để AI xác minh theo rubric. Chuẩn bị bản ghi cho tất cả câu trong đề và lưu mức hoặc lý do kỳ vọng trước khi chạy. Nếu sinh lại làm đổi ID hoặc dữ kiện, gắn lại câu trả lời theo đề mới duyệt.

## Mốc bàn giao và chọn cấu hình

| Mốc | Việc cần làm |
|---|---|
| **09/11 12:00** | Nghi bàn giao checklist và kịch bản sơ bộ cho [#56–#60](https://github.com/csc10014-team01/adaptive-learning/issues?q=is%3Aissue+%5BW07%5D). |
| **10/11 12:00 và 20:00** | Khánh Như bàn giao contract lúc 12:00. Ánh Dương bàn giao mã đọc/ghi và bài nộp mẫu lúc 20:00. |
| **12/11 20:00** | Yến Trân bàn giao bộ chấm AI và kết quả kiểm tra Indirect. |
| **13/11 sau 20:00** | Sau khi có API tích hợp, Nghi chọn cấu hình để QA chạy thử dựa trên kết quả Indirect và môi trường thực tế. |
| **14/11 16:00** | Chi Mai bàn giao giao diện giáo viên và cách chạy cho QA. |
| **15/11 12:00, 20:00 và 21:00** | QA gửi kết quả lúc 12:00. Nghi xác nhận cấu hình từ kết quả đó, chạy demo lúc 20:00 và ghi kết quả, đầu việc W08 trước 21:00. |

- **Cấu hình ưu tiên:** Qwen thật cho luồng adaptive sau khi QA xác nhận đề demo. Nếu lỗi lệch nghĩa Indirect còn xuất hiện hoặc chưa xác minh được, chạy thử với `KORO_EXPERIMENTAL_INDIRECT=0`.
- **Phương án dự phòng:** Nếu Ollama không chạy được hoặc đề Qwen chưa đạt khi chạy thử, dùng chế độ sinh đề giả lập theo hướng dẫn tích hợp. Ghi riêng chế độ chấm bài và phần nào còn chờ kiểm chứng bằng model thật.

## Kết quả demo và bàn giao W08

| Nội dung | Ghi sau khi chạy |
|---|---|
| Bản tích hợp, môi trường và cấu hình | [Commit, chế độ sinh đề, model, Indirect, chế độ chấm] |
| Dữ liệu demo | [Học sinh mẫu, mã đề, revision đã duyệt, mã bài nộp] |
| Kết quả và lỗi | [Ca đạt, ca lỗi, ca chưa chạy, liên kết báo cáo QA và issue liên quan] |
| Việc chuyển W08 | [Người phụ trách và mốc cho chấm tay, chốt toàn bài và cập nhật hồ sơ PCM/EAP] |

W08 cần kiểm thử chấm tay câu được chuyển, chốt toàn bài khi đủ kết quả hợp lệ và cập nhật mastery/evidence theo kỹ năng. Dùng dữ liệu mẫu để kiểm chứng tính toán và kiểm tra gửi lại yêu cầu không cộng trùng bằng chứng. Đánh giá chất lượng sinh đề chính thức theo rubric thuộc W09.

Tham chiếu [Workflow và tiêu chí nghiệm thu W06](../design/W06_Grading_Workflow_and_Acceptance_Criteria.md), [Dữ liệu mẫu PCM/EAP](../../data/sample/grading/W06_Grading_Sample_Data.json) và [báo cáo tích hợp bộ sinh đề](../report/finalized_generator_integration.md).
