# Thiết kế dữ liệu chấm bài và cơ chế cập nhật hồ sơ năng lực
Trình bày: Nguyễn Ngọc Ánh Dương
## Tóm tắt:
- Dùng **Partial Credit Model (PCM)** để tính xác xuất đúng bước đó của học sinh dựa trên các bước học sinh làm đúng và độ khó của bước đó.
- Dùng EAP ability estimation (dichotomous and polytomous IRT models) để tính điểm mong đợi của từng câu.
- Quy đổi sang mastery_score
## 1. Mục tiêu

Sử dụng **Partial Credit Model (PCM)** để đánh giá mức độ thành thạo của
học sinh theo từng kỹ năng (`skill_id`) dựa trên kết quả chấm rubric của
từng câu hỏi.

Thiết kế gồm hai tầng:

1.  **Đánh giá từng câu hỏi:** sử dụng PCM để ước lượng năng lực tiềm ẩn
    của học sinh từ `observed_level` và `step_difficulties`, sau đó quy
    đổi về điểm thành thạo trên thang 0--4.
2.  **Tổng hợp theo kỹ năng:** tổng hợp điểm thành thạo của các câu hỏi
    cùng đánh giá một kỹ năng để cập nhật `student_skill_mastery`.

> Lưu ý học thuật: PCM nguyên bản thường ước lượng năng lực từ một tập
> hợp câu hỏi. Thiết kế trong tài liệu này áp dụng PCM ở cấp từng câu
> hỏi, kết hợp ước lượng Bayesian để xử lý trường hợp mỗi câu chỉ có một
> kết quả quan sát. Vì vậy, nên mô tả đây là cơ chế chấm điểm dựa trên
> PCM ở cấp câu hỏi, không phải quy trình ước lượng năng lực PCM nguyên
> bản trên toàn bài kiểm tra.

------------------------------------------------------------------------

## 2. Cấu trúc dữ liệu

### 2.1. Rubric

Rubric mô tả các mức độ thể hiện có thứ tự từ 0 đến mức tối đa `m`.

Ví dụ rubric 0--4:

``` python
rubric = {
    0: "Chưa nhận diện được phép tổ hợp",
    1: "Nhận diện được tình huống chọn nhóm",
    2: "Thiết lập đúng biểu thức tổ hợp",
    3: "Thực hiện phần lớn phép tính đúng",
    4: "Giải đúng và kết luận đầy đủ"
}
```

### 2.2. Step difficulty

Trong PCM, `step_difficulty` là độ khó của **bước chuyển từ mức điểm
trước sang mức điểm tiếp theo**, không phải độ khó của bản thân mức
điểm.

Với rubric 0--4, có bốn bước chuyển:

  Bước   Ý nghĩa
  ------ ---------
  1      0 → 1
  2      1 → 2
  3      2 → 3
  4      3 → 4

Ví dụ:

``` python
step_difficulties = [-0.5, 0.5, 1.0, 1.5]
```

Các giá trị trên chỉ là dữ liệu giả định để minh họa. Khi triển khai
thực tế, tham số cần được hiệu chuẩn từ dữ liệu phản hồi của học sinh.
Các tham số của câu hỏi và bộ tham số tham chiếu phải nằm trên cùng một
thang đo năng lực.

### 2.3. Các bảng và trường dữ liệu đề xuất

-   `QuestionTemplate`: lưu rubric mặc định của câu hỏi thuộc template.
-   `QuestionRubric`: lưu rubric riêng cho câu hỏi vận dụng hoặc câu hỏi
    cần rubric tùy chỉnh.
-   `PCMTemplateParameters`: lưu `template_id`, `step_difficulties`,
    phiên bản tham số và trạng thái hiệu chuẩn.
-   `PCMQuestionParameters`: lưu tham số PCM riêng của câu hỏi nếu câu
    hỏi có rubric độc lập.
-   `test_questions`: lưu `test_id`, `question_id`, `observed_level`,
    `question_mastery_score`.
-   `TestQuestionSkillResult` (chỉ cần nếu một câu đánh giá nhiều
    skill): lưu `test_id`, `question_id`, `skill_id`, `observed_level`,
    `theta_eap`, `question_mastery_score`.
-   `question_skills`: ánh xạ câu hỏi với kỹ năng.
-   `student_skill_mastery`: lưu `student_id`, `skill_id`,
    `mastery_score`, `evidence_count`.

Nếu mỗi câu hỏi chỉ đánh giá một skill, có thể lưu kết quả trực tiếp
trong `test_questions` và không cần `TestQuestionSkillResult`.

Cần xác định phiên bản rubric/tham số PCM được sử dụng khi chấm. Nếu
rubric hoặc step difficulty thay đổi, kết quả cũ có thể cần được tính
toán lại.

------------------------------------------------------------------------
## 3. Cơ chế tính PCM riêng từng câu hỏi

### 3.1. Dữ liệu đầu vào

Với câu hỏi thứ \(i\):

- `observed_level = x_i`: mức rubric học sinh đạt được.
- `step_difficulties = [\delta_{i1}, \delta_{i2}, \ldots, \delta_{im}]`: độ khó của các bước chuyển.
- \(m\): mức điểm tối đa của rubric.
- Prior năng lực: giả định ban đầu về phân phối của \(\theta_i\).

### 3.2. Stage 1: Tính xác suất theo PCM

Công thức này cho phép tính xác suất đạt từng mức rubric khi biết năng lực \(\theta_i\).

Với một giá trị năng lực thử nghiệm \(\theta\), xác suất đạt mức \(k\) là:

$$
P(X_i=k\mid\theta)=
\frac{
\exp\left(\sum_{j=1}^{k}(\theta-\delta_{ij})\right)
}{
\sum_{r=0}^{m}
\exp\left(\sum_{j=1}^{r}(\theta-\delta_{ij})\right)
}
$$

Quy ước tổng rỗng tại \(k=0\) bằng 0, do đó tử số của mức 0 bằng:

$$
\exp(0)=1
$$

Trong đó:

- \(\theta\): năng lực tiềm ẩn đang xét.
- \(\delta_{ij}\): độ khó của bước chuyển thứ \(j\) trong câu hỏi \(i\).
- \(k\): mức rubric đang tính xác suất.
- \(m\): mức rubric tối đa.

### 3.3. Stage 2: Ước lượng năng lực bằng MAP

**Vì sao không dùng MLE trực tiếp?**

Giả sử:

$$
\theta_i\sim N(\mu_0,\sigma_0^2)
$$

Có thể chọn giá trị khởi đầu:

$$
\mu_0=0,\qquad \sigma_0=1
$$

Đây là giả định khởi tạo, không phải tham số bắt buộc của PCM. Cần giữ nhất quán thang đo giữa prior, step difficulties và bộ tham chiếu.

Theo Bayes:

$$
P(\theta_i\mid X_i=x_i)
\propto
P(X_i=x_i\mid\theta_i)P(\theta_i)
$$

Hàm log-posterior, bỏ qua hằng số không phụ thuộc vào \(\theta\), là:

$$
\boxed{
L_i(\theta)=
\log P(X_i=x_i\mid\theta)
-\frac{(\theta-\mu_0)^2}{2\sigma_0^2}
}
$$

Ước lượng MAP:

$$
\boxed{
\hat{\theta}_{MAP,i}
=
\arg\max_{\theta}L_i(\theta)
}
$$

MAP tạo ra nghiệm hữu hạn nhờ prior, kể cả khi `observed_level` ở mức thấp nhất hoặc cao nhất.

Tuy nhiên, một kết quả rubric vẫn là lượng bằng chứng hạn chế. MAP không làm cho ước lượng từ một câu trở nên chắc chắn; nó chỉ giúp kết quả ổn định hơn bằng giả định prior.

### 3.4. Stage 3: Ước lượng EAP (khuyến nghị khi cần xét độ bất định)

Thay vì chỉ sử dụng điểm cực đại MAP, có thể sử dụng trung bình hậu nghiệm EAP:

$$
\pi_i(\theta\mid x_i)=
\frac{
P(X_i=x_i\mid\theta)\phi(\theta;\mu_0,\sigma_0^2)
}{
\int_{-\infty}^{+\infty}
P(X_i=x_i\mid t)\phi(t;\mu_0,\sigma_0^2)\,dt
}
$$

Trong đó \(\phi\) là mật độ phân phối chuẩn.

Giá trị EAP:

$$\boxed{
\hat{\theta}_{EAP,i} =

\int_{-\infty}^{+\infty}
\theta\,\pi_i(\theta\mid x_i)\,d\theta
}
$$

- `theta_map`: giá trị tại cực đại của phân phối hậu nghiệm.
- `theta_eap`: trung bình của phân phối hậu nghiệm.

**Đề xuất:** Nếu cần một giá trị theta đại diện để tính mastery, ưu tiên `theta_eap`. Nếu MVP cần đơn giản hơn, có thể sử dụng `theta_map`, nhưng phải thống nhất cách dùng trong toàn hệ thống.

Các tích phân có thể được tính gần đúng bằng numerical integration trên một khoảng theta đủ rộng, hoặc bằng phương pháp lưới (grid approximation).

### 3.5. Đề xuất thang đo step_difficulty

| Độ khó giáo viên chọn | Ý nghĩa | `step_difficulty` |
|---:|---|---:|
| 0 | Rất dễ | -1.5 |
| 1 | Dễ | -0.75 |
| 2 | Trung bình | 0 |
| 3 | Khó | 0.75 |
| 4 | Rất khó | 1.5 |

Công thức quy đổi:

$$
b_i=0.75(d_i-2)
$$

## 4. Quy đổi theta sang question_mastery_score

### 4.1. Expected Score theo chính câu hỏi

Với xác suất PCM của câu hỏi \(i\), điểm kỳ vọng là:

$$
\boxed{
E(X_i\mid\theta_i)
=
\sum_{k=0}^{m}kP_i(X_i=k\mid\theta_i)
}
$$

Với rubric 0–4:

$$
E(X_i\mid\theta_i)
=
\sum_{k=0}^{4}kP_i(X_i=k\mid\theta_i)
$$

Giá trị nằm trong khoảng \([0,4]\).

Cách này phù hợp khi muốn diễn giải điểm dự kiến trên chính rubric của câu hỏi. Tuy nhiên, nếu các câu có step difficulties khác nhau, điểm kỳ vọng theo rubric riêng của từng câu có thể không so sánh trực tiếp công bằng giữa câu dễ và câu khó.

### 4.2. Đề xuất chính: Expected Score theo bộ tham chiếu chung

Để tổng hợp các câu hỏi có độ khó khác nhau, đề xuất sử dụng một bộ step difficulties tham chiếu cố định:

$$
\delta_{ref}=[-1.5,-0.5,0.5,1.5]
$$

Các giá trị trên chỉ là ví dụ. Bộ tham chiếu cần được xác định trên cùng thang đo năng lực với các tham số câu hỏi và được giữ cố định trong cùng một phiên bản hệ thống.

Với bộ tham chiếu, tính xác suất đạt mức \(k\):

$$
P_{ref}(X=k\mid\theta)=
\frac{
\exp\left(\sum_{j=1}^{k}(\theta-\delta_{ref,j})\right)
}{
\sum_{r=0}^{m}
\exp\left(\sum_{j=1}^{r}(\theta-\delta_{ref,j})\right)
}
$$

**Phương án: Dùng EAP làm giá trị theta đại diện**

$$
\boxed{
question\_mastery_i
=
\sum_{k=0}^{m}
kP_{ref}(X=k\mid\hat{\theta}_{EAP,i})
}
$$

### 4.4. Vì sao cần bộ tham chiếu chung?

Nếu mỗi câu sử dụng bộ step difficulties riêng để tính Expected Score, cùng một theta có thể tạo ra điểm khác nhau do độ khó câu hỏi khác nhau.

Dùng chung bộ tham chiếu giúp:

- Chuyển theta của các câu về cùng một thang diễn giải.
- Hạn chế việc câu dễ tự tạo ra điểm kỳ vọng cao hơn câu khó chỉ do tham số riêng.
- Hỗ trợ tổng hợp các câu cùng đánh giá một skill.

**Điều kiện quan trọng:** step difficulties của từng câu và bộ tham chiếu phải được đặt trên cùng một thang đo. Không thể tùy ý đặt các tham số độc lập rồi mặc định chúng có thể so sánh.

## 5. Tổng hợp question_mastery_score theo skill

Sau khi tính được `question_mastery_score` cho từng kết quả đánh giá, nhóm các kết quả theo `skill_id`.

Trong MVP, sử dụng trung bình cộng:

$$
\boxed{
mastery\_score_s=
\frac{1}{n_s}
\sum_{i=1}^{n_s}question\_mastery_i
}
$$

Trong đó:

- \(s\): kỹ năng đang xét.
- \(n_s\): số kết quả đánh giá hợp lệ của kỹ năng \(s\).
- `question_mastery_i`: điểm thành thạo của câu hỏi sau khi quy đổi về thang tham chiếu chung.

Không nhân thêm `question_difficulty` làm trọng số trong công thức này. Độ khó đã tham gia vào quá trình ước lượng theta; việc tiếp tục dùng độ khó làm trọng số có thể khiến câu khó được tính ảnh hưởng hai lần.

Nếu sau này muốn sử dụng trọng số, cần có căn cứ rõ ràng, chẳng hạn độ tin cậy của bằng chứng hoặc thiết kế đánh giá. Không nên mặc định câu khó luôn có trọng số cao hơn.

Nếu một câu hỏi đánh giá nhiều skill, cần có kết quả rubric riêng cho từng skill. Không dùng một `observed_level` chung để suy ra nhiều năng lực khác nhau.


------------------------------------------------------------------------

## 6. Cập nhật evidence_count

`evidence_count` là số kết quả đánh giá hợp lệ đã được sử dụng làm bằng
chứng cho một skill.
$$
\[ `\boxed{
evidence\_count_s=n_s
}`{=tex} \]
$$
Mỗi kết quả đánh giá chỉ được tính một lần cho một skill. Nếu một câu
đánh giá hai skill và có hai kết quả rubric độc lập, câu đó có thể đóng
góp một bằng chứng cho mỗi skill.

Cần phân biệt:

-   Không có dữ liệu đánh giá: chưa đủ bằng chứng, không tự động gán
    mastery bằng 0.
-   Có dữ liệu và tất cả kết quả đều ở mức 0: đây là bằng chứng hợp lệ
    về mức thể hiện thấp.

------------------------------------------------------------------------

## 7. Luồng thuật toán

### 7.1. Khi thêm bài kiểm tra: `add_test()`

``` text
add_test()
    |
    |-- Lưu Test
    |
    |-- Lưu TestQuestion và observed_level
    |
    |-- Với từng kết quả đánh giá
    |       |
    |       |-- Truy xuất rubric
    |       |-- Truy xuất step_difficulties
    |       |-- Tính phân phối hậu nghiệm bằng Bayesian PCM
    |       |-- Tính theta_eap (hoặc theta_map)
    |       |-- Quy đổi bằng PCM tham chiếu
    |       |-- Lưu question_mastery_score
    |
    |-- Gom các kết quả theo skill_id
    |
    |-- Lấy các bằng chứng trước đó của các skill liên quan
    |
    |-- Tính lại mastery_score từ toàn bộ bằng chứng
    |
    |-- Cập nhật student_skill_mastery
    |-- Cập nhật evidence_count
```

Chỉ tính PCM cho các kết quả mới. Các kết quả cũ có thể được tái sử dụng
nếu rubric, step difficulties, prior và bộ tham chiếu không thay đổi.

### 7.2. Khi truy xuất bài kiểm tra: `get_test()`

`get_test()` chỉ truy xuất dữ liệu đã lưu, không tự tính lại mastery.

### 7.3. Khi xây dựng lại hồ sơ: `rebuild_student_skill_mastery()`

``` text
rebuild_student_skill_mastery(student_id)
    |
    |-- Lấy toàn bộ kết quả đánh giá hợp lệ
    |
    |-- Phân nhóm theo skill_id
    |
    |-- Tính lại mastery_score từ các question_mastery_score
    |
    |-- Đếm evidence_count
    |
    |-- Ghi đè student_skill_mastery
```

Nếu thay đổi công thức tổng hợp, có thể tái sử dụng
`question_mastery_score` cũ nếu các tham số PCM không đổi.

Nếu thay đổi rubric, step difficulties, prior hoặc bộ tham chiếu, cần
tính lại các kết quả chịu ảnh hưởng.

------------------------------------------------------------------------

## 8. Các lưu ý triển khai

1.  **Tính ổn định số học:** Khi tính PCM, nên sử dụng kỹ thuật
    `log-sum-exp` thay vì tính trực tiếp các số mũ lớn.
2.  **Giới hạn miền theta:** Khi dùng grid approximation hoặc tối ưu số,
    chọn miền đủ rộng và kiểm tra kết quả không bị ảnh hưởng đáng kể bởi
    biên.
3.  **Phiên bản tham số:** Lưu phiên bản rubric, step difficulties,
    prior và bộ tham chiếu để có thể tái lập kết quả.
4.  **Thiếu bằng chứng:** Không nên xem một câu hỏi là phép đo chắc chắn
    về năng lực. Có thể lưu thêm `evidence_count` và trạng thái độ tin
    cậy.
5.  **Hiệu chuẩn:** Các giá trị difficulty giả định chỉ phục vụ MVP và
    kiểm thử. Khi có dữ liệu đủ lớn, cần hiệu chuẩn tham số và đánh giá
    độ phù hợp của mô hình.
6.  **Transaction:** Chỉ cập nhật hồ sơ mastery sau khi dữ liệu bài kiểm
    tra và kết quả đánh giá được lưu thành công.
7.  **Tính nhất quán:** `add_test()` và
    `rebuild_student_skill_mastery()` phải dùng cùng một công thức tổng
    hợp.

------------------------------------------------------------------------

## 9. Tóm tắt công thức được lựa chọn

### Ước lượng xác suất PCM

\[ P(X_i=k`\mid`{=tex}`\theta`{=tex})= `\frac{
\exp\left(\sum_{j=1}^{k}(\theta-\delta_{ij})\right)
}{
\sum_{r=0}^{m}
\exp\left(\sum_{j=1}^{r}(\theta-\delta_{ij})\right)
}`{=tex} \]

### Ước lượng MAP

\[ `\hat{\theta}`{=tex}*{MAP,i} =
`\arg`{=tex}`\max`{=tex}*{`\theta`{=tex}} `\left[
\log P(X_i=x_i\mid\theta)
-
\frac{(\theta-\mu_0)^2}{2\sigma_0^2}
\right]`{=tex}\]

### Ước lượng EAP

\[ `\hat{\theta}`{=tex}*{EAP,i} =
`\int`{=tex}*{-`\infty`{=tex}}\^{+`\infty`{=tex}}
`\theta`{=tex}`\pi`{=tex}\_i(`\theta`{=tex}`\mid `{=tex}x_i),d`\theta`{=tex}
\]

### Quy đổi mastery bằng bộ tham chiếu (MVP dùng EAP)

\[ question_mastery_i = `\sum`{=tex}*{k=0}\^{m}
kP*{ref}(X=k`\mid`{=tex}`\hat{\theta}`{=tex}\_{EAP,i}) \]

### Tổng hợp theo skill

\[ mastery_score_s= `\frac{1}{n_s}`{=tex}
`\sum`{=tex}\_{i=1}\^{n_s}question_mastery_i \]

### Đếm bằng chứng

\[ evidence_count_s=n_s \]

------------------------------------------------------------------------

## 10. Tài liệu học thuật nền tảng

-   Masters, G. N. (1982). *A Rasch Model for Partial Credit Scoring*.
    Psychometrika, 47(2), 149--174.
-   Masters, G. N. (1988). *The Analysis of Partial Credit Scoring*.
    Applied Measurement in Education, 1(4), 279--297.
-   EAP ability estimation (dichotomous and polytomous IRT models)

Các tài liệu trên là nền tảng cho PCM và chấm điểm từng phần. Việc dùng
prior Bayesian, MAP/EAP cho từng câu và bộ tham chiếu chung là các lựa
chọn thiết kế được đề xuất để phù hợp với kiến trúc của hệ thống; không
nên quy toàn bộ quy trình này thành thuật toán nguyên bản của Masters.
