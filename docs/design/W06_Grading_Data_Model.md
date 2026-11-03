# Thiết kế dữ liệu chấm bài và quy tắc cập nhật hồ sơ
**Phương pháp: Dùng Partial Credit Model (PCM) để ước lượng mastery**
## 1. Các bảng và trường cần thêm

- skills: thêm column rubric chấm điểm: 0 - 4
Skill: A004 - Combination
Rubric:{
    "0": {"description": Chưa nhận diện được phép tổ hợp, "Difficulty": -1.5},
    "1": {"description": Nhận diện được tình huống chọn nhóm, "Difficulty": -0.5},
    "2": {"description": Thiết lập đúng biểu thức tổ hợp, "Difficulty": 0.5},
    "3": {"description": Thực hiện phần lớn phép tính đúng, "Difficulty": 1},
    "4": {"description": Giải đúng và kết luận đầy đủ, "Difficulty": 1.5}
}
Lưu ý: không phải level nào cũng có mức độ khó như nhau

- Tests: test_id, student_id
- test_questions: test_id, question_id, is_correct, observed_level 
- Test_mastery_score: test_id, skill_id, mastery_score, sum_of_difficulty, number_of_question

observed_level: mức mà học sinh thực tế đạt được.

## 2. Luồng cơ bản:
Sau khi học sinh làm test -> giáo viên/AI chấm điểm từng câu và trả về rate_correct co từng question -> Lấy skill của từng question thực hiện cập nhật mastery_score bằng rate_correct và difficulty theo từng test -> lấy trung bình skill đó qua từng test

## 3. Cơ chế cập nhật mastery_score
### 3.1. Mục tiêu

Xây dựng cơ chế tính toán và cập nhật mức độ thành thạo (mastery_score) của từng học sinh theo từng kỹ năng (skill_id), dựa trên kết quả làm bài kiểm tra được lưu trong database.

Cơ chế này được sử dụng chung cho hai trường hợp:

add_test(): Cập nhật mức độ thành thạo khi học sinh có bài kiểm tra mới.

get_test(): Tính toán lại mức độ thành thạo dựa trên lịch sử các bài kiểm tra đã lưu.

### 3.2. Dữ liệu đầu vào

Bảng

Dữ liệu sử dụng

- Tests: test_id, student_id
- test_questions: test_id, question_id, is_correct, rate_correct
- questions: question_id, difficulty
- question_skills: Quan hệ giữa câu hỏi và kỹ năng
- student_skill_mastery: student_id, skill_id, mastery_score, evidence_count

Trong MVP1, hệ thống sử dụng is_correct để đánh giá kết quả trả lời:

1: Trả lời đúng.

0: Trả lời sai.

### 3.3. Cơ chế đề xuất tính toán

#### 3.3.1. Mô hình Partial Credit (PCM) tính mastery của từng kỹ năng trong một bài kiểm tra: calculate_test_skill_mastery()

##### 3.3.1.1. Stage 1: Tính xác xuất PCM 
Đối với một câu hỏi có các bậc điểm được xếp thứ tự từ 0 đến m, xác suất đạt được điểm x là:

\[P(X_i=x\vert{}\theta_i)= \frac{ \exp\left( \sum_{j=1}^{x}(\theta_i-\delta_{ij}) \right) }{ \sum_{k=0}^{m} \exp\left( \sum_{j=1}^{k}(\theta_i-\delta_{ij}) \right) }\]

Trong đó:

- `theta_i`: năng lực của học sinh được ước lượng từ câu hỏi i.
- `delta_ij`: độ khó của bước j trong câu hỏi i.
- `x`: điểm số quan sát được.
- `m`: điểm số tối đa của câu hỏi.

Với x = 0, tử số bằng 1.

##### 3.3.1.2. Stage 2: Hàm Log-likelihood
Cho trước phản hồi quan sát được x_i, hàm log-likelihood là:

\[\ell_i(\theta_i)= \ln P(X_i=x_i\vert{}\theta_i)\]

Năng lực được ước lượng là:

\[\hat{\theta}_i= \arg\max_{\theta_i}\ell_i(\theta_i)\]

Đối với các tiêu chí rubric đa thành phần, hàm hợp lý (likelihood) được xây dựng từ các điểm số quan sát được của các tiêu chí đó.

Việc ước lượng năng lực được thực hiện độc lập cho từng câu hỏi.

-   `theta` (năng lực): giá trị liên tục, chưa nằm sẵn trên thang 0--4.
-   `delta[i, j]` (step difficulty): độ khó của bước chuyển từ mức
    `j - 1` lên `j` ở câu hỏi `i`.
-   `mastery_score`: trong ví dụ này lưu `theta`; nếu giao diện cần
    thang 0--4 thì chuyển đổi riêng để hiển thị.

> **Lưu ý:** Step difficulty cần được hiệu chuẩn từ dữ liệu phản hồi của
> nhiều học sinh. Các giá trị dưới đây chỉ là dữ liệu giả định để minh
> họa thuật toán.

##### 3.3.1.3. Stage 3: Ước lượng năng lực:
Đối với mỗi câu hỏi:

1. Truy xuất rubric kỹ năng liên quan.
2. Truy xuất các mức độ đạt được quan sát được của học sinh.
3. Truy xuất độ khó các bước của rubric.
4. Xây dựng hàm hợp lý (likelihood) PCM.
5. Tìm giá trị năng lực tối đa hóa hàm hợp lý.
6. Lưu trữ năng lực ước lượng dưới dạng `theta_i`.


###### 3.3.1.4. Stage 4: Quy đổi về thang 4:
Công thức tính điểm năng lực tổng kết được điều chỉnh thông qua hàm chuyển đổi logistic (sigmoid) và phép co giãn tuyến tính để đưa giá trị cuối cùng về khoảng $(1, 4)$:

$$\text{mastery\_score} = 1 + 3 \times \frac{\sum_{i=1}^{n} d_i p_i}{\sum_{i=1}^{n} d_i}$$

Trong đó, xác suất thành công $p_i$ cho mỗi câu hỏi được định nghĩa bởi hàm logistic:
$$p_i = \frac{1}{1 + e^{-\theta_i}}$$

---

###### 3.3.1.4.2. Ý nghĩa của các thành phần
* **$p_i$ (Xác suất thành công / Giá trị chuyển đổi):** 
  * Ánh xạ năng lực $\theta_i$ (vốn nằm trên trục số thực từ $-\infty$ đến $+\infty$) về khoảng giới hạn $(0, 1)$. 
  * Khi năng lực $\theta_i$ tăng, $p_i$ tiến dần về $1$; khi năng lực thấp, $p_i$ tiến dần về $0$.
* **Trung bình có trọng số ($\frac{\sum d_i p_i}{\sum d_i}$):**
  * Sử dụng độ khó $d_i$ làm trọng số cho từng giá trị $p_i$.
  * Do mọi $p_i \in (0, 1)$, giá trị của biểu thức trung bình có trọng số này cũng sẽ nằm trong khoảng $(0, 1)$.
* **Phép biến đổi tuyến tính ($1 + 3 \times \dots$):**
  * Nhân với $3$: Co giãn dải giá trị từ khoảng $(0, 1)$ thành $(0, 3)$.
  * Cộng thêm $1$: Dịch chuyển dải giá trị lên, kết quả cuối cùng sẽ thuộc khoảng $(1, 4)$.

---

###### 3.3.1.4.3. Diễn giải trực quan cơ chế hoạt động

1. **Cơ chế trọng số theo độ khó ($d_i$):**
   * Các câu hỏi khó hơn ($d_i$ lớn) sẽ có trọng số đóng góp lớn hơn vào tổng điểm năng lực.
   * Điều này phản ánh thực tế sư phạm: Nếu học sinh giải quyết thành công các câu hỏi khó, điểm mastery sẽ được thưởng cao hơn nhiều so với việc chỉ làm đúng các câu hỏi dễ.

2. **Cân bằng giữa năng lực và thử thách:**
   * Tử số ($\sum d_i \theta_i$) tổng hợp mức độ thành công của học sinh khi đối mặt với các mức độ thử thách khác nhau.
   * Mẫu số ($\sum d_i$) đóng vai trò chuẩn hóa, đảm bảo tổng trọng số của toàn bộ các câu hỏi trong kỹ năng được cân đối công bằng.

3. **Ý nghĩa của việc nhân hệ số 4:**
   * Giúp quy đổi giá trị năng lực tổng hợp (thường nằm trên một dải liên tục tùy thuộc vào phân phối IRT/PCM) về lại **thang đo điểm số trực quan (0–4)** của rubric kỹ năng ban đầu, giúp giáo viên và học sinh dễ dàng đọc hiểu kết quả.

### 3.3.2. Luồng thuật toán

1.  Lấy các kết quả `observed_level` của học sinh theo một `skill_id`.
2.  Lấy step difficulty đã hiệu chuẩn của từng câu/bài.
3.  Với một giá trị thử của `theta`, tính trọng số các mức `S_0` đến
    `S_4`.
4.  Chuẩn hóa trọng số để thu được xác suất đạt từng mức.
5.  Tính log-likelihood của các mức học sinh thực sự đạt.
6.  Tối ưu để tìm `theta_hat` làm log-likelihood lớn nhất.
7.  Lưu `theta_hat`; nếu cần, chuyển thành điểm hiển thị 0--4.

### 3.3.3. Ghi chú triển khai

-   `observed_level` là điểm rubric quan sát được; `theta` là năng lực
    tiềm ẩn được mô hình ước lượng. Hai đại lượng này không giống nhau.
-   Nếu một câu đánh giá nhiều skill, nên có kết quả chấm riêng cho từng
    skill; một `observed_level` chung không đủ để suy ra năng lực từng
    skill.
-   Với rất ít câu hoặc chỉ một mức điểm xuất hiện, MLE có thể không ổn
    định hoặc không có nghiệm hữu hạn. Hệ thống thực tế có thể cần
    prior/regularization hoặc chờ thêm bằng chứng.
-   PCM không yêu cầu tính trung bình có trọng số `sum_of_difficulty`.
    Số câu có dữ liệu có thể lưu riêng làm `evidence_count`.

#### 3.3.4. Cập nhật evidence_count

evidence_count thể hiện tổng số câu hỏi đã được sử dụng làm bằng chứng đánh giá một kỹ năng.

                evidence_count_new = SUM(n_j)

Trong đó n_j là số câu hỏi thuộc kỹ năng đang xét trong bài kiểm tra thứ j.

Mỗi câu hỏi chỉ được tính một lần cho mỗi kỹ năng trong phạm vi dữ liệu đánh giá tương ứng. Nếu một câu hỏi liên quan đến nhiều kỹ năng, câu hỏi đó có thể đóng góp bằng chứng cho từng kỹ năng liên quan.

### 3.3.5. Cơ chế cập nhật database: update_student_skill_mastery()

- Sau khi tính toán, hệ thống kiểm tra sự tồn tại của bản ghi tương ứng trong student_skill_mastery.
- Kỹ năng đã tồn tại: Cập nhật mastery_score và evidence_count bằng kết quả tổng hợp mới.
- Kỹ năng chưa tồn tại: Tạo bản ghi mới với student_id, skill_id, mastery_score và evidence_count tương ứng.

Không cộng trực tiếp điểm mastery mới vào điểm mastery cũ, vì cách này có thể khiến điểm vượt khỏi thang đo quy định.

### 3.3.6. Tích hợp với các hàm hiện tại: 

#### 3.3.6.1. Trường hợp add_test()

- Thêm bài kiểm tra vào Tests.
- Thêm các câu hỏi và kết quả trả lời vào test_questions.
- Sau khi lưu thành công, gọi hàm cập nhật mastery cho student_id và test_id của bài kiểm tra mới.
- Tính điểm của từng kỹ năng trong bài kiểm tra mới.
- Tổng hợp với các bài kiểm tra trước đó và cập nhật student_skill_mastery.

Hệ thống chỉ cập nhật mastery sau khi việc thêm bài kiểm tra và các câu hỏi liên quan thành công.

#### 3.3.6.2. Trường hợp rebuild_student_skill_mastery()

- Truy xuất danh sách bài kiểm tra của học sinh từ Tests.
- Duyệt từng test_id và lấy dữ liệu tương ứng trong test_questions.
- Tính lại mastery của từng kỹ năng theo từng bài kiểm tra nếu câ.
- Tổng hợp kết quả từ toàn bộ lịch sử.

Cập nhật lại student_skill_mastery.

Trong trường hợp này, hệ thống phải tính lại từ dữ liệu gốc hoặc ghi đè kết quả cũ, tránh cộng lặp dữ liệu đã được tính trước đó.

### 3.3.7 Đảm bảo tính nhất quán

Để tránh sai lệch dữ liệu, cần tuân thủ các nguyên tắc:

- Dùng chung công thức tính mastery cho cả add_test() và get_test().
- Không tính lặp một bài kiểm tra khi cập nhật tăng dần.
- Sử dụng transaction để đảm bảo tính nhất quán khi ghi database.
- Chỉ cập nhật mastery_score khi có dữ liệu đánh giá hợp lệ cho kỹ năng.
- Phân biệt trường hợp chưa có dữ liệu với trường hợp đã có dữ liệu nhưng tất cả câu trả lời đều sai.

## 3.4. Tài liệu học thuật liên quan
### 3.4.1 Partial Credit Model: 
**Masters, G. N. (1982). A Rasch Model for Partial Credit Scoring. Psychometrika, 47(2), 149–174.Đây là một trong những tài liệu nền tảng về mô hình chấm điểm từng phần trong đánh giá giáo dục.**

Tác giả xây dựng mô hình Rasch mở rộng cho câu hỏi có nhiều mức điểm thay vì chỉ đúng hoặc sai. Các mức điểm được xem là những danh mục có thứ tự, phản ánh các mức độ thể hiện năng lực khác nhau.

Thuật toán này được áp dụng để tính mastery_score

#### 3.4.2. Cơ chế hoạt động của Partial Credit Scoring

##### 3.4.2.1. Ví dụ minh họa và Thang điểm

Xét bài toán: *Có bao nhiêu cách chọn 2 học sinh từ 5 học sinh, sau đó sắp xếp 2 học sinh đã chọn?*

**Các bước giải tiêu chuẩn:**
1. Xác định sử dụng tổ hợp.
2. Tính số cách chọn 2 học sinh.
3. Xác định số cách sắp xếp 2 học sinh.
4. Kết hợp các kết quả để tìm đáp án cuối cùng.

**Rubric chấm điểm:**

| Điểm | Mức độ thể hiện |
| :---: | :--- |
| **0** | Không thể hiện được phương pháp giải phù hợp |
| **1** | Xác định đúng phương pháp nhưng chưa triển khai chính xác |
| **2** | Thực hiện đúng phần lớn các bước nhưng còn sai sót |
| **3** | Hoàn thành lời giải chính xác |

Biểu diễn dữ liệu điểm số thu được:

$$X_i \in \{0, 1, 2, 3\}$$

##### 3.4.2.2. Bản chất Mô hình Partial Credit (PCM)

* **Ước lượng xác suất:** PCM không tính điểm bằng cách chia điểm đạt được cho điểm tối đa, mà sử dụng mô hình xác suất để ước lượng năng lực tiềm ẩn của học sinh từ các mức điểm quan sát được.
* **Mở rộng mô hình Rasch:** Đưa mô hình Rasch (dành cho câu hỏi nhị phân $0/1$) sang áp dụng cho các bài tập có nhiều mức điểm theo thứ tự (Masters).

##### 3.4.2.3. Ý tưởng cốt lõi: Các bước chuyển về năng lực

Mỗi thang điểm đại diện cho một bước chuyển năng lực (*step transition*):

* $0 \rightarrow 1$: Bước chuyển 1 (Đạt điểm 1)
* $1 \rightarrow 2$: Bước chuyển 2 (Đạt điểm 2)
* $2 \rightarrow 3$: Bước chuyển 3 (Đạt điểm 3)

Mỗi bước chuyển này được đặc trưng bởi một tham số độ khó riêng, gọi là **step difficulty** (hoặc *step parameter*).

### 3.4.3. Phân tích chấm điểm từng phần: 
**Masters, G. N. (1988). The Analysis of Partial Credit Scoring. Applied Measurement in Education, 1(4), 279–297.**
Tài liệu trình bày cách áp dụng mô hình Partial Credit trong thực tế và thảo luận các vấn đề khi diễn giải điểm số từ câu hỏi có nhiều mức điểm.

### 3.4.4. Nghiên cứu so sánh chấm điểm nhị phân và chấm điểm từng phần: 
**May et al. (2023). Examining how using dichotomous and partial credit scoring models influence sixth-grade mathematical problem-solving assessment outcomes. School Science and Mathematics, 123(2), 54–67.** 

Nghiên cứu so sánh hai phương pháp chấm điểm trên bài đánh giá kỹ năng giải quyết vấn đề Toán học lớp 6.

Kết quả cho thấy các mô hình Rasch chấm nhị phân và chấm điểm từng phần đều có kết quả đo lường khá tương đồng trong bối cảnh nghiên cứu.