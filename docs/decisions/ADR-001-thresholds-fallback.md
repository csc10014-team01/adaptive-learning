# ADR-001: Định lượng ngưỡng phân loại năng lực và cơ chế Rẽ nhánh / Fallback

- **Trạng thái:** Chấp thuận
- **Ngày quyết định:** 19/10/2026
- **Người ra quyết định:** Nhất Nghi (Project Lead)
- **Tham vấn:** Yến Trân (AI Lead), Ánh Dương (Data Lead)

## 1. Bối cảnh và Vấn đề (Context & Problem)
Trong Chặng 1 của MVP hệ thống Sinh đề Toán tự luận, chúng ta cần một cơ sở logic minh bạch để quyết định khi nào hệ thống nên cá nhân hóa đề thi (Personalized Blueprint) và khi nào nên dùng khung chuẩn (Default Blueprint). 

Nếu ép mô hình AI cá nhân hóa khi dữ liệu học sinh quá ít, hệ thống sẽ rơi vào trạng thái "Overfitting" (đánh giá sai lệch năng lực, ví dụ: học sinh làm sai 1 câu khó do bất cẩn nhưng hệ thống đánh giá là yếu toàn diện). Do đó, nhóm cần chốt một bộ quy tắc định lượng cứng để phân loại hồ sơ học sinh và các cơ chế phòng vệ (fallback) khi hệ thống gặp lỗi.

## 2. Quyết định (Decision)

### 2.1. Tiêu chí phân loại (Classification Thresholds)
Chúng ta thống nhất sử dụng biến **`evidence_count`** (số lượng câu hỏi đã được giáo viên đánh giá trong một chủ đề) làm thước đo duy nhất để phân loại trạng thái học sinh. Phân loại thành 3 nhóm:

1. **`no_data` (Thiếu dữ liệu hoàn toàn): `evidence_count == 0`**
   - **Tình trạng:** Học sinh chưa từng làm bài hoặc lớp chưa kiểm tra chủ đề này.
   - **Quyết định rẽ nhánh:** Bắt buộc áp dụng **Default Blueprint**.

2. **`partial` (Dữ liệu một phần / Chưa đủ tin cậy): `evidence_count == 1`**
   - **Tình trạng:** Học sinh có lịch sử làm bài nhưng chưa đủ để hình thành xu hướng năng lực rõ ràng. 
   - **Quyết định rẽ nhánh:** Bắt buộc áp dụng **Default Blueprint**.

3. **`sufficient` (Đủ dữ liệu đánh giá): `evidence_count >= 2`**
   - **Tình trạng:** Dữ liệu đủ lớn để tính toán `mastery_score` (điểm thành thạo) một cách chính xác.
   - **Quyết định rẽ nhánh:** Kích hoạt **Personalized Blueprint** (Tự động điều chỉnh tỷ lệ câu Dễ/Khó và trọng tâm kiến thức dựa theo `mastery_score`).

### 2.2. Cơ chế phòng vệ (Fallback Mechanism)
Để đảm bảo API luôn trả về kết quả (không làm sập UI của Giáo viên), hệ thống áp dụng cơ chế Fallback (tự động lùi về phương án an toàn nhất là Default Blueprint) trong các trường hợp ngoại lệ sau:
- **Lỗi dữ liệu (Data Missing):** Nếu JSON hồ sơ học sinh gửi lên bị khuyết trường `evidence_count` hoặc `mastery_score` không hợp lệ (null/NaN).
- **Lỗi AI Timeout:** Nếu Qwen Local phản hồi quá thời gian quy định (Timeout).
- **Lỗi định dạng JSON (JSON Parse Error):** Nếu Qwen trả về kết quả bị cắt cụt, sai Schema, hoặc không qua được vòng kiểm tra Toán học của Output Validator.

## 3. Hệ quả và Tác động (Consequences)

Quyết định này "khóa" logic của hệ thống trong MVP 1 và ảnh hưởng trực tiếp đến task của các thành viên:
- **M3 (Data):** Chỉ cần tạo dữ liệu tĩnh mô phỏng đúng 3 mốc `evidence_count` (0, 1, và >=2) mà không cần xây dựng công thức tính toán Time-decay phức tạp.
- **M4 (AI):** Cập nhật lại Pseudocode. Xóa bỏ các nhánh logic chưa rõ ràng (TBD), chỉ sử dụng vòng lặp `if/else` đơn giản dựa trên `evidence_count`.
- **M2 (UI):** Khóa tùy chọn sinh đề "Thích ứng" trên giao diện nếu dữ liệu trả về thuộc nhóm `no_data` hoặc `partial`.
- **M6 (QA):** Dựa vào đúng các ngưỡng (0, 1, 2) để viết các test case (Test Situations) kiểm thử rẽ nhánh.