# W06: Generation Quality Rubric (Detailed Draft)

- **Author:** Lê Thị Hoài Thương (QA & Evaluation Lead)
- **Status:** Draft / Review Required (Chờ nhóm review)
- **Target Scope:** Đánh giá chi tiết chất lượng chuyên môn nội dung đề thi / câu hỏi sinh ra dựa trên Use cases UC-01, UC-02 (Phần Đại số tổ hợp - Toán 10).

---

## 1. Nguồn tham khảo & Lý do lựa chọn (References & Rationale)
- **Nguồn tham khảo:** 
  * **Educational Testing Service (ETS, 2014), *ETS Standards for Quality and Fairness*, Chương 7 (*Test Design and Development*), đặc biệt là Tiêu chuẩn 7.4 (*Obtaining Reviews*, tr. 31).** [Tiêu chuẩn 7.4](https://www.ets.org/pdfs/about/standards-quality-fairness.pdf#page=37)
  * **Phân phối chương trình Toán 10, phần Đại số tổ hợp.**
- **Lý do chọn tiêu chí:** Đảm bảo các câu hỏi và đề thi do hệ thống sinh ra đạt chất lượng chuyên môn sư phạm, tuyệt đối chính xác về mặt toán học, bám sát kỹ năng mục tiêu và phản ánh đúng định hướng cá nhân hóa theo hồ sơ học sinh.

---

## 2. Tiêu chuẩn đánh giá chi tiết & Trọng số (Detailed Scoring Criteria & Weighting)

Tổng điểm tối đa: **100 điểm**. Ngưỡng đạt mục tiêu (Target Passing Score): **>= 80/100 điểm**.

### C1. Tính chính xác và logic toán học (Trọng số: 35% - Tối đa 35 điểm)
Tiêu chuẩn này đánh giá tính đúng đắn tuyệt đối về mặt kiến thức toán học của câu hỏi, phương án lựa chọn và phần lời giải.
* **C1.1. Tính chính xác của đề bài (10 điểm):**
  * Các giả thiết, dữ kiện cho trong đề bài phải đầy đủ, mạch lạc và không mâu thuẫn lẫn nhau.
  * Bài toán phải có nghiệm hoặc có hướng giải quyết hợp lý trong tập hợp số học phổ thông (chương trình Toán 10), không tồn tại các điều kiện vô lý làm triệt tiêu bản chất bài toán tổ hợp.
* **C1.2. Tính chính xác của đáp án cuối cùng & phương án nhiễu (15 điểm):**
  * Kết quả đáp án cuối cùng (`correct_answer`) phải được tính toán chính xác tuyệt đối (ví dụ: áp dụng đúng công thức hoán vị $P_n$, chỉnh hợp $A_n^k$, tổ hợp $C_n^k$, hoặc quy tắc cộng/nhân).
  * Đối với dạng câu hỏi tự luận, hệ thống phải cung cấp khung biểu điểm chi tiết (marking scheme) phân bổ rõ ràng cho từng bước giải (ví dụ: bước nhận dạng toán, bước áp dụng công thức, bước biến đổi trung gian và kết quả), đảm bảo giáo viên hoặc hệ thống chấm tự luận có căn cứ chấm điểm minh bạch.
* **C1.3. Chất lượng của phần lời giải chi tiết (10 điểm):**
  * Phần hướng dẫn giải (`explanation`) phải trình bày từng bước logic rõ ràng: từ việc nhận diện dạng toán, áp dụng công thức nào, cho đến các bước biến đổi trung gian và kết luận.
  * Lời giải không được bỏ sót bước hoặc nhảy cóc khiến người đọc khó hiểu.

### C2. Độ phù hợp sư phạm & Kỹ năng mục tiêu (Trọng số: 25% - Tối đa 25 điểm)
Tiêu chuẩn này đánh giá mức độ bám sát chương trình học và tính phân hóa năng lực học sinh.
* **C2.1. Sự bám sát kỹ năng mục tiêu (15 điểm):**
  * Nội dung câu hỏi phải phản ánh chính xác kỹ năng được chỉ định (`skill_id`) trong chương trình Toán 10 phần Đại số tổ hợp (như quy tắc đếm, hoán vị, chỉnh hợp, tổ hợp, nhị thức Newton).
  * Không xuất hiện hiện tượng lạc đề, lan man sang các chủ đề hình học, đại số đại cương hoặc chương trình lớp khác.
* **C2.2. Tính phù hợp của mức độ khó (10 điểm):**
  * Độ khó của câu hỏi phải phản ánh đúng năng lực học sinh theo phân loại mức độ nhận thức (từ nhận biết, thông hiểu cho đến vận dụng/vận dụng cao).
  * Tránh trường hợp gắn nhãn câu hỏi là mức độ khó nhưng thực chất chỉ là áp dụng công thức cơ bản một bước, hoặc ngược lại.

### C3. Chất lượng ngôn ngữ & Cấu trúc đề (Trọng số: 20% - Tối đa 20 điểm)
Tiêu chuẩn này đảm bảo đề thi đạt tiêu chuẩn sư phạm về mặt hình thức trình bày và văn phong.
* **C3.1. Văn phong và thuật ngữ toán học (7 điểm):**
  * Sử dụng ngôn ngữ tiếng Việt trong sáng, chuẩn mực, đúng thuật ngữ toán học phổ thông.
  * Không sử dụng câu văn tối nghĩa, đa nghĩa hoặc gây hiểu lầm cho học sinh khi đọc đề.
* **C3.2. Tính độc lập và không trùng lặp (7 điểm):**
  * Các câu hỏi trong cùng một đề thi phải độc lập với nhau, dữ kiện của câu này không làm lộ đáp án hoặc ảnh hưởng đến câu khác.
  * Không có hiện tượng lặp lại nguyên văn hoặc chỉ thay đổi con số một cách máy móc giữa các câu hỏi trong cùng một bộ đề.
* **C3.3. Tính trực quan và định dạng hiển thị (6 điểm):**
  * Các biểu thức, ký hiệu toán học (phân số, chỉ số trên/dưới, ký hiệu tổ hợp $C_n^k$) phải được trình bày rõ ràng, mạch lạc, dễ đọc.

### C4. Khả năng cá nhân hóa theo hồ sơ học sinh (Trọng số: 20% - Tối đa 20 điểm)
Tiêu chuẩn này đánh giá mức độ chính xác của đề thi khi được điều chỉnh dựa trên hồ sơ năng lực thực tế của học sinh.
* **C4.1. Sự phù hợp với mức độ thành thạo kỹ năng (8 điểm):**
  * Đối với học sinh có điểm thành thạo thấp (`mastery_score` thấp) ở một kỹ năng cụ thể, đề thi phải ưu tiên phân bổ các câu hỏi tập trung vào kỹ năng đó nhằm giúp học sinh củng cố phần kiến thức còn hổng.
  * Đối với học sinh có mức độ thành thạo cao, đề thi cần tăng tỷ lệ câu hỏi ở mức độ vận dụng cao để phát huy năng lực.
* **C4.2. Tính đúng đắn của việc phân phối tỷ lệ câu hỏi (6 điểm):**
  * Đánh giá việc phân bổ tỷ lệ các mức độ khó có phản ánh đúng trạng thái năng lực của học sinh trong hồ sơ hay không.
* **C4.3. Tính nhất quán với lịch sử học tập (6 điểm):**
  * Đề thi sinh ra phải tận dụng được dữ liệu từ lịch sử làm bài trước đó, tránh lặp lại các bài toán học sinh đã thành thạo hoặc bỏ sót các lỗi tư duy học sinh từng mắc phải.

---

## 3. Điều kiện Hard-Fail, Xử lý tiêu chí không áp dụng & Cách tính điểm

- **Điều kiện Hard-Fail (Lỗi chuyên môn nghiêm trọng — Loại ngay 0 điểm / Không đạt):**
  1. *Sai kiến thức toán học căn bản:* Đề bài sai giả thiết vô nghiệm vô lý hoặc đáp án tính toán sai bản chất toán học.
  2. *Lỗi lạc chủ đề trọng tâm:* Câu hỏi sinh ra không thuộc phạm vi chương trình Toán 10 phần Đại số tổ hợp.
  3. *Lỗi lặp đề nghiêm trọng:* Các câu hỏi trong cùng một đề thi bị trùng lặp ý tưởng hoặc nội dung quá nhiều.
  4. *Lỗi đi ngược năng lực cá nhân hóa:* Sinh đề quá khó đối với học sinh có mức độ thành thạo kém (gây nản chí) hoặc quá dễ đối với học sinh giỏi.

- **Cách xử lý tiêu chí không áp dụng:** 
  Trong các trường hợp sinh đề chuẩn chung (Default Blueprint) không yêu cầu cá nhân hóa sâu theo hồ sơ học sinh, tiêu chí **C4** sẽ được tạm hoãn và trọng số sẽ được quy đổi tỷ trọng phân bổ đều sang C1 và C2 theo thống nhất của nhóm.

- **Cách tính điểm trung bình để đánh giá mục tiêu 80/100:**
  Điểm tổng chất lượng đề thi được tính bằng tổng tích các điểm thành phần nhân với trọng số tương ứng: 
  $$\text{Total Score} = (C_1 \times 0.35) + (C_2 \times 0.25) + (C_3 \times 0.20) + (C_4 \times 0.20)$$
  Để được công nhận **Đạt mục tiêu (Pass)**, đề thi phải đạt tổng điểm từ **80/100 trở lên** và **tuyệt đối không vi phạm bất kỳ lỗi Hard-Fail nào**.

---

## 4. Phân biệt chi tiết: Rubric Đánh Giá Đề Sinh Ra vs. Barem Chấm Bài Học Sinh

Để tránh nhầm lẫn trong quá trình vận hành hệ thống kiểm định, nhóm phân định rõ ràng ranh giới, phạm vi và mục đích giữa hai khái niệm này như sau:

| Tiêu chí so sánh | Rubric Đánh Giá Chất Lượng Đề Sinh Ra (Tài liệu này - W06) | Barem Chấm Điểm Bài Làm Học Sinh (Grading Scheme / Rubric Chấm Bài) |
| :--- | :--- | :--- |
| **Đối tượng đánh giá** | Đánh giá **chất lượng của bộ câu hỏi và đề thi** do hệ thống AI sinh ra (Question & Exam Generation). | Đánh giá **chất lượng câu trả lời và bài làm thực tế** của học sinh sau khi hoàn thành bài kiểm tra. |
| **Chủ thể áp dụng** | Hội đồng chuyên môn, giáo viên bộ môn hoặc hệ thống kiểm định chất lượng nội dung tự động trước khi phát hành đề. | Hệ thống chấm tự động (AI Evaluator) hoặc giáo viên khi chấm điểm chi tiết bài làm của từng học sinh. |
| **Tiêu chí trọng tâm** | - Tính chính xác toán học của đề bài, đáp án, lời giải.<br>- Độ phù hợp sư phạm và mức độ khó.<br>- Chất lượng ngôn ngữ, cấu trúc và tính không trùng lặp.<br>- Khả năng cá nhân hóa dựa trên hồ sơ học sinh (`mastery_score`). | - Tính đúng đắn của các bước biến đổi trung gian.<br>- Mức điểm thưởng/trừ theo từng ý trong lời giải tự luận.<br>- Khả năng nhận diện các lỗi sai phổ biến của học sinh (như tính toán nhầm, áp dụng sai công thức). |
| **Thời điểm sử dụng** | **Trước khi thi (Pre-exam phase):** Dùng để lọc, duyệt hoặc yêu cầu hệ thống tái tạo (`regenerate`) các đề thi chưa đạt chuẩn. | **Sau khi thi (Post-exam phase):** Dùng để chấm bài, quy đổi điểm số và cập nhật lại mức độ thành thạo (`evidence_count` & `mastery_score`) vào hồ sơ học sinh. |
| **Mục tiêu đầu ra** | Đảm bảo đề thi đủ tiêu chuẩn sư phạm, không có lỗi toán học, đạt ngưỡng $\ge 80/100$ điểm để đưa vào ngân hàng đề thi chính thức. | Đưa ra điểm số chính xác, khách quan kèm theo lời giải thích (`explanation`) giúp học sinh hiểu rõ nguyên nhân sai sót. |

---

## 5. Ví dụ cụ thể kịch bản chấm thử theo Rubric (Walkthrough Example)

* **Bối cảnh học sinh:** Học sinh Nguyễn Văn A có mức độ thành thạo kỹ năng **Quy tắc đếm cơ bản và Hoán vị** (`skill_id: COMB_01`) ở mức *cần cải thiện* (điểm thấp trong hồ sơ), trong khi kỹ năng *Tổ hợp và Chỉnh hợp* ở mức trung bình. Hệ thống tiến hành sinh một đề kiểm tra ngắn gồm 3 câu hỏi dựa trên hồ sơ cá nhân hóa này.

### 5.1. Nội dung đề thi sinh ra:
* **Câu 1 (Mức độ Nhận biết - Kỹ năng yếu `COMB_01`):** *Từ các chữ số $1, 2, 3, 4, 5$, có thể lập được bao nhiêu số tự nhiên gồm 3 chữ số khác nhau?*
  * *Đáp án chuẩn (`correct_answer`):* $A_5^3 = 60$ số.
  * *Lời giải chi tiết (`explanation`):* Mỗi số tự nhiên gồm 3 chữ số khác nhau lập từ 5 chữ số là một chỉnh hợp chập 3 của 5 phần tử. Ta có công thức $A_n^k = \frac{n!}{(n-k)!}$. Thay số vào ta được $A_5^3 = \frac{5!}{2!} = 60$.
* **Câu 2 (Mức độ Thông hiểu - Kỹ năng yếu `COMB_01`):** *Một lớp học có 20 học sinh nam và 15 học sinh nữ. Có bao nhiêu cách chọn ra một đôi nam nữ làm lớp trưởng và lớp phó?*
  * *Đáp án chuẩn:* $20 \times 15 = 300$ cách.
  * *Lời giải chi tiết:* Áp dụng quy tắc nhân, chọn 1 học sinh nam từ 20 nam có 20 cách; chọn 1 học sinh nữ từ 15 nữ có 15 cách. Số cách chọn là $20 \times 15 = 300$.
* **Câu 3 (Mức độ Vận dụng - Kỹ năng trung bình):** *Có bao nhiêu cách xếp 4 học sinh nam và 3 học sinh nữ thành một hàng dọc sao cho các học sinh nữ luôn đứng cạnh nhau?*
  * *Đáp án chuẩn:* $720$ cách.
  * *Lời giải chi tiết:* Coi 3 học sinh nữ là một khối (1 phần tử), kết hợp với 4 học sinh nam thành 5 phần tử xếp hàng dọc (có $5! = 120$ cách). Trong khối 3 học sinh nữ, các bạn có thể đổi chỗ cho nhau (có $3! = 6$ cách). Theo quy tắc nhân, tổng số cách là $120 \times 6 = 720$.

### 5.2. Đánh giá chi tiết theo tiêu chí Rubric:
* **C1: Tính chính xác và logic toán học (Trọng số 35% - Điểm tối đa 35):**
  * *Đánh giá:* Cả 3 câu hỏi đều có giả thiết rõ ràng, không mâu thuẫn. Đáp án của các câu được tính toán chính xác tuyệt đối. Lời giải chi tiết trình bày từng bước logic từ việc nhận diện công thức đến kết quả cuối cùng.
  * *Điểm đạt:* **35 / 35 điểm**.
* **C2: Độ phù hợp sư phạm & Kỹ năng mục tiêu (Trọng số 25% - Điểm tối đa 25):**
  * *Đánh giá:* Các câu hỏi bám sát đúng chương trình Toán 10 phần Đại số tổ hợp. Phân phối mức độ khó hợp lý (từ nhận biết đến vận dụng), đúng chuẩn phân loại nhận thức.
  * *Điểm đạt:* **25 / 25 điểm**.
* **C3: Chất lượng ngôn ngữ & Cấu trúc đề (Trọng số 20% - Điểm tối đa 20):**
  * *Đánh giá:* Văn phong tiếng Việt trong sáng, chuẩn thuật ngữ toán học phổ thông. Các câu hỏi độc lập nhau, không bị trùng lặp ý tưởng. Ký hiệu toán học rõ ràng.
  * *Điểm đạt:* **18 / 20 điểm** *(trừ nhẹ 2 điểm do diễn đạt câu 3 ở phần cấu trúc chữ nghĩa hơi dài dòng một chút)*.
* **C4: Khả năng cá nhân hóa theo hồ sơ học sinh (Trọng số 20% - Điểm tối đa 20):**
  * *Đánh giá:* Đề thi đã thể hiện rõ tính cá nhân hóa khi ưu tiên phân bổ 2 trên tổng số 3 câu hỏi tập trung vào kỹ năng `COMB_01` (quy tắc đếm và chỉnh hợp) mà học sinh đang có điểm thành thạo thấp trong hồ sơ, giúp học sinh củng cố đúng vùng kiến thức còn hổng.
  * *Điểm đạt:* **18 / 20 điểm**.

### 5.3. Tổng kết điểm chất lượng đề thi:
$$\text{Total Score} = 35 + 25 + 18 + 18 = 96 / 100 \text{ điểm}$$

* **Kết quả chung:** Đạt từ 80/100 trở lên, không vi phạm lỗi Hard-Fail $\rightarrow$ **Đạt chuẩn chuyên môn nội dung (Pass)**.
