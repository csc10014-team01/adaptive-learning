# Wireframe Specification & Data Contract: Student Profile -> Question Generation

- **Lead Designer / Owner:** Trần Lộc Chi Mai
- **Backend / Reviewer:** Đoàn Khánh Như

---

## 1. Màn hình 1: Student Profile (`/students/:id/profile`)

### 1.1. Bố cục Wireframe phác thảo 
```text
+-----------------------------------------------------------------------------------+
|  [Logo] Team 01                             [Lớp 10A1]  [GV: Nguyen Van A]        |
+-----------------------------------------------------------------------------------+
|  < Quay lại danh sách học sinh                                                    |
|                                                                                   |
|  +-----------------------------------------------------------------------------+  |
|  |   Nguyen Van B (ID: HS-2026-089)                  Lớp: 10A1                 |  |
|  |   Trạng thái dữ liệu: [ SUFFICIENT (Đủ dữ liệu) ] <Badge xanh>              |  |
|  |   Bài kiểm tra đã làm: 12 bài | Điểm trung bình: 6.8                        |  |
|  +-----------------------------------------------------------------------------+  |
|                                                                                   |
|  Bộ lọc: [ 30 ngày gần nhất v ]                                                   |
|                                                                                   |
|  +-----------------------------------------+ +----------------------------------+ |
|  | Biểu đồ năng lực theo chuyên đề         | | Đánh giá & Khuyến nghị           | |
|  |                                         | |                                  | |
|  |   Hàm số & Đồ thị        [======== ] 78%| | [!] Cần cải thiện:               | |
|  |   Hình không gian Oxyz   [====     ] 45%| | - Phương trình mặt phẳng (Oxyz)  | |
|  |   Nguyên hàm - Tích phân [======   ] 62%| | - Ứng dụng tích phân tính diện   | |
|  |   Số phức                [=======  ] 70%| |   tích hình phẳng                | |
|  |                                         | |                                  | |
|  |                                         | | Khuyến nghị: Ôn tập bổ trợ 3 câu | |
|  |                                         | | tự luận mức độ Vận dụng          | |
|  +-----------------------------------------+ +----------------------------------+ |
|                                                                                   |
|  [ Xem lịch sử bài làm ]                          [ + Tạo đề ôn tập thích ứng -> ]|
+-----------------------------------------------------------------------------------+
```

### 1.2. Biến thể trạng thái dữ liệu (Data Status Variants)
1. **`sufficient` (Đầy đủ dữ liệu):** Hiển thị đầy đủ thanh/radar chart, danh sách lỗ hổng kiến thức cụ thể, nút bấm màu xanh "Tạo đề ôn tập thích ứng".
2. **`partial` (Dữ liệu một phần):** Badge màu vàng cam `[ PARTIAL ]`. Hiển thị ghi chú: *"Dữ liệu ước tính dựa trên 2 bài kiểm tra gần nhất"*. Một số chủ đề chưa kiểm tra hiển thị `N/A`.
3. **`no_data` (Chưa có dữ liệu):** Badge màu xám `[ NO_DATA ]`. Vùng biểu đồ thay bằng placeholder rỗng kèm text: *"Chưa có lịch sử làm bài. Nhấn bên dưới để tạo đề kiểm tra đánh giá ban đầu với Default Blueprint"*. Nút bấm đổi thành "Tạo đề khảo sát (Default Blueprint)".

### 1.3. Bảng đặc tả Data Contract (Input / Output)

#### Frontend Input (Query Params)
| Tên trường | Kiểu dữ liệu | Bắt buộc | Mô tả |
| :--- | :--- | :---: | :--- |
| `student_id` | `String` | Có | Mã định danh duy nhất của học sinh (VD: `"HS-2026-089"`) |
| `time_range` | `String` | Không | Khoảng thời gian lọc (`"7d"`, `"30d"`, `"semester_1"`, `"all"`) |

#### Backend Response Output (JSON)
| Tên trường | Kiểu dữ liệu | Mô tả |
| :--- | :--- | :--- |
| `student_id` | `String` | ID học sinh |
| `student_name` | `String` | Tên đầy đủ học sinh |
| `class_name` | `String` | Tên lớp học |
| `data_status` | `Enum("sufficient", "partial", "no_data")` | Trạng thái tin cậy của dữ liệu năng lực |
| `total_tests_taken` | `Integer` | Tổng số bài kiểm tra đã thực hiện |
| `overall_mastery_score` | `Float (0.0 - 100.0)` | Điểm làm chủ kiến thức tổng thể (null nếu `no_data`) |
| `topic_mastery` | `Array<Object>` | Danh sách các chủ đề: `{ topic_id, topic_name, mastery_percentage, confidence_level }` |
| `weak_areas` | `Array<String>` | Danh sách các chủ đề/tiểu kỹ năng cần cải thiện |
| `recommended_blueprint_mode`| `Enum("adaptive", "default_blueprint")` | Chế độ sinh đề đề xuất cho Frontend |

---

## 2. Màn hình 2: Question Generation Configuration (`/students/:id/generate`)

### 2.1. Bố cục Wireframe phác thảo (ASCII Art)

+-----------------------------------------------------------------------------------+
|  < Quay lại Hồ sơ học sinh                                                        |
|                                                                                   |
|  Cấu hình sinh đề Toán tự luận cho: Nguyen Van B (Lớp 10A1)                       |
|  Trạng thái dữ liệu hồ sơ: [ SUFFICIENT ]                                         |
|  -------------------------------------------------------------------------------  |
|                                                                                   |
|  Chế độ sinh đề:                                                                  |
|  (•) Thích ứng theo lỗ hổng kiến thức  ( ) Sử dụng khung chuẩn (Default Blueprint)|
|                                                                                   |
|  Các chuyên đề trọng tâm:                                                         |
|  [x] Hình không gian Oxyz (Điểm hồ sơ: 45%)                                       |
|  [x] Nguyên hàm & Tích phân (Điểm hồ sơ: 62%)                                     |
|  [ ] Hàm số và đồ thị                                                             |
|                                                                                   |
|  Cấu hình số câu & Thời lượng:                                                    |
|  Số lượng câu hỏi: [ 4 câu v ]         Thời gian làm bài: [ 45 phút v ]           |
|                                                                                   |
|  Phân bổ mức độ nhận thức:                                                        |
|  Nhận biết: [ 25% ] | Thông hiểu: [ 25% ] | Vận dụng: [ 30% ] | VDC: [ 20% ]      |
|                                                                                   |
|  > Tùy chọn nâng cao (Prompt Context, LaTeX format, Barem 0.25đ...) [v]           |
|                                                                                   |
|  [ Hủy ]                                              [ Bắt đầu sinh đề bằng AI ] |
+-----------------------------------------------------------------------------------+

### 2.2. Bảng đặc tả Data Contract (Input / Output)

#### Frontend Request Payload (`POST /api/v1/exams/generate`)
| Tên trường | Kiểu dữ liệu | Bắt buộc | Mô tả |
| :--- | :--- | :---: | :--- |
| `student_id` | `String` | Có | ID học sinh mục tiêu |
| `generation_mode` | `Enum("adaptive", "default_blueprint")` | Có | Chế độ sinh đề |
| `selected_topic_ids`| `Array<String>` | Có | Danh sách mã chủ đề chọn đưa vào đề |
| `total_questions` | `Integer` | Có | Số câu hỏi tự luận (khoảng từ 1 đến 10) |
| `duration_minutes` | `Integer` | Có | Thời gian làm bài dự kiến (phút) |
| `difficulty_distribution` | `Object` | Có | Tỷ lệ `%` tương ứng: `{ recognition, understanding, application, advanced_application }` |
| `advanced_options` | `Object` | Không | `{ include_real_world_context: Boolean, step_scoring_granularity: Float }` |

#### Backend Response Output (Khởi tạo Job sinh đề)
| Tên trường | Kiểu dữ liệu | Mô tả |
| :--- | :--- | :--- |
| `job_id` | `String` | ID của tác vụ sinh đề bất đồng bộ (hoặc `exam_id` nếu xử lý đồng bộ) |
| `status` | `Enum("queued", "processing", "completed", "failed")` | Trạng thái xử lý |
| `estimated_wait_seconds`| `Integer` | Thời gian ước lượng để Frontend đếm ngược chờ |

---

## 3. Màn hình 3: Exam Preview, Solutions & Rubric (`/exams/:exam_id/preview`)

### 3.1. Bố cục Wireframe phác thảo (ASCII Art)

+-----------------------------------------------------------------------------------+
|  Xem trước đề kiểm tra Toán tự luận (Mã đề: EX-8821)             Trạng thái: Nháp |
|  Học sinh: Nguyen Van B | Chuyên đề: Oxyz, Tích phân | 4 câu - 45 phút            |
+-----------------------------------------------------------------------------------+
|                                                                                   |
|  +-----------------------------------------------------------------------------+  |
|  | Câu 1: (2.5 điểm) - Mức độ: Vận dụng                                        |  |
|  | Đề bài: Trong không gian với hệ tọa độ $Oxyz$, cho điểm $A(1; 2; -1)$ và... |  |
|  |                                                                             |  |
|  | [v] Lời giải chi tiết & Hướng dẫn chấm (Barem)                              |  |
|  | + Bước 1: Tìm tọa độ vector chỉ phương...                     -> 0.5 điểm   |  |
|  | + Bước 2: Thiết lập phương trình mặt phẳng $(P)$ qua $A$...   -> 1.0 điểm   |  |
|  | + Bước 3: Tính khoảng cách từ gốc tọa độ $O$ đến $(P)$...     -> 1.0 điểm   |  |
|  |                                                                             |  |
|  | [ Sửa thủ công ]                                      [ Tạo lại câu này ]   |  |
|  +-----------------------------------------------------------------------------+  |
|                                                                                   |
|  +-----------------------------------------------------------------------------+  |
|  | Câu 2: (2.5 điểm) - Mức độ: Thông hiểu                                      |  |
|  | Đề bài: Tính tích phân $I = \int_{0}^{1} (2x + 1)e^x dx$...                 |  |
|  | ...                                                                         |  |
|  +-----------------------------------------------------------------------------+  |
|                                                                                   |
|  [ Hủy bỏ ]                   [ Xuất file PDF / Word ]     [ Phê duyệt & Giao đề ]|
+-----------------------------------------------------------------------------------+

### 3.2. Bảng đặc tả Data Contract (Input / Output)

#### Frontend Request (`GET /api/v1/exams/:exam_id`)
- Tham số URL: `exam_id` (String).

#### Backend Response Output (`exam` Object)
| Tên trường | Kiểu dữ liệu | Mô tả |
| :--- | :--- | :--- |
| `exam_id` | `String` | ID duy nhất của đề thi |
| `student_id` | `String` | ID học sinh được phân công |
| `title` | `String` | Tiêu đề bài kiểm tra |
| `total_score` | `Float` | Tổng điểm toàn bài (VD: `10.0`) |
| `questions` | `Array<Object>` | Danh sách các câu hỏi tự luận chi tiết: |
| ↳ `question_id` | `String` | ID định danh câu hỏi |
| ↳ `order_index` | `Integer` | Thứ tự câu (1, 2, 3...) |
| ↳ `content_latex` | `String` | Nội dung câu hỏi (chứa mã LaTeX công thức Toán) |
| ↳ `topic_tag` | `String` | Chuyên đề của câu |
| ↳ `cognitive_level`| `String` | Nhận biết / Thông hiểu / Vận dụng / Vận dụng cao |
| ↳ `max_score` | `Float` | Điểm tối đa của câu |
| ↳ `step_solutions` | `Array<Object>` | Các bước giải: `[{ step_number, explanation, score }]` |
| ↳ `rubric` | `Array<Object>` | Tiêu chí chấm: `[{ criteria, sub_score }]` |

#### Action Request: Tái tạo riêng 1 câu hỏi (`POST /api/v1/exams/:exam_id/questions/:question_id/regenerate`)
| Tên trường | Kiểu dữ liệu | Mô tả |
| :--- | :--- | :--- |
| `reason` | `String` | Lý do/yêu cầu thay đổi (VD: `"Đổi dữ liệu số"`, `"Tăng độ khó"`) |
| *Response* | `Question Object` | Dữ liệu câu hỏi mới thay thế trực tiếp vào vị trí hiện tại |
