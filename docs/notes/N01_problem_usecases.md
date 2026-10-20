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