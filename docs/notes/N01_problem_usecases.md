# N01 — PROBLEM BRIEF: Hệ thống AI hỗ trợ giáo viên sinh đề Toán tự luận cá nhân hóa

* **Mã tài liệu:** N01 (Problem Brief v1.1)
* **Owner:** Ngô Nhất Nghi (Project & Product Lead)
* **Reviewer:** Phạm Yến Trân (AI & Algorithms Lead)
* **Ngày cập nhật:** 19/10/2026

---

## 1. Bối cảnh & Vấn đề cốt lõi (Problem Statement)
* **Người dùng mục tiêu (Target Persona):** Giáo viên giảng dạy môn Toán cấp 3 (lớp 10).
* **Nỗi đau (Pain Point):** Giáo viên hiểu rõ mỗi học sinh có điểm yếu ở các chủ đề khác nhau, nhưng việc tự biên soạn các bộ đề tự luận riêng biệt cho từng nhóm học sinh tốn quá nhiều thời gian. Hệ quả là giáo viên thường phải dùng chung một cấu trúc đề cho cả lớp, khiến học sinh yếu bị quá tải còn học sinh khá không được rèn luyện đúng trọng tâm.
* **Mục tiêu hệ thống:** Xây dựng trợ lý thông minh giúp giáo viên quản lý hồ sơ và sinh đề Toán tự luận bằng mô hình ngôn ngữ cục bộ (Local Qwen). Khả năng cá nhân hóa của hệ thống được chứng minh thông qua việc **tự động rẽ nhánh và sinh ra các bộ đề (Blueprint) có cấu trúc/độ khó hoàn toàn khác biệt tương ứng với 3-4 nhóm hồ sơ năng lực đặc thù của học sinh.**

---

## 2. Luồng sử dụng đầu cuối (E2E User Journey)
Hệ thống vận hành qua luồng 4 bước dành cho giáo viên. (Trong phạm vi MVP, luồng này sẽ được chạy lặp lại trên 3-4 hồ sơ học sinh khác nhau để minh chứng khả năng cá nhân hóa):

1. **Nạp & Chọn Hồ sơ (Profile Selection):** Hệ thống nạp sẵn dữ liệu giả lập (synthetic data) của các học sinh đại diện cho các nhóm năng lực khác nhau (VD: Học sinh mới chưa có dữ liệu, Học sinh yếu Tổ hợp, Học sinh yếu Hoán vị). Giáo viên chọn một học sinh để tiến hành sinh đề.
2. **Quyết định cấu hình sinh đề (Blueprint Routing):** Dựa trên trạng thái hồ sơ tĩnh, thuật toán hệ thống tự động rẽ nhánh:
   * Nếu hồ sơ `"no_data"` / `"partial"` (Học sinh mới): Áp dụng **Cấu trúc mặc định (Default Blueprint)** với phân bổ độ khó và chủ đề đồng đều.
   * Nếu hồ sơ `"sufficient"` (Đã đủ dữ liệu): Áp dụng **Cấu trúc cá nhân hóa (Personalized Blueprint)** (VD: tăng số lượng câu hỏi Dễ/Trung bình xoáy sâu vào chủ đề mà học sinh đó đang yếu).
3. **Sinh bộ câu hỏi (Local Qwen Generation):** Backend dịch Blueprint thành Prompt và gọi mô hình Qwen (chạy local). Qwen sinh bộ câu hỏi Toán tự luận dưới định dạng JSON (gồm đề bài, mức độ, đáp án, và biểu điểm/rubric).
4. **Kiểm định, Duyệt & Xuất đề (Validation & Export):** Bộ Output Validator tự động chặn các kết quả lỗi định dạng hoặc lỗi toán học nghiêm trọng. Nếu đạt, hệ thống hiển thị bản xem trước (Preview) để giáo viên duyệt, chỉnh sửa thủ công và xuất đề.

---

## 3. Đầu vào & Đầu ra của hệ thống (Inputs & Outputs)
* **Inputs:**
  * File dữ liệu hồ sơ học sinh giả lập (Synthetic Student Profiles tạo sẵn với 3-4 ca kiểm thử điển hình).
  * Lựa chọn của giáo viên (Chọn học sinh nào để sinh đề, cấu hình bổ sung nếu cần).
* **Outputs:**
  * Hồ sơ năng lực tĩnh của học sinh được hiển thị trực quan.
  * Bộ câu hỏi Toán tự luận cá nhân hóa (kèm lời giải và rubric chấm) tương thích chính xác với điểm yếu trong hồ sơ, sẵn sàng để xuất file.

---

## 4. Phạm vi dự án (MVP Scope & Non-Goals)

| Trong phạm vi MVP (In Scope) | Ngoài phạm vi MVP (Out of Scope / Non-Goals) |
| :--- | :--- |
| • **Student Profiles:** Hiển thị hồ sơ năng lực học sinh theo chủ đề từ dữ liệu tạo sẵn. | • **Dashboard & Bulk Grade Import:** Bỏ qua tính năng thống kê lớp học và tính năng upload/kiểm duyệt bảng điểm hàng loạt. |
| • **Personalized Question Generation:** Sinh câu hỏi tự động. Minh chứng bằng 3-4 bộ đề đầu ra khác biệt cho 3-4 hồ sơ đầu vào khác biệt. | • **Vòng lặp cập nhật điểm (Feedback Loop):** Không làm tính năng nhập điểm sau bài làm để tự cập nhật hồ sơ. |
| • **Rule Engine + Local Qwen:** Thuật toán minh bạch quyết định blueprint; chạy Qwen local có kiểm soát chất lượng (Validator). | • **Giao diện & Chấm bài học sinh:** Không làm UI học sinh, không dùng AI chấm bài tự luận. |
| | • **API LLM Cloud:** Không phụ thuộc API LLM đám mây trong luồng chính. |

---

## 5. Quyết định nền tảng (Decisions) vs. Giả định cần kiểm chứng (Assumptions)

### Các quyết định đã chốt (Decisions D1 – D6):
* **D1 (Người dùng):** Người dùng trực tiếp duy nhất là Giáo viên.
* **D2 (Môn học & Dạng bài):** Môn Toán; chương Đại số Tổ hợp; định dạng câu hỏi mở tự luận (kèm đáp án, lời giải và rubric chấm).
* **D3 (Dữ liệu thử nghiệm):** Sử dụng các hồ sơ năng lực giả lập tĩnh (Synthetic static profiles) làm đầu vào để test thuật toán sinh đề cá nhân hóa.
* **D4 (Thu hẹp luồng E2E):** Thu hẹp scope chỉ tập trung vào luồng chuyển đổi từ: **Profile có sẵn $\rightarrow$ Blueprint Rules $\rightarrow$ Bộ đề Qwen**.
* **D5 (Rẽ nhánh Blueprint):** Bắt buộc xử lý phân tách hành vi giữa hồ sơ thiếu dữ liệu (dùng Default) và hồ sơ đủ dữ liệu (dùng Personalized).

### Các giả định cần kiểm chứng (Assumptions to Verify):
* **A1 (Hiệu năng phần cứng Local Qwen):** Giả định cấu hình máy cá nhân chạy được Qwen pretrained sinh ra JSON hợp lệ ở mức độ trễ (latency) và bộ nhớ chấp nhận được cho buổi Live Demo.
* **A2 (Nhu cầu Fine-tuning):** MVP ưu tiên dùng Qwen pretrained làm baseline; chỉ fine-tune nếu model gốc không thể sinh JSON và câu hỏi toán học đúng chuẩn sau khi Prompt Engineering.

---

## 6. Tiêu chí thành công & Thước đo (Success Criteria & Metrics)
Hệ thống được đánh giá thành công khi thỏa mãn các thước đo định lượng sau:
1. **Độ chính xác toán học (Mathematical Correctness Rate):** Tỷ lệ câu hỏi sinh ra không mắc lỗi toán học nghiêm trọng (áp dụng Hard-Fail rule).
2. **Điểm chất lượng bộ đề (Average Rubric Score):** Điểm trung bình theo Rubric 9 tiêu chí đạt **$\ge 80/100$**.
3. **Tính nhất quán cá nhân hóa (Personalization Consistency):** Hệ thống chứng minh rẽ nhánh thành công: 3-4 hồ sơ học sinh khác nhau (No Data, Yếu Tổ hợp, Yếu Hoán vị) phải xuất ra được 3-4 bộ cấu hình đề (Blueprint) và đầu ra Qwen hoàn toàn tương ứng với điểm yếu đó.
4. **Độ tin cậy (Reliability & Safeguards):** Bắt được lỗi timeout hoặc sai định dạng JSON từ Qwen để kích hoạt cơ chế fallback, không thất bại âm thầm.
5. **Độ trễ sinh đề (Generation Latency):** Thời gian sinh 1 bộ đề nằm trong giới hạn chờ đợi hợp lý trên cấu hình phần cứng demo.

---

## 7. Tiêu chí nghiệm thu Task N01 (Acceptance Criteria)
- [x] Xác định rõ persona Giáo viên, nỗi đau và luồng E2E 4 bước rút gọn.
- [x] Phân định rạch ròi 2 tính năng In-Scope (Profiles, Question Gen) và các Non-Goals (Bỏ Dashboard, Bulk Import, UI học sinh, Feedback Loop).
- [x] Nhấn mạnh phương pháp kiểm chứng MVP: Chạy 3-4 hồ sơ tĩnh khác nhau để đánh giá thuật toán rẽ nhánh cá nhân hóa.
- [x] Định nghĩa bộ chỉ số đo lường (metrics) và quy tắc Hard-Fail rõ ràng.
- [ ] Được **AI & Algorithms Lead** review và xác nhận tính khả thi kỹ thuật trên Pull Request.