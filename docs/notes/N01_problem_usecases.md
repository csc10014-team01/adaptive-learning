# Problem Brief: Hệ thống AI hỗ trợ giáo viên sinh đề Toán tự luận cá nhân hóa

* **Mã tài liệu:** N01 (Problem Brief v1.1 & Use Cases)
* **Owner:** Ngô Nhất Nghi (Project & Product Lead), Trần Lộc Chi Mai (UX & Requirements Lead)
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


# Use Cases: Luồng Hồ Sơ Năng Lực Học Sinh & Sinh Đề Toán Tự Luận

Hệ thống hỗ trợ Giáo viên theo dõi hồ sơ năng lực học sinh và sinh đề kiểm tra/ôn tập thích ứng dạng Toán tự luận dựa trên dữ liệu đánh giá quá khứ hoặc cấu trúc đề chuẩn.

---

### UC01: Xem tổng quan hồ sơ năng lực học sinh (Đầy đủ dữ liệu - Happy Path)
- **Actor:** Giáo viên.
- **Pre-condition:** Học sinh đã hoàn thành đủ số lượng bài kiểm tra yêu cầu (`data_status = "sufficient"`).
- **Main Flow:**
  1. Giáo viên truy cập danh sách lớp và chọn một học sinh cụ thể.
  2. Hệ thống tải thông tin học sinh và hiển thị nhãn trạng thái `sufficient` (màu xanh lục).
  3. Hệ thống trực quan hóa điểm thành phần theo từng chủ đề Toán (Đại số, Hình học, Lượng giác...) qua biểu đồ radar/cột.
  4. Hệ thống gợi ý danh sách các dạng bài học sinh còn yếu cần ôn tập.
  5. Giáo viên xem chi tiết phân tích và bấm "Tạo đề thích ứng".
- **Post-condition:** Chuyển sang màn hình cấu hình sinh đề với các tham số gợi ý sẵn từ hồ sơ học sinh.

---

### UC02: Xem hồ sơ học sinh có dữ liệu không đầy đủ (Partial Data)
- **Actor:** Giáo viên.
- **Pre-condition:** Học sinh mới làm 1–2 bài test ngắn, dữ liệu chưa đủ để suy luận toàn diện (`data_status = "partial"`).
- **Main Flow:**
  1. Giáo viên mở trang hồ sơ của học sinh.
  2. Hệ thống hiển thị nhãn `partial` (màu vàng cam) kèm chú thích: "Dữ liệu hạn chế, một số chỉ số mang tính ước tính".
  3. Hệ thống hiển thị điểm cho các chủ đề đã có dữ liệu, các chủ đề chưa có bài làm được đánh dấu "Chưa đánh giá".
  4. Hệ thống đề xuất dùng khung cấu trúc đề chuẩn kết hợp ưu tiên các chủ đề đã ghi nhận điểm thấp.
- **Post-condition:** Giáo viên nắm được mức độ tin cậy của dữ liệu trước khi cấu hình bài kiểm tra.

---

### UC03: Xem hồ sơ học sinh mới chưa có dữ liệu (No Data)
- **Actor:** Giáo viên.
- **Pre-condition:** Học sinh mới tạo tài khoản hoặc chưa làm bài kiểm tra nào (`data_status = "no_data"`).
- **Main Flow:**
  1. Giáo viên mở trang hồ sơ của học sinh.
  2. Hệ thống hiển thị nhãn `no_data` (màu xám) và thông báo: "Chưa có dữ liệu bài làm. Hệ thống sẽ áp dụng ma trận đề chuẩn mặc định (Default Blueprint)".
  3. Biểu đồ năng lực được thay thế bằng màn hình placeholder hướng dẫn giáo viên tạo đề kiểm tra đầu vào (Diagnostic Test).
- **Post-condition:** Nút bấm chính trên giao diện chuyển thành "Tạo đề chẩn đoán ban đầu".

---

### UC04: Lọc và phân tích lịch sử làm bài theo mốc thời gian
- **Actor:** Giáo viên.
- **Pre-condition:** Giáo viên đang ở màn hình hồ sơ học sinh.
- **Main Flow:**
  1. Giáo viên chọn khoảng thời gian cần lọc (7 ngày qua, 30 ngày qua, Học kỳ 1, hoặc Tùy chọn).
  2. Hệ thống lọc lại dữ liệu bài nộp và cập nhật lại biểu đồ năng lực theo mốc thời gian tương ứng.
  3. Giáo viên theo dõi đường xu hướng tiến bộ/sa sút của học sinh qua từng tuần.
- **Alternative Flow:** Nếu trong khoảng thời gian chọn không có bài nộp nào, hệ thống hiển thị thông báo "Không có bài làm trong khoảng thời gian này" và giữ nguyên trạng thái tổng quan gần nhất.

---

### UC05: Cấu hình sinh đề thích ứng tự động từ hồ sơ đủ dữ liệu
- **Actor:** Giáo viên.
- **Pre-condition:** Bắt đầu từ UC01 (`data_status = "sufficient"`).
- **Main Flow:**
  1. Hệ thống tự động điền cấu hình đề:
     - Tập trung vào các chủ đề có điểm năng lực dưới 65%.
     - Tỷ lệ độ khó phân bổ tự động: 30% Nhận biết, 40% Thông hiểu, 30% Vận dụng/Vận dụng cao.
  2. Giáo viên chọn số lượng câu hỏi tự luận (ví dụ: 3–5 câu) và thời lượng dự kiến (ví dụ: 45 phút).
  3. Giáo viên bấm "Bắt đầu sinh đề".
  4. Hệ thống gửi yêu cầu sang backend và hiển thị trạng thái chờ sinh đề.
- **Post-condition:** Yêu cầu được gửi sang pipeline sinh đề Toán tự luận của backend.

---

### UC06: Cấu hình sinh đề bằng Default Blueprint khi thiếu hoặc không có dữ liệu
- **Actor:** Giáo viên.
- **Pre-condition:** Bắt đầu từ UC02 hoặc UC03 (`data_status` là `partial` hoặc `no_data`).
- **Main Flow:**
  1. Hệ thống khóa tùy chọn "Tự động phân bổ theo năng lực" và kích hoạt chế độ "Default Blueprint".
  2. Hệ thống nạp ma trận đề chuẩn theo chương trình môn học (tỷ lệ chuẩn: 40% Nhận biết, 30% Thông hiểu, 20% Vận dụng, 10% Vận dụng cao).
  3. Giáo viên có thể tự tích chọn danh sách chủ đề cần kiểm tra thủ công.
  4. Giáo viên bấm "Bắt đầu sinh đề".
- **Post-condition:** Đề được sinh theo ma trận chuẩn mà không phụ thuộc vào hồ sơ học sinh.

---

### UC07: Tùy chỉnh tham số nâng cao cho đề kiểm tra
- **Actor:** Giáo viên.
- **Pre-condition:** Đang ở màn hình cấu hình sinh đề (UC05 hoặc UC06).
- **Main Flow:**
  1. Giáo viên mở rộng mục "Tùy chọn nâng cao".
  2. Giáo viên điều chỉnh:
     - Phong cách ngữ cảnh câu hỏi (toán thuần túy, toán liên hệ thực tế đời sống, toán kinh tế/vật lý).
     - Định dạng xuất (kèm lời giải từng bước, kèm barem chi tiết theo từng 0.25 điểm).
     - Ngôn ngữ biểu diễn công thức (LaTeX/KaTeX).
  3. Giáo viên xác nhận lưu cấu hình nâng cao.
- **Post-condition:** Tham số cấu hình nâng cao được đính kèm vào payload gửi đến backend.

---

### UC08: Xem trước nội dung đề thi, đáp án chi tiết và rubric chấm điểm
- **Actor:** Giáo viên.
- **Pre-condition:** Backend sinh đề thành công.
- **Main Flow:**
  1. Hệ thống chuyển sang màn hình Preview hiển thị đề thi dạng Toán tự luận gồm:
     - Danh sách câu hỏi tự luận kèm công thức toán hiển thị trực quan (LaTeX render).
     - Lời giải mẫu chi tiết từng bước.
     - Bảng Rubric chấm điểm: tiêu chí chia điểm nhỏ cho từng bước biến đổi/kết quả.
  2. Giáo viên kiểm tra tính chính xác của đề bài và barem điểm.
- **Post-condition:** Giáo viên xác nhận đề bài đạt tiêu chuẩn hoặc lựa chọn chỉnh sửa tiếp.

---

### UC09: Tái tạo hoặc chỉnh sửa thủ công từng câu hỏi tự luận
- **Actor:** Giáo viên.
- **Pre-condition:** Giáo viên đang xem màn hình Preview (UC08).
- **Sub-flow A (Tái tạo bằng AI):**
  1. Giáo viên bấm nút "Tạo lại câu này" tại một câu hỏi cụ thể kèm lý do (ví dụ: "Cho số liệu đẹp hơn", "Tăng độ khó phần kết luận").
  2. Hệ thống gọi API sinh lại riêng câu hỏi đó cùng lời giải và rubric tương ứng.
- **Sub-flow B (Sửa thủ công):**
  1. Giáo viên bấm "Chỉnh sửa trực tiếp" tại câu hỏi.
  2. Giáo viên gõ lại đề bài hoặc sửa lại phân bổ điểm trong rubric.
  3. Giáo viên bấm "Lưu chỉnh sửa".
- **Post-condition:** Câu hỏi và rubric được cập nhật lại trên màn hình Preview.

---

### UC10: Phê duyệt và giao bài cho học sinh
- **Actor:** Giáo viên.
- **Pre-condition:** Giáo viên đã ưng ý với nội dung xem trước ở UC08 hoặc UC09.
- **Main Flow:**
  1. Giáo viên chọn hạn nộp bài và thời gian mở đề.
  2. Giáo viên bấm "Lưu & Phân công cho học sinh".
  3. Hệ thống tạo mã đề, ghi nhận trạng thái đề thi là `published` và gửi thông báo vào danh sách bài tập của học sinh.
  4. Hệ thống chuyển hướng giáo viên về trang quản lý bài tập.
- **Post-condition:** Đề thi được kích hoạt thành công trên hệ thống.

---

### UC11: Xử lý ngoại lệ khi tiến trình sinh đề gặp lỗi hoặc quá thời gian (Generation Failure / Timeout)
- **Actor:** Giáo viên.
- **Pre-condition:** Giáo viên bấm "Bắt đầu sinh đề", nhưng mô hình backend quá tải hoặc mất kết nối mạng.
- **Main Flow:**
  1. Sau khoảng thời gian chờ (timeout) hoặc khi backend trả mã lỗi (500 / 504), hệ thống ngắt trạng thái loading.
  2. Màn hình hiển thị thông báo lỗi rõ ràng: "Không thể sinh đề thi lúc này do hệ thống phản hồi chậm. Toàn bộ tùy chọn của bạn đã được lưu lại."
  3. Hệ thống giữ nguyên toàn bộ form cấu hình mà giáo viên vừa thiết lập (không bị reset dữ liệu).
  4. Nút hành động chính chuyển thành "Thử lại" (Retry).
  5. Giáo viên bấm "Thử lại" để gửi lại request với cùng tham số.
- **Post-condition:** Hệ thống khôi phục tiến trình mà không làm mất thời gian nhập lại cấu hình của giáo viên.
