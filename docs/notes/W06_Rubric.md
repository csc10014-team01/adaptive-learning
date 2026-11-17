# W06: Generation Quality Rubric

- **Author:** Lê Thị Hoài Thương (QA & Evaluation Lead)
- **Status:** Review Required
- **Target Scope:** Đánh giá chi tiết chất lượng chuyên môn nội dung đề thi / câu hỏi sinh ra dựa trên Use cases UC-01, UC-02 (Phần Đại số tổ hợp - Toán 10).

---

## 1. Nguồn tham khảo & Lý do lựa chọn (References & Rationale)
- **Nguồn tham khảo:** 
  * **Educational Testing Service (ETS, 2014), *ETS Standards for Quality and Fairness*, Chương 7 (*Test Design and Development*), đặc biệt là Tiêu chuẩn 7.4 (*Obtaining Reviews*, tr. 31).** [Tiêu chuẩn 7.4](https://www.ets.org/pdfs/about/standards-quality-fairness.pdf#page=37)
  * **Phân phối chương trình Toán 10, phần Đại số tổ hợp.**
- **Lý do chọn tiêu chí:** Đảm bảo các câu hỏi và đề thi do hệ thống sinh ra đạt chất lượng chuyên môn sư phạm, chính xác về mặt toán học, bám sát kỹ năng mục tiêu và phản ánh đúng định hướng cá nhân hóa theo hồ sơ học sinh.

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
  * Đáp án phải trả lời đúng đại lượng được hỏi, nêu đủ điều kiện và đơn vị nếu có. Với câu trắc nghiệm, đáp án đúng phải duy nhất và các phương án nhiễu phải hợp lý.
* **C1.3. Tính đúng đắn và đầy đủ của các bước giải (10 điểm):**
  * Phần hướng dẫn giải (`explanation`) phải trình bày các bước có thứ tự: xác định cách đếm, giải thích lựa chọn công thức và điều kiện áp dụng, thực hiện các phép tính hoặc biến đổi cần thiết, rồi kết luận khớp với đáp án cuối cùng.
  * Mỗi bước phải xuất phát hợp lý từ dữ kiện và các bước trước; không bỏ sót lập luận quan trọng, đếm thiếu hoặc đếm trùng. Cần làm rõ việc xét thứ tự, cho phép lặp, phân biệt đối tượng và các ràng buộc khi có liên quan.

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

### 2.1. Thang chấm cho từng tiêu chí con

Mỗi tiêu chí con được chấm ở một mức nguyên **0–4** theo bảng dưới đây. Điểm quy đổi của tiêu chí con được tính bằng **mức chấm / 4 × điểm tối đa**; điểm C1–C4 là tổng điểm quy đổi của các tiêu chí con tương ứng. Ví dụ, C4.2 tối đa 6 điểm: mức 2 được 3 điểm, mức 3 được 4,5 điểm, mức 4 được 6 điểm; không tự cho 5/6 điểm ngoài thang này.

Chấm trên **toàn bộ đề**, ghi rõ mã câu hoặc bằng chứng dẫn đến mức chấm. Chỉ cho mức cao nhất khi tất cả yêu cầu của mức đó được đáp ứng. Nếu có hard-fail ở bất kỳ câu nào, áp dụng mục 3 trước; các mức điểm dưới đây không được dùng để bù lỗi hard-fail.

| Tiêu chí con (điểm tối đa) | Mức 0 | Mức 1 | Mức 2 | Mức 3 | Mức 4 |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **C1.1. Đề bài (10)** | Thiếu dữ kiện cốt lõi hoặc mâu thuẫn, không xác định được bài toán. | Phải sửa hoặc bổ sung dữ kiện mới giải được. | Có chi tiết mơ hồ cần làm rõ trước khi giải. | Đủ dữ kiện, chỉ có thông tin thừa không ảnh hưởng cách hiểu. | Đầy đủ, nhất quán, rõ đối tượng và điều kiện đếm. |
| **C1.2. Đáp án và phương án nhiễu (15)** | Không có đáp án nào hoặc có đáp án sai bản chất toán học; trường hợp sai bản chất là hard-fail. | Các đáp án hiện có đúng nhưng phần lớn câu còn thiếu đáp án hoặc phương án nhiễu bắt buộc. | Các đáp án hiện có đúng; còn thiếu đáp án hoặc phương án nhiễu bắt buộc ở ít nhất một câu, không quá một nửa số câu. | Tất cả câu có đáp án đúng và đủ phương án nếu có; còn lỗi trình bày nhỏ về kết luận hoặc đơn vị, không làm thay đổi ý nghĩa toán học. | Tất cả đáp án được kiểm chứng, đúng đại lượng, đủ điều kiện và đơn vị nếu có; với trắc nghiệm, đáp án đúng duy nhất và phương án nhiễu hợp lý. |
| **C1.3. Các bước giải (10)** | Không có các bước giải hoặc có lỗi sai về kiến thức toán học cơ bản; trường hợp sai bản chất là hard-fail. | Chỉ nêu công thức/đáp số hoặc thiếu phần lớn các bước cần thiết. | Hướng giải đúng nhưng thiếu bước suy luận hoặc tính toán quan trọng, người đọc phải tự bổ sung mới kiểm tra được kết quả. | Đủ bước và tính toán đúng, nhưng còn thiếu giải thích vì sao chọn cách đếm hoặc công thức. | Các bước đúng, đủ, có thứ tự; giải thích được lựa chọn phương pháp và điều kiện áp dụng; kết luận khớp đáp án. |
| **C2.1. Kỹ năng mục tiêu (15)** | Có câu ngoài phạm vi Đại số tổ hợp Toán 10 → hard-fail. | Phần lớn câu không kiểm tra kỹ năng được gắn. | Có ít nhất một câu gắn sai kỹ năng chính, dù vẫn thuộc chủ đề. | Kỹ năng chính đúng; còn thiếu hoặc thừa nhãn kỹ năng phụ. | Tất cả câu khớp kỹ năng chính/phụ theo catalogue và yêu cầu đề. |
| **C2.2. Độ khó (10)** | Toàn bộ câu lệch mức yêu cầu. | Phần lớn câu lệch mức yêu cầu. | Không quá một nửa số câu lệch mức yêu cầu. | Các câu chỉ lệch nhẹ; cần chỉnh nhãn ở tối đa một câu, lệch một mức liền kề. | Mức nhận thức và số bước suy luận của tất cả câu khớp nhãn/yêu cầu. |
| **C3.1. Ngôn ngữ (7)** | Không hiểu được yêu cầu hoặc thuật ngữ sai nghiêm trọng. | Nhiều câu khó hiểu, cần viết lại phần lớn. | Hiểu được nhưng còn lỗi diễn đạt hoặc thuật ngữ ở nhiều câu. | Chỉ có lỗi chính tả, lặp từ hoặc diễn đạt nhỏ, không đổi nghĩa. | Tiếng Việt rõ ràng, đúng thuật ngữ, không đa nghĩa. |
| **C3.2. Độc lập, không trùng lặp (7)** | Câu hỏi làm lộ đáp án của nhau hoặc lặp lại phần lớn nội dung. | Có nhiều câu cùng cấu trúc, chỉ thay số/ngữ cảnh. | Có một cặp câu cùng cấu trúc, chỉ thay số/ngữ cảnh. | Có câu cùng dạng nhưng khác điều kiện hoặc thao tác suy luận; không làm lộ đáp án. | Các câu độc lập; cách hỏi/điều kiện đếm đa dạng, không có cặp chỉ đổi số/ngữ cảnh. |
| **C3.3. Hiển thị (6)** | Công thức hoặc nội dung cốt lõi không đọc được trên giao diện. | Nhiều lỗi hiển thị cản trở làm bài. | Còn ít nhất một lỗi công thức/xuống dòng cần sửa để đọc đúng. | Chỉ có lỗi khoảng cách hoặc căn chỉnh nhỏ, không ảnh hưởng đọc hiểu. | Tất cả nội dung và công thức hiển thị rõ trên giao diện được kiểm tra. |
| **C4.1. Thành thạo kỹ năng (8)** | Phân bổ hoàn toàn đi ngược nhóm kỹ năng ưu tiên của hồ sơ. | Phần lớn câu ưu tiên sai nhóm kỹ năng. | Có ưu tiên kỹ năng yếu nhưng số câu chưa khớp kế hoạch đã chốt. | Đúng nhóm và số câu ưu tiên, nhưng có câu chưa phù hợp nhu cầu củng cố. | Đúng nhóm/số câu ưu tiên và nội dung phù hợp mức thành thạo có bằng chứng. |
| **C4.2. Phân phối độ khó (6)** | Không phản ánh hồ sơ hoặc kế hoạch độ khó. | Nhiều ô phân phối lệch kế hoạch. | Có phân hóa theo hồ sơ nhưng từ hai câu trở lên sai ô độ khó. | Chỉ một câu sai ô độ khó so với kế hoạch. | Số câu từng mức khớp kế hoạch, kể cả quy tắc làm tròn và xử lý thiếu nguồn đã chốt. |
| **C4.3. Lịch sử học tập (6)** | Bỏ qua lịch sử, lặp lại các bài đã thành thạo và không xử lý lỗi đã ghi nhận. | Phần lớn lựa chọn trái với mục tiêu ôn tập từ lịch sử. | Chỉ xử lý được một phần: tránh lặp bài hoặc tập trung lỗi cũ. | Xử lý được cả hai nhưng còn một trường hợp chưa phù hợp. | Dùng đúng lịch sử sẵn có, tránh bài đã thành thạo và tạo cơ hội sửa lỗi đã ghi nhận. |

Nếu một mô tả mức điểm dẫn đến lỗi chuyên môn nghiêm trọng theo mục 3 thì vẫn phải hard-fail. Không suy luận rằng mọi mức 0 đều tự động là hard-fail, hoặc mức lớn hơn 0 luôn loại trừ hard-fail. Khi nhiều mức có thể cùng phù hợp, chọn mức cao nhất thỏa đầy đủ mô tả và ghi lý do.

---

## 3. Điều kiện Hard-Fail, Xử lý tiêu chí không áp dụng & Cách tính điểm

- **Điều kiện Hard-Fail (Lỗi chuyên môn nghiêm trọng - Loại ngay 0 điểm / Không đạt):**
  1. *Sai kiến thức toán học căn bản:* Đề bài có giả thiết sai hoặc mâu thuẫn, khiến bài toán không có lời giải hợp lý, đáp án tính toán sai bản chất toán học hoặc bước giải dùng sai công thức, đếm thiếu/đếm trùng hay suy luận sai bản chất, kể cả khi đáp số tình cờ đúng.
  2. *Lỗi lạc chủ đề trọng tâm:* Câu hỏi sinh ra không thuộc phạm vi chương trình Toán 10 phần Đại số tổ hợp.
  3. *Lỗi lặp đề nghiêm trọng:* Các câu hỏi trong cùng một đề thi bị trùng lặp ý tưởng hoặc nội dung ≥30%.
  4. *Lỗi đi ngược năng lực cá nhân hóa:*

     **Điều kiện loại đề:** Với đề cá nhân hóa, nếu cần điều chỉnh mức độ khó của **từ 30% tổng số câu trở lên** để đúng kế hoạch thì đề bị hard-fail.

     **Căn cứ đối chiếu:** Kế hoạch phải được lập trước từ hồ sơ học sinh, đã tính đến cách làm tròn số câu và cách xử lý khi thiếu nguồn câu hỏi. Độ khó thực tế của từng câu được kiểm tra theo C2.2.

     **Cách tính:** So sánh số câu thực tế với kế hoạch ở từng mức độ khó. Cộng số câu **vượt kế hoạch** ở các mức; đây là số câu tối thiểu cần đổi mức để bù vào các mức còn thiếu. Mỗi câu chỉ tính một lần.

     **Ví dụ — đề 10 câu:**

     | Mức độ khó | Kế hoạch | Thực tế | Số câu vượt kế hoạch |
     | :--- | ---: | ---: | ---: |
     | Nhận biết | 4 | 1 | 0 |
     | Thông hiểu | 4 | 4 | 0 |
     | Vận dụng | 2 | 3 | 1 |
     | Vận dụng cao | 0 | 2 | 2 |

     Đề thiếu 3 câu Nhận biết, đồng thời dư 1 câu Vận dụng và 2 câu Vận dụng cao. Cần điều chỉnh **3/10 câu = 30% → hard-fail**.

     Nếu tỷ lệ cần điều chỉnh **dưới 30%**, trừ điểm C4.2 nhưng chưa loại đề theo điều kiện này.

### 3.1. Xử lý tiêu chí không áp dụng (N/A)

**N/A nghĩa là “không áp dụng”.** Tiêu chí được đánh dấu N/A sẽ không tham gia tính điểm; không coi là bị chấm 0 điểm.

**1. Chọn cách xử lý theo từng trường hợp**

Trước khi chấm, xác định ở cấp **tiêu chí con** (ví dụ C4.3) và ghi rõ lý do. Dùng bảng sau để phân biệt trường hợp không áp dụng với trường hợp có lỗi hoặc chưa được kiểm tra:

| Trường hợp | Cách xử lý |
| :--- | :--- |
| Đề chuẩn chung (`default_blueprint`), không yêu cầu cá nhân hóa | **N/A:** C4.1, C4.2 và C4.3. |
| Học sinh thực sự chưa có lịch sử học tập | **Có thể N/A:** C4.3. Vẫn chấm C4.1 và C4.2 theo kế hoạch dành cho hồ sơ đó. |
| Đề tự luận không có phương án nhiễu | **Vẫn chấm C1.2:** kiểm tra đáp án, bỏ qua phần phương án nhiễu. Không đánh dấu N/A cho cả tiêu chí. |
| Đầu ra thiếu các bước giải | **Trừ điểm C1.3**, không dùng N/A để bỏ qua phần còn thiếu. |
| Chưa kiểm tra hiển thị trên giao diện | Ghi C3.3 là **Chưa đánh giá**, không phải N/A. Cần kiểm tra và bổ sung bằng chứng trước khi kết luận Pass. |

Không dùng N/A để bỏ qua lỗi, chức năng còn thiếu hoặc bằng chứng chưa thu thập.

**2. Tính điểm**

- Bỏ tiêu chí N/A khỏi cả **điểm đạt được** và **điểm tối đa** khi tính tổng.
- Quy đổi phần còn lại về thang **100 điểm** theo công thức ở mục 3.2.
- Không chuyển điểm tối đa của tiêu chí N/A sang C1 hoặc C2.

**3. Ghi kết quả và áp dụng hard-fail**

- Liệt kê rõ **tiêu chí nào là N/A và vì sao**.
- Báo cáo riêng nhóm đề có đánh giá C4 và nhóm không áp dụng C4. Điểm của nhóm không áp dụng C4 **không chứng minh khả năng cá nhân hóa**.
- Chỉ áp dụng hard-fail về cá nhân hóa cho đề có yêu cầu cá nhân hóa. Vẫn kiểm tra các hard-fail khác theo phạm vi tương ứng.

### 3.2. Cách tính điểm từng đề và điểm trung bình

**1. Tính điểm từng tiêu chí con**

Mỗi tiêu chí con được chấm ở mức **0–4**, sau đó quy đổi theo điểm tối đa của tiêu chí đó:

$$p_j = \frac{r_j}{4} \times m_j$$

Trong đó: $r_j$ là mức chấm, $m_j$ là điểm tối đa và $p_j$ là điểm quy đổi của tiêu chí con $j$.

**2. Tính tổng điểm của đề**

- **Tất cả tiêu chí đều áp dụng:** cộng điểm C1, C2, C3 và C4.

$$\text{Total Score} = C_1 + C_2 + C_3 + C_4$$

- **Có tiêu chí N/A:** chỉ cộng các tiêu chí áp dụng, rồi quy đổi về thang 100. Gọi $A$ là tập các tiêu chí con áp dụng:

$$\text{Total Score} = 100 \times \frac{\sum_{j \in A} p_j}{\sum_{j \in A} m_j}$$

**Ví dụ khi C4 hoàn toàn N/A:**

| Tiêu chí | Điểm đạt | Điểm tối đa áp dụng |
| :--- | ---: | ---: |
| C1 | 30 | 35 |
| C2 | 25 | 25 |
| C3 | 17 | 20 |
| C4 | N/A | Không tính |
| **Tổng** | **72** | **80** |

$$\text{Total Score} = 100 \times \frac{72}{80} = 90/100$$

Khi báo cáo, ghi đủ: **điểm thô 72/80**, **C4.1–C4.3 là N/A** và **điểm chuẩn hóa 90/100**. Nếu không có tiêu chí nào áp dụng thì không tính điểm.

**3. Kết luận Pass/Fail và làm tròn điểm**

| Trường hợp | Kết luận |
| :--- | :--- |
| Có hard-fail | **0/100 — Fail**, bất kể điểm thành phần hoặc việc chuẩn hóa N/A. |
| Không có hard-fail, đã chấm đủ các tiêu chí áp dụng và tổng điểm ≥80/100 | **Pass**. |
| Không có hard-fail, đã chấm đủ các tiêu chí áp dụng và tổng điểm <80/100 | **Fail**. |
| Còn tiêu chí áp dụng chưa được chấm, chưa phát hiện hard-fail | **Chưa đánh giá đầy đủ**; chưa được kết luận Pass. |

- Không làm tròn điểm thành phần.
- Chỉ làm tròn điểm hiển thị cuối cùng đến **hai chữ số thập phân**.
- Quyết định Pass/Fail theo **điểm chưa làm tròn**.

**4. Tính điểm trung bình của các đề**

Với $n$ đề đã đánh giá đầy đủ, gọi $S_i$ là điểm tổng của đề thứ $i$:

$$\bar{S} = \frac{\sum_{i=1}^{n} S_i}{n}$$

- Đề hard-fail có $S_i = 0$ và **vẫn được tính vào số đề $n$**.
- Báo cáo kèm số đề được chấm, số đề Pass/Fail, số hard-fail và các trường hợp chưa đánh giá.
- Điểm trung bình **≥80/100 không có nghĩa là mọi đề đều Pass**.

---

## 4. Ví dụ cụ thể kịch bản chấm thử theo Rubric (Walkthrough Example)

**Hồ sơ giả định — Nguyễn Văn A**

| Kỹ năng | Điểm thành thạo (`mastery_score`) | Số bằng chứng (`evidence_count`) |
| :--- | ---: | ---: |
| A002 — Quy tắc nhân | 1,5 — cần cải thiện | 3 |
| A006 — Chỉnh hợp | 1,5 — cần cải thiện | 3 |
| A003 — Hoán vị | 2,5 | 3 |
| A009 — Đếm điều kiện có ràng buộc | 2,5 | 3 |

**Kế hoạch chấm đối chiếu giả định — 3 câu**

| Câu | Mức độ | Kỹ năng chính | Ưu tiên kỹ năng yếu |
| :---: | :--- | :--- | :---: |
| 1 | Thông hiểu | A006 | Có |
| 2 | Thông hiểu | A002 | Có |
| 3 | Vận dụng | A009, kết hợp A003 | Không |

**Lịch sử giả định**

- Đã ghi nhận lỗi không phân biệt thứ tự khi lập số.
- Học sinh đã thành thạo bài chọn nhóm không xét thứ tự thuộc A004 (Tổ hợp).
- Ba câu minh họa là bài mới, không lặp lại bài đã thành thạo. Câu 1 tạo cơ hội củng cố việc phân biệt thứ tự.

### 4.1. Nội dung đề thi sinh ra:

#### Câu 1

**Mức độ:** Thông hiểu · **Kỹ năng chính:** `A006` · **Kỹ năng phụ:** `A002`

**Đề bài:** Từ các chữ số $1, 2, 3, 4, 5$, có thể lập được bao nhiêu số tự nhiên gồm 3 chữ số khác nhau?

**Đáp án (`correct_answer`):** $A_5^3 = 60$ số.

**Các bước giải (`explanation`):**

1. Nhận dạng: Mỗi số tự nhiên gồm 3 chữ số khác nhau lập từ 5 chữ số là một chỉnh hợp chập 3 của 5 phần tử.
2. Áp dụng công thức $A_n^k = \frac{n!}{(n-k)!}$, tính $A_5^3 = \frac{5!}{2!} = 60$.
3. Kết luận: Có 60 số thỏa mãn yêu cầu.

#### Câu 2

**Mức độ:** Thông hiểu · **Kỹ năng chính:** `A002`

**Đề bài:** Một lớp học có 20 học sinh nam và 15 học sinh nữ. Có bao nhiêu cách chọn một học sinh nam làm lớp trưởng và một học sinh nữ làm lớp phó?

**Đáp án:** $20 \times 15 = 300$ cách.

**Các bước giải:**

1. Chọn lớp trưởng từ 20 học sinh nam: có 20 cách.
2. Với mỗi lựa chọn lớp trưởng, chọn lớp phó từ 15 học sinh nữ: có 15 cách.
3. Theo quy tắc nhân, số cách chọn là $20 \times 15 = 300$. Vậy có 300 cách.

#### Câu 3

**Mức độ:** Vận dụng · **Kỹ năng chính:** `A009` · **Kỹ năng phụ:** `A003`, `A002`

**Đề bài:** Có bao nhiêu cách xếp 4 học sinh nam và 3 học sinh nữ thành một hàng dọc sao cho cả 3 học sinh nữ đứng liền nhau? Các học sinh là những người phân biệt.

**Đáp án:** $720$ cách.

**Các bước giải:**

1. Vì 3 học sinh nữ phải đứng liền nhau, coi các bạn là một khối. Khối này cùng với 4 học sinh nam tạo thành 5 phần tử phân biệt.
2. Sắp xếp 5 phần tử thành hàng: có $5! = 120$ cách.
3. Với mỗi cách xếp trên, sắp xếp 3 học sinh nữ trong khối: có $3! = 6$ cách.
4. Mỗi hàng thỏa mãn xác định duy nhất vị trí khối nữ và thứ tự trong khối, nên không đếm thiếu hoặc trùng. Theo quy tắc nhân, tổng số cách là $120 \times 6 = 720$. Vậy có 720 cách.

### 4.2. Đánh giá chi tiết theo thang 0–4

| Tiêu chí con | Mức chấm | Điểm quy đổi | Căn cứ trong ví dụ giả định |
| :--- | :---: | ---: | :--- |
| C1.1 | 4 | 10 | Dữ kiện và điều kiện rõ; Câu 2 đã ấn định giới tính cho từng chức vụ. |
| C1.2 | 4 | 15 | Đáp án 60 số, 300 cách, 720 cách đúng với đại lượng và điều kiện từng câu, được kiểm chứng bằng các phép tính tương ứng. |
| C1.3 | 3 | 7,5 | Đủ bước tính; Câu 1 chưa giải thích rõ vì sao đổi thứ tự các chữ số tạo số khác và vì sao dùng chỉnh hợp thay vì tổ hợp. |
| C2.1 | 4 | 15 | Kỹ năng chính/phụ khớp catalogue và kế hoạch minh họa. |
| C2.2 | 4 | 10 | Hai câu áp dụng cách đếm cơ bản; câu còn lại cần gom khối và xét hoán vị trong khối, phù hợp mức nhận thức giả định. |
| C3.1 | 4 | 7 | Câu chữ rõ nghĩa; không còn mơ hồ về vai trò lớp trưởng/lớp phó. |
| C3.2 | 4 | 7 | Ba câu độc lập, không có cặp chỉ thay số/ngữ cảnh. |
| C3.3 | 4 | 6 | Theo giả định bản render đã được kiểm tra và không có lỗi. |
| C4.1 | 4 | 8 | Hai slot ưu tiên tập trung đúng A006 và A002 theo kế hoạch giả định. |
| C4.2 | 4 | 6 | Đúng kế hoạch giả định: 2 câu Thông hiểu, 1 câu Vận dụng. |
| C4.3 | 4 | 6 | Câu 1 tập trung lỗi về thứ tự; không lặp lại bài A004 đã thành thạo trong lịch sử giả định. |

### 4.3. Tổng kết điểm minh họa

**Không có tiêu chí N/A trong ví dụ.**

| Nhóm tiêu chí | Điểm đạt | Điểm tối đa |
| :--- | ---: | ---: |
| C1 — Chính xác và logic toán học | 32,5 | 35 |
| C2 — Sư phạm và kỹ năng mục tiêu | 25 | 25 |
| C3 — Ngôn ngữ và cấu trúc đề | 20 | 20 |
| C4 — Cá nhân hóa | 20 | 20 |
| **Tổng** | **97,5** | **100** |

$$\text{Total Score} = 32{,}5 + 25 + 20 + 20 = 97{,}5/100$$

**Kết luận trong ví dụ giả định:**

- **Kết quả:** 97,5/100, không có hard-fail → **Pass** theo rubric.
- **Điểm cần cải thiện:** Giải thích rõ lựa chọn chỉnh hợp ở bước 1 của Câu 1.
