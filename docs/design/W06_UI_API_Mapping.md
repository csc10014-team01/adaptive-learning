# W06 - UI and API Mapping Document

Phạm vi: luồng **Hồ sơ học sinh → Cấu hình sinh đề** (Figma Frame 3 và Frame 1), chế độ **Thích ứng theo lỗ hổng kiến thức**. Chế độ "Sử dụng khung chuẩn" và màn "Xem lại đề" (Frame 2) chưa nằm trong phạm vi.

Nguồn đối chiếu: `src/api/schemas.py`, `README.md`, và response thực tế của backend (chạy `python -m src.ui --fake`). Mọi endpoint đều yêu cầu header `Authorization: Bearer <teacher_token>`.

---

## I. BẢNG MAPPING GIAO DIỆN UI – API

### 1. Màn Hồ sơ học sinh (Frame 3)

Khi vào màn, UI gọi song song 3 endpoint: `profile`, `topics`, `plan`.

| Thông tin trên UI | Endpoint | Field | Cách hiển thị |
| :--- | :--- | :--- | :--- |
| Tên học sinh, Lớp | `GET /api/v1/students/{student_id}/profile` | `name`, `grade_level` | "Lớp 10" (API chỉ trả số, không có "10A") |
| Số bài kiểm tra đã làm | `GET .../profile` | `learning_history` | Độ dài mảng, hiển thị "N bài" |
| Tên kỹ năng | `GET /api/v1/topics` | `items[].skills[].{skill_id, name}` | Đổi mã `A001…` thành tên tiếng Việt |
| % mastery mỗi kỹ năng | `GET .../profile` | `skill_mastery[].mastery_score` | Thang **0–4**, hiển thị `score / 4 × 100`, làm tròn |
| Số câu đã làm mỗi kỹ năng | `GET .../profile` | `skill_mastery[].evidence_count` | "N câu đã làm" |
| Phân loại kỹ năng | `POST /api/v1/exams/plan` | `skill_classifications` | `NO_DATA`, `PARTIAL`, `WEAK`, `ACHIEVED` (xem mục II) |
| Nhãn "Dữ liệu hồ sơ" | `POST .../plan` | suy ra từ `skill_classifications` | UI tự suy ra (xem mục II) |
| Kỹ năng đủ dữ liệu (x/y) | `POST .../plan` | `skill_classifications` | Đếm kỹ năng `WEAK` hoặc `ACHIEVED` trên tổng kỹ năng |
| Khối "Cần cải thiện" | `POST .../plan` | `skill_classifications` | Liệt kê kỹ năng `WEAK` |
| Khối "Khuyến nghị ôn tập" | `POST .../plan` | `strategy`, `quota_summary.requested_groups` | UI ghép câu theo mẫu cố định (API không trả văn bản khuyến nghị) |
| Nút "Tạo đề ôn tập thích ứng" | (điều hướng) | – | Chuyển sang `#/students/{id}/generate`, giữ nguyên `student_id` |

Request `plan` dùng cho màn này: `generation_mode: "adaptive"`, `selected_topic_ids: ["combinatorics"]`, `total_questions: 4`, `duration_minutes: 45`, `difficulty_distribution: null`.

### 2. Màn Cấu hình sinh đề (Frame 1)

| Thông tin trên UI | Endpoint | Field | Ghi chú |
| :--- | :--- | :--- | :--- |
| Học sinh, Lớp | `GET .../profile` | `name`, `grade_level` | Lấy theo `student_id` trên URL |
| Chế độ sinh đề | `POST .../plan`, `POST /api/v1/exams/generate` | `generation_mode` | Chỉ `"adaptive"` hoạt động. Thẻ khung chuẩn bị khóa, nhãn "Sắp có" |
| Số câu hỏi | cả hai | `total_questions` | Số nguyên **1–10** |
| Thời gian làm bài | cả hai | `duration_minutes` | Số nguyên **1–180** |
| Phân bố mức độ | `POST .../plan` | `quota_summary.requested_levels` | **Chỉ đọc.** Giá trị là **số câu** mỗi mức (không phải %), UI tự tính % = số câu / tổng. Request gửi `difficulty_distribution: null` để planner tự phân bổ |
| Chiến lược / Trọng tâm ôn tập | `POST .../plan` | `strategy`, `skill_classifications`, `quota_summary` | Cập nhật lại khi đổi số câu |
| Cảnh báo | `POST .../plan` | `warnings` | Hiển thị nếu không rỗng |
| Hình thức (Tự luận) | – | không có field | Hằng số "Tự luận" ở UI |
| Nút "Bắt đầu tạo đề" | `POST /api/v1/exams/generate` | body `GenerateExamRequest` | Xử lý loading, lỗi, thử lại (mục III) |

Body `POST /api/v1/exams/generate`:

```json
{
  "student_id": "ST001",
  "generation_mode": "adaptive",
  "selected_topic_ids": ["combinatorics"],
  "total_questions": 4,
  "duration_minutes": 45,
  "difficulty_distribution": null
}
```

### 3. Mã lỗi backend và cách UI xử lý

| HTTP | Mã lỗi | Ý nghĩa | UI |
| :--- | :--- | :--- | :--- |
| 401 | `TEACHER_AUTH_REQUIRED` | Thiếu token | Màn "Không có quyền truy cập" |
| 403 | `TEACHER_ACCESS_DENIED` | Token sai | Màn "Không có quyền truy cập" |
| 503 | `TEACHER_ACCESS_NOT_CONFIGURED` | Server chưa cấu hình token | Màn "Không có quyền truy cập" |
| 404 | `STUDENT_NOT_FOUND` | Không có học sinh | Màn lỗi, nút "Thử lại" |
| 409 | `INSUFFICIENT_QUESTION_BANK` | Ngân hàng câu không đủ | Thông báo lỗi, **giữ nguyên form** |
| 409 | `ADAPTIVE_NOT_ALLOWED` | Hồ sơ không đủ điều kiện sinh đề thích ứng | Thông báo lỗi, **giữ nguyên form** |
| 502 | `INVALID_MODEL_OUTPUT` | Model trả kết quả không hợp lệ | Thông báo lỗi, **giữ nguyên form**, nút "Thử lại" |
| 503 | `MODEL_UNAVAILABLE` | Ollama/model chưa sẵn sàng | Như trên |
| 504 | `GENERATION_TIMEOUT` | Sinh đề quá thời gian | Như trên |

---

## II. QUY TẮC HIỂN THỊ ĐÃ THỐNG NHẤT (UI Display Rules)

1. **Phân loại kỹ năng do planner quyết định, UI không tự tính ngưỡng.**

   | Loại | Điều kiện (theo planner) |
   | :--- | :--- |
   | `NO_DATA` | `evidence_count = 0` |
   | `PARTIAL` | `evidence_count` từ 1 đến 2 |
   | `WEAK` | `evidence_count ≥ 3` và `mastery_score < 3.0` |
   | `ACHIEVED` | `evidence_count ≥ 3` và `mastery_score ≥ 3.0` |

   Lý do: với dưới 3 câu đã làm thì chưa đủ cơ sở đánh giá mức độ thông thạo, nên kỹ năng đó không bị coi là yếu.

2. **Hiển thị `mastery` trên thanh tiến trình:**
   * `NO_DATA`: thanh rỗng, hiển thị "—" và "Chưa có dữ liệu" (không hiển thị 0%).
   * `PARTIAL`: thanh màu xám, nhãn "Cần thêm dữ liệu · n/3 câu".
   * `WEAK`, `ACHIEVED`: thanh mastery bình thường, phân biệt bằng màu.
   * Số 3 trong "n/3" chỉ để hiển thị, lấy từ chính sách planner (README), không dùng để phân loại.

3. **Hiển thị `evidence`:** là **một số nguyên theo từng kỹ năng** (`evidence_count`), hiển thị "N câu đã làm". API không có danh sách bài làm hay điểm theo từng bài.

4. **Hiển thị `khuyến nghị`:** API không có trường văn bản khuyến nghị theo kỹ năng. UI ghép từ:
   * Khối "Cần cải thiện": kỹ năng `WEAK`. Nếu không có kỹ năng yếu, hiển thị "Chưa đủ dữ liệu" hoặc "Không có kỹ năng yếu" tùy phân loại.
   * Khối "Khuyến nghị ôn tập": mẫu câu theo `strategy` (`focused_practice`, `diagnostic_review`, `advanced_review`, `standard`).
   * Không hiển thị nguyên văn `questions[].reasons` vì đó là chuỗi kỹ thuật.

5. **Nhãn "Dữ liệu hồ sơ"** (API không có field, UI suy ra):
   * Mọi kỹ năng `NO_DATA`: "Chưa có dữ liệu".
   * Còn kỹ năng `NO_DATA` hoặc `PARTIAL`: "Một phần".
   * Còn lại: "Đầy đủ".

6. **Phân bố mức độ do trợ lý quyết định:** giáo viên không chỉnh. Bốn ô phần trăm ở Frame 1 chỉ hiển thị, nhãn ghi nguồn "Do trợ lý đề xuất". Việc làm tròn số câu mỗi mức do backend tính, UI không tự làm tròn.

---

## III. DANH SÁCH CHECKLIST DỮ LIỆU THIẾU / CẦN PHẢN HỒI

**Đã khớp:**

- [x] Payload sinh đề đã đủ `total_questions`, `duration_minutes`, `generation_mode`, `difficulty_distribution`.
- [x] Mã lỗi backend đã đủ để phân biệt lỗi quyền, lỗi dữ liệu, lỗi model (mục I.3).

**Thiếu trên API, UI xử lý tạm (cần nhóm xác nhận):**

- [ ] **Điểm trung bình học sinh** (Figma: "6.8 / 10"): profile không có field. Tạm thay bằng "Kỹ năng đủ dữ liệu: x/y". Nếu muốn giữ điểm trung bình, backend cần bổ sung field.
- [ ] **Nhãn "Dữ liệu hồ sơ"**: hiện UI tự suy ra từ `skill_classifications`. Cần xác nhận quy tắc ở mục II.5.
- [ ] **Văn bản khuyến nghị theo kỹ năng**: hiện UI ghép theo mẫu. Cần xác nhận nội dung mẫu.
- [ ] **Hình thức đề (Tự luận)**: không có field, UI dùng hằng số.
- [ ] **Response `/exams/plan`**: cần xác nhận có các field `priority_skills`, `target_count` hay không. `PlannerSummary` trong `schemas.py` không khai báo hai field này, nên UI chỉ dùng `skill_classifications` và `quota_summary`.
- [ ] **Lưu bản nháp, Giao đề cho học sinh** (Frame 2): chưa có endpoint. Ngoài phạm vi giai đoạn này.

**Phân quyền:**

- [ ] Hiện chỉ có **một teacher token dùng chung**, chưa có phân quyền theo giáo viên hay theo lớp. Màn "Không có quyền truy cập" xuất hiện khi token thiếu, sai hoặc server chưa cấu hình. Chưa thể hiển thị tình huống "giáo viên không được xem học sinh của lớp khác" vì backend chưa có khái niệm này.
- [ ] Token chỉ giữ trong bộ nhớ trình duyệt (theo thiết kế bảo mật của nhóm). Tải lại trang (F5) hoặc mở tab mới phải kết nối lại từ launcher.

**Giữ cấu hình khi sinh đề thất bại:**

- [ ] UI giữ nguyên toàn bộ form (số câu, thời lượng) khi sinh đề trả lỗi 409, 502, 503, 504, và cho phép bấm "Thử lại" với đúng cấu hình cũ.
