# get_student_profiles

> Bản app-local trong thư mục này là fixture đã seed cho kiểm thử offline, không
> còn là nguồn hồ sơ mặc định của UI/API. Nguồn mặc định hiện là
> `pre-work/data/sample/memory/student_profiles_sample.db` từ workspace root.
> Không chạy seed lên database Data Lead. Quy tắc hiện tại: chưa có evidence thì
> API trả mastery null, UI hiện `--/4`; có evidence phải giữ đúng mastery SQL.
> Xem [báo cáo sửa missing mastery](../../../docs/report/missing_student_mastery.md).

## Hồ sơ thử đa dạng — cập nhật 27/10/2026

`student_profiles_sample.db` có 20 học sinh và 140 dòng `student_skill_mastery`
(7 kỹ năng A001–A007 mỗi học sinh). Điểm mastery 0–4 và evidence 0–18 trong lần
cập nhật này là **dữ liệu giả lập để test planner**, không phải kết quả đánh giá
thật và không được tính lại từ lịch sử bài làm. Thông tin học sinh, bảng `Tests`
và `test_questions` được giữ nguyên.

Nguồn có thể tái tạo: [profile_scenarios.json](profile_scenarios.json).
Policy cập nhật 28/10/2026: WEAK khi mastery <2.0/4 và có ít nhất 3 evidence.
Manifest ngày 27/10 vẫn giữ mô tả/expected_strategy của ngưỡng cũ; không đổi điểm,
evidence hoặc SQL để ép kết quả. Bảng dưới mô tả hành vi theo policy mới.
Seed offline có backup và transaction:

```powershell
.\.venv\Scripts\python.exe data/sample/memory/seed_sample_profiles.py
```

Chạy từ repository root. Lệnh chỉ cập nhật mastery/evidence trong database
sample; ứng dụng vẫn chỉ đọc dữ liệu M3. Bản SQLite trước mỗi thay đổi nằm trong
`data/sample/memory/backups/`; tên file dùng thời gian UTC. Chạy lại khi dữ liệu
đã đúng fixture sẽ không ghi lại hoặc tạo thêm backup. Script từ chối danh mục
kỹ năng hoặc danh sách học sinh không khớp, không tự remap dữ liệu.

| Học sinh | Tình huống | Kết quả khi chọn Adaptive |
|---|---|---|
| ST001 | Yếu quy tắc cộng, đủ evidence | Focus một kỹ năng |
| ST002 | Yếu quy tắc nhân, đủ evidence | Focus một kỹ năng |
| ST003 | Cộng 1.7 là WEAK; nhân 2.2 là ACHIEVED | Focus một kỹ năng |
| ST004 | Yếu quy tắc nhân và hoán vị | Focus hai kỹ năng |
| ST005 | Tất cả mastery ≥2.0 và đủ evidence | Advanced Review |
| ST006 | Hai kỹ năng yếu; mastery 2.4 đã ACHIEVED | Chọn hai kỹ năng yếu nhất |
| ST007 | Tất cả đã đạt; mastery ở nhiều mức | Advanced Review |
| ST008 | Tất cả mastery 4.0, nhiều evidence | Advanced Review |
| ST009 | Trộn achieved, partial và no-data | Diagnostic + Maintenance |
| ST010 | Mọi kỹ năng chỉ có 1–2 evidence | Diagnostic Review, không gán WEAK |
| ST011 | Mọi kỹ năng chưa có evidence | Diagnostic Review |
| ST012 | Mastery 2.99 và 3.00 đều ACHIEVED | Advanced Review |
| ST013 | Điểm thấp nhưng evidence 2 so với 3 | Chỉ skill đủ evidence được Focus |
| ST014 | Mastery 0 nhưng có 6 evidence | WEAK, không phải NO_DATA |
| ST015 | Mastery 1.49 | Kiểm tra dải độ khó thấp |
| ST016 | Mastery 1.50 và 2.50 | Kiểm tra biên các dải độ khó |
| ST017 | Yếu tổ hợp (A004) | Cảnh báo thiếu nguồn primary phù hợp |
| ST018 | Yếu sơ đồ cây và chỉnh hợp | Cảnh báo thiếu nguồn primary phù hợp |
| ST019 | Trộn achieved và nhiều kỹ năng thiếu dữ liệu | Diagnostic + Maintenance |
| ST020 | Mastery 3.49, 3.50 và các mức cao | Advanced Review, kiểm tra biên 3.50 |

Hiện có 53 câu đủ primary annotation: A001=9, A002=42, A003=2; A004–A007 chưa có
câu đủ điều kiện primary. Vì vậy ST017/ST018 vẫn chọn chiến lược focused_practice
nhưng có thể không đạt câu Focus nào và trả `personalized=false` cùng warnings.
Fixture không tự sửa metadata ngân hàng để che thiếu hụt này.

Trong UI, chọn học sinh rồi bấm **Xem kế hoạch** để kiểm tra. M3 profiles
được đọc mới mỗi request: chọn lại học sinh để tải điểm mới, không cần restart.
Demo và Qwen dùng cùng planner cá nhân hóa; Demo trình bày nguyên văn câu nguồn.
Không còn chế độ Standard hay tỷ lệ độ khó thủ công trên teacher UI/API.
Theo ngưỡng 2.0/4, bộ dữ liệu hiện có 11 Focus, 4 Diagnostic và 5 Advanced scenarios.

Các mô tả legacy getter ở phần dưới không thay thế policy hiện hành:
evidence được xét theo từng skill với ngưỡng 3, mastery target 2.0/4.

## 1. Overview

Module này quản lý thông tin hồ sơ học sinh, lịch sử làm bài kiểm tra và mức độ thành thạo các kỹ năng. Dữ liệu được truy xuất từ SQLite database `student_profiles_sample.db`.

Các chức năng chính:
- Xác định trạng thái dữ liệu học tập của học sinh.
- Thêm bài kiểm tra vào lịch sử học tập trong bộ nhớ.
- Truy xuất lịch sử bài kiểm tra và các câu trả lời sai.
- Lấy danh sách toàn bộ học sinh.
- Lấy thông tin chi tiết của một học sinh theo `student_id`.

## 2. Function Descriptions

### 2.1. `update_status(student)`

**Prototype:**
```python
def update_status(student: dict) -> None:
```

**Nhiệm vụ:**

Xác định trạng thái dữ liệu học tập của học sinh dựa trên số bài kiểm tra trong `learning_history`, sau đó cập nhật trường `status` của đối tượng `student`.

**Quy tắc xác định trạng thái:**

| Điều kiện | Status | Ý nghĩa |
|---|---|---|
| Có từ 2 bài kiểm tra trở lên | `sufficent` | Có đủ dữ liệu theo ngưỡng hiện tại |
| Có 1 bài kiểm tra | `partial` | Có dữ liệu nhưng chưa đủ |
| Không có bài kiểm tra | `no_data` | Chưa có dữ liệu học tập |

**Input:**
- `student` (`dict`): hồ sơ học sinh, cần có trường `learning_history` kiểu danh sách.

**Return:** `None`. Hàm cập nhật trực tiếp trường `status` của `student`.

### 2.2. `add_test(test, student)`

**Prototype:**
```python
def add_test(test: dict, student: dict, test_question) -> None:
```

**Nhiệm vụ:**

Thêm thông tin một bài kiểm tra vào lịch sử học tập của học sinh trong bộ nhớ, sau đó cập nhật trạng thái dữ liệu học tập bằng `update_status()`.

**Input:**
- `test` (`dict`): thông tin bài kiểm tra cần thêm.
    test = {
        "test_id": "T001",
        "test_name": "Kiểm tra Đại số tổ hợp",
        "date": "2026-10-21",
        "score": 8.5
    }
- `test_question`: các câu hỏi trong test đó
    test_questions = [
        {
            "question_id": "QA0001",
            "question_order": 1,
            "is_correct": 1
        },
        {
            "question_id": "QA0002",
            "question_order": 2,
            "is_correct": 0
        },
        {
            "question_id": "QA0003",
            "question_order": 3,
            "is_correct": 1
        }
    ]
- `student` (`dict`): hồ sơ học sinh, cần có danh sách lịch sử bài kiểm tra.

**Return:** `None`.

### 2.3. `get_test(student)`

**Prototype:**
```python
def get_test(
    student: dict
) -> list[dict[str, str | list[str]]]:
```

**Nhiệm vụ:**

Truy xuất lịch sử bài kiểm tra của một học sinh từ database, đồng thời lấy danh sách các câu hỏi học sinh trả lời sai trong từng bài.

**Quy trình xử lý:**
1. Lấy các `test_id` từ bảng `Tests` theo `student_id`.
2. Với mỗi bài kiểm tra, truy vấn bảng `test_questions`.
3. Lọc các câu có `is_correct = 0`.
4. Sắp xếp các câu sai theo `question_order`.
5. Trả về danh sách lịch sử bài kiểm tra.

**Input:**
- `student` (`dict`): hồ sơ học sinh, cần có trường `student_id`.

**Return:** `list[dict]`. Mỗi phần tử gồm:
- `test_id` (`str`): mã bài kiểm tra.
- `wrongs` (`list[str]`): danh sách ID câu hỏi trả lời sai.

**Ví dụ:**
```python
[
    {
        "test_id": "T001",
        "wrongs": ["QA0003", "QA0007"]
    },
    {
        "test_id": "T002",
        "wrongs": ["QA0005"]
    }
]
```

Nếu xảy ra lỗi SQLite, hàm in thông báo lỗi và trả về danh sách rỗng `[]`.

### 2.4. `get_all_student()`

**Prototype:**
```python
def get_all_student() -> list[dict[str, object]] | None:
```

**Nhiệm vụ:**

Truy xuất toàn bộ hồ sơ học sinh từ database, bổ sung lịch sử bài kiểm tra và dữ liệu thành thạo kỹ năng, sau đó xác định trạng thái dữ liệu học tập của từng học sinh.

**Quy trình xử lý:**
1. Lấy thông tin cơ bản từ bảng `Students`.
2. Gọi `get_test(student)` để lấy lịch sử bài kiểm tra và các câu trả lời sai.
3. Truy vấn bảng `student_skill_mastery` để lấy dữ liệu thành thạo kỹ năng.
4. Gọi `update_status(student)` để xác định trạng thái dữ liệu học tập.
5. Thêm hồ sơ hoàn chỉnh vào danh sách kết quả.

**Return:** Danh sách các đối tượng `dict`, mỗi đối tượng gồm:

| Trường | Mô tả |
|---|---|
| `student_id` | Mã học sinh |
| `grade_level` | Khối/lớp học |
| `name` | Họ tên |
| `birthday` | Ngày sinh |
| `learning_history` | Lịch sử bài kiểm tra và danh sách câu sai |
| `skill_mastery` | Danh sách kỹ năng, điểm thành thạo và số lượng bằng chứng |
| `status` | Trạng thái dữ liệu học tập |

Hàm trả về danh sách rỗng nếu không có học sinh nào trong database. Trong code hiện tại, kiểu trả về thực tế khi thành công là `list[dict[str, object]]`; chưa có nhánh chủ động trả về `None`.

### 2.5. `get_student_by_id(student_id)`

**Prototype:**
```python
def get_student_by_id(student_id: str) -> dict | None:
```

**Nhiệm vụ:**

Truy xuất hồ sơ chi tiết của một học sinh dựa trên mã `student_id`.

**Quy trình xử lý:**
1. Tìm thông tin học sinh trong bảng `Students`.
2. Nếu không tìm thấy, trả về `None`.
3. Gọi `get_test(student)` để lấy lịch sử bài kiểm tra.
4. Truy vấn `student_skill_mastery` để lấy dữ liệu thành thạo kỹ năng.
5. Gọi `update_status(student)`.
6. Trả về hồ sơ học sinh hoàn chỉnh.

**Input:**
- `student_id` (`str`): mã định danh học sinh cần tìm.

**Return:**
- `dict`: hồ sơ học sinh đầy đủ nếu tìm thấy.
- `None`: nếu không tìm thấy học sinh có mã tương ứng.

## 3. Database Dependencies

Module sử dụng SQLite database có đường dẫn được xác định tương đối với file Python:

```python
BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "student_profiles_sample.db"
```

Các bảng được sử dụng:

| Bảng | Vai trò |
|---|---|
| `Students` | Lưu thông tin cơ bản của học sinh |
| `Tests` | Lưu thông tin các bài kiểm tra và học sinh thực hiện |
| `test_questions` | Lưu câu hỏi trong từng bài kiểm tra và kết quả trả lời |
| `student_skill_mastery` | Lưu điểm thành thạo và số lượng bằng chứng theo kỹ năng |

## 4. Example Usage

### Lấy toàn bộ hồ sơ học sinh

```python
students = get_all_student()

for student in students:
    print(student)
```

### Lấy hồ sơ theo mã học sinh

```python
student = get_student_by_id("ST001")

if student is not None:
    print(student)
else:
    print("Student not found")
```

## 5. Notes and Limitations

- `get_test()` truy xuất dữ liệu từ database nhưng không cập nhật database.
- `update_status()` chỉ cập nhật trạng thái trên đối tượng Python, không ghi trạng thái vào database.
- `add_test()` hiện chỉ thêm bài kiểm tra vào danh sách trong bộ nhớ; hàm chưa thực hiện thao tác `INSERT` vào bảng `Tests` hoặc `test_questions`.
- `get_all_student()` và `get_student_by_id()` gọi `update_status()` trước khi trả về hồ sơ.
- Các hàm truy xuất hồ sơ cần database tồn tại và có cấu trúc bảng phù hợp.
- Nên thống nhất tên key `learning_history` trong toàn bộ module để tránh lỗi truy cập dữ liệu.
