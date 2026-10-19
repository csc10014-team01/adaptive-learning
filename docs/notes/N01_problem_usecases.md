# N01 — PROBLEM BRIEF: Hệ thống AI hỗ trợ giáo viên sinh đề Toán tự luận cá nhân hóa

* **Mã tài liệu:** N01 (Problem Brief v2.0)
* **Owner:** Ngô Nhất Nghi (Project & Product Lead)
* **Reviewer:** Phạm Yến Trân (AI & Algorithms Lead)
* **Ngày cập nhật:** 19/10/2026

---

## 1. Bối cảnh & Vấn đề cốt lõi (Problem Statement)
* **Người dùng mục tiêu (Target Persona):** Giáo viên giảng dạy môn Toán cấp 3 (lớp 10).
* **Nỗi đau (Pain Point):** Để thiết kế lộ trình ôn tập cá nhân hóa, giáo viên gặp khó khăn trong việc liên tục theo dõi và tinh chỉnh độ khó/chủ đề bài tập dựa trên tiến bộ thực tế của học sinh. Việc tự biên soạn đề, giao bài, thu thập kết quả và điều chỉnh thủ công cho từng em tốn quá nhiều thời gian, dẫn đến việc dùng chung một đề cho cả lớp bất chấp năng lực khác nhau.
* **Mục tiêu hệ thống:** Xây dựng trợ lý thông minh giúp giáo viên quản lý hồ sơ học sinh và sinh đề Toán tự luận bằng mô hình ngôn ngữ cục bộ (Local Qwen). Hệ thống bắt đầu bằng cấu trúc đề mặc định và tự động tinh chỉnh cấu hình sinh đề (độ khó, chủ đề ưu tiên) thông qua việc cập nhật kết quả giải đề của học sinh sau một số lần nhất định.

---

## 2. Luồng sử dụng đầu cuối (E2E User Journey)
Hệ thống vận hành qua vòng lặp 5 bước khép kín dành cho giáo viên:
1. **Khởi tạo hệ thống (Init Profiles):** Hệ thống nạp dữ liệu hồ sơ học sinh giả lập (synthetic student profiles) đã được tạo sẵn.
2. **Cấu hình sinh đề (Blueprint Configuration):** Giáo viên có thể lựa chọn tạo đề cho học sinh cụ thể hoặc tạo đề theo lớp.
   * Nếu học sinh chưa có hoặc chưa đủ lịch sử làm bài, hệ thống áp dụng cấu trúc đề mặc định (**Default Blueprint**). 
   * Nếu đã có đủ dữ liệu từ các lần giải đề trước, hệ thống đề xuất điều chỉnh độ khó và chủ đề cần tập trung.
3. **Sinh bộ câu hỏi bằng Qwen Local:** Mô hình Qwen chạy local sinh câu hỏi tự luận mở theo đúng cấu trúc JSON schema (gồm đề bài, metadata, và tùy chọn đáp án, lời giải, rubric chấm).
4. **Kiểm định, Duyệt & Xuất đề:** Hệ thống kiểm tra tính hợp lệ của đầu ra (chặn lỗi định dạng/lỗi toán học); giáo viên xem trước, chỉnh sửa trực tiếp và xuất bộ đề hoàn chỉnh cho học sinh làm.
5. **Cập nhật Hồ sơ năng lực (Feedback Loop):** Sau khi học sinh hoàn thành bài, giáo viên nhập kết quả giải đề vào hệ thống. Hệ thống tự động cập nhật lại hồ sơ năng lực của học sinh để làm cơ sở ra đề cá nhân hóa cho chu kỳ tiếp theo.

---

## 3. Đầu vào & Đầu ra của hệ thống (Inputs & Outputs)
* **Inputs:**
  * File dữ liệu hồ sơ học sinh giả lập (Synthetic Student Profiles tạo sẵn).
  * Cấu hình yêu cầu sinh đề của giáo viên (tổng số câu, yêu cầu kèm lời giải/rubric).
  * Kết quả giải đề của học sinh (giáo viên nhập lại sau khi học sinh làm bài xong).
* **Outputs:**
  * Hồ sơ năng lực học sinh (Student Profiles) được cập nhật động theo thời gian.
  * Bộ câu hỏi Toán tự luận cá nhân hóa (kèm lời giải và rubric chấm) đã qua kiểm duyệt để giáo viên xuất file.

---

## 4. Phạm vi dự án (MVP Scope & Non-Goals)

| Trong phạm vi MVP (In Scope) | Ngoài phạm vi MVP (Out of Scope / Non-Goals) |
| :--- | :--- |
| • **Student Profiles:** Quản lý và theo dõi hồ sơ năng lực học sinh theo từng chủ đề. | • **Dashboard & Bulk Grade Import:** Bỏ qua tính năng thống kê lớp học tổng quan và tính năng upload/kiểm duyệt bảng điểm Excel/CSV hàng loạt. |
| • **Personalized Question Generation:** Sinh câu hỏi Toán tự luận mở, từ cấu trúc mặc định đến cá nhân hóa dựa trên lịch sử giải đề; cho phép xem trước, sửa và xuất. | • **Giao diện học sinh:** Không xây dựng UI, tài khoản học sinh hoặc chức năng học sinh làm bài trực tiếp trên hệ thống. |
| • **Rule Engine + Local Qwen:** Thuật toán minh bạch cập nhật hồ sơ từ kết quả giải đề; chạy Qwen local có kiểm soát chất lượng đầu ra. | • **Chấm bài tự động:** Không dùng AI để chấm câu trả lời của học sinh. Giáo viên phải tự chấm và nhập kết quả để hệ thống cập nhật hồ sơ. |
| | • **API LLM Cloud & Pre-training:** Không phụ thuộc API LLM đám mây; không huấn luyện mô hình từ đầu. |

---

## 5. Quyết định nền tảng (Decisions) vs. Giả định cần kiểm chứng (Assumptions)

### Các quyết định đã chốt (Decisions D1 – D6):
* **D1 (Người dùng):** Người dùng trực tiếp duy nhất là Giáo viên.
* **D2 (Môn học & Dạng bài):** Môn Toán; định dạng câu hỏi mở tự luận (kèm đáp án, lời giải và rubric chấm).
* **D3 (Nguồn dữ liệu):** Dùng dữ liệu hồ sơ học sinh giả lập tạo sẵn (không dùng file điểm thô quá khứ). Năng lực được phản ánh thông qua kết quả của chuỗi các lần giải đề.
* **D4 (Không chấm tự động):** Giáo viên tự đánh giá bài làm của học sinh và nhập kết quả vào hệ thống.
* **D5 (Hai tính năng cốt lõi):** Thu hẹp scope chỉ tập trung vào 2 tính năng E2E: **Student Profiles** và **Personalized Question Generation**.
* **D6 (Sinh đề động):** Bắt buộc khởi đầu bằng **Default Blueprint**. Chỉ cá nhân hóa độ khó/chủ đề khi có đủ dữ liệu từ số lần giải đề nhất định.

### Các giả định cần kiểm chứng (Assumptions to Verify):
* **A1 (Ngưỡng cập nhật năng lực):** Cần xác định cụ thể "số lần nhất định giải đề" là bao nhiêu để hệ thống quyết định tăng/giảm độ khó hoặc chuyển trọng tâm chủ đề.
* **A2 (Hiệu năng phần cứng Local Qwen):** Giả định cấu hình máy cá nhân chạy được Qwen pretrained ở mức độ trễ và bộ nhớ chấp nhận được.
* **A3 (Nhu cầu Fine-tuning LoRA/QLoRA):** MVP ưu tiên dùng Qwen pretrained làm baseline; chỉ fine-tune nếu vượt qua Feasibility Gate.

---

## 6. Tiêu chí thành công & Thước đo (Success Criteria & Metrics)
Hệ thống được đánh giá thành công khi thỏa mãn các thước đo định lượng sau:
1. **Độ chính xác toán học (Mathematical Correctness Rate):** Tỷ lệ câu hỏi sinh ra được người đánh giá xác nhận đúng toán học. Áp dụng quy tắc **Hard-Fail**: Bất kỳ bộ đề nào có lỗi toán học nghiêm trọng đều bị chặn.
2. **Điểm chất lượng bộ đề (Average Rubric Score):** Điểm trung bình theo Rubric 9 tiêu chí (thang 100 điểm) đạt **$\ge 80/100$**.
3. **Tính nhất quán cá nhân hóa (Personalization Consistency):** Hệ thống chuyển đổi mượt mà từ **Default Blueprint** (khi học sinh chưa có kết quả giải đề) sang cấu hình cá nhân hóa (khi giáo viên đã nhập đủ số bài giải).
4. **Độ tin cậy & Xử lý lỗi (Reliability & Safeguards):** Lỗi mô hình (timeout, sai định dạng JSON) phải được bắt lại, có cơ chế retry/fallback an toàn.
5. **Độ trễ sinh đề (Generation Latency):** Thời gian sinh đề nằm trong mức chấp nhận được trên cấu hình phần cứng thực tế.

---

## 7. Tiêu chí nghiệm thu Task N01 (Acceptance Criteria)
- [x] Xác định rõ persona Giáo viên, nỗi đau và luồng E2E 5 bước (cập nhật hồ sơ thông qua kết quả giải đề).
- [x] Phân định rạch ròi 2 tính năng In-Scope (Profiles, Question Gen) và các Non-Goals (Bỏ Dashboard, Bulk Import, UI học sinh).
- [x] Tách biệt rõ các quyết định đã chốt và các giả định cần kiểm chứng thực nghiệm.
- [x] Định nghĩa đầy đủ bộ chỉ số đo lường (metrics) và quy tắc Hard-Fail.
- [ ] Được **AI & Algorithms Lead** review và xác nhận tính khả thi kỹ thuật trên Pull Request.