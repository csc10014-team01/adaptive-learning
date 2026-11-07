# W06 - UI and API Mapping Document

## I. BẢNG MAPPING GIAO DIỆN UI – API

| Màn hình / Component | Dữ liệu hiển thị / Tương tác | Endpoint API dự kiến | Method | Trạng thái đối chiếu |
| :--- | :--- | :--- | :--- | :--- |
| **Màn hình Hồ sơ học sinh** | Thông tin học sinh (`student_id`, Tên, Lớp) | `/api/v1/students/{student_id}` | `GET` | Đã có API |
| **Bảng Kỹ năng** | Chỉ số `mastery` (Độ thông thạo) | `/api/v1/students/{student_id}/skills` | `GET` | Cần thống nhất format |
| **Bảng Kỹ năng** | Dữ liệu `evidence` (Minh chứng bài tập) | `/api/v1/students/{student_id}/skills` | `GET` | Cần thống nhất format |
| **Bảng Kỹ năng** | Nội dung `khuyến nghị` theo kỹ năng | `/api/v1/students/{student_id}/skills` | `GET` | Cần thống nhất format |
| **Nút "Xem kế hoạch"** | Chuyển/Mở danh sách lộ trình học tập | `/api/v1/planner/{student_id}` | `GET` | Đã có API planner |
| **Nút "Cấu hình sinh đề"** | Chuyển màn hình & giữ đúng `student_id` | *(Chuyển state trên Frontend)* | - | Code UI tự quản lý State |
| **Form Cấu hình sinh đề** | Chọn Chế độ 1 / Chế độ 2 | `/api/v1/generate-exam` | `POST` | Cần check payload |
| **Form Cấu hình sinh đề** | Ô nhập: Số câu, Thời lượng, Mức độ (Dễ/TB/Khó) | `/api/v1/generate-exam` | `POST` | Validate input tại Frontend (>0) |
| **Nút "Sinh đề"** | Gửi request sinh đề & nhận file/kết quả đề | `/api/v1/generate-exam` | `POST` | Xử lý Loading / Retry |

---

## II. QUY TẮC HIỂN THỊ CẦN THỐNG NHẤT (UI Display Rules)

1. **Quy tắc hiển thị `mastery` (Độ thông thạo):**
   * **Thiết kế UI:** Hiển thị dạng % (ví dụ: 85%) hoặc màu sắc thanh tiến trình (Progress bar).
   * **Dữ liệu API:** Cần trả về giá trị chuẩn dạng số nguyên (85) kèm theo mức đánh giá.

2. **Quy tắc hiển thị `evidence` (Minh chứng):**
   * **Thiết kế UI:** Hiển thị danh sách các bài làm/bài kiểm tra gần nhất liên quan đến kỹ năng.
   * **Dữ liệu API:** Cần thống nhất dạng cấu trúc Mảng danh sách bài làm `[{ "exam_id": "...", "score": 9, "date": "..." }]`.

3. **Quy tắc hiển thị `khuyến nghị`:**
   * **Thiết kế UI:** Thẻ gợi ý (Card) hiển thị bài học hoặc kỹ năng học sinh cần cải thiện.
   * **Dữ liệu API:** Trả về danh sách chuỗi văn bản gợi ý theo từng kỹ năng cụ thể.

---

## III. DANH SÁCH CHECKLIST DỮ LIỆU THIẾU / CẦN PHẢN HỒI (Hạn T5)

- [ ] **Khớp nối Payload Sinh đề:** Cấu trúc JSON gửi lên từ 2 chế độ sinh đề đã có đủ các trường `question_count`, `duration`, `difficulty_distribution` chưa.
- [ ] **Thiếu trường dữ liệu:** Đối chiếu các nhãn/ô hiển thị trên Figma xem Response API hiện tại đã có đủ thông tin chưa.
- [ ] **Mã lỗi (Error Codes):** Khi API Sinh đề gặp lỗi (500/400), backend cần trả về thông báo lỗi chi tiết để giao diện giữ nguyên thông số form cho người dùng chọn "Thử lại".
- [ ] **Phân quyền (Permissions):** Xử lý hiển thị thông báo hợp lý khi tài khoản không có quyền truy cập thông tin học sinh.