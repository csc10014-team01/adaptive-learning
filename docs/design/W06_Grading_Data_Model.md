# Thiết kế dữ liệu chấm bài và cơ chế cập nhật hồ sơ năng lực
Trình bày: Nguyễn Ngọc Ánh Dương

Ví dụ chạy tay:
https://chatgpt.com/c/6af05643-db64-83ec-959a-c552c18801e4

## Tóm tắt:
- Dùng **Partial Credit Model (PCM)** để tính xác xuất đúng bước đó của học sinh dựa trên các bước học sinh làm đúng và độ khó của bước đó.
- Dùng EAP ability estimation (dichotomous and polytomous IRT models) để tính điểm mong đợi của từng câu.
- Quy đổi sang mastery_score
## 1. Mục tiêu

Sử dụng **Partial Credit Model (PCM)** để đánh giá mức độ thành thạo của
học sinh theo từng kỹ năng (`skill_id`) dựa trên kết quả chấm rubric của
từng câu hỏi.

Thiết kế gồm hai tầng:

1. **Tầng câu hỏi:** dùng Partial Credit Model (PCM) để tính xác suất đạt từng mức rubric; dùng Bayesian EAP để ước lượng năng lực đại diện `theta_eap` từ kết quả rubric của câu hỏi đó.
2. **Tầng kỹ năng:** quy đổi `theta_eap` qua một bộ PCM tham chiếu chung thành `question_mastery_score`, rồi tổng hợp các bằng chứng của cùng `skill_id` để cập nhật `mastery_score`.

> **Lưu ý học thuật:** PCM nguyên bản thường ước lượng năng lực từ một tập hợp câu hỏi. Thiết kế này áp dụng PCM ở cấp từng câu hỏi, kết hợp prior Bayesian để có thể xử lý một kết quả rubric đơn lẻ. Vì vậy, nên mô tả đây là cơ chế chấm điểm dựa trên PCM ở cấp câu hỏi, không phải quy trình ước lượng năng lực PCM nguyên bản trên toàn bài kiểm tra.

## 2. Quy ước và dữ liệu đầu vào

### 2.1. Rubric

Rubric gồm các mức có thứ tự từ `0` đến `m`. Ví dụ rubric 0–4:

| Mức | Mô tả |
|---:|---|
| 0 | Chưa nhận diện được phép tổ hợp |
| 1 | Nhận diện được tình huống chọn nhóm |
| 2 | Thiết lập đúng biểu thức tổ hợp |
| 3 | Thực hiện phần lớn phép tính đúng |
| 4 | Giải đúng và kết luận đầy đủ |

`observed_level` là mức rubric thực tế học sinh đạt được, thuộc `[0, m]`.

### 2.2. Step difficulties

Trong PCM, `step_difficulty` là độ khó của **bước chuyển từ mức điểm trước sang mức điểm tiếp theo**, không phải độ khó của bản thân mức điểm.

Với rubric 0–4 có bốn bước chuyển:

| Bước | Chuyển mức |
|---:|---|
| 1 | 0 → 1 |
| 2 | 1 → 2 |
| 3 | 2 → 3 |
| 4 | 3 → 4 |

Ví dụ:

```python
step_difficulties = [-0.5, 0.5, 1.0, 1.5]
```

Các giá trị trên chỉ là dữ liệu giả định để minh họa. Khi triển khai thực tế, tham số cần được hiệu chuẩn từ dữ liệu phản hồi của học sinh. `step_difficulties`, prior và bộ tham chiếu phải nằm trên cùng một thang đo năng lực.

Có thể quy đổi lựa chọn độ khó của giáo viên (0–4) theo đề xuất:

| Giáo viên chọn | Ý nghĩa | `step_difficulty` |
|---:|---|---:|
| 0 | Rất dễ | -1.5 |
| 1 | Dễ | -0.75 |
| 2 | Trung bình | 0 |
| 3 | Khó | 0.75 |
| 4 | Rất khó | 1.5 |

Công thức quy đổi:

\[
b = 0.75(d - 2)
\]

Trong đó `d` là độ khó giáo viên chọn và `b` là giá trị difficulty trên thang PCM. Nếu mỗi bước có độ khó riêng, thực hiện phép quy đổi cho từng bước để tạo thành vector `step_difficulties`.

## 3. Thiết kế dữ liệu

Các bảng dưới đây là cấu trúc logic đề xuất. Có thể điều chỉnh tên cột theo convention của dự án.

### 3.1. Nhóm dữ liệu câu hỏi và tham số PCM

#### `QuestionTemplate`

Lưu thông tin template câu hỏi và rubric mặc định.

Các trường liên quan:

- `template_id`: khóa định danh template.
- `rubric`: cấu hình các mức rubric mặc định, nếu rubric được lưu dạng JSON.
- `max_level`: mức rubric tối đa, ví dụ `4`.

#### `QuestionRubric`

Chỉ cần khi câu hỏi có rubric riêng hoặc rubric tùy chỉnh.

- `question_id`: câu hỏi áp dụng rubric.
- `rubric`: mô tả các mức rubric.
- `max_level`: mức tối đa của rubric.
- `version`: phiên bản rubric.

#### `PCMTemplateParameters`

Lưu tham số PCM dùng chung cho các câu hỏi thuộc template.

- `template_id`
- `step_difficulties`: vector độ khó của các bước chuyển.
- `version`
- `calibration_status`: trạng thái hiệu chuẩn tham số.

#### `PCMQuestionParameters`

Chỉ cần khi một câu hỏi có bộ tham số PCM riêng, độc lập với template.

- `question_id`
- `step_difficulties`
- `version`
- `calibration_status`

Khi lấy tham số cho một câu, hệ thống ưu tiên tham số riêng của câu hỏi nếu có; nếu không thì lấy tham số của template.

### 3.2. Nhóm dữ liệu bài kiểm tra và kết quả

#### `Test`

Lưu thông tin bài kiểm tra.

- `test_id`
- `student_id`
- `created_at` / `submitted_at`
- Các trường thông tin bài kiểm tra khác của hệ thống.

#### `TestQuestion`

Lưu câu hỏi được đưa vào bài kiểm tra và kết quả chấm của học sinh.

- `test_id`
- `question_id`
- `observed_level`: mức rubric học sinh đạt được.
- `theta_eap`: năng lực EAP ước lượng từ kết quả câu hỏi này.
- `question_mastery_score`: điểm thành thạo sau khi quy đổi qua bộ tham chiếu.
- `pcm_parameter_version`: phiên bản tham số PCM đã sử dụng.
- `reference_parameter_version`: phiên bản bộ tham chiếu đã sử dụng.
- `prior_version`: phiên bản prior đã sử dụng.

Nếu mỗi câu chỉ đánh giá một kỹ năng, có thể lưu `skill_id` trực tiếp trong `TestQuestion` hoặc truy xuất thông qua `question_skills`.

#### `question_skills`

Ánh xạ câu hỏi với kỹ năng.

- `question_id`
- `skill_id`

Nếu một câu hỏi đánh giá nhiều skill, cần có kết quả rubric độc lập cho từng skill. Không dùng một `observed_level` chung để suy ra nhiều năng lực khác nhau.

Trong trường hợp một câu có thể đánh giá nhiều skill, nên dùng bảng kết quả chi tiết sau.

#### `TestQuestionSkillResult`

Mỗi dòng đại diện cho một kết quả đánh giá của một câu hỏi đối với một skill.

- `test_id`
- `question_id`
- `skill_id`
- `observed_level`
- `theta_eap`
- `question_mastery_score`
- `pcm_parameter_version`
- `reference_parameter_version`
- `prior_version`

Khóa duy nhất nên bảo đảm một bài kiểm tra không tạo trùng bằng chứng cho cùng một cặp câu hỏi–skill, ví dụ `(test_id, question_id, skill_id)`.

### 3.3. Nhóm hồ sơ năng lực

#### `student_skill_mastery`

Lưu trạng thái mastery hiện tại của từng học sinh theo từng kỹ năng.

- `student_id`
- `skill_id`
- `mastery_score`: điểm thành thạo tổng hợp.
- `evidence_count`: số kết quả đánh giá hợp lệ đã được dùng làm bằng chứng.
- `updated_at`

Khóa duy nhất: `(student_id, skill_id)`.

### 3.4. Quan hệ dữ liệu tổng quát

```text
Student
  |
  | 1 - n
  v
Test
  |
  | 1 - n
  v
TestQuestion ---------------- Question
  |                               |
  |                               | n - n
  |                               v
  |                         question_skills
  |                               |
  |                               v
  |                             Skill
  |
  |-- observed_level
  |-- theta_eap
  |-- question_mastery_score
  |
  v
TestQuestionSkillResult (nếu một câu đánh giá nhiều skill)
  |
  | nhóm theo student_id + skill_id
  v
student_skill_mastery
  |-- mastery_score
  |-- evidence_count
```

## 4. Hàm tính xác suất PCM

Với câu hỏi `i`, rubric có mức tối đa `m`, vector độ khó chuyển mức là:
$$
\[
\boldsymbol{\delta}_i =
[\delta_{i1}, \delta_{i2}, \ldots, \delta_{im}]
\]
$$
Với một giá trị năng lực thử nghiệm \(\theta\), xác suất đạt mức rubric `k` theo PCM:
$$
\[
P(X_i=k\mid\theta)=
\frac{
\exp\left(\sum_{j=1}^{k}(\theta-\delta_{ij})\right)
}{
\sum_{r=0}^{m}
\exp\left(\sum_{j=1}^{r}(\theta-\delta_{ij})\right)
}
\]
$$
Quy ước tổng rỗng tại `k = 0` bằng 0, do đó tử số của mức 0 bằng `exp(0) = 1`.

### Prototype

```python
def pcm_probability(
    theta: float,
    step_difficulties: list[float],
) -> list[float]:
    """
    Trả về xác suất đạt từng mức rubric [0, ..., m].

    Parameters
    ----------
    theta:
        Giá trị năng lực tiềm ẩn đang xét.
    step_difficulties:
        Vector độ khó của các bước chuyển mức.
        Với rubric 0–4, vector có 4 phần tử tương ứng
        các bước 0→1, 1→2, 2→3, 3→4.

    Returns
    -------
    list[float]:
        Danh sách xác suất [P(X=0), ..., P(X=m)].
        Tổng các xác suất bằng 1.
    """
```

**Giải thích parameter:**

- `theta`: một giá trị năng lực giả định. Hàm không tự ước lượng `theta`; nó chỉ tính phân phối xác suất rubric tại giá trị đó.
- `step_difficulties`: độ khó của từng bước chuyển rubric. Số phần tử bằng mức rubric tối đa `m`.
- Kết quả có `m + 1` phần tử, lần lượt là xác suất đạt các mức `0, 1, ..., m`.

Khi triển khai, nên dùng `log-sum-exp` hoặc chuẩn hóa bằng cách trừ logit lớn nhất trước khi lấy hàm mũ để hạn chế tràn số.

## 5. Hàm ước lượng EAP cho từng câu hỏi

### 5.1. Ý nghĩa EAP

EAP (Expected A Posteriori) là trung bình của phân phối hậu nghiệm năng lực sau khi kết hợp:

- Khả năng quan sát kết quả rubric nếu học sinh có năng lực \(\theta\), được tính bằng PCM.
- Phân phối prior mô tả giả định ban đầu về năng lực.

Giả sử prior:

$$
\[
\theta \sim N(\mu_0,\sigma_0^2)
\]
$$
Có thể khởi tạo:
$$
\[
\mu_0=0,\qquad \sigma_0=1
\]
$$

Đây là giả định khởi tạo, không phải tham số bắt buộc của PCM. Prior phải nhất quán với thang đo của `step_difficulties` và bộ tham chiếu.

Với kết quả quan sát `x`, mật độ hậu nghiệm chưa chuẩn hóa:

$$
\[
p(\theta\mid X=x)
\propto
P(X=x\mid\theta)\,
\phi(\theta;\mu_0,\sigma_0^2)
\]
$$

Trong đó \(\phi\) là mật độ phân phối chuẩn. EAP là:

$$
\[
\hat{\theta}_{EAP}=
\frac{
\int_{-\infty}^{+\infty}
\theta\,P(X=x\mid\theta)\,
\phi(\theta;\mu_0,\sigma_0^2)\,d\theta
}{
\int_{-\infty}^{+\infty}
P(X=x\mid\theta)\,
\phi(\theta;\mu_0,\sigma_0^2)\,d\theta
}
\]
$$

Có thể tính gần đúng bằng numerical integration hoặc grid approximation trên một miền theta đủ rộng.

### Prototype

```python
def estimate_eap(
    observed_level: int,
    step_difficulties: list[float],
    prior_mean: float = 0.0,
    prior_std: float = 1.0,
    theta_grid: list[float] | None = None,
) -> float:
    """
    Ước lượng theta EAP từ một kết quả rubric của một câu hỏi.

    Parameters
    ----------
    observed_level:
        Mức rubric thực tế học sinh đạt được, từ 0 đến m.
    step_difficulties:
        Vector độ khó các bước chuyển mức của câu hỏi.
    prior_mean:
        Trung bình của phân phối prior năng lực.
    prior_std:
        Độ lệch chuẩn của phân phối prior; phải lớn hơn 0.
    theta_grid:
        Các điểm theta dùng để xấp xỉ tích phân.
        Nếu không truyền vào, hàm sử dụng grid mặc định
        do module cấu hình.

    Returns
    -------
    float:
        Giá trị theta EAP của kết quả câu hỏi.
    """
```

**Giải thích parameter:**

- `observed_level`: kết quả chấm rubric của học sinh. Giá trị hợp lệ nằm trong `[0, m]`.
- `step_difficulties`: vector tham số PCM của đúng câu hỏi đang được chấm.
- `prior_mean`: trung bình prior. Với khởi tạo chuẩn hóa thường dùng `0`. Và bằng theta_eap của câu hỏi có skill_id đó gần nhất được cập nhật.
- `prior_std`: độ lệch chuẩn prior. Ví dụ `1.0`; không được bằng hoặc nhỏ hơn 0.
- `theta_grid`: lưới các giá trị năng lực dùng để xấp xỉ tích phân. Grid cần đủ rộng và đủ mịn để kết quả ổn định.

`estimate_eap()` có thể gọi `pcm_probability(theta, step_difficulties)` tại từng điểm trong grid để lấy likelihood của `observed_level`, sau đó nhân với mật độ prior và chuẩn hóa trọng số hậu nghiệm.

> Một kết quả rubric đơn lẻ chỉ cung cấp lượng bằng chứng hạn chế. EAP tạo ra một ước lượng hữu hạn và ổn định hơn nhờ prior, nhưng không đồng nghĩa độ tin cậy của ước lượng đã cao.

## 6. Quy đổi EAP thành `question_mastery_score`

### 6.1. Vì sao không lấy trực tiếp EAP làm mastery?

`theta_eap` nằm trên thang năng lực tiềm ẩn, có thể âm hoặc dương và không phải điểm rubric 0–4. Trong khi đó, `mastery_score` của hệ thống cần một thang dễ diễn giải và tổng hợp.

Do đó, cần quy đổi `theta_eap` qua một bộ tham chiếu PCM chung.

### 6.2. Bộ tham chiếu chung

Ví dụ với rubric 0–4:
$$
\[
\boldsymbol{\delta}_{ref}=
[-1.5,-0.5,0.5,1.5]
\]
$$
Đây là giá trị minh họa. Bộ tham chiếu thực tế phải cùng thang đo năng lực với các tham số câu hỏi và được giữ cố định trong cùng một phiên bản hệ thống.

Tính xác suất rubric tham chiếu tại `theta_eap`:
$$
\[
P_{ref}(X=k\mid\theta_{EAP})=
\frac{
\exp\left(\sum_{j=1}^{k}(\theta_{EAP}-\delta_{ref,j})\right)
}{
\sum_{r=0}^{m}
\exp\left(\sum_{j=1}^{r}(\theta_{EAP}-\delta_{ref,j})\right)
}
\]
$$
Điểm mastery của câu hỏi:
$$
\[
question\_mastery\_score
=
\sum_{k=0}^{m}
kP_{ref}(X=k\mid\hat{\theta}_{EAP})
\]
$$
Với rubric 0–4, điểm nằm trong `[0, 4]`.

**Ý nghĩa:** mỗi câu hỏi có bộ difficulty riêng để ước lượng `theta_eap`, nhưng sau đó mọi `theta_eap` đều được quy đổi bằng cùng một bộ tham chiếu. Nhờ vậy, các kết quả từ câu dễ và câu khó có cùng thang diễn giải trước khi tổng hợp theo skill.

### 6.3. Dữ liệu cần lưu cho từng câu trong từng test

Mỗi kết quả câu hỏi nên lưu tối thiểu:

| Trường | Ý nghĩa |
|---|---|
| `test_id` | Bài kiểm tra chứa câu hỏi |
| `question_id` | Câu hỏi được đánh giá |
| `observed_level` | Mức rubric học sinh đạt |
| `theta_eap` | Điểm năng lực EAP ước lượng từ câu hỏi |
| `question_mastery_score` | Điểm mastery đã quy đổi qua bộ tham chiếu |
| `pcm_parameter_version` | Phiên bản tham số PCM dùng để ước lượng EAP |
| `reference_parameter_version` | Phiên bản bộ tham chiếu dùng để quy đổi |
| `prior_version` | Phiên bản prior |

**Không lưu một `theta_eap` duy nhất cho toàn bộ test nếu mục tiêu của thiết kế là theo dõi năng lực từ từng câu hỏi.** Với một test có 5 câu, hệ thống có thể lưu 5 giá trị `theta_eap` tương ứng 5 kết quả câu hỏi (hoặc nhiều hơn nếu có kết quả độc lập theo skill).

Nếu một câu đánh giá nhiều skill, mỗi skill phải có kết quả riêng; khi đó `theta_eap` được lưu ở `TestQuestionSkillResult`, không dùng chung một giá trị cho các skill.

## 7. Cơ chế cập nhật `mastery_score` tổng theo skill

Sau khi có `question_mastery_score`, gom các kết quả hợp lệ theo `skill_id`.

Trong MVP, dùng trung bình cộng:
$$
\[
mastery\_score_s
=
\frac{1}{n_s}
\sum_{i=1}^{n_s}question\_mastery_i
\]
$$
Trong đó:

- `s`: kỹ năng đang xét.
- `n_s`: số kết quả đánh giá hợp lệ của skill `s` trong toàn bộ lịch sử.
- `question_mastery_i`: điểm mastery của kết quả câu hỏi thứ `i`, đã quy đổi qua bộ tham chiếu chung.

Không nhân thêm `question_difficulty` làm trọng số. Độ khó đã tham gia vào quá trình ước lượng `theta`; tiếp tục dùng độ khó làm trọng số có thể khiến độ khó ảnh hưởng hai lần.

### `evidence_count`

$$
\[
evidence\_count_s=n_s
\]
$$

`evidence_count` là số kết quả đánh giá hợp lệ đã được dùng làm bằng chứng cho skill đó.

Cần phân biệt:

- Không có dữ liệu đánh giá: chưa đủ bằng chứng; không tự động gán mastery bằng 0.
- Có dữ liệu và tất cả kết quả đều ở mức 0: đây vẫn là bằng chứng hợp lệ về mức thể hiện thấp.

## 8. Cơ chế `add_test()` cập nhật mastery

### 8.1. Trách nhiệm của `add_test()`

`add_test()` không chỉ lưu một bài kiểm tra mới. Hàm còn chịu trách nhiệm tính điểm cho các kết quả mới và đồng bộ lại hồ sơ mastery của những skill bị ảnh hưởng.

Luồng xử lý:

```text
add_test(test_data, question_results)
    |
    |-- Bắt đầu database transaction
    |
    |-- Kiểm tra test, học sinh, câu hỏi và kết quả rubric
    |
    |-- Lưu Test
    |
    |-- Với từng kết quả câu hỏi mới
    |      |
    |      |-- Xác định skill được đánh giá
    |      |-- Truy xuất rubric và max_level
    |      |-- Truy xuất step_difficulties và version
    |      |-- Tính theta_eap bằng Bayesian PCM
    |      |-- Quy đổi theta_eap bằng PCM tham chiếu chung
    |      |-- Lưu observed_level, theta_eap,
    |          question_mastery_score và các version
    |
    |-- Xác định các skill bị ảnh hưởng
    |
    |-- Với từng skill bị ảnh hưởng
    |      |
    |      |-- Lấy toàn bộ bằng chứng hợp lệ của học sinh
    |      |-- Tính lại trung bình question_mastery_score
    |      |-- Đếm evidence_count
    |      |-- Upsert student_skill_mastery
    |
    |-- Commit transaction
```

### 8.2. Prototype đề xuất

```python
def add_test(
    student_id: int,
    test_data: dict,
    question_results: list[dict],
) -> int:
    """
    Lưu bài kiểm tra, tính EAP cho từng kết quả câu hỏi,
    lưu question_mastery_score và cập nhật mastery theo skill.

    Parameters
    ----------
    student_id:
        ID học sinh làm bài kiểm tra.
    test_data:
        Thông tin chung của test, ví dụ tên bài, thời điểm,
        loại bài kiểm tra và các metadata cần lưu.
    question_results:
        Danh sách kết quả chấm. Mỗi phần tử cần có tối thiểu
        question_id và observed_level. Nếu một câu đánh giá
        nhiều skill, phải có kết quả observed_level độc lập
        cho từng skill.

    Returns
    -------
    int:
        ID của test vừa được tạo.
    """
```

### 8.3. Chi tiết xử lý một kết quả câu hỏi

Với mỗi phần tử trong `question_results`:

1. Lấy `question_id` và `observed_level`.
2. Xác định skill tương ứng.
3. Lấy rubric và `max_level`.
4. Lấy `step_difficulties` từ `PCMQuestionParameters`; nếu không có thì lấy từ `PCMTemplateParameters`.
5. Gọi `estimate_eap()` để tính `theta_eap`.
6. Gọi `pcm_probability(theta_eap, reference_step_difficulties)` để lấy phân phối rubric tham chiếu.
7. Tính kỳ vọng theo rubric tham chiếu để có `question_mastery_score`.
8. Lưu kết quả và phiên bản các tham số đã sử dụng.

Chỉ tính PCM/EAP cho kết quả mới. Các kết quả cũ có thể tái sử dụng nếu rubric, step difficulties, prior và bộ tham chiếu không thay đổi.

### 8.4. Cập nhật lại mastery từ toàn bộ bằng chứng

Sau khi lưu kết quả mới, với từng skill bị ảnh hưởng:

```text
evidence = lấy toàn bộ kết quả hợp lệ
           của student_id và skill_id

n = số phần tử trong evidence

nếu n > 0:
    mastery_score = trung bình question_mastery_score
    evidence_count = n
    upsert student_skill_mastery
```

**Vì sao lấy toàn bộ bằng chứng thay vì chỉ cộng điểm mới vào mastery cũ?**

Nếu chỉ có `mastery_score` và `evidence_count` hiện tại, có thể cập nhật trung bình bằng công thức:

$$
\[
M_{new} =
\frac{M_{old}N_{old}+\sum_{j=1}^{q}x_j}
{N_{old}+q}
\]
$$

Trong đó `x_j` là các điểm mastery mới. Tuy nhiên, cách này chỉ an toàn khi không có sửa/xóa kết quả cũ, không có trùng dữ liệu và toàn bộ điểm được tính trên cùng phiên bản tham số. Với MVP, truy vấn toàn bộ bằng chứng rồi tính lại sẽ dễ kiểm soát và tránh sai lệch do cập nhật lặp.

Nếu không có bằng chứng hợp lệ, không tạo mastery bằng 0. Có thể giữ nguyên bản ghi hiện tại hoặc đánh dấu trạng thái chưa đủ bằng chứng theo quy ước của hệ thống.

### 8.5. Transaction và chống tạo bằng chứng trùng

Toàn bộ thao tác lưu test, lưu kết quả câu hỏi và cập nhật mastery nên nằm trong một transaction. Nếu một bước thất bại, rollback để tránh tình trạng test đã được lưu nhưng mastery chưa cập nhật.

Cần có ràng buộc duy nhất cho kết quả đánh giá, chẳng hạn:

- Một câu chỉ đánh giá một skill: `(test_id, question_id)`.
- Một câu có kết quả độc lập theo nhiều skill: `(test_id, question_id, skill_id)`.

Nếu cho phép chấm lại hoặc sửa kết quả, cần cập nhật bản ghi kết quả cũ thay vì insert thêm một bằng chứng mới. Sau đó chạy lại việc tổng hợp mastery cho các skill liên quan.

## 9. Các hàm liên quan khác

### 9.1. Lấy bài kiểm tra

```python
def get_test(test_id: int) -> dict | None:
    """
    Truy xuất thông tin test và các kết quả câu hỏi đã lưu.

    Parameters
    ----------
    test_id:
        ID bài kiểm tra cần truy xuất.

    Returns
    -------
    dict | None:
        Dữ liệu test cùng observed_level, theta_eap,
        question_mastery_score của từng kết quả; None nếu không tồn tại.
    """
```

`get_test()` chỉ truy xuất dữ liệu đã lưu, không tự tính lại mastery.

### 9.2. Xây dựng lại hồ sơ mastery

```python
def rebuild_student_skill_mastery(student_id: int) -> None:
    """
    Tính lại toàn bộ mastery của học sinh từ các bằng chứng hợp lệ.

    Parameters
    ----------
    student_id:
        ID học sinh cần xây dựng lại hồ sơ mastery.
    """
```

Luồng:

```text
rebuild_student_skill_mastery(student_id)
    |
    |-- Lấy toàn bộ kết quả đánh giá hợp lệ
    |-- Phân nhóm theo skill_id
    |-- Tính lại mastery_score từ question_mastery_score
    |-- Đếm evidence_count
    |-- Ghi đè/upsert student_skill_mastery
```

Nếu thay đổi công thức tổng hợp, có thể tái sử dụng `question_mastery_score` cũ nếu các tham số PCM không đổi. Nếu thay đổi rubric, step difficulties, prior hoặc bộ tham chiếu, cần tính lại các kết quả chịu ảnh hưởng trước khi rebuild mastery.

## 10. Quy tắc phiên bản và tính nhất quán

Nên lưu version của các thành phần sau cùng với kết quả:

- Rubric.
- PCM step difficulties.
- Prior.
- Bộ tham chiếu PCM.

Khi một thành phần thay đổi:

| Thành phần thay đổi | Có cần tính lại EAP? | Có cần tính lại question mastery? |
|---|---|---|
| Rubric / max level | Có | Có |
| PCM step difficulties | Có | Có |
| Prior | Có | Có |
| Bộ tham chiếu | Không nhất thiết | Có |
| Công thức tổng hợp theo skill | Không | Không, chỉ rebuild mastery |

`add_test()` và `rebuild_student_skill_mastery()` phải dùng cùng một công thức tổng hợp để kết quả không lệch nhau.

## 11. Tóm tắt trách nhiệm từng hàm

| Hàm | Trách nhiệm |
|---|---|
| `pcm_probability()` | Tính phân phối xác suất rubric tại một giá trị theta |
| `estimate_eap()` | Ước lượng `theta_eap` từ một `observed_level` và tham số PCM của câu |
| `add_test()` | Lưu test, tính và lưu EAP/mastery cho từng kết quả câu hỏi, cập nhật mastery theo skill |
| `get_test()` | Truy xuất dữ liệu test đã lưu |
| `rebuild_student_skill_mastery()` | Tính lại hồ sơ mastery từ toàn bộ bằng chứng đã lưu |

## 12. Lưu ý triển khai

1. **Ổn định số học:** dùng `log-sum-exp` khi tính PCM và chuẩn hóa trọng số hậu nghiệm.
2. **Giới hạn theta:** grid phải đủ rộng và đủ mịn; kiểm tra kết quả không bị ảnh hưởng đáng kể bởi biên.
3. **Cùng thang đo:** prior, step difficulties và bộ tham chiếu phải tương thích.
4. **Thiếu bằng chứng:** không xem một câu hỏi là phép đo chắc chắn về năng lực; `evidence_count` phản ánh số lượng bằng chứng, không tự nó chứng minh độ tin cậy thống kê.
5. **Hiệu chuẩn:** difficulty giả định chỉ phù hợp cho MVP/kiểm thử. Khi có dữ liệu đủ lớn, cần hiệu chuẩn tham số và đánh giá độ phù hợp mô hình.
6. **Transaction:** chỉ cập nhật hồ sơ mastery sau khi dữ liệu test và kết quả đánh giá được lưu thành công.
7. **Không nhân đôi ảnh hưởng độ khó:** không tiếp tục dùng độ khó câu hỏi làm trọng số tổng hợp nếu độ khó đã được dùng trong PCM.
8. **Một câu – nhiều skill:** phải có rubric/result độc lập theo từng skill.
9. **Tái lập kết quả:** lưu đầy đủ phiên bản tham số đã dùng cho mỗi kết quả.

## 13. Tài liệu nền tảng

- Masters, G. N. (1982). *A Rasch Model for Partial Credit Scoring*. Psychometrika, 47(2), 149–174.
- Masters, G. N. (1988). *The Analysis of Partial Credit Scoring*. Applied Measurement in Education, 1(4), 279–297.
- EAP ability estimation for dichotomous and polytomous IRT models.

Các tài liệu trên là nền tảng cho PCM và chấm điểm từng phần. Việc dùng prior Bayesian, MAP/EAP cho từng câu và bộ tham chiếu chung là các lựa chọn thiết kế được đề xuất để phù hợp với kiến trúc hệ thống; không nên quy toàn bộ quy trình này thành thuật toán nguyên bản của Masters.
