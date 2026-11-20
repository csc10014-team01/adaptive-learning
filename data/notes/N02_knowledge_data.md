#[N03] Pre-work: Chủ đề Đại số tổ hợp, Câu hỏi mẫu & Data Dictionary/Schema
**Owner**: Nguyen Ngoc Anh Duong
**Issue**: #5
**Tổng quan**: 
Tài liệu mô tả hai phần dữ liệu của dự án **AI sinh đề Toán cá nhân hóa hỗ trợ giáo viên** trong phạm vi **MVP 1**.

- **question_bank.db**: lưu ngân hàng câu hỏi, kỹ năng, đáp án/lời giải và thuật ngữ Toán học.
- **student_profiles_sample**: lưu hồ sơ học sinh và lịch sử kiểm tra để hệ thống có dữ liệu phục vụ quá trình sinh đề.

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

## 2. question_bank — Ngân hàng câu hỏi

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
student_profiles_sample (memory.db)
  ├── student_skill_mastery
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

## 6. Cơ chế cập nhật mastery_score
### 6.1. Mục tiêu

Xây dựng cơ chế tính toán và cập nhật mức độ thành thạo (mastery_score) của từng học sinh theo từng kỹ năng (skill_id), dựa trên kết quả làm bài kiểm tra được lưu trong database.

Cơ chế này được sử dụng chung cho hai trường hợp:

add_test(): Cập nhật mức độ thành thạo khi học sinh có bài kiểm tra mới.

get_test(): Tính toán lại mức độ thành thạo dựa trên lịch sử các bài kiểm tra đã lưu.

### 6.2. Dữ liệu đầu vào

Bảng

Dữ liệu sử dụng

- Tests: test_id, student_id
- test_questions: test_id, question_id, is_correct
- questions: question_id, difficulty
- question_skills: Quan hệ giữa câu hỏi và kỹ năng
- student_skill_mastery: student_id, skill_id, mastery_score, evidence_count

Trong MVP1, hệ thống sử dụng is_correct để đánh giá kết quả trả lời:

1: Trả lời đúng.

0: Trả lời sai.

Trường rate_correct chưa được sử dụng trong giai đoạn này.

### 6.3. Cơ chế đề xuất tính toán

#### 6.3.1. Tính mastery của từng kỹ năng trong một bài kiểm tra

Đối với mỗi bài kiểm tra, hệ thống lấy các câu hỏi và xác định những kỹ năng liên quan. Các câu hỏi có cùng skill_id được nhóm lại để tính điểm riêng cho từng kỹ năng.

Công thức:

                M_test = 4 * SUM(difficulty_i * is_correct_i) / SUM(difficulty_i)

Trong đó:

- M_test: Điểm mastery của kỹ năng trong bài kiểm tra.
- difficulty_i: Độ khó của câu hỏi thứ i.
- is_correct_i: Kết quả trả lời câu hỏi, bằng 1 nếu đúng và 0 nếu sai.
- Tổng được tính trên tất cả câu hỏi thuộc kỹ năng đang xét trong bài kiểm tra.
- Điểm mastery nằm trong khoảng từ 0 đến 4, với điều kiện độ khó của các câu hỏi lớn hơn 0.

#### 6.3.2. Tổng hợp mastery qua nhiều bài kiểm tra
##### 6.3.2.1 Công thức tính mastery_score của kỹ năng trong bài 1 kiểm tra

Điểm mastery của một kỹ năng trong bài kiểm tra được tính bằng tổng điểm đóng góp của các câu hỏi đánh giá kỹ năng đó. Mỗi câu hỏi có độ khó riêng và điểm đóng góp được tính dựa trên tỷ lệ trả lời đúng nhân với độ khó của câu hỏi.

**Công thức:**

```
                M_j = SUM(r_ij * d_ij)
```

Trong đó:

- `M_j`: Điểm mastery của kỹ năng trong bài kiểm tra thứ j.
- `n_j`: Số câu hỏi thuộc kỹ năng đang xét trong bài kiểm tra thứ j.
- `r_ij`: Tỷ lệ trả lời đúng của câu hỏi thứ i trong bài kiểm tra thứ j, nằm trong khoảng [0, 1]. MVP 1 lấy r_ij = {0, 1}
- `d_ij`: Độ khó của câu hỏi thứ i trong bài kiểm tra thứ j.

Điểm đóng góp của mỗi câu hỏi được tính theo công thức:

```
                Score_ij = r_ij * d_ij
```

Nếu một câu hỏi đánh giá nhiều kỹ năng, điểm đóng góp của câu hỏi đó được tính riêng cho từng kỹ năng tương ứng.

##### 6.3.2.2 Công thức cập nhật mastery_score qua nhiều bài kiểm tra

Điểm mastery tổng hợp mới của kỹ năng được tính bằng trung bình có trọng số theo độ khó của các câu hỏi thuộc kỹ năng đó qua nhiều bài kiểm tra.

**Công thức:**

```text
                M_new = 4 * SUM(r_ij * d_ij) / SUM(d_ij)
```

Trong đó, các tổng được tính trên toàn bộ câu hỏi thuộc kỹ năng đang xét trong các bài kiểm tra có dữ liệu đánh giá.

- `M_new`: Điểm mastery tổng hợp mới của kỹ năng, nằm trong khoảng [0, 4].
- `k`: Tổng số bài kiểm tra có dữ liệu đánh giá kỹ năng.
- `n_j`: Số câu hỏi thuộc kỹ năng đang xét trong bài kiểm tra thứ j.
- `r_ij`: Tỷ lệ trả lời đúng của câu hỏi thứ i trong bài kiểm tra thứ j.
- `d_ij`: Độ khó của câu hỏi thứ i trong bài kiểm tra thứ j.

Công thức đảm bảo các câu hỏi có độ khó cao đóng góp trọng số lớn hơn vào điểm mastery tổng hợp của kỹ năng.

##### 6.3.2.3. Dữ liệu ví dụ

###### Bài kiểm tra 1

| Câu hỏi | Difficulty | Rate_correct | Điểm đóng góp (`rate_correct * difficulty`) |
|---|---:|---:|---:|
| Q1 | 1 | 1.0 | 1.0 |
| Q2 | 2 | 0.5 | 1.0 |
| Q3 | 4 | 0.0 | 0.0 |
| **Tổng** | **7** | | **2.0** |

Tính mastery của kỹ năng trong bài kiểm tra 1:

```text
M_1 = 1.0 * 1 + 0.5 * 2 + 0.0 * 4
    = 1.0 + 1.0 + 0.0
    = 2.0
```

###### Bài kiểm tra 2

| Câu hỏi | Difficulty | Rate_correct | Điểm đóng góp (`rate_correct * difficulty`) |
|---|---:|---:|---:|
| Q1 | 2 | 1.0 | 2.0 |
| Q2 | 3 | 1.0 | 3.0 |
| Q3 | 4 | 0.5 | 2.0 |
| **Tổng** | **9** | | **7.0** |

Tính mastery của kỹ năng trong bài kiểm tra 2:

```text
M_2 = 1.0 * 2 + 1.0 * 3 + 0.5 * 4
    = 2.0 + 3.0 + 2.0
    = 7.0
```

###### Tính `M_new`

Cộng điểm đóng góp của tất cả câu hỏi thuộc kỹ năng trong cả hai bài kiểm tra:

```text
Tong_diem_dong_gop = M_1 + M_2
                   = 2.0 + 7.0
                   = 9.0
```

Cộng tổng độ khó của tất cả câu hỏi:

```text
Tong_difficulty = 7 + 9
                = 16
```

Thay vào công thức:

```text
M_new = 4 * 9.0 / 16
      = 36 / 16
      = 2.25
```

**Kết quả: `M_new = 2.25` trên thang điểm `[0, 4]`.**

###### Diễn giải

Trong ví dụ này, kỹ năng A001 có mastery tổng hợp là **2.25/4**.

Công thức dùng độ khó làm trọng số: câu hỏi có difficulty cao hơn sẽ có ảnh hưởng lớn hơn đến kết quả tổng hợp. Tỷ lệ trả lời đúng của từng câu vẫn quyết định mức điểm đóng góp thực tế.

> Lưu ý: `M_j` là tổng điểm đóng góp chưa chuẩn hóa trong một bài kiểm tra; `M_new` là điểm tổng hợp đã chuẩn hóa về thang `[0, 4]`. Vì vậy, không nên diễn giải trực tiếp `M_j` như một điểm mastery trên thang `[0, 4]`.


#### 6.3.3. Cập nhật evidence_count

evidence_count thể hiện tổng số câu hỏi đã được sử dụng làm bằng chứng đánh giá một kỹ năng.

                evidence_count_new = SUM(n_j)

Trong đó n_j là số câu hỏi thuộc kỹ năng đang xét trong bài kiểm tra thứ j.

Mỗi câu hỏi chỉ được tính một lần cho mỗi kỹ năng trong phạm vi dữ liệu đánh giá tương ứng. Nếu một câu hỏi liên quan đến nhiều kỹ năng, câu hỏi đó có thể đóng góp bằng chứng cho từng kỹ năng liên quan.

### 6.4. Cơ chế cập nhật database

- Sau khi tính toán, hệ thống kiểm tra sự tồn tại của bản ghi tương ứng trong student_skill_mastery.
- Kỹ năng đã tồn tại: Cập nhật mastery_score và evidence_count bằng kết quả tổng hợp mới.
- Kỹ năng chưa tồn tại: Tạo bản ghi mới với student_id, skill_id, mastery_score và evidence_count tương ứng.

Không cộng trực tiếp điểm mastery mới vào điểm mastery cũ, vì cách này có thể khiến điểm vượt khỏi thang đo quy định.

### 6.5. Tích hợp với các hàm hiện tại

#### 6.5.1. Trường hợp add_test()

- Thêm bài kiểm tra vào Tests.
- Thêm các câu hỏi và kết quả trả lời vào test_questions.
- Sau khi lưu thành công, gọi hàm cập nhật mastery cho student_id và test_id của bài kiểm tra mới.
- Tính điểm của từng kỹ năng trong bài kiểm tra mới.
- Tổng hợp với các bài kiểm tra trước đó và cập nhật student_skill_mastery.

Hệ thống chỉ cập nhật mastery sau khi việc thêm bài kiểm tra và các câu hỏi liên quan thành công.

#### 6.5.2. Trường hợp get_test()

- Truy xuất danh sách bài kiểm tra của học sinh từ Tests.
- Duyệt từng test_id và lấy dữ liệu tương ứng trong test_questions.
- Tính lại mastery của từng kỹ năng theo từng bài kiểm tra.
- Tổng hợp kết quả từ toàn bộ lịch sử.

Cập nhật lại student_skill_mastery.

Trong trường hợp này, hệ thống phải tính lại từ dữ liệu gốc hoặc ghi đè kết quả cũ, tránh cộng lặp dữ liệu đã được tính trước đó.

### 6.6 Đảm bảo tính nhất quán

Để tránh sai lệch dữ liệu, cần tuân thủ các nguyên tắc:

- Dùng chung công thức tính mastery cho cả add_test() và get_test().
- Không tính lặp một bài kiểm tra khi cập nhật tăng dần.
- Sử dụng transaction để đảm bảo tính nhất quán khi ghi database.
- Chỉ cập nhật mastery_score khi có dữ liệu đánh giá hợp lệ cho kỹ năng.
- Phân biệt trường hợp chưa có dữ liệu với trường hợp đã có dữ liệu nhưng tất cả câu trả lời đều sai.

### 6.7. Hướng phát triển

Trong các phiên bản tiếp theo, hệ thống có thể bổ sung rate_correct để biểu diễn kết quả trả lời chi tiết hơn thay vì chỉ sử dụng giá trị đúng/sai. Công thức tính mastery khi đó có thể được điều chỉnh để phản ánh mức độ hoàn thành của từng câu hỏi.

Ngoài ra, có thể lưu các thống kê trung gian như tổng trọng số và tổng điểm có trọng số nhằm hỗ trợ cập nhật tăng dần hiệu quả mà không phải truy vấn lại toàn bộ lịch sử mỗi khi học sinh hoàn thành một bài kiểm tra mới.

## 7. Đề xuất cơ chế sinh đề cá nhân hóa dựa trên `skill_mastery`

### 7.1. Mục tiêu

Cơ chế `skill_mastery` lưu mức độ thành thạo của từng học sinh đối với
từng kỹ năng (`skill_id`). Dữ liệu này được cập nhật từ kết quả làm bài
trong bảng `test_questions`, sau đó có thể được dùng làm đầu vào để lựa
chọn kỹ năng và độ khó câu hỏi khi sinh đề cá nhân hóa.

Trong phiên bản MVP1, hệ thống sử dụng kết quả đúng/sai của từng câu hỏi
và độ khó câu hỏi. Trường `rate_correct` chưa tham gia tính toán.

### 7.2. Bảng dữ liệu liên quan

#### 7.2.1. `student_skill_mastery`

Lưu mức độ thành thạo hiện tại của một học sinh đối với một kỹ năng.

  -----------------------------------------------------------------------
  Cột                                 Ý nghĩa
  ----------------------------------- -----------------------------------
  `student_id`                        Mã học sinh

  `status`                            Điều kiện có phù hợp để sinh 
                                      đề cá nhân hóa không

  `skill_id`                          Mã kỹ năng

  `mastery_score`                     Điểm thành thạo của kỹ năng, nằm
                                      trong khoảng 0--4

  `evidence_count`                    Tổng số câu hỏi đã được dùng làm
                                      bằng chứng đánh giá kỹ năng
  -----------------------------------------------------------------------

Khóa chính gồm `(student_id, skill_id)`, do đó mỗi học sinh chỉ có một
bản ghi cho mỗi kỹ năng.

#### 7.2.2. `test_questions`

Lưu các câu hỏi thuộc từng bài kiểm tra, cùng kết quả làm bài. Cơ chế
cập nhật sử dụng tối thiểu các thông tin:

-   `test_id`: xác định bài kiểm tra.
-   `question_id`: xác định câu hỏi.
-   `is_correct`: kết quả đúng/sai của câu hỏi.
-   Thông tin liên kết câu hỏi với kỹ năng (`skill_id`) và độ khó
    (`difficulty`) lấy từ dữ liệu câu hỏi/kỹ năng tương ứng.

Nếu một câu hỏi liên kết với nhiều kỹ năng, câu hỏi có thể đóng góp bằng
chứng cho từng kỹ năng liên quan.

### 7.5. Dùng `skill_mastery` để sinh đề cá nhân hóa

Sau khi có điểm thành thạo của từng kỹ năng, bộ sinh đề có thể sử dụng
dữ liệu này để điều chỉnh nội dung bài kiểm tra:

1. **Xét status của học sinh**: sufficent: >= 2 đề, partial: 1 đề
    , no_data: 0 đề đã làm. Cho biết mức độ tin cậy của đề cá nhân
    hóa. Với no_data, AI tự random đề theo độ khó trung bình.
2.  **Đọc hồ sơ kỹ năng:** lấy `mastery_score` của học sinh theo từng
    `skill_id`.
3.  **Xác định kỹ năng cần ưu tiên:** kỹ năng có điểm thấp có thể được
    ưu tiên ôn tập; kỹ năng có điểm cao có thể nhận câu hỏi vận dụng
    hoặc nâng cao.
4.  **Chọn câu hỏi phù hợp:** truy vấn ngân hàng câu hỏi hoặc ngân hàng
    question_template theo kỹ năng cần kiểm tra và mức độ khó phù hợp.
5.  **Tạo đề:** kết hợp các câu hỏi theo mục tiêu của đề, bảo đảm có đủ
    nội dung cần đánh giá.
6.  **Sau khi học sinh làm bài:** lưu kết quả vào `test_questions` và
    cập nhật lại `skill_mastery`, tạo vòng phản hồi cho lần sinh đề tiếp
    theo.

`skill_mastery` là tín hiệu định lượng về mức độ thành thạo, không tự nó
quyết định toàn bộ đề thi. Bộ sinh đề vẫn cần tuân thủ các ràng buộc như
số lượng câu, phạm vi kiến thức, phân bố độ khó và yêu cầu của giáo
viên.

### 7.6. Ví dụ minh họa

Giả sử kỹ năng `A001` có hai bài kiểm tra:

  -----------------------------------------------------------------------
  Bài kiểm tra          Tổng độ khó câu hỏi (W)  Điểm thành thạo theo bài
                                                                      (M)
  ------------------- ------------------------- -------------------------
  Bài 1                                       4                         2

  Bài 2                                       6                         3
  -----------------------------------------------------------------------

Điểm tổng hợp:

    M{A001}= (2*4 + 3*6)/ (4+6) = 2.6

Nếu tổng số câu thuộc kỹ năng `A001` trong hai bài là 5, thì
`evidence_count = 5`. Bản ghi tương ứng trong `student_skill_mastery` sẽ
lưu `mastery_score = 2.6` và `evidence_count = 5`.

### 7.7. Giới hạn của MVP1 và hướng mở rộng

-   **Chưa dùng `rate_correct`:** hiện tại mỗi câu được xem là đúng hoặc
    sai hoàn toàn. Có thể bổ sung cách tính điểm cho câu đúng một phần
    khi dữ liệu và quy tắc chấm đã thống nhất.
-   **Chưa phản ánh độ mới của bằng chứng:** công thức hiện tại tổng hợp
    các bài theo trọng số độ khó, chưa ưu tiên kết quả gần đây hơn.
-   **Phụ thuộc chất lượng dữ liệu:** cần bảo đảm `is_correct`, độ khó
    và liên kết câu hỏi--kỹ năng chính xác.
-   **Cần tránh đếm trùng:** nếu một câu hỏi liên kết với nhiều kỹ năng,
    phải xác định rõ câu đó được tính cho từng kỹ năng liên quan; không
    được nhân bản số câu ngoài ý muốn trong `evidence_count`.
-   **Cần thống nhất nguồn dữ liệu:** điểm tổng hợp nên được tính từ dữ
    liệu bài kiểm tra gốc, để việc gọi lại hàm không làm thay đổi kết
    quả nếu dữ liệu đầu vào không đổi.

### 7.8. Tóm tắt

`update_skill_mastery()` là hàm dùng chung để cập nhật mức độ thành thạo
kỹ năng từ dữ liệu bài kiểm tra. Hàm tính điểm cho từng kỹ năng trong
từng bài theo độ khó và kết quả đúng/sai, sau đó tổng hợp nhiều bài bằng
trung bình có trọng số. `add_test()` gọi hàm sau khi thêm bài kiểm tra;
`get_test()` có thể gọi lại để tái tính từ dữ liệu nguồn. Điểm tổng hợp
trong khoảng 0--4 cùng `evidence_count` được lưu trong
`student_skill_mastery` và cung cấp tín hiệu cho bước lựa chọn kỹ năng,
độ khó khi sinh đề cá nhân hóa.


## 8. Phạm vi phát triển tiếp theo

Các nội dung sau **chưa thuộc MVP 1**, chỉ bổ sung README và schema khi nhóm bắt đầu triển khai MVP 2:

- `Issue_catalog`: danh mục các vấn đề/lỗi học tập đã chuẩn hóa.
- `student_issue_status`: theo dõi vấn đề học tập theo từng học sinh.

