#[N03] Pre-work: Chủ đề Đại số tổ hợp, Câu hỏi mẫu & Data Dictionary/Schema
**Owner**: Nguyen Ngoc Anh Duong
**Issue**: #5
**Tổng quan**: 
Tài liệu mô tả hai phần dữ liệu của dự án **AI sinh đề Toán cá nhân hóa hỗ trợ giáo viên** trong phạm vi **MVP 1**.

- **Dataset**: lưu ngân hàng câu hỏi, kỹ năng, đáp án/lời giải và thuật ngữ Toán học.
- **Memory**: lưu hồ sơ học sinh và lịch sử kiểm tra để hệ thống có dữ liệu phục vụ quá trình sinh đề.

## 1. Cấu trúc tổng quát

Cấu trúc tham khảo — điều chỉnh tên file theo repository thực tế:

```text
Dataset/
└── 
    ├── dataset.db
    ├── get_database.py
Memory/
└──
    ├── memory.db
    ├── get_memory.py
```

- `dataset.db`: cơ sở dữ liệu ngân hàng câu hỏi.
- `get_database`: modude lấy dữ liệu từ database.db theo định dạng được viết trong Format_dictionary.md
- `memory.db`: cơ sở dữ liệu hồ sơ học sinh và lịch sử kiểm tra.
- `get_memory.py`: module lấy dữ liệu từ memory theo định dạng được viết trong Format_dictionary.md

## 2. Dataset — Ngân hàng câu hỏi

### 2.1. Vai trò

Dataset cung cấp câu hỏi để hệ thống truy vấn và tạo đề Toán. Mỗi câu hỏi có thông tin về nội dung, khối lớp, độ khó và trạng thái sử dụng. Câu hỏi có thể được liên kết với một hoặc nhiều kỹ năng.

### 2.2. Các bảng chính

| Bảng | Vai trò | Các trường tiêu biểu |
|---|---|---|
| `skills` | Danh mục kỹ năng/kiến thức | `skill_id`, `topic`, `name`, `grade_level`, `description` |
| `questions` | Ngân hàng câu hỏi | `question_id`, `question_type`, `difficulty`, `content`, `grade_level`, `status` |
| `question_skills` | Liên kết câu hỏi với kỹ năng | `question_id`, `skill_id` |
| `answers` | Đáp án và lời giải | `answer_id`, `question_id`, `correct_answer`, `explanation` |
| `question_part` | Thành phần của câu hỏi, nếu cần tách nhỏ nội dung | Theo schema hiện hành |
| `answers_part` | Thành phần của đáp án/lời giải, nếu cần tách nhỏ nội dung | Theo schema hiện hành |
| `answer_option` | Các lựa chọn của câu trắc nghiệm, nếu được sử dụng | Theo schema hiện hành |
| `terminology` | Thuật ngữ và phần giải thích | `term`, `text` |

Danh sách trên là mô tả chức năng. Kiểu dữ liệu, khóa chính, khóa ngoại và tên bảng chính xác cần được đối chiếu với schema SQL hiện tại của nhóm.

**Lưu ý về đáp án:** `answers.correct_answer` được lưu dưới kiểu `TEXT` theo thiết kế dữ liệu của dự án. Trường này có thể lưu đáp án dạng chữ, số hoặc biểu thức; `explanation` lưu phần giải thích/lời giải tương ứng.

### 2.3. Thang độ khó

Trường `auestions.difficulty` sử dụng thang từ 1 đến 6:

| Mức | Diễn giải |
|---:|---|
| 1 | Nền tảng |
| 2 | Trung bình |
| 3 | Khá |
| 4 | Khó/Giỏi |
| 5 | Rất khó/Xuất sắc |
| 6 | Vượt cấp/đội tuyển |

Độ khó là thuộc tính của câu hỏi, không phải điểm đánh giá mức độ thành thạo của học sinh.

### 2.4. Quan hệ câu hỏi — kỹ năng

Một câu hỏi có thể kiểm tra nhiều kỹ năng; một kỹ năng cũng có thể xuất hiện trong nhiều câu hỏi. Quan hệ này được lưu qua bảng trung gian `question_skills`, thay vì ghi nhiều `skill_id` trong một ô.

Ví dụ, nếu câu `QA0001` liên kết với hai kỹ năng `A001` và `A002`, hệ thống có thể truy xuất câu hỏi theo một trong hai kỹ năng đó.

### 2.5. Nguyên tắc quản lý Dataset

- Mỗi câu hỏi, kỹ năng và đáp án cần có ID duy nhất, ổn định.
- Dùng `question_skills` để quản lý quan hệ nhiều-nhiều giữa câu hỏi và kỹ năng.
- Giữ nội dung câu hỏi tách biệt với đáp án/lời giải theo schema.
- Kiểm tra lại công thức, ký hiệu Toán và định dạng sau khi trích xuất dữ liệu từ PDF.
- Chỉ đưa các câu hỏi đã được kiểm tra vào quy trình sinh đề, theo quy ước của trường `status`.

## 3. student_profiles_sample — Dữ liệu học sinh

### 3.1. Vai trò trong MVP 1

Memory lưu thông tin học sinh và lịch sử các bài kiểm tra. Trong MVP 1, dữ liệu này hỗ trợ tra cứu hồ sơ, ghi nhận kết quả và liên kết các câu hỏi đã xuất hiện trong bài kiểm tra.

MVP 1 **chưa triển khai** cơ chế phân tích lỗi học tập theo danh mục, theo dõi vấn đề lặp lại hoặc lưu mức thành thạo riêng cho từng kỹ năng.

### 3.2. Các bảng chính

| Bảng | Vai trò | Các trường tiêu biểu |
|---|---|---|
| `Students` | Hồ sơ học sinh | `student_id` và các trường hồ sơ được định nghĩa trong schema hiện hành |
| `Tests` | Thông tin bài kiểm tra | `test_id`, `student_id`, `test_name`, `date`, `score` |
| `test_questions` | Các câu hỏi thuộc bài kiểm tra và kết quả từng câu | `test_id`, `question_id`, `question_order`, `is_correct` |

Tên và kiểu dữ liệu thực tế phải khớp với database của nhóm. Nếu schema MVP 1 có thêm bảng ghi nhận lần làm bài riêng, hãy bổ sung bảng đó sau khi thống nhất thiết kế; không nên mô tả bảng chưa được tạo như một thành phần đã triển khai.

### 3.3. Quan hệ giữa các bảng

- `Students` định danh học sinh.
- `Tests.student_id` liên kết bài kiểm tra với học sinh.
- `test_questions.test_id` liên kết câu hỏi với bài kiểm tra.
- `test_questions.question_id` dùng để đối chiếu câu hỏi trong Dataset.

Luồng quan hệ cơ bản:

```text
Students
   │
   └── Tests
          │
          └── test_questions ─────► Questions (Dataset)
```

Nếu `dataset.db` và `memory.db` là hai file SQLite độc lập, quan hệ giữa chúng cần được xử lý ở tầng ứng dụng hoặc thông qua `ATTACH DATABASE`; không thể tạo khóa ngoại SQLite thông thường xuyên qua hai file database độc lập.

### 3.4. Ghi nhận kết quả bài kiểm tra

Trong MVP 1, giáo viên nhập hoặc xác nhận kết quả làm bài. Hệ thống lưu thông tin bài kiểm tra và kết quả từng câu theo schema hiện hành.

- `is_correct` dùng để ghi nhận câu trả lời đúng/sai.
- `score` trong `Tests` lưu điểm bài kiểm tra theo quy ước của dự án.
- `question_order` lưu thứ tự câu hỏi trong bài.
- Mỗi `question_id` phải đối chiếu được với câu hỏi tồn tại trong Dataset.

Nhóm cần thống nhất cách biểu diễn câu chưa làm hoặc câu không được tính điểm để tránh nhầm lẫn với câu trả lời sai.

## 4. Luồng dữ liệu MVP 1

```text
Dataset (dataset.db)
  ├── Questions
  ├── Skills
  ├── Question_skills
  ├── Answers
  └── Các bảng thành phần/thuật ngữ đang sử dụng
          │
          │ Truy vấn câu hỏi theo nội dung, kỹ năng,
          │ khối lớp và độ khó
          ▼
     Sinh đề cá nhân hóa
          │
          ▼
Memory (memory.db)
  ├── Students
  ├── Tests
  └── test_questions
          │
          └── Lưu bài kiểm tra và kết quả từng câu
```

### Luồng xử lý cơ bản

1. Tra cứu hồ sơ học sinh trong `Students`.
2. Truy vấn câu hỏi phù hợp từ Dataset.
3. Sinh đề cho học sinh.
4. Lưu thông tin bài kiểm tra trong `Tests`.
5. Lưu các câu hỏi thuộc bài và kết quả tương ứng trong `test_questions` khi có kết quả.
6. Dùng dữ liệu đã lưu để tra cứu lịch sử kiểm tra.

Các bước cập nhật `skill_mastery` hoặc phân tích `Issue_catalog` không thuộc luồng MVP 1 hiện tại.

## 5. Kiểm tra và duy trì dữ liệu

### Các điểm cần kiểm tra

- ID trong từng bảng không bị trùng.
- Các `student_id`, `test_id` và `question_id` tham chiếu đến bản ghi tồn tại.
- Câu hỏi trong `test_questions` có thể đối chiếu với Dataset.
- Đáp án và lời giải được gắn đúng `question_id`.
- Công thức Toán và ký hiệu đặc biệt không bị lỗi sau khi nhập dữ liệu.
- Sao lưu database trước khi thay đổi schema hoặc chạy script cập nhật hàng loạt.

## 6. Phạm vi phát triển tiếp theo

Các nội dung sau **chưa thuộc MVP 1**, chỉ bổ sung README và schema khi nhóm bắt đầu triển khai MVP 2:

- `skill_mastery` / `student_skill_mastery`: theo dõi mức thành thạo theo từng kỹ năng.
- `question_template`: quản lý mẫu câu hỏi phục vụ phân loại hoặc phân tích sâu hơn.
- `Issue_catalog`: danh mục các vấn đề/lỗi học tập đã chuẩn hóa.
- `student_issue_status`: theo dõi vấn đề học tập theo từng học sinh.

## 7. Tài liệu liên quan

Bổ sung đường dẫn tương ứng trong repository khi có:

- Logical schema và physical schema.
- SQL tạo bảng hoặc migration.
- Script nhập dữ liệu từ CSV/PDF.
- Module Python truy vấn Dataset và Memory.
- Test case kiểm tra sinh đề, lưu bài kiểm tra và ghi nhận kết quả.
