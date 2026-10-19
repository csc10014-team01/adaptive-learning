# Danh mục Rủi ro & Cơ chế Dự phòng (Failure Catalogue)

**Owner:** Lê Thị Hoài Thương (QA, Evaluation & Documentation Lead)

## 1. Định nghĩa Thang đánh giá
*   **Likelihood (Xác suất xảy ra):** Low (Ít khi), Medium (Thỉnh thoảng), High (Thường xuyên).
*   **Impact (Mức độ ảnh hưởng):** Low (Không đáng kể), Medium (Ảnh hưởng một phần tính năng), High (Sập luồng chính, sai lệch dữ liệu).
*   **Severity/Priority:**
    *   **P1 (Critical):** High Likelihood + High Impact (Phải ưu tiên xử lý ngay, ngăn chặn lỗi lan rộng).
    *   **P2 (Major):** Medium Likelihood + High Impact hoặc High Likelihood + Medium Impact.
    *   **P3 (Minor):** Các trường hợp còn lại.

## 2. Bảng Quản lý Rủi ro (Risk Register)

| Risk ID | Layer | Risk Name | Description | Trigger / Root Cause | Likelihood | Impact | Severity / Priority | Detection Method | Prevention / Mitigation | Fallback / Recovery | Test Case ID | Owner |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **RSK-DATA-01** | Data | Lỗi thiếu `studentId` hoặc Profile rỗng | Giáo viên yêu cầu sinh đề cá nhân hóa nhưng không truyền `studentId` hoặc học sinh chưa có điểm/kỹ năng trong DB. | Giao diện UI lỗi không block nút Submit khi bỏ trống form, hoặc học sinh mới tạo chưa làm bài nào. | Medium | High | **P2** | Validation tại tầng `Student Profile Service` ném lỗi 400 Bad Request. | Bắt buộc chọn học sinh trên UI. Gán skillMastery mặc định = 0 khi tạo mới. | Tự động chuyển sang cấu hình Default Blueprint (không cá nhân hóa). | TS-A1 | M5 |
| **RSK-DATA-02** | Data | Dữ liệu `difficulty` không hợp lệ | Tham số độ khó bị truyền vào ngoài khoảng 1-6 (ví dụ: chuỗi text "Khó", hoặc số 0, 7). | Lỗi ép kiểu dữ liệu từ giao diện gửi xuống API. | Low | Medium | **P3** | API schema validation (zod/pydantic) bắt lỗi type mismatch. | Đảm bảo input form trên UI dùng dropdown list thay vì text input. | API trả về 422 Unprocessable Entity, UI báo lỗi yêu cầu nhập lại. | TS-D1 | M5 |
| **RSK-MODEL-01** | Model | Qwen sinh sai Toán (Hallucination) | Local Qwen sinh ra lời giải sai bản chất toán học, áp dụng sai quy tắc đếm/tổ hợp. | Mô hình nội suy sai do prompt thiếu ngữ cảnh hoặc mô hình tự bịa kiến thức (hallucination). | High | High | **P1 (Critical)** | `Question Validator` chạy độc lập giải lại bài toán bằng sandbox, đối chiếu kết quả. | Áp dụng **RAG Pattern**: Cung cấp sẵn lý thuyết SGK vào prompt để giới hạn ảo giác. | Kích hoạt vòng lặp **Critic/Self-Correction**: Yêu cầu Qwen sửa lại lỗi. Nếu vẫn thất bại -> Hủy. | TS-F1 | M4 |
| **RSK-MODEL-02** | Model | Lệch chủ đề (Topic mismatch) | Sinh bài tập ngoài phạm vi Toán 10 (VD: dính tích phân, lượng giác). | LLM bị "trôi" ngữ cảnh khi cố gắng tăng độ khó quá mức. | Medium | High | **P2** | Check từ khóa bằng Regex tại `Question Validator` (chứa "sin", "cos", "tích phân" -> fail). | Dùng **Chain-of-Thought (CoT)**, ép Qwen phải khẳng định: "Đây là bài Tổ hợp lớp 10" trước khi giải. | Hủy kết quả, loại khỏi danh sách hiển thị cho Giáo viên. | TS-B1 | M4 |
| **RSK-SYS-01** | System | Sai cấu trúc JSON | Qwen trả về kết quả bị cụt, thiếu dấu ngoặc `}`, hoặc chèn text rác ngoài JSON. | Lỗi phổ biến của LLM; hoặc do độ dài token sinh ra vượt quá `max_new_tokens` cho phép. | High | High | **P1 (Critical)** | JSON.parse() ném ra exception (lỗi cú pháp). | Sử dụng **Structured Output Pattern** (ép LLM sinh đúng schema json). | Dùng thuật toán sửa lỗi JSON tự động hoặc Regex trích xuất phần `{}`. Nếu thất bại, retry API 1 lần. | TS-E1 | M5 |
| **RSK-SYS-02** | System | Timeout mô hình cục bộ | Yêu cầu sinh đề bị treo, không phản hồi vượt quá Generation Latency cho phép. | Máy chủ chạy Local Qwen bị quá tải VRAM hoặc nghẽn hàng đợi (Queue) do có quá nhiều request sinh đề cùng lúc. | Medium | High | **P2** | Đặt giới hạn thời gian (Timeout) ở Gateway API. | Xây dựng hàng đợi bất đồng bộ (Message Queue / Redis) để xử lý tuần tự. | Cắt kết nối hiện tại, gửi thông báo "Hệ thống đang bận" xuống giao diện để giáo viên thử lại sau. | TS-C1 | M5 |