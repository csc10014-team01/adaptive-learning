# N05. Tiêu chí Đánh giá Qwen (Evaluation Rubric & Hard-fail)

**Owner:** Lê Thị Hoài Thương (M6)

## 1. Nguyên tắc Chấm điểm & Hard-fail
*   **Điểm tuyệt đối:** 100 điểm, chia làm 9 tiêu chí.
*   **Thang điểm thành phần (0-4):** Mỗi tiêu chí được chấm từ 0 đến 4 điểm.
    *   *Công thức:* `Điểm đạt được = (Mức điểm / 4) * Trọng số`.
*   **Ngưỡng Pass (Success Metric):** Hệ thống chỉ được đánh giá thành công khi Điểm trung bình (Average Rubric Score) của các bộ đề đạt **>= 80/100 điểm**.
*   **Quy tắc Hard-fail:** Đây là "vùng cấm". Bất kỳ bộ đề nào có lỗi toán học nghiêm trọng hoặc vỡ cấu trúc sẽ bị đánh giá là **0 điểm tổng**, không cần chấm các tiêu chí khác và tự động bị loại khỏi kho đề.
*   **Cách thức chấm:** Các thành viên sẽ chấm chéo độc lập 10 câu hỏi sinh ngẫu nhiên. Chênh lệch điểm giữa 2 người không được quá 10 điểm, nếu vượt quá phải thảo luận lại.

## 2. Bảng Draft Rubric 100 Điểm (Dành cho Sinh đề Toán tự luận)

| ID | Tiêu chí đánh giá | Trọng số | Quy tắc Hard-fail (Lỗi chí mạng) |
| :--- | :--- | :--- | :--- |
| **C1** | **Độ chính xác Toán học (Math Accuracy)** | 25 | **[YES]** Lời giải sai bản chất, áp dụng sai công thức, kết quả cuối cùng tính toán sai. |
| **C2** | **Cấu trúc dữ liệu hợp lệ (JSON Integrity)** | 15 | **[YES]** Chuỗi trả về không thể parse thành JSON, thiếu các key bắt buộc (question, solution). |
| **C3** | **Sự phù hợp Topic (Topic Alignment)** | 10 | **[YES]** Bài toán sử dụng kiến thức nằm ngoài chương trình Toán 10 (Đại số tổ hợp). |
| **C4** | **Phản ánh đúng độ khó (Difficulty Match)** | 10 | Không |
| **C5** | **Tính logic của bẫy tư duy (Trap Logic)** | 10 | Không |
| **C6** | **Chất lượng dẫn dắt (Scaffolding Quality)** | 10 | Không |
| **C7** | **Độ tự nhiên của Ngôn ngữ (Natural Language)** | 10 | Không |
| **C8** | **Định dạng hiển thị (LaTeX Rendering)** | 5 | Không |
| **C9** | **Tính độc đáo của ngữ cảnh (Originality)** | 5 | Không |
| **TỔNG** | | **100** | |

## 3. Định nghĩa Thang điểm (0-4) cho từng Tiêu chí

### C1: Độ chính xác Toán học (25 điểm) - Có Hard-fail
*   **0 (Hard-fail):** Sai bản chất, sai công thức, hoặc sai đáp án.
*   **1:** Đúng hướng giải, nhưng sai sót tính toán số học ở nhiều bước.
*   **2:** Lời giải đúng, kết quả đúng, nhưng thiếu điều kiện ràng buộc của biến số.
*   **3:** Lời giải hoàn toàn đúng, đủ điều kiện, chỉ dư thừa một vài bước không cần thiết.
*   **4:** Lời giải hoàn hảo, tối ưu, kết quả chính xác 100%.

### C2: Cấu trúc dữ liệu hợp lệ (15 điểm) - Có Hard-fail
*   **0 (Hard-fail):** Format hoàn toàn hỏng, vỡ cấu trúc JSON, không thể parse.
*   **1:** Có cấu trúc JSON nhưng thiếu ít nhất 1 trường dữ liệu cốt lõi do backend quy định.
*   **2:** JSON hợp lệ, nhưng bị chèn lẫn văn bản hội thoại thừa của AI (vd: "Sure, here is your output:").
*   **3:** JSON hợp lệ, đúng cấu trúc, nhưng có chứa ký tự escape (`\n`, `\t`) bị lỗi định dạng.
*   **4:** JSON hoàn hảo, parse thành công ngay lập tức không qua xử lý trung gian.

### C3: Sự phù hợp Topic (10 điểm) - Có Hard-fail
*   **0 (Hard-fail):** Đưa kiến thức Giải tích, Hình học không không gian vào bài toán.
*   **1:** Dùng kiến thức Toán 10 nhưng sai chủ đề (vd: Yêu cầu Tổ hợp nhưng sinh bài Phương trình).
*   **2:** Bài toán có 20% - 30% kiến thức lạc đề, nhưng phần chính vẫn là Tổ hợp.
*   **3:** Bài toán tập trung vào Tổ hợp, nhưng ngôn từ dùng sai thuật ngữ chuẩn.
*   **4:** Bám sát 100% phạm vi Tổ hợp - Quy tắc đếm của Toán 10.

### C4: Phản ánh đúng độ khó (10 điểm)
*   **0:** Lệch hoàn toàn (yêu cầu khó mức 6 nhưng sinh bài cơ bản mức 1).
*   **1:** Lệch đáng kể (cách biệt 2-3 mức độ).
*   **2:** Có sự phân hóa nhưng vẫn chưa khớp hoàn toàn với định nghĩa mức khó.
*   **3:** Phản ánh tốt độ khó, chỉ hơi chênh lệch nhẹ ở cách đặt câu hỏi.
*   **4:** Mức độ tư duy và số lượng bước giải khớp hoàn toàn với thang năng lực.

### C5: Tính logic của bẫy tư duy (10 điểm)
*   *Lưu ý: Chỉ chấm khi yêu cầu `has_trap = true`.*
*   **0:** Bẫy phi logic, đánh đố học sinh bằng câu chữ mập mờ thay vì tư duy toán học.
*   **1:** Bẫy quá lộ liễu, học sinh yếu nhất cũng không bao giờ sai.
*   **2:** Bẫy dựa trên một lỗi sai cơ bản, nhưng giải thích trong lời giải chưa làm bật được.
*   **3:** Gài bẫy đúng những lỗi thường gặp, nhưng ngữ cảnh hơi gượng ép.
*   **4:** Bẫy rất tinh tế, phản ánh chính xác ngộ nhận kinh điển, ngữ cảnh rất tự nhiên.

### C6: Chất lượng dẫn dắt (10 điểm)
*   **0:** Không có lời giải chi tiết, chỉ đưa ra đáp số cuối cùng.
*   **1:** Lời giải nhảy cóc quá nhiều bước, học sinh trung bình không thể hiểu.
*   **2:** Lời giải đầy đủ bước nhưng viết dưới dạng công thức khô khan.
*   **3:** Giải thích rõ các bước, nhưng chưa giải thích "Tại sao" lại chọn cách làm đó.
*   **4:** Lời giải step-by-step xuất sắc, giải thích cặn kẽ tại sao dùng công thức này.

### C7: Độ tự nhiên của Ngôn ngữ (10 điểm)
*   **0:** Dịch máy ngô nghê, sai cấu trúc ngữ pháp tiếng Việt nghiêm trọng.
*   **1:** Văn phong lủng củng, lặp từ nhiều, đọc khó hiểu ngữ cảnh bài toán.
*   **2:** Ngôn từ hiểu được, nhưng dùng từ lóng hoặc từ ngữ không phù hợp.
*   **3:** Văn phong tự nhiên, lưu loát, chỉ sai 1-2 lỗi chính tả nhỏ.
*   **4:** Ngôn ngữ trong sáng, chuẩn mực, giống hệt đề kiểm tra của giáo viên.

### C8: Định dạng hiển thị LaTeX (5 điểm)
*   **0:** Hoàn toàn không bọc công thức Toán học bằng dấu `$` hoặc `$$`.
*   **1:** Có dùng LaTeX nhưng sai cú pháp nghiêm trọng khiến thư viện hiển thị bị crash.
*   **2:** Công thức bị tràn dòng, thiếu dấu ngoặc `{}` khiến hiển thị bị méo mó.
*   **3:** Hiển thị tốt 90%, thỉnh thoảng lỗi khoảng trắng hoặc thiếu in nghiêng tên biến.
*   **4:** Mã LaTeX chuẩn xác, render hoàn hảo trên UI.

### C9: Tính độc đáo của ngữ cảnh (5 điểm)
*   **0:** Copy y nguyên (100%) bài toán trong sách giáo khoa, chỉ đổi số.
*   **1:** Thay đổi một vài từ vựng, ngữ cảnh vẫn là những bài cũ rích (chia kẹo, xếp bi).
*   **2:** Ngữ cảnh có thay đổi nhưng chưa phong phú.
*   **3:** Ngữ cảnh gắn với thực tế (thể thao, công nghệ, sắp xếp lịch trình).
*   **4:** Ngữ cảnh hoàn toàn mới mẻ, hiện đại, sáng tạo nhưng vẫn chặt chẽ Toán học.