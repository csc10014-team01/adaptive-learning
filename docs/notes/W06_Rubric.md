# W06 — Generation Quality Rubric

**Phiên bản:** Revised v2.0 — đề xuất để QA Lead phê duyệt

**Tác giả gốc:** Lê Thị Hoài Thương (QA & Evaluation Lead)

**Phạm vi:** UC-01, UC-02; chất lượng câu hỏi và đề kiểm tra Đại số tổ hợp — Toán 10

**Trạng thái:** Review Required — chưa coi là contract đã được phê duyệt

**Nguyên tắc:** Đánh giá chất lượng nội dung trước khi phát hành, không thay thế barem chấm bài học sinh hoặc kiểm thử hiệu năng hệ thống.

> **Lưu ý đối chiếu:** Bản này hợp nhất các đoạn cũ/mới trong tệp W06 do nhóm cung cấp. Không có ảnh gốc kèm theo để đối chiếu trực quan. Các quy tắc kỹ thuật được bổ sung (đặc biệt ngưỡng trùng ý tưởng và trạng thái REVIEW_REQUIRED) là **đề xuất cần chốt**, không được coi là quyết định đã được QA Lead thông qua.

## Ghi chú tích hợp vào repository — 20/11/2026

Bản Revised v2.0 thay thế nội dung bản nháp W06 trước đây để review tiêu chí chất lượng câu hỏi/đề thi. Đây là cập nhật tài liệu; code, API và chính sách chấm đang chạy chưa được chuyển sang v2.0. Các mục dưới đây mô tả specification đề xuất, không xác nhận tính năng đã triển khai.

**Chính sách đã được chủ dự án phê duyệt ngày 14/11/2026, hiện vẫn dùng trong code** (`w06-approved-integration-v1`):

- Đề thích ứng: cộng trực tiếp C1/C2/C3/C4 theo tối đa **35/25/20/20**, không nhân trọng số lần hai.
- Structured Assessment (`default_blueprint`): C4 không áp dụng; tối đa C1/C2/C3 là **45/35/20**. Quy tắc chuẩn hóa theo tổng trọng số áp dụng ở mục 5–6 của v2.0 là thay đổi đề xuất, chưa thay thế cách chấm hiện hành.
- Giáo viên vẫn được duyệt thủ công cả đề khi báo cáo còn `NEEDS_REVIEW`; hành động này không chuyển báo cáo thành `PASS` hoặc tự cấp điểm. Lỗi đã xác nhận vẫn bị chặn.
- Code hiện ghi nhận bằng chứng ở cấp C1–C4; chưa triển khai đầy đủ thang 0–4 cho 11 tiêu chí con, ngưỡng Hard-Fail 30%, contract và tên trạng thái của v2.0. Ngưỡng trùng ý tưởng/lệch độ khó nghiêm trọng vẫn chưa được bật trong policy hiện hành.

Xem [Quality Gate hiện hành](../design/W06_Exam_Quality_Gate.md). Khi triển khai v2.0 cần đồng bộ evaluator, contract, giao diện, công cụ chấm và kiểm thử theo chính sách đã chốt.

**Bộ thực nghiệm 30 đề ngày 14/11/2026:** giữ nguyên [rubric snapshot](../../eval/results/w06/20261114_formal_01/rubric_snapshot.md), manifest và phiếu chấm gốc. Việc thay tài liệu này không chấm lại hoặc đổi kết quả bộ cũ. Nếu đánh giá lại bằng v2.0, lưu thành đợt đánh giá riêng, ghi rõ phiên bản rubric.

## 1. Cơ sở, mục đích và phạm vi

**Cơ sở tham khảo:** ETS (2014), *ETS Standards for Quality and Fairness*, chương 7 về thiết kế và phát triển bài kiểm tra, đặc biệt nội dung rà soát chuyên môn; chương trình Toán 10 và catalogue kỹ năng Đại số tổ hợp do nhóm sử dụng. Việc viện dẫn ETS là cơ sở tham khảo về kiểm soát chất lượng, **không có nghĩa** ETS quy định các trọng số 35/25/20/20 hoặc các ngưỡng 30% của dự án.

**Đối tượng:** (i) câu hỏi: dữ kiện, đáp án, lời giải, kỹ năng, độ khó, ngôn ngữ, hiển thị; (ii) toàn đề: cấu trúc, trùng lặp, phân phối kỹ năng/độ khó, cá nhân hóa; (iii) hệ thống: hiệu năng, lưu/tải, lỗi, UX được kiểm thử riêng, **không tính vào 100 điểm nội dung**.

**Đơn vị kết luận:** một đề. Điểm từng câu được tổng hợp vào các tiêu chí cấp câu; các tiêu chí cấp đề chấm trực tiếp. Đề chỉ **PASS** khi đã đủ đánh giá, không có Hard-Fail và điểm chưa làm tròn ≥80/100.

## 2. Cấu trúc tiêu chí và trọng số

| Nhóm | Tiêu chí con | Điểm tối đa | Cấp đánh giá | Phương thức chủ đạo |
|---|---|---:|---|---|
| C1 — Chính xác và logic toán học (35) | C1.1 Dữ kiện, giả thiết và tính xác định | 10 | Câu | Code kiểm tra hình thức + Qwen + giáo viên khi nghi vấn |
| | C1.2 Đáp án, tính duy nhất và phương án nhiễu (nếu có) | 15 | Câu | Code/solver độc lập + giáo viên xác nhận trường hợp không kiểm chứng được |
| | C1.3 Lập luận và các bước giải | 10 | Câu | Qwen hỗ trợ + giáo viên; code kiểm tra nhất quán có thể xác định |
| C2 — Sư phạm và kỹ năng mục tiêu (25) | C2.1 Bám sát skill catalogue | 15 | Câu | Code đối chiếu nhãn + Qwen + giáo viên |
| | C2.2 Độ khó nhận thức thực tế | 10 | Câu | Qwen gợi ý + giáo viên hiệu chuẩn |
| C3 — Ngôn ngữ và cấu trúc đề (20) | C3.1 Ngôn ngữ, thuật ngữ | 7 | Câu | Qwen + giáo viên |
| | C3.2 Độc lập và không trùng ý tưởng | 7 | Đề | Code tìm ứng viên + Qwen/giáo viên xác nhận |
| | C3.3 Hiển thị công thức, bố cục | 6 | Câu | Code/render test + kiểm tra giao diện |
| C4 — Cá nhân hóa (20) | C4.1 Ưu tiên kỹ năng theo mastery | 8 | Đề | Code đối chiếu ExamPlan + giáo viên khi cần |
| | C4.2 Phân phối độ khó theo ExamPlan | 6 | Đề | Code đếm + nhãn độ khó đã được xác minh |
| | C4.3 Phù hợp lịch sử học tập | 6 | Đề | Code đối chiếu lịch sử + Qwen/giáo viên |
| **Tổng** | **11 tiêu chí con** | **100** | | |

**Nguyên tắc phân quyền:** Code thực hiện phép đếm, so sánh ID/metadata, xác thực schema và các điều kiện định lượng. Qwen là **bộ đánh giá hỗ trợ**, không được tự coi đánh giá ngữ nghĩa là chân lý. Giáo viên/QA là nguồn quyết định khi bằng chứng xung đột, không đủ chắc chắn hoặc có nguy cơ lỗi toán học nghiêm trọng. Đánh giá tự động chỉ được kết luận PASS nếu mọi tiêu chí bắt buộc có bằng chứng được chấp nhận theo chính sách QA đã duyệt.

## 3. Thang chấm chi tiết 0–4

Mỗi tiêu chí con áp dụng cho một câu được chấm **một mức nguyên** 0–4 cho mỗi câu; tiêu chí cấp đề được chấm một mức nguyên 0–4 cho cả đề. Chọn mức cao nhất đáp ứng **đầy đủ** mô tả. Mức 0 **không mặc nhiên** đồng nghĩa Hard-Fail; ngược lại lỗi Hard-Fail có thể xảy ra bất kể mức điểm.

### 3.1. Cấp câu hỏi

| Tiêu chí | 0 | 1 | 2 | 3 | 4 |
|---|---|---|---|---|---|
| **C1.1** | Thiếu/mâu thuẫn dữ kiện cốt lõi, không xác định bài toán | Phải bổ sung/sửa dữ kiện mới giải được | Có chi tiết mơ hồ cần làm rõ | Đủ dữ kiện, có thông tin thừa không gây hiểu sai | Dữ kiện đầy đủ, nhất quán; rõ đối tượng và điều kiện đếm |
| **C1.2** | Không có đáp án hoặc đáp án sai | Đáp án đúng nhưng thiếu bộ lựa chọn bắt buộc của trắc nghiệm | Đáp án đúng nhưng thiếu điều kiện trình bày hoặc nhiễu chưa đầy đủ/hợp lý | Đáp án đúng, đủ lựa chọn; lỗi trình bày nhỏ | Đáp án được kiểm chứng, đúng đại lượng; trắc nghiệm có duy nhất một lựa chọn đúng và nhiễu hợp lý |
| **C1.3** | Không có lời giải hoặc suy luận sai kiến thức cơ bản | Chỉ có công thức/đáp số, thiếu phần lớn lập luận | Hướng đúng nhưng thiếu bước quan trọng | Các bước đúng và đủ nhưng giải thích chọn phương pháp chưa rõ | Các bước đúng, đủ, có thứ tự, giải thích điều kiện áp dụng, tránh đếm thiếu/trùng và khớp đáp án |
| **C2.1** | Ngoài phạm vi Đại số tổ hợp Toán 10 | Gắn sai kỹ năng chính, không có kỹ năng phụ phù hợp | Sai kỹ năng chính nhưng có kỹ năng phụ phù hợp | Kỹ năng chính đúng, nhãn phụ còn thiếu/thừa | Kỹ năng chính/phụ khớp catalogue và yêu cầu |
| **C2.2** | Độ khó thực tế lệch 3 bậc | Lệch 2 bậc | Lệch 1 bậc | Đúng bậc nhưng yêu cầu suy luận hơi nhẹ/nặng so với mô tả | Đúng bậc và đúng yêu cầu suy luận đã chốt |
| **C3.1** | Không hiểu yêu cầu/thuật ngữ sai nghiêm trọng | Cần viết lại phần lớn | Nhiều lỗi diễn đạt/thuật ngữ | Lỗi nhỏ không đổi nghĩa | Rõ nghĩa, chuẩn tiếng Việt và thuật ngữ toán |
| **C3.3** | Nội dung/công thức cốt lõi không đọc được | Nhiều lỗi cản trở làm bài | Có lỗi công thức/xuống dòng phải sửa | Lỗi căn chỉnh nhỏ | Nội dung và công thức hiển thị đúng trên giao diện đã kiểm tra |

**C2.2:** Thứ tự bậc: Nhận biết (0) → Thông hiểu (1) → Vận dụng (2) → Vận dụng cao (3). Khoảng cách = trị tuyệt đối hiệu chỉ số. Nhãn độ khó **thực tế** cần bằng chứng từ lời giải/yêu cầu nhận thức, không lấy nhãn do generator tự gắn làm sự thật.

**C1.2:** Câu tự luận không bắt buộc có phương án nhiễu. Nếu sản phẩm yêu cầu `marking_scheme` cho tự luận, kiểm tra sự tồn tại và tính nhất quán của khung biểu điểm trong checklist bắt buộc; lỗi thiếu khung biểu điểm không được che bằng N/A.

### 3.2. Cấp đề

| Tiêu chí | 0 | 1 | 2 | 3 | 4 |
|---|---|---|---|---|---|
| **C3.2** | Câu làm lộ đáp án của nhau hoặc lặp phần lớn nội dung | Nhiều câu cùng cấu trúc, chỉ đổi số/ngữ cảnh | Có một cặp cùng cấu trúc, chỉ đổi số/ngữ cảnh | Cùng dạng nhưng khác điều kiện/thao tác suy luận | Các câu độc lập, không có cặp chỉ đổi số/ngữ cảnh |
| **C4.1** | Hoàn toàn đi ngược ưu tiên kỹ năng | Phần lớn câu ưu tiên sai | Có ưu tiên đúng nhưng số câu chưa khớp kế hoạch | Đúng số câu ưu tiên, có câu chưa phù hợp nhu cầu củng cố | Đúng kỹ năng, đúng số câu và có bằng chứng phù hợp mastery |
| **C4.2** | Không phản ánh hồ sơ/kế hoạch | Sai phân phối nghiêm trọng, nhiều ô lệch | Có phân hóa nhưng ≥2 câu tối thiểu phải thay mức | Chỉ 1 câu tối thiểu phải thay mức | Số câu từng mức khớp ExamPlan đã chốt |
| **C4.3** | Bỏ qua lịch sử, lặp bài đã thành thạo và không xử lý lỗi cũ | Phần lớn lựa chọn trái mục tiêu lịch sử | Chỉ đáp ứng một trong hai: tránh lặp hoặc sửa lỗi | Đáp ứng cả hai, còn một trường hợp chưa phù hợp | Khai thác đúng lịch sử, tránh lặp bài đã thành thạo và nhắm lỗi được ghi nhận |

**Quy tắc cho C4.2:** Các mô tả 0–2 định tính cần giáo viên hiệu chuẩn khi có tranh chấp. Có thể áp dụng bảng quy tắc định lượng nhất quán hơn: `mismatch=0 → 4; mismatch=1 → 3; mismatch=2 → 2; mismatch≥3 → 1`, riêng mức 0 khi không có ExamPlan hợp lệ hoặc toàn bộ phân phối không phản ánh kế hoạch. Đây là **đề xuất thay thế cần phê duyệt**; không được dùng đồng thời hai bảng theo hai cách khác nhau. Khi mismatch/N≥30% áp dụng Hard-Fail trước.

## 4. Hard-Fail: điều kiện và thuật toán

**Chính sách:** Khi một Hard-Fail được **xác nhận**, đề có `final_score=0`, `status=FAIL`, lưu riêng `diagnostic_score` và điểm từng tiêu chí để sửa lỗi. Nếu chỉ có nghi vấn chưa được xác minh, trạng thái `REVIEW_REQUIRED`, **không tự động** gán PASS hoặc Hard-Fail.

### HF-01 — Lỗi toán học nghiêm trọng (cấp câu)

Bất kỳ câu nào có giả thiết mâu thuẫn khiến không thể giải theo ý định, đáp án sai bản chất, nhiều đáp án đúng khi yêu cầu một đáp án, dùng sai công thức/suy luận/đếm thiếu hoặc đếm trùng làm hỏng lập luận, kể cả khi đáp số tình cờ đúng. Bằng chứng gồm `question_id`, mô tả lỗi, phép kiểm tra độc lập hoặc xác nhận của giáo viên. Một bài toán cố ý hỏi số trường hợp bằng 0 **không mặc nhiên** là lỗi.

### HF-02 — Ngoài phạm vi nội dung (cấp câu)

Bất kỳ câu nào có nội dung chính ngoài catalogue/phạm vi Đại số tổ hợp Toán 10 đã chốt. Kiểm tra nhãn không đủ để khẳng định nội dung thực tế; trường hợp mơ hồ chuyển review.

### HF-03 — Trùng ý tưởng ≥30% (cấp đề)

**Định nghĩa đề xuất (chọn cách B):** Một nhóm câu được coi trùng ý tưởng khi cùng mục tiêu nhận thức, cùng cấu trúc suy luận/điều kiện đếm, cùng cách giải cốt lõi và chỉ khác số liệu, tên gọi hoặc ngữ cảnh bề mặt. **Không** tự coi mọi câu cùng `skill_id` là trùng. Các câu cùng dạng nhưng có ràng buộc mới làm thay đổi chiến lược giải có thể không trùng.

**Thuật toán chuẩn:**

1. Chuẩn hóa văn bản và metadata; lấy `source_id`, `template_id`, `skill_id`, mô tả thao tác suy luận, điều kiện xét thứ tự/lặp/ràng buộc.
2. Code đánh dấu cặp ứng viên trùng chính xác (ID/nội dung chuẩn hóa) và ứng viên trùng cấu trúc (template/concept fingerprint). Các cặp ngữ nghĩa chưa chắc chắn được Qwen hỗ trợ phân tích, giáo viên/QA xác nhận.
3. Lập các **nhóm tương đương đã xác nhận**; mỗi nhóm giữ một câu đại diện, các câu còn lại là câu dư. Không dùng nối thành phần liên thông mù quáng từ các phán đoán cặp không bắc cầu: nếu A≈B, B≈C nhưng A không≈C, phải QA phân nhóm lại.
4. Với N câu, số câu dư `D = Σ_g (size(g) − 1) = N − G`, trong đó G là số nhóm ý tưởng đã xác nhận (kể cả nhóm một câu). `duplicate_ratio = D/N`.
5. `D/N ≥ 0.30` ⇒ **HF-03**. So sánh bằng số nguyên `10×D ≥ 3×N`, tránh sai số số thực. Với N=0, dữ liệu đề không hợp lệ, không chia cho 0.

**Ví dụ:** 10 câu có hai nhóm trùng kích thước 3 và 2, còn 5 câu đơn lẻ → D=(3−1)+(2−1)=3 → 30% → Hard-Fail. Với 5 câu gồm nhóm 3 câu và hai câu độc lập → D=2 → 40%. Nhóm 3 câu trong đề 10 câu chỉ có 2 câu dư → 20%, **không** Hard-Fail theo HF-03.

**Không nhầm lẫn:** Trùng với lịch sử học tập là phạm vi C4.3; HF-03 xét trùng **bên trong cùng đề**. Nếu có hai câu làm lộ trực tiếp đáp án của nhau, QA có thể yêu cầu sửa theo C3.2 dù chưa đạt 30%; cần chốt có bổ sung Hard-Fail độc lập cho lộ đáp án hay không.

### HF-04 — Sai phân phối độ khó cá nhân hóa ≥30% (cấp đề)

Chỉ áp dụng khi `exam_type=personalized` và có `ExamPlan` đã khóa trước sinh đề. Kế hoạch phải ghi N, phân phối độ khó, quy tắc làm tròn và xử lý thiếu nguồn. Dùng **độ khó thực tế đã xác minh**, không dùng nhãn generator tự khai.

Gọi `P_l` là số câu kế hoạch tại mức l và `A_l` là số câu thực tế tại mức l; yêu cầu `ΣP_l=ΣA_l=N`. Số câu tối thiểu phải **thay bằng câu có độ khó khác** để khớp phân phối là:

`M = Σ_l max(0, A_l − P_l) = ½ Σ_l |A_l − P_l|`.

`adjust_ratio = M/N`. Nếu `10×M ≥ 3×N` ⇒ **HF-04**. Mỗi câu chỉ được tính một lần. Không được chỉ sửa metadata `difficulty` để giả vờ đạt kế hoạch.

**Ví dụ:** N=10, kế hoạch `[4,4,2,0]`, thực tế `[1,4,3,2]` theo thứ tự Nhận biết/Thông hiểu/Vận dụng/Vận dụng cao. M = 0+0+1+2=3 ⇒ 30% ⇒ Hard-Fail. Với N=3, M=1 ⇒ 33,33% ⇒ Hard-Fail; do đó đề ngắn nhạy với ngưỡng 30% và cần ghi rõ trong báo cáo.

**Giới hạn:** M chỉ đo lệch **phân phối toàn đề**, không bảo đảm mỗi slot đúng kỹ năng, độ khó hoặc mục tiêu. Sai slot được ghi riêng ở C2.2/C4.1 và kiểm tra ExamPlan; không dùng M để che lỗi đó.

### HF-05 — Điều kiện dữ liệu/bằng chứng không đủ (không phải Hard-Fail chuyên môn)

Thiếu `ExamPlan`, hồ sơ cần thiết, câu chưa kiểm chứng toán, chưa xem render hoặc các đánh giá bất đồng ⇒ `REVIEW_REQUIRED`/`INCOMPLETE`, không được kết luận PASS. Không biến thiếu dữ liệu thành N/A hoặc tự động thành lỗi chuyên môn.

## 5. Quy tắc N/A và trạng thái chưa đánh giá

| Trường hợp | Xử lý |
|---|---|
| `default_blueprint`, không cá nhân hóa | C4.1–C4.3 = N/A |
| Cá nhân hóa nhưng học sinh thực sự chưa có lịch sử | C4.3 có thể N/A, phải ghi lý do; C4.1/C4.2 vẫn chấm theo kế hoạch hợp lệ |
| Tự luận không có nhiễu | C1.2 vẫn chấm đáp án; bỏ qua thành phần nhiễu |
| Thiếu đáp án/lời giải bắt buộc | Chấm lỗi ở C1.2/C1.3, không dùng N/A |
| Chưa render/kiểm tra hiển thị | C3.3 = NOT_EVALUATED, không phải N/A |
| Thiếu bằng chứng, model không chắc chắn, giáo viên chưa xác nhận | NOT_EVALUATED hoặc REVIEW_REQUIRED; chưa PASS |

N/A được xác định ở **ô câu × tiêu chí** khi hợp lệ; nếu mọi câu đều N/A trong một tiêu chí cấp câu, cả tiêu chí N/A. Tiêu chí N/A toàn đề được loại khỏi cả tử số và mẫu số chuẩn hóa. Không chuyển trọng số N/A sang riêng C1/C2.

## 6. Công thức điểm và quyết định

### 6.1. Điểm tiêu chí cấp câu

Với tiêu chí j có điểm tối đa `W_j`, tập câu áp dụng `S_j` và mức chấm nguyên `r_ij ∈ {0,1,2,3,4}`:

`score_j = (Σ_(i∈S_j) r_ij / |S_j|) × W_j / 4`.

Ví dụ C1.3: mức `[3,4,4]` → `(11/3)×10/4 = 9.166666…/10`.

### 6.2. Điểm tiêu chí cấp đề

`score_j = r_j × W_j / 4`.

### 6.3. Tổng điểm

Nếu tất cả áp dụng: `raw_score = Σ score_j` (tối đa 100). Nếu có N/A toàn đề: `normalized_score = 100 × Σ(score_j áp dụng) / Σ(W_j áp dụng)`. Ví dụ C1=30/35, C2=25/25, C3=17/20, C4=N/A → 72/80 → **90/100**. Luôn hiển thị cả `raw_points=72`, `applicable_max=80`, `normalized_score=90`, danh sách N/A.

**Không dùng** công thức `(C1×0.35)+(C2×0.25)+...` khi C1, C2... đã là điểm trên thang 35,25,20,20; như vậy sẽ nhân trọng số **hai lần**. Công thức trọng số chỉ hợp lệ nếu C1–C4 đã được chuẩn hóa về cùng thang 0–100 trước đó.

### 6.4. Trạng thái cuối

1. Có Hard-Fail **đã xác nhận** ⇒ `FAIL`, `final_score=0`, giữ `diagnostic_score` để truy vết.
2. Không có Hard-Fail nhưng còn ô bắt buộc chưa đánh giá hoặc nghi vấn chưa giải quyết ⇒ `REVIEW_REQUIRED` (hoặc `INCOMPLETE` nếu thiếu dữ liệu), **chưa công bố điểm Pass**.
3. Đã đủ bằng chứng, không Hard-Fail, điểm chuẩn hóa chưa làm tròn ≥80 ⇒ `PASS`.
4. Đã đủ bằng chứng, không Hard-Fail, điểm chuẩn hóa chưa làm tròn <80 ⇒ `FAIL`.

Chỉ làm tròn **để hiển thị** tới hai chữ số thập phân; so sánh ngưỡng trên giá trị đầy đủ.

### 6.5. Thống kê nhiều đề

`average_score = Σ(final_score của các đề đã kết luận) / số đề đã kết luận`. Đề Hard-Fail có điểm cuối 0 vẫn được tính; đề đang review/chưa đánh giá được báo cáo riêng. Báo cáo thêm tỷ lệ PASS, tỷ lệ Hard-Fail theo loại, tỷ lệ chờ review, phân tách đề mặc định và cá nhân hóa.

## 7. Quy trình Quality Gate và trách nhiệm

1. **Input validation (code):** Xác thực đề, số câu, loại đề, question schema, ExamPlan, catalogue phiên bản, hồ sơ/lịch sử và yêu cầu đáp án/lời giải/marking scheme.
2. **Deterministic checks (code):** Kiểm tra thiếu trường, đáp án theo solver khả dụng, số phương án, trùng ID/nội dung, phân phối mức độ, số câu theo kỹ năng, tỷ lệ 30%, khả năng render tự động.
3. **Semantic review (Qwen):** Đề xuất mức chấm C1.1/C1.3/C2.1/C2.2/C3.1/C3.2/C4.3 kèm trích dẫn cụ thể từ đề và lời giải; phân tích cặp trùng ý tưởng; báo `uncertain` nếu không đủ cơ sở. Qwen không được tự ghi đè kết quả toán học đã được kiểm chứng độc lập.
4. **Human adjudication (giáo viên/QA):** Giải quyết bất đồng, nghi vấn toán học, trùng ngữ nghĩa, phân loại độ khó khó xác định; xác nhận các Hard-Fail cần phán đoán chuyên môn.
5. **Aggregation (code):** Tính mức/điểm, N/A, Hard-Fail, trạng thái, bằng chứng, lý do và danh sách sửa.
6. **Release gate:** Chỉ phát hành đề `PASS`; `FAIL` → sửa/tái sinh và đánh giá lại phiên bản mới; `REVIEW_REQUIRED` → chờ xác nhận, không phát hành tự động.

**Chính sách tin cậy đề xuất:** Với phát hiện mang tính xác định và có bằng chứng (ví dụ đáp án sai qua solver độc lập, lệch phân phối đã xác minh), code có thể kích hoạt Hard-Fail. Với nhận định ngữ nghĩa chỉ từ Qwen, chỉ tạo `hard_fail_candidate`; giáo viên/QA hoặc cơ chế kiểm chứng thứ hai được nhóm phê duyệt mới xác nhận. Không tự đặt ngưỡng confidence số học nếu chưa có bộ dữ liệu hiệu chuẩn.

## 8. Contract đầu ra tối thiểu (đề xuất)

```json
{
  "exam_id": "EXAMPLE-001",
  "exam_version": 1,
  "rubric_version": "W06-v2.0-proposed",
  "exam_type": "personalized",
  "status": "REVIEW_REQUIRED",
  "diagnostic_score": null,
  "final_score": null,
  "applicable_max": 100,
  "criteria": [
    {
      "criterion_id": "C1.1",
      "scope": "question",
      "max_points": 10,
      "score": null,
      "question_assessments": [
        {
          "question_id": "Q1",
          "rating": null,
          "state": "NOT_EVALUATED",
          "evaluator": null,
          "evidence": []
        }
      ]
    }
  ],
  "hard_fail_candidates": [],
  "confirmed_hard_fails": [],
  "not_applicable": [],
  "duplicate_check": {
    "confirmed_groups": [],
    "duplicate_excess_count": null,
    "ratio": null
  },
  "difficulty_check": {
    "planned_counts": null,
    "actual_verified_counts": null,
    "minimum_replacements": null,
    "ratio": null
  },
  "pending_reviews": ["C1.1/Q1"],
  "evaluator_versions": {},
  "evaluated_at": null
}
```

**Ràng buộc contract:** `rating` chỉ là số nguyên 0–4 khi `state=EVALUATED`; N/A cần lý do; mỗi kết luận có `evidence` và `evaluator`; Hard-Fail có mã HF, câu/nhóm liên quan, lý do, nguồn xác nhận; lưu `exam_version` để tránh dùng đánh giá của đề trước khi regenerate. `final_score=0` chỉ khi đã xác nhận Hard-Fail, không khi đang chờ đánh giá.

## 9. Ví dụ chấm đề cá nhân hóa 3 câu

**Hồ sơ giả định:** A002 (Quy tắc nhân) mastery 1,5, evidence 3; A006 (Chỉnh hợp) mastery 1,5, evidence 3; A003 (Hoán vị) mastery 2,5, evidence 3; A009 (Đếm có ràng buộc) mastery 2,5, evidence 3. Đây là dữ liệu minh họa, không suy ra ngưỡng mastery áp dụng cho toàn hệ thống.

**ExamPlan đã chốt:** Câu 1 Thông hiểu/A006 (ưu tiên yếu); Câu 2 Thông hiểu/A002 (ưu tiên yếu); Câu 3 Vận dụng/A009 kết hợp A003. Lịch sử: học sinh từng nhầm xét thứ tự khi lập số; đã thành thạo dạng chọn nhóm không xét thứ tự (A004). Các câu minh họa đều mới.

**Câu 1 — Thông hiểu, A006 (phụ A002).** Từ các chữ số 1,2,3,4,5 lập được bao nhiêu số tự nhiên có 3 chữ số khác nhau? Đáp án `A_5^3=60`. Giải: chọn và sắp thứ tự 3 chữ số khác nhau từ 5 chữ số, `5×4×3=60`. Cần nói rõ đổi thứ tự tạo số khác.

**Câu 2 — Thông hiểu, A002.** Lớp có 20 nam, 15 nữ. Có bao nhiêu cách chọn một học sinh nam làm lớp trưởng và một học sinh nữ làm lớp phó? Đáp án `20×15=300`. Giải: 20 cách chọn lớp trưởng; với mỗi cách có 15 cách chọn lớp phó.

**Câu 3 — Vận dụng, A009 (phụ A003, A002).** Xếp 4 học sinh nam và 3 học sinh nữ phân biệt thành hàng sao cho cả 3 nữ đứng liền nhau. Đáp án `5!×3!=720`. Giải: gom ba nữ thành một khối, xếp 5 phần tử; xếp nội bộ ba nữ; mỗi cách xếp được đếm đúng một lần.

**Giả định kiểm tra giao diện:** cả ba câu hiển thị tốt. Mức chấm cấp câu:

| Tiêu chí | Câu 1 | Câu 2 | Câu 3 | Điểm quy đổi |
|---|---:|---:|---:|---:|
| C1.1 | 4 | 4 | 4 | 10/10 |
| C1.2 | 4 | 4 | 4 | 15/15 |
| C1.3 | 3 | 4 | 4 | 9,1666…/10 |
| C2.1 | 4 | 4 | 4 | 15/15 |
| C2.2 | 4 | 4 | 4 | 10/10 |
| C3.1 | 4 | 4 | 4 | 7/7 |
| C3.3 | 4 | 4 | 4 | 6/6 |

C1.3 của câu 1 mức 3 vì bản lời giải rút gọn chưa giải thích rõ lý do chọn chỉnh hợp thay vì tổ hợp; các câu khác mức 4 theo giả định chuyên môn. Cấp đề: C3.2=4 (7/7); C4.1=4 (8/8); C4.2=4 (6/6); C4.3=4 (6/6). Như vậy C1=34,1666…/35, C2=25/25, C3=20/20, C4=20/20, **tổng 99,1666… → hiển thị 99,17/100**. Không có Hard-Fail, đủ bằng chứng theo giả định ⇒ **PASS**.

**Lưu ý kiểm thử:** Với đề 3 câu, một câu trùng dư hoặc một câu cần đổi mức chiếm 33,33%, vượt ngưỡng 30%; ví dụ này không vi phạm vì ba ý tưởng độc lập và phân phối thực tế khớp kế hoạch.

## 10. Phân biệt W06 với barem chấm bài học sinh

| Nội dung | W06 — kiểm định đề sinh ra | Barem — chấm bài học sinh |
|---|---|---|
| Đối tượng | Câu hỏi/đề, đáp án, lời giải, phân phối | Bài làm thực tế của học sinh |
| Thời điểm | Trước phát hành | Sau khi học sinh làm bài |
| Mục tiêu | PASS/FAIL đề và yêu cầu sửa/tái sinh | Chấm điểm, phản hồi và cập nhật mastery |
| Đầu ra | `ExamQualityEvaluationResult` | Điểm bài làm, nhận xét, bằng chứng năng lực |
| Marking scheme | Kiểm tra khung chấm của câu tự luận có hợp lệ | Áp dụng khung chấm để cho điểm bài làm |

## 11. Những quyết định QA Lead cần phê duyệt trước khi khóa specification

1. **HF-03:** Chấp nhận cách B `D=N−G` (đếm câu dư sau khi giữ một đại diện), thay vì đếm toàn bộ câu thuộc nhóm trùng; quy tắc xác nhận nhóm tương đương và xử lý cặp chưa chắc chắn.
2. **HF-04:** Chấp nhận `M=Σmax(0,A−P)`, so sánh `M/N≥30%`, yêu cầu độ khó thực tế đã xác minh và ExamPlan được khóa trước khi sinh.
3. **C4.2:** Chốt bảng mức 0–4 dựa trên M; không giữ song song mô tả định tính mâu thuẫn với số câu cần đổi.
4. **Quyền phán quyết:** Xác định điều kiện cho code auto-fail, điều kiện Qwen chỉ đề xuất và khi nào bắt buộc giáo viên xác nhận.
5. **Thiếu dữ liệu:** Phê duyệt `REVIEW_REQUIRED`/`INCOMPLETE`, N/A hợp lệ và chính sách không phát hành tự động khi chưa đủ bằng chứng.
6. **Catalogue/ExamPlan:** Khóa phiên bản skill IDs, mô tả bốn mức độ khó, quy tắc làm tròn, xử lý thiếu nguồn và tiêu chuẩn đủ dữ liệu lịch sử.
7. **C3.2:** Chốt có Hard-Fail riêng cho câu làm lộ đáp án nhau dù tỷ lệ trùng <30% hay chỉ bắt buộc sửa theo rubric.
8. **C1.2 tự luận:** Chốt `marking_scheme` là trường bắt buộc trong loại câu nào và cơ chế kiểm tra tổng điểm từng bước.

## 12. Checklist nghiệm thu trước triển khai

- [ ] Bộ tiêu chí 11 mục, tổng trọng số 100, không nhân trọng số hai lần.
- [ ] Mỗi tiêu chí có mức 0–4, cấp chấm và người chịu trách nhiệm.
- [ ] HF-01/HF-02 có bằng chứng và đường chuyển review khi chưa chắc chắn.
- [ ] HF-03 có nhóm ý tưởng xác nhận, D, N, tỷ lệ và danh sách câu dư.
- [ ] HF-04 có ExamPlan phiên bản, phân phối thực tế xác minh, M, N và tỷ lệ.
- [ ] N/A không bị nhầm với thiếu dữ liệu hoặc lỗi.
- [ ] Không PASS khi chưa render, chưa kiểm tra toán hoặc đang có nghi vấn chưa xử lý.
- [ ] Kết quả lưu rating, score, evidence, evaluator, phiên bản đề/rubric.
- [ ] Có unit tests: N=3, N=5, N=10; tỷ lệ 20%, 30%, 33,33%; trường hợp nhóm trùng không bắc cầu.
- [ ] Có bộ đề được giáo viên gán nhãn để hiệu chuẩn Qwen và đánh giá sai lệch.

---

**Kết luận:** Đây là bản rubric có thể dùng làm **đề xuất specification để review**. Chỉ chuyển trạng thái `Approved for Implementation` sau khi QA Lead xác nhận các quyết định ở mục 11 và đội dev thống nhất input/output contract.
