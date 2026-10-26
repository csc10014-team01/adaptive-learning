# N03 – Thuật toán & AI: Thử nghiệm cơ sở Qwen cục bộ và sinh câu hỏi dựa trên hồ sơ học sinh

> **Cập nhật 23/10/2026:** Backend thật đã được bổ sung theo
> [ADR-002](../decisions/ADR-002-real-personalized-mvp.md): cá nhân hóa từ 1 evidence
> theo từng skill, đọc M3 SQLite, Planner + Ollama/Qwen + lưu đề SQLite riêng.
> ADR-002 thay thế ngưỡng cấp student trong mã giả §4 cho backend thật. Nội dung
> thử nghiệm/đề xuất phía dưới được giữ để truy vết; bộ kiểm định ngữ nghĩa đầy đủ
> vẫn chưa được triển khai. Hướng dẫn chạy hiện tại ở [README](../../README.md).

**Issue liên quan:** #6 (đã hoàn thành thử nghiệm khả thi cơ sở trên máy cục bộ); #19 (đồng bộ Profile JSON và mã giả Blueprint)  
**Phụ trách:** M4 – Trưởng nhóm AI & Thuật toán  
**Người review Issue #19:** Nhukei (Trưởng nhóm Kiến trúc), Hoài Thương (Trưởng nhóm Rủi ro)  
**Trạng thái tài liệu:** Đã hoàn thành thử nghiệm cơ sở; mã giả của Issue #19 đã được đồng bộ với các quy tắc nêu trong Decision Log; kiến trúc bộ sinh câu hỏi mục tiêu được trình bày dưới dạng đề xuất cho giai đoạn triển khai tiếp theo.  
**Môn học / chủ đề trong MVP:** Toán lớp 10 / Đại số tổ hợp (`topic_id = "combinatorics"`). Giữ `topic_id` trong interface để có thể hỗ trợ thêm chủ đề sau này.

> **Phạm vi và bằng chứng.** Các mục 2–3 và 6 ghi nhận thử nghiệm Qwen cục bộ thực tế được thực hiện ngày 2026-10-19. Mục 4 thể hiện **quy tắc rẽ nhánh đã thống nhất chỉ bằng mã giả**, sử dụng Profile JSON do M3 tính sẵn. Mục 7 mô tả thiết kế dự kiến cho toàn bộ quy trình sinh câu hỏi; nội dung này **không khẳng định** rằng các module hoặc bộ kiểm định sáu lớp đã được triển khai hay kiểm thử.

## 1. Quyết định kiến trúc và phân công trách nhiệm

Hệ thống tạo **đề ôn tập cá nhân hóa** gồm các câu hỏi tự luận. Backend nhận hồ sơ học sinh, chủ đề do giáo viên chọn và số lượng câu hỏi được yêu cầu. Các thành phần có trách nhiệm riêng:

1. **Backend / Bộ lập kế hoạch đề thi theo quy tắc (Rule-based Exam Planner):** dựa trên `evidence_count` trong hồ sơ để xác định chế độ mặc định hay cá nhân hóa; sau đó lập kế hoạch độ khó, kỹ năng mục tiêu và chọn các bài toán phù hợp từ dataset.
2. **Bộ lập kế hoạch nội dung và cách diễn đạt (Content & Expression Planner):** chọn ngữ cảnh thực tế phù hợp về mặt toán học và `generate_type` (`direct` hoặc `indirect`).
3. **Bộ sinh câu hỏi Qwen cục bộ (Local Qwen Generator):** diễn đạt một bài toán **đã được chọn** thành một câu hỏi tiếng Việt, không thay đổi dữ kiện, ràng buộc hay đáp án dự kiến.
4. **Bộ kiểm định (Validator):** áp dụng năm lớp kiểm định tự động; lớp thứ sáu là giáo viên review. Tùy trường hợp, loại bỏ, đánh dấu hoặc yêu cầu sinh lại với số lần thử giới hạn.
5. **Bộ tổng hợp đề thi (Exam Assembler):** đánh số các câu hỏi ứng viên đã được chấp nhận, gắn đáp án từ dataset và xuất bản nháp đề thi để giáo viên phê duyệt.

**Phần toán học được xử lý bằng quy tắc xác định trong phạm vi được hỗ trợ:** đáp án tham chiếu lấy từ dữ liệu đã được kiểm chứng trong dataset hoặc từ quy tắc tính đáp án xác định, **không lấy từ suy đoán của Qwen**. Việc sử dụng Qwen3-1.7B đã được huấn luyện sẵn thông qua Ollama cục bộ đáp ứng thử nghiệm tích hợp AI cơ sở; đây không phải mô hình do nhóm tự huấn luyện.

**Cần phân biệt rõ:** `evidence_count` xác định **hồ sơ đã có đủ bằng chứng để kích hoạt cấu trúc đề cá nhân hóa (Personalized Blueprint) hay chưa**. Trường này **không** trực tiếp đo mức độ yếu của kỹ năng. Việc ưu tiên kỹ năng là một quyết định lập kế hoạch riêng, dựa trên các trường do M3 / backend cung cấp và chính sách ưu tiên đã thống nhất.

## 2. Thử nghiệm cơ sở Qwen cục bộ đã hoàn thành: thiết lập và contract đầu vào/đầu ra

Mục này ghi lại kết quả của Issue #6; nội dung này **không** định nghĩa JSON contract cuối cùng của Qwen cho phiên bản triển khai thực tế.

- **Máy chủ suy luận cục bộ:** `http://127.0.0.1:11434` (Ollama; không dùng API suy luận bên ngoài).
- **Mô hình:** `qwen3:1.7b` (lượng tử hóa `Q4_K_M`).
- **Cấu hình thử nghiệm cơ sở:** `temperature=0`, `seed=42`, `num_predict=250`, `think=false`, `stream=false`.
- **C01:** chọn ba trong tám học sinh, không lặp, không xét thứ tự; đáp án dự kiến do Python tính là `C(8,3) = 56`.
- **C02:** phân công ba vai trò khác nhau cho ba trong bảy học sinh, mỗi học sinh chỉ nhận một vai trò; đáp án dự kiến do Python tính là `A(7,3) = 210`.
- **JSON schema của Qwen trong thử nghiệm đã thực hiện:** `question: string`, `task: enum`, `n: int`, `k: int`, `answer: int`.
- **Script chạy thử nghiệm:** `src/ai/qwen_spike.py`.
- **Bằng chứng:** `eval/results/baseline_spike_output.json` (dữ liệu chạy thực tế, không phải mô phỏng).

**Khung prompt của thử nghiệm cơ sở:**

```text
Bạn là người soạn đề Toán tổ hợp lớp 10.
Viết đúng MỘT câu hỏi tự luận bằng tiếng Việt từ đặc tả toán học.
Giữ nguyên số liệu, phép toán, quan hệ và mọi điều kiện.
Không tự ý thêm/bớt điều kiện làm thay đổi đáp án.
Trả JSON theo schema thử nghiệm: {question, task, n, k, answer}.
```

Code thử nghiệm kiểm tra cấu trúc JSON và tính nhất quán cơ bản của metadata / số liệu, nhưng **không thể chứng minh toàn bộ bài toán có lời văn tiếng Việt tương đương về mặt toán học với đặc tả gốc**. Cần có giáo viên review.

## 3. Số liệu đo phần cứng và độ trễ thực tế

**Ngày thử nghiệm:** 2026-10-19  
**Người thực hiện:** Phạm Yến Trân (Trưởng nhóm AI & Thuật toán)

| Hạng mục đo | Kết quả thực tế |
|---|---|
| Hệ điều hành | Windows 11 (`10.0.26200`) |
| Python / Ollama | Python `3.14.4` / Ollama `0.40.6` |
| CPU | Intel64 Family 6 Model 186 Stepping 2, GenuineIntel; 16 nhân CPU logic |
| RAM được lắp trên hệ thống | `24,118.2 MiB` (khoảng `23.55 GiB`) |
| NVIDIA GPU / VRAM | Script đo không phát hiện GPU NVIDIA; không có `nvidia-smi`, VRAM được ghi là `N/A` |
| Mô hình / lượng tử hóa | `qwen3:1.7b` / `Q4_K_M` |
| Mã băm mô hình | `8f68893c685c3ddff2aa3fffce2aa60a30bb2da65ca488b61fff134a4d1730e7` |
| Kích thước file mô hình | `1,359,293,444 bytes` |
| C01: thời gian thực của API / tổng thời gian Ollama / thời gian nạp mô hình | `5.403 s` / `5.388 s` / `1.541 s` |
| C01: RAM trước khi chạy / đỉnh ghi nhận qua lấy mẫu / mức tăng | `14,679.3 MiB` / `16,599.3 MiB` / `+1,920.0 MiB` |
| C01: kiểm định JSON / metadata | Đạt; chưa hoàn thành review của giáo viên |
| C02: thời gian thực của API / tổng thời gian Ollama / thời gian nạp mô hình | `4.208 s` / `4.193 s` / `0.005 s` |
| C02: RAM trước khi chạy / đỉnh ghi nhận qua lấy mẫu / mức tăng | `16,599.4 MiB` / `16,696.1 MiB` / `+96.8 MiB` |
| C02: kiểm định JSON / metadata | Đạt; chưa hoàn thành review của giáo viên |

**Lưu ý về phép đo:**

- Thời gian thực của API được đo bằng `time.perf_counter` của Python; các trường thời gian của Ollama được chuyển từ nano giây sang giây.
- `psutil` lấy mẫu **tổng RAM đang được toàn hệ thống sử dụng**, không phải bộ nhớ chỉ riêng tiến trình Qwen sử dụng.
- Các giá trị VRAM NVIDIA là `null`/`N/A` vì không có phương thức đo tương ứng; **không được hiểu là mức sử dụng VRAM bằng không hoặc bằng chứng máy không có GPU khác**.
- Việc lấy mẫu có thể bỏ sót các đỉnh sử dụng bộ nhớ ngắn hạn. Lần gọi thứ hai được đo khi mô hình đã được nạp; chỉ có hai trường hợp được thử nghiệm nên chưa đủ cơ sở để kết luận chung về tốc độ hoặc chất lượng.

## 4. Profile JSON và mã giả chọn Blueprint theo quy tắc (Issue #19)

### 4.1. Contract và phạm vi

**Nguồn dữ liệu chuẩn:** M3 cung cấp **Student Profile JSON tĩnh**, có sẵn `evidence_count` và các giá trị `mastery_score` theo kỹ năng. Module này **không** duyệt `graded_records`, tính điểm chuẩn hóa, cập nhật mức độ thành thạo hoặc chấm bài bằng AI.

Để quyết định rẽ nhánh trong MVP, `evidence_count` được hiểu là **số lượng bằng chứng ở cấp học sinh do M3 cung cấp**. Nếu hồ sơ thực tế của M3 chỉ lưu số lượng theo từng kỹ năng, M3 và backend phải cung cấp một giá trị ở cấp học sinh đã được thống nhất **trước khi** gọi hàm rẽ nhánh này; M4 không được tự đặt công thức tổng hợp mà không thông báo.

**Interface minh họa** (cấu trúc trường là ví dụ tích hợp, không khẳng định đây là JSON cuối cùng của M3):

```json
{
  "student_id": "HS001",
  "grade_level": 10,
  "evidence_count": 3,
  "skill_mastery": [
    {"skill_id": "SK02", "mastery_score": 2.0},
    {"skill_id": "SK04", "mastery_score": 3.5}
  ],
  "priority_skill_ids": ["SK02"]
}
```

Các số `2.0` và `3.5` ở đây **chỉ là giá trị đầu vào minh họa**. Tài liệu này không định nghĩa thang đo hay tính các giá trị đó. Danh sách ưu tiên là metadata lập kế hoạch tùy chọn do thành phần phía trước cung cấp; nếu không có danh sách này, Exam Planner phải sử dụng cách diễn giải thang điểm thành thạo đã được quy định riêng, thay vì tự cho rằng một giá trị cụ thể có nghĩa là “yếu”.

**Quy tắc rẽ nhánh bắt buộc của Issue #19:**

| `evidence_count` ở cấp học sinh | Nhóm bằng chứng | Nhánh Blueprint |
|---:|---|---|
| `0` | `no_data` | `default` |
| `1` hoặc `2` | `partial` | `default` |
| `>= 3` | `sufficient` | `personalized` |

Ba nhóm này mô tả **mức độ đầy đủ của dữ liệu**, không phản ánh trực tiếp kiến thức hay trình độ tuyệt đối của học sinh.

### 4.2. Mã giả: phân loại bằng chứng và chọn Blueprint

```text
FUNCTION classify_evidence(student_profile):
    count = student_profile.evidence_count  // Provided by M3

    IF count IS MISSING OR count IS NOT A NONNEGATIVE INTEGER:
        RETURN {status: "invalid_profile", reason: "Invalid evidence_count"}

    IF count == 0:
        RETURN {status: "no_data", mode: "default"}

    IF count <= 2:
        RETURN {status: "partial", mode: "default"}

    RETURN {status: "sufficient", mode: "personalized"}
END FUNCTION


FUNCTION select_exam_blueprint(student_profile, topic_id, question_count):
    IF student_profile IS MISSING OR student_profile.student_id IS MISSING:
        RETURN {status: "invalid_request", reason: "Student profile required"}

    IF question_count IS NOT A POSITIVE INTEGER:
        RETURN {status: "invalid_request", reason: "Invalid question_count"}

    IF topic_id IS MISSING OR topic_id IS NOT SUPPORTED:
        RETURN {status: "invalid_request", reason: "Unsupported topic"}

    category = classify_evidence(student_profile)
    IF category.status == "invalid_profile":
        RETURN category  // Do not infer or fabricate evidence

    IF category.mode == "default":
        blueprint = DEFAULT_BLUEPRINT(topic_id, question_count)
    ELSE:
        // evidence_count >= 3: use the Personalized branch.
        // Read mastery_score / skill priorities from M3's profile;
        // never recalculate mastery inside this module.
        blueprint = PERSONALIZED_BLUEPRINT(
            student_profile, topic_id, question_count
        )

    IF blueprint CANNOT SATISFY question_count OR topic REQUIREMENTS:
        RETURN {
            status: "insufficient_question_bank",
            missing_slots: blueprint.missing_slots
        }

    RETURN {
        status: "ready",
        student_id: student_profile.student_id,
        topic_id: topic_id,
        evidence_status: category.status,
        generation_mode: category.mode,
        blueprint: blueprint
    }
END FUNCTION
```

`DEFAULT_BLUEPRINT` và `PERSONALIZED_BLUEPRINT` biểu diễn interface của các bộ lập kế hoạch, không phải phần triển khai đã hoàn thành trong `qwen_spike.py`. **Ngưỡng và tên nhánh ở trên được cố định theo Issue #19**; chi tiết chính sách bên trong các bộ lập kế hoạch được mô tả riêng ở Mục 7.

### 4.3. Các trường hợp kiểm thử rẽ nhánh và ví dụ

| Trường hợp | Đầu vào hồ sơ | Kết quả mong đợi |
|---|---|---|
| Học sinh mới | `evidence_count = 0` | `no_data` → Default Blueprint |
| Có một phần bằng chứng | `evidence_count = 1` | `partial` → Default Blueprint |
| Có một phần bằng chứng | `evidence_count = 2` | `partial` → Default Blueprint |
| Đủ bằng chứng | `evidence_count = 3` | `sufficient` → Personalized Blueprint |
| Có thêm bằng chứng | `evidence_count = 5` | `sufficient` → Personalized Blueprint |
| Hồ sơ không hợp lệ | Số lượng âm, bị thiếu hoặc không phải số nguyên | `invalid_profile`; yêu cầu sửa dữ liệu |

**Giới hạn diễn giải:** Học sinh vẫn có thể cần được hỗ trợ nhiều dù `evidence_count >= 3`, và vẫn có thể thể hiện điểm mạnh khi chỉ có hai bản ghi bằng chứng. `evidence_count` chọn nhánh; thông tin kỹ năng riêng biệt quyết định **nhánh cá nhân hóa sẽ thực hiện những điều chỉnh nào**.

## 5. Rủi ro và cơ chế dự phòng (fallback)

| Rủi ro / trường hợp biên | Cách xử lý / giới hạn |
|---|---|
| Thiếu hoặc sai `evidence_count` ở cấp học sinh | Từ chối/đánh dấu hồ sơ sai cấu trúc và yêu cầu M3/backend sửa; không tự đặt công thức tổng hợp |
| `evidence_count` bằng 0, 1 hoặc 2 | Luôn dùng Default Blueprint theo yêu cầu của Issue #19 |
| Đủ bằng chứng nhưng thiếu hoặc chưa có tài liệu về ưu tiên kỹ năng hay thang điểm | Chọn nhánh Personalized; đánh dấu đầu vào còn thiếu thay vì tự xếp hạng kỹ năng |
| Chủ đề hoặc số câu yêu cầu nằm ngoài khả năng của ngân hàng câu hỏi | Trả `insufficient_question_bank` / lỗi rõ ràng, không thay bằng nội dung sai yêu cầu |
| Mô hình cục bộ không sẵn sàng, hết bộ nhớ hoặc quá thời gian chờ | Ghi log lỗi runtime; dùng fallback đã cấu hình hoặc dừng; không bịa nội dung đã sinh |
| Qwen trả JSON không hợp lệ hoặc thay đổi ràng buộc | Validator từ chối hoặc đánh dấu để review; backend điều phối việc thử lại với số lần giới hạn |
| Đúng cú pháp nhưng sai ngữ nghĩa toán học | Kiểm tra tự động chưa đầy đủ; cần giáo viên review trước khi phát hành |
| Chỉ thay đổi câu chữ nhưng lặp lại nội dung | Bộ kiểm tra độ đa dạng so sánh các câu ứng viên với câu đã dùng; không coi cách diễn đạt mới là nội dung toán học mới |
| Không thể lấy mẫu VRAM của GPU ngoài NVIDIA | Báo `N/A`, không báo `0` |
| Dữ liệu học sinh xuất hiện trong prompt Qwen | Chỉ gửi dữ kiện toán học cần thiết và ngữ cảnh tối thiểu không nhạy cảm; không đưa thông tin định danh học sinh vào prompt |

## 6. Kết quả thực tế và diễn giải

**Trạng thái thử nghiệm cơ sở: đã hoàn thành trên phần cứng cục bộ ngày 2026-10-19.**

- Qwen3-1.7B cục bộ đã sinh hai câu hỏi Đại số tổ hợp bằng tiếng Việt.
- Cả hai đầu ra đều đạt kiểm tra JSON và metadata của thử nghiệm cơ sở (`2/2`).
- Đáp án tham chiếu do Python tính bằng quy tắc xác định lần lượt là `56` và `210`.
- Thời gian thực của API đo được là `5.403 s` và `4.208 s`.
- Đã lấy mẫu RAM hệ thống; không có số liệu VRAM NVIDIA.
- **Chưa ghi nhận kết quả review ngữ nghĩa của giáo viên**. Các kết quả này chưa xác lập tỷ lệ đúng toán học nói chung.
- Mã giả rẽ nhánh theo hồ sơ đã được đồng bộ với Issue #19 nhưng **không** chứng minh rằng đã có runtime tích hợp với Profile JSON thực tế của M3.

## 7. Kiến trúc sinh câu hỏi dự kiến cho MVP (đề xuất thiết kế sản phẩm)

> Mục này ghi lại ý tưởng sản phẩm đang được nhóm phát triển, **không phải các tiêu chí nghiệm thu bổ sung của Issue #19**. Nội dung này cũng không thay thế số liệu thử nghiệm cơ sở đã đo ở các mục 2–3.

### 7.1. Đầu vào và thứ tự xử lý

Backend nhận `student_profile`, `question_count` và `topic_id` do giáo viên chọn. MVP hiện hỗ trợ `topic_id = "combinatorics"`, nhưng vẫn giữ trường này để mở rộng sang môn học/chủ đề khác sau này.

```text
Student Profile + Teacher Request (topic_id, question_count)
    -> Rule-based Exam Planner (Section 4: Default / Personalized)
    -> Choose suitable mathematical problems from Dataset
    -> Content & Expression Planner (context + direct / indirect)
    -> Local Qwen Generator (Vietnamese question candidates)
    -> Validator (five automated layers)
    -> Exam Assembler (draft + numbered questions + stored answers)
    -> Teacher review (sixth validation layer)
    -> Approved exam, or revision / rejection
```

**Bản ghi bài toán phía dataset (minh họa):** giữ `question_id` (hoặc mã định danh bài toán ổn định tương ứng), `topic_id`, `skill_ids`, `difficulty` theo bốn mức, các điều kiện và tham số toán học ở dạng máy có thể đọc, cùng **đáp án tham chiếu và phương pháp giải đã được kiểm chứng**. Chuỗi `content` tiếng Việt hoàn chỉnh và `generate_type` **không bắt buộc phải có trong bản ghi toán học nguồn**. Nếu bảng SQL `Questions` hiện tại tiếp tục lưu `content` đã diễn đạt, nhóm dataset/backend cần phân biệt **dữ liệu toán học nguồn** với **câu chữ được sinh ra** trong mô hình lưu trữ.

### 7.2. Chính sách lập kế hoạch theo quy tắc: kỹ năng và độ khó

**Bảy nhóm kỹ năng đã thống nhất** (các ID dưới đây là nhãn interface được đề xuất, không phải ID chuẩn đã tồn tại trong SQL):

| ID minh họa | Nhóm kỹ năng |
|---|---|
| `SK01` | Năng lực tính toán cơ bản |
| `SK02` | Khả năng hiểu và biểu diễn bài toán |
| `SK03` | Quy tắc cộng, quy tắc nhân |
| `SK04` | Hoán vị, chỉnh hợp, tổ hợp |
| `SK05` | Phân tích điều kiện và ràng buộc |
| `SK06` | Lựa chọn chiến lược giải |
| `SK07` | Kiểm tra và đánh giá kết quả |

**Bốn nhãn độ khó đã thống nhất:**

- `recognition` – Nhận biết
- `comprehension` – Thông hiểu
- `application` – Vận dụng
- `advanced_application` – Vận dụng cao

Thang `difficulty` từ 1–6 từng được đề cập trước đây **không được sử dụng** trong thiết kế mục tiêu này.

**Phân bổ độ khó mặc định được đề xuất cho dự án:** lần lượt là 20% / 40% / 30% / 10%. Với 10 câu hỏi, số câu tương ứng là 2 / 4 / 3 / 1. Với số câu yêu cầu khác, dùng quy tắc làm tròn xác định sao cho tổng luôn bằng `question_count`; một mức có thể không có câu nào trong đề rất ngắn. Phân bổ này phản ánh thiết kế sản phẩm do M4 thảo luận, **không phải ngưỡng định lượng do Issue #19 đưa ra**.

**Đề xuất chính sách cá nhân hóa:** ban đầu giữ nguyên phân bổ độ khó bốn mức nhưng **ưu tiên các kỹ năng đã được xác định là cần luyện tập thêm**. Backend sử dụng thông tin ưu tiên từ hồ sơ hoặc chính sách đã được phê duyệt để diễn giải `mastery_score` của M3; **backend không tính mức độ thành thạo**. Có thể thử tỷ lệ 60% cho các kỹ năng ưu tiên và 40% cho các kỹ năng khác nếu ngân hàng câu hỏi đáp ứng được; đây là chính sách lập kế hoạch có thể điều chỉnh, không phải quy tắc của Issue #19.

Kế hoạch cần ưu tiên sự phù hợp về chủ đề và kỹ năng, phân bổ mức độ nhận thức hợp lý và tránh lặp lại quá nhiều. Chỉ gắn nhãn kỹ năng cho câu hỏi khi việc giải câu đó thực sự rèn luyện kỹ năng tương ứng. Nếu ngân hàng câu hỏi không đáp ứng được kế hoạch, phải báo các vị trí câu hỏi còn thiếu.

### 7.3. Bộ lập kế hoạch nội dung và cách diễn đạt (Content & Expression Planner)

Backend chọn **ngữ cảnh** phù hợp (ví dụ: chọn các học sinh khác nhau vào một nhóm, phân công vai trò trong ban cán sự) **sau khi** chọn bài toán. Ngữ cảnh phải giữ nguyên ý nghĩa toán học ban đầu; việc chọn ngẫu nhiên danh từ mà không có ràng buộc có thể làm thay đổi tính phân biệt của đối tượng hoặc việc có xét thứ tự hay không.

Enum `generate_type` đã chốt có **đúng hai giá trị**:

- `direct`: trình bày rõ dữ kiện số và ràng buộc cần thiết để người học dễ nhận ra cấu trúc bài toán.
- `indirect`: dùng tình huống dễ hiểu, yêu cầu người học tự nhận diện cấu trúc toán học; **không** thêm điều kiện toán học mới hoặc dữ kiện gây nhiễu không liên quan.

`generate_type` độc lập với nhãn `difficulty` theo bốn mức.

**Đề xuất cá nhân hóa cách diễn đạt:** với kỹ năng cần hỗ trợ nhiều hơn, ban đầu chọn nhiều câu `direct` và ít câu `indirect` hơn (ví dụ: tỷ lệ 80/20 có thể cấu hình). Đây là **chính sách trình bày** được quyết định trước khi gọi Qwen, **không** phải thuộc tính suy ra từ `evidence_count` và **không** phải quy tắc để Qwen tự chọn. Nếu chưa có chỉ báo đáng tin cậy về mức hỗ trợ cần thiết, dùng giá trị mặc định được cấu hình rõ ràng thay vì suy mức độ yếu của học sinh từ số lượng bằng chứng.

### 7.4. Mã giả: bộ sinh câu hỏi Qwen cục bộ (chỉ Module 4)

```text
FUNCTION qwen_generate_question(
    problem_data,
    context,
    generate_type,
    model_config,
    previous_validation_errors = []
):
    IF problem_data IS MISSING OR context IS MISSING:
        RETURN {status: "generation_error", reason: "Missing input"}

    IF generate_type NOT IN ["direct", "indirect"]:
        RETURN {status: "generation_error", reason: "Invalid generate_type"}

    IF generate_type == "direct":
        expression_instruction =
            "State the provided mathematical facts clearly and explicitly."
    ELSE:
        expression_instruction =
            "Use a natural situation so students must identify the math structure."

    prompt = BUILD_PROMPT(
        mathematical_facts = problem_data,
        approved_context = context,
        expression_instruction = expression_instruction,
        feedback = previous_validation_errors,
        constraints = [
            "Write exactly one Vietnamese open-ended question",
            "Preserve ALL original mathematical quantities and constraints",
            "Do not add/remove mathematical conditions or irrelevant facts",
            "Do not change the operation, order rules or object distinctions",
            "Do not generate or recalculate the reference answer",
            "Return JSON containing only a question string"
        ]
    )

    start_time = CURRENT_TIME()

    TRY:
        raw_response = OLLAMA_GENERATE(
            model = model_config.model_name,
            prompt = prompt,
            temperature = model_config.temperature,
            seed = model_config.seed,
            stream = FALSE,
            format = "json"
        )
    CATCH inference_error:
        RETURN {status: "generation_error", reason: inference_error}

    RETURN {
        status: "pending_validation",
        raw_response: raw_response,
        generate_type: generate_type,
        model: model_config.model_name,
        latency_seconds: CURRENT_TIME() - start_time
    }
END FUNCTION
```

**Response contract đề xuất cho Qwen:** `{"question": "..."}`. Ứng dụng bao quanh giữ `problem_data`, đáp án đã kiểm chứng, `skill_ids`, `difficulty` và `generate_type` được yêu cầu. Qwen **không** tạo các trường dữ liệu chuẩn này. Lớp kiểm định đầu tiên phân tích cú pháp và kiểm tra JSON do Qwen trả về.

### 7.5. Kiểm định và thử lại có giới hạn (điều phối tại backend)

**Sáu lớp kiểm định:** (1) cấu trúc JSON, (2) dữ kiện và ràng buộc toán học, (3) mức độ tuân thủ cách diễn đạt direct/indirect, (4) tính tương đương của đáp án so với bài toán tham chiếu, (5) độ đa dạng / phát hiện gần trùng lặp và (6) giáo viên review. Các lớp 1–5 được dự kiến dùng để sàng lọc tự động. Lớp 6 là phê duyệt bản nháp đã chuẩn bị; kết quả tự động `pass` không đồng nghĩa với `teacher_approved`.

**Quy tắc kiểm tra đáp án:** không chỉ yêu cầu chính mô hình Qwen giải câu hỏi nó vừa sinh rồi tin vào việc hai kết quả trùng nhau. Trong phạm vi được hỗ trợ, cần phân tích/xác minh ràng buộc và kiểm tra bằng code xác định; nếu chưa xác lập được tính tương đương ngữ nghĩa, đánh dấu để giáo viên review. Một AI khác có thể hỗ trợ trích xuất điều kiện như tín hiệu phụ, không phải bằng chứng toán học duy nhất.

```text
FUNCTION create_candidate_with_retry(problem_data, context, generate_type, config):
    errors = []

    FOR attempt FROM 1 TO config.max_attempts:
        attempt_config = COPY(config)
        attempt_config.seed = config.seed + attempt - 1

        candidate = qwen_generate_question(
            problem_data, context, generate_type,
            attempt_config, previous_validation_errors = errors
        )

        IF candidate.status == "generation_error":
            errors = [candidate.reason]
            CONTINUE

        verdict = VALIDATE_AUTOMATED_LAYERS_1_TO_5(
            original_problem = problem_data,
            approved_context = context,
            requested_generate_type = generate_type,
            generated_response = candidate.raw_response
        )

        IF verdict.status == "pass":
            RETURN {status: "pending_teacher_review", candidate: candidate}

        IF verdict.status == "needs_review":
            RETURN {status: "pending_teacher_review", candidate: candidate,
                    review_notes: verdict.errors}

        errors = verdict.errors  // FAIL: retry with a bounded attempt count

    RETURN {status: "generation_failed", reasons: errors}
END FUNCTION
```

Hàm thử lại này thuộc **tầng điều phối backend**, không thuộc chính thành phần suy luận Qwen. Các seed được sử dụng qua những lần thử có thể tăng mức độ biến đổi nhưng **không bảo đảm** đầu ra khác biệt hoặc chính xác. Sinh nhiều cách diễn đạt thay thế để tăng độ đa dạng là một tính năng tùy chọn riêng.

### 7.6. JSON đầu ra đề thi được đề xuất và điều kiện phát hành

**Phiên bản dành cho giáo viên/backend** của đề đã tổng hợp chứa nội dung câu hỏi được đánh số, mã định danh nguồn gốc, độ khó, ID kỹ năng, kiểu sinh câu hỏi, đáp án tham chiếu đã lưu, kết quả kiểm định và trạng thái review của giáo viên. **Phiên bản dành cho học sinh không được chứa đáp án tham chiếu hoặc metadata kiểm định nội bộ**.

```json
{
  "exam_id": "EXAM001",
  "student_id": "HS001",
  "topic_id": "combinatorics",
  "question_count": 1,
  "generation_mode": "personalized",
  "status": "pending_teacher_review",
  "questions": [
    {
      "question_order": 1,
      "question_id": "Q001",
      "skill_ids": ["SK02", "SK04"],
      "difficulty": "comprehension",
      "generate_type": "indirect",
      "content": "Một lớp có 8 học sinh. Giáo viên muốn lập nhóm 3 bạn; hai nhóm chỉ khác nhau khi có ít nhất một thành viên khác nhau. Có bao nhiêu nhóm?",
      "answer": {
        "correct_answer": "56",
        "explanation": "C(8,3) = 56"
      },
      "validation": {
        "auto_status": "pass",
        "teacher_approved": false
      }
    }
  ]
}
```

JSON một câu hỏi này là **ví dụ về interface**, không phải đầu ra Qwen đã ghi nhận và không minh họa phân bổ 20/40/30/10 (phân bổ này áp dụng khi số câu cho phép). Bộ tổng hợp đề thi thực tế phải đáp ứng số câu được yêu cầu hoặc báo các vị trí chưa đáp ứng. Cần duy trì khả năng truy vết giữa mã định danh trong dataset nguồn và mã định danh câu hỏi được sinh, kể cả khi chúng được lưu thành các bản ghi riêng.

## 8. Ranh giới triển khai và các bước tiếp theo

**Đã chứng minh qua thử nghiệm (Issue #6):** suy luận bằng Qwen cục bộ cho hai trường hợp mẫu, file JSON kết quả có thể tạo lại khi chạy thử nghiệm, số liệu đo độ trễ và lấy mẫu RAM hệ thống.

**Tài liệu đã được đồng bộ cho Issue #19:** không có vòng lặp `graded_records`; sử dụng Profile JSON tĩnh của M3; bắt buộc dùng default khi số bằng chứng là 0 hoặc 1–2, dùng personalized khi >=3; giữ nguyên số liệu thử nghiệm cơ sở đã hoàn thành. Việc đồng bộ này là **thay đổi tài liệu/mã giả**, không khẳng định đã có code tích hợp.

**Các bước kỹ thuật tiếp theo (công việc triển khai riêng):**

1. Thống nhất với M3/backend về đường dẫn các trường trong Profile JSON thực tế, ý nghĩa của `evidence_count` **ở cấp học sinh** và cách diễn giải thang điểm `mastery_score` đầu vào.
2. Định nghĩa bản ghi bài toán ở dạng máy có thể đọc và quy tắc tương thích ngữ cảnh; không yêu cầu Qwen trong phiên bản triển khai thực tế tự tạo ID câu hỏi hoặc đáp án.
3. Triển khai Exam Planner hai nhánh và phân bổ số câu được yêu cầu theo quy tắc xác định.
4. Triển khai Content & Expression Planner, chỉ sử dụng `direct` và `indirect`.
5. Chuyển `qwen_spike.py` thành adapter sinh câu hỏi độc lập theo Mục 7.4, không thay đổi bằng chứng thử nghiệm cơ sở đã ghi nhận.
6. Xây dựng tập kiểm thử tập trung vào lỗi cho cả năm lớp kiểm định tự động, bao gồm các trường hợp cố ý thêm điều kiện, đổi số liệu, đổi thứ tự/quy tắc lặp, trùng lặp và diễn đạt không rõ; thu thập nhãn review của giáo viên về tính đúng đắn ngữ nghĩa.
7. Tích hợp thử lại có giới hạn, tổng hợp đề thi và phê duyệt của giáo viên; không đưa đáp án vào response dành cho học sinh.

**Ngoài phạm vi giai đoạn này:** giáo viên chấm bài làm đã hoàn thành của học sinh, AI cập nhật mức độ thành thạo của người học, fine-tuning tự động hoặc tự do tạo cấu trúc toán học không có giới hạn.
