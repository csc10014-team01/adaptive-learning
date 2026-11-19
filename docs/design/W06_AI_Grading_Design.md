# W06 — Thiết kế AI Grading

**Project:** MIRA — Mastery-Informed Review Assistant
**Use case:** UC-03 — Grade Submitted Practice Exam
**Owner:** N04 — AI & Algorithms Lead (Phạm Yến Trân)
**Cập nhật:** 19/11/2026
**Trạng thái:** Chốt cơ chế của bản thử nghiệm để chuẩn bị tách module; chưa tích hợp API/DB chính.
**Mốc implementation:** `R2026-11-17-scoped-skill-guidance-v11` trong `Grading_Test_v2/run_test.py` của source đã cung cấp.

## 1. Mục tiêu và phạm vi

Chấm bài tự luận tổ hợp lớp 10 theo đề, đáp án tham chiếu và rubric của đúng đề học sinh đã nhận. Kết quả mỗi câu là **đúng**, **sai**, hoặc **chưa thể kết luận tự động**; ghi nhận kỹ năng sai khi bài làm cung cấp căn cứ.

Bản hiện tại dùng Qwen phân tích và đề xuất chấm. Python kiểm tra cấu trúc, nguồn trích dẫn, các phép toán hỗ trợ và một số mâu thuẫn. Python **không có bộ ánh xạ ngữ nghĩa độc lập có thể chứng minh mọi lập luận của Qwen là đúng**.

Giữ nguyên cơ chế này trong đợt chuẩn bị tích hợp; không tối ưu prompt tiếp ở bước tách module. Phần API nhận bài, đọc phiên bản đề đã duyệt, quyền truy cập và lưu DB sẽ nối sau khi source nhóm ổn định. Tài liệu không khẳng định các phần đó đã triển khai.

## 2. Quy tắc đã chốt

- Bài học sinh ban đầu là một khối văn bản có lời giải và phép toán, không có sẵn step.
- Qwen đọc toàn bộ bài, phân tích hành động theo thứ tự học sinh viết, mô tả ý nghĩa và ánh xạ các mốc rubric.
- `description` mô tả học sinh đang làm gì; `evidence` giữ trích dẫn nguyên văn bài gốc trong dữ liệu nội bộ.
- Rubric hướng dẫn đánh giá, không ép học sinh viết giống đáp án hoặc có cùng số lượng/thứ tự bước.
- Chấp nhận phương pháp khác hợp lệ. Khác mẫu không tự động dẫn đến review.
- Đọc toàn bài để hiểu vai trò bước trung gian, sau đó chỉ giữ phần đánh giá đến lỗi đầu tiên được chấp nhận sau kiểm tra.
- Không phân loại lỗi gốc và lỗi kéo theo. Các bước sau điểm dừng không được tự điền đúng/sai.
- Thiếu cách giải bắt buộc theo rubric: `INCORRECT`, lý do **“Bài làm tự luận chưa đầy đủ.”** Bài ngắn nhưng đủ ý vẫn hợp lệ.
- Chỉ nói đã làm nháp không chứng minh phần lập luận bị thiếu. Một danh sách được khẳng định đầy đủ nhưng bỏ trường hợp hợp lệ là lỗi liệt kê/phương pháp, khác với chưa trình bày cách làm.
- Chỉ gắn kỹ năng sai có căn cứ; thiếu trình bày không tự chứng minh sai một kỹ năng cụ thể.
- Kết quả dành cho DB không có feedback từng bước/câu. Chỉ tổng hợp feedback ở cấp đề sau khi đã xử lý đủ câu.

Đây là quy tắc mong muốn của bản chốt; các giới hạn thực tế tại mục 9 vẫn tồn tại. Ví dụ, model chưa luôn tách đúng hành động hoặc chỉ ra đúng lỗi đầu tiên.

## 3. Đầu vào

### 3.1 Ngữ cảnh để chấm một câu

| Trường | Ý nghĩa |
| --- | --- |
| `question_text` | Nguyên văn đề học sinh nhận. |
| `student_answer` | Bài tự luận nguyên khối; phải giữ bản gốc để kiểm tra evidence. |
| `reference_answer` | Đáp số/biểu thức tham chiếu đã được duyệt; bản thử hỗ trợ một tập con biểu thức số. |
| `rubric[]` | Mỗi mốc có `id`, `description`, `skill_ids`; mô tả điều kiện, cách giải hợp lệ và yêu cầu trình bày. |
| `skill_ids[]` | Các kỹ năng của câu. Không đồng nghĩa tất cả các kỹ năng đó đều sai khi câu sai. |

Rubric riêng của câu hoặc rubric template phải được cụ thể hóa cho đúng câu được giao. Bản thử dùng rubric đã có trong JSON; chưa gọi DB để lấy hoặc sinh rubric.

Rubric phải nêu rõ phần trình bày bắt buộc và cho phép phương pháp tương đương nếu phù hợp. Điều kiện câu hỏi không được thay đổi theo output model.

### 3.2 Đóng gói ở cấp đề khi chuẩn bị tích hợp

- `test_id`, `student_id` xác định đề và học sinh.
- `questions[]` cung cấp ngữ cảnh câu và `question_id`.
- `submissions[]` có `question_id`, `student_answer` để nối với ngữ cảnh tương ứng.
- Backend phải bảo đảm đề, đáp án và rubric thuộc đúng phiên bản đề đã duyệt mà học sinh nhận. Tên trường version/snapshot sẽ theo contract của nhóm; chưa áp đặt một trường mới bắt buộc trong mẫu này.
- `case_id`, gold và annotation chỉ phục vụ benchmark, không phải đầu vào nghiệp vụ bắt buộc.

File `W06_Grading_Sample_Data.json` minh họa cách đóng gói trên. Đây chưa phải API contract đã duyệt.

Bản loader benchmark hiện từ chối bài trống/toàn khoảng trắng và thiếu ngữ cảnh bắt buộc. Luồng xử lý bài không trả lời khi tích hợp còn cần thống nhất; không coi lỗi dữ liệu hệ thống là học sinh sai.

## 4. Luồng xử lý thực tế

### 4.1 Chuẩn bị request

`make_payload()` chỉ đưa đề, rubric, đáp án tham chiếu, bài gốc và kỹ năng vào model. Gold, nhãn kỳ vọng, annotation và metric không vào request ban đầu hoặc repair.

Cấu hình mặc định: local Ollama `qwen3:4b-q4_K_M`, `think=false`, temperature 0, seed 42, context 8192, tối đa 1200 output tokens, timeout 120 giây/request. Đây là cấu hình thử nghiệm, **không phải cam kết độ trễ**. Thời gian cả câu có thể gồm hai request khi repair.

### 4.2 Qwen đề xuất phân tích và chấm

Schema nội bộ gồm:

| Trường | Nội dung |
| --- | --- |
| `steps[].evidence` | Một đoạn trích nguyên văn liên tiếp từ bài học sinh. Các đoạn theo thứ tự, bao phủ phần được xét. |
| `steps[].description` | Mô tả ngắn hành động của học sinh; yêu cầu tiếng Việt, chưa được code bảo đảm hoàn toàn. |
| `steps[].rubric_ids` | ID mốc rubric liên quan; không phải số thứ tự cố định bắt học sinh tuân theo. |
| `steps[].decision` | `CORRECT`, `UNCERTAIN`, `ARITHMETIC_ERROR`, `METHOD_OR_CONDITION_ERROR`, hoặc `INCOMPLETE_SOLUTION`. |
| `steps[].skill_errors[]` | `skill_id`, lý do ngắn cho kỹ năng được cho là sai; bước đúng/chưa rõ/thiếu trình bày phải để rỗng. |
| `final_answer_quote` | Trích từ bài gốc chứa kết luận của học sinh, không tự tính hộ hoặc thay bằng đáp án chuẩn. |

Đây là proposal nội bộ; không lưu nguyên schema này làm kết quả nghiệp vụ. Qwen vẫn có thể xuất bước sau lỗi; code chỉ nhận phần đánh giá đến điểm dừng.

### 4.3 Validator Python

`validate_case()` kiểm tra lần lượt:

1. Schema, decision, ID rubric và kỹ năng hợp lệ.
2. Evidence có thực sự nằm trong bài gốc, đúng thứ tự, không chồng lặp hoặc bỏ nội dung trước điểm dừng.
3. Tính lại các đẳng thức hỗ trợ từ bài gốc bằng AST giới hạn; không thực thi văn bản học sinh như mã chương trình.
4. Một số sai lệch số trong description và mâu thuẫn giữa decision/kỹ năng.
5. Khi xác nhận sai số học, có thể đổi kết quả bước sang `ARITHMETIC_ERROR/A008`, ghi phép tính gốc và giá trị đúng. Nếu lỗi phương pháp và số học cùng một bước chưa phân định thứ tự thì giữ chưa kết luận để xử lý lại.
6. Khi nhận một bước sai hợp lệ theo các kiểm tra, trả `INCORRECT` và dừng xét. Nhận lỗi ngữ nghĩa vẫn dựa vào nhận định Qwen, không phải chứng minh toán học độc lập.
7. Nếu các bước đều đúng, phải bao phủ hết bài, trích/chuẩn hóa kết luận từ nguồn và so với đáp án tham chiếu trước khi trả `CORRECT`.

Phép tính đúng chỉ chứng minh số học của biểu thức, không chứng minh mô hình đếm đúng. Parser hỗ trợ biểu thức số có giới hạn: phép cộng/trừ/nhân/chia, ngoặc, giai thừa và các hàm tổ hợp/chỉnh hợp dạng hỗ trợ. Nhiều ký hiệu, biểu thức đại số, đẳng thức chuỗi và định dạng khác có thể không kiểm tra được; phải ghi là chưa xác minh.

### 4.4 Repair có điều kiện

`grade_question()` gọi Qwen ban đầu một lần, rồi gọi sửa tối đa một lần nếu validator chưa chấp nhận kết quả và lỗi thuộc nhánh có thể sửa. Lỗi provider/timeout dừng, không tiếp tục gọi sửa nội dung.

- Lỗi trích đáp số: sửa riêng `final_answer_quote`, giữ các bước; giới hạn tối đa 160 tokens output cho request sửa này.
- Lỗi evidence, thiếu bao phủ, mâu thuẫn số học hoặc schema/nội dung: request sửa hiện có thể tạo lại proposal chấm. Không có cơ chế độc lập bảo đảm repair sẽ đúng.
- Output sửa phải qua validator lại. Nếu vẫn không chấp nhận, trả `NEEDS_REVIEW/UNCERTAIN`.
- Không có vòng sửa vô hạn hoặc lượt thứ ba.

### 4.5 Thu gọn và tổng hợp

`exam_payload()` lấy các bước đã được nhận trong phần assessed prefix. Các bước chưa xét không vào `answer` của kết quả gọn. Với câu review, bản formatter hiện xuất `answer: []`; `step_results` có thể giữ phần đúng đã xét trước khi gặp vấn đề.

Khi đã xử lý đủ câu, code tổng hợp feedback chung từ kết quả, không gọi thêm AI để viết feedback. Đủ câu đã xử lý không đồng nghĩa mọi câu đã có kết luận cuối hoặc giáo viên đã duyệt.

## 5. JSON đầu ra dành cho tầng lưu trữ

Mẫu hiện tại dùng `test_id`, `student_id`, `submissions`, `feedback`. Formatter benchmark còn có `repeat` và `complete` để biểu diễn lượt thử và việc xử lý đủ câu. Đây là chi tiết đóng gói hiện tại, cần map lại theo contract nhóm khi tích hợp; không phải bắt DB thêm hai cột đó.

Mỗi phần tử `submissions` gồm `question_id`, `answer[]`, `grading_result`:

| Trường trong `grading_result` | Quy ước |
| --- | --- |
| `grading_status` | `AI_GRADED` hoặc `NEEDS_REVIEW`. |
| `requires_teacher` | `false` khi nhận kết quả tự động; `true` khi chưa kết luận. Với lỗi kỹ thuật, backend có thể cần retry/xử lý hệ thống trước khi nhờ giáo viên. |
| `overall_result` | `CORRECT`, `INCORRECT`, hoặc `UNCERTAIN`. |
| `final_answer_correct` | `true` khi bản hiện tại đã xác minh kết luận trong luồng tất cả bước đúng; `null` khi dừng sớm hoặc chưa xác minh. Không tự đổi thành `false` chỉ vì có một bước sai. |
| `step_results[]` | Các bước đã xét với `step`, `result`, `start`, `end`; không có feedback. |
| `errors[]` | Lỗi đầu tiên: `step`, `error_type`, `skill_ids`, `reason` ngắn. Thiếu trình bày có `skill_ids: []`. Câu đúng/review có `errors: []`. |
| `missing_steps[]` | Trường tương thích hiện giữ rỗng; chưa có bộ phát hiện bước thiếu độc lập. |
| `teacher_comment` | `null` từ AI; dành cho tầng giáo viên sau này. |

`answer[]` chứa `step`, `description`, `start`, `end`. Offset là chỉ số ký tự Python, bắt đầu từ 0, end không bao gồm ký tự cuối; tham chiếu bài gốc chưa sửa. Nếu frontend dùng cách đếm ký tự khác, tầng tích hợp phải chuyển đổi phù hợp.

Các mã A001–A009 là **mã kỹ năng**, không phải mã lý do chuyển giáo viên. Không yêu cầu thêm `reason_code` vào contract nghiệp vụ. `review_kind`, `review_reason` hiện ở log nội bộ để chẩn đoán, không trộn vào bài làm học sinh.

`expected_result`/gold là nhãn benchmark; kết quả chạy thật dùng `grading_result`. `AI_GRADED` nghĩa là hệ thống đã chấp nhận output qua các kiểm tra hiện có, không có nghĩa mọi ngữ nghĩa đã được chứng minh đúng.

## 6. Kỹ năng và giới hạn gán lỗi

Phạm vi gồm 9 kỹ năng: A001 quy tắc cộng; A002 quy tắc nhân; A003 hoán vị; A004 tổ hợp; A005 sơ đồ cây/liệt kê theo nhánh; A006 chỉnh hợp; A007 kết hợp các quy tắc; A008 tính toán; A009 đếm có ràng buộc. Đây là cách gọi đang dùng trong bộ thử; tên chuẩn và taxonomy cần khớp dữ liệu nhóm khi nối vào.

- A008: sai số học có thể đối chiếu bằng phép toán hỗ trợ.
- A009: bỏ ràng buộc dẫn tới lựa chọn/số lượng không hợp lệ.
- A002: sai cách kết hợp lựa chọn hoặc các giai đoạn; không tự gắn thêm chỉ vì một tích dùng số lựa chọn vi phạm ràng buộc.
- Mỗi kỹ năng sai cần lý do riêng. Python kiểm tra cấu trúc và nguồn liên hệ của lý do, không chứng minh ý nghĩa lý do đúng.

`errors[].skill_ids` đang có trong prototype, là phần đề xuất cần thống nhất với Data Lead. Không coi đó là cột DB đã tồn tại hoặc contract đã được phê duyệt.

## 7. Ví dụ và cách sử dụng file mẫu

`W06_Grading_Sample_Data.json` có:

- `input`: ngữ cảnh các câu và bài tự luận nguyên khối trước AI.
- `output`: kết quả gọn của đề minh họa; có câu đúng, sai số học, thiếu trình bày và review do evidence không hợp lệ.
- `provenance`, `example_notes`: giải thích cho nhóm đọc, không phải dữ liệu cần lưu nguyên vào DB hoặc gửi model.

Mẫu được tạo bằng phát lại proposal Qwen đã lưu qua validator và formatter của source chốt, không gọi Qwen mới. Bốn bài được ghép thành một đề minh họa và feedback được tổng hợp lại bằng code. Đây không phải kết quả một phiên học sinh thật.

## 8. Phần đã có và bước tích hợp tiếp theo

| Thành phần | Trạng thái |
| --- | --- |
| Gọi Qwen, phân tích/chấm theo rubric, validator, repair | Có trong runner standalone. |
| Output JSON gọn và feedback cấp đề | Có trong formatter standalone. |
| Tách thành `src/ai/answer_grading.py` và demo trong `scripts/grading/` | Bước tiếp theo đã thống nhất; chưa khẳng định đã tạo module. |
| Đọc ngữ cảnh đúng phiên bản đề đã duyệt từ API/DB | Chờ source nhóm ổn định và contract tích hợp. |
| Lưu kết quả, quyền xem/sửa của giáo viên | Tầng tích hợp phải triển khai; chưa phải chức năng của runner. |

Khi tách module, giữ nguyên prompt, validator, cấu hình và repair đã chốt. Kiểm tra tính tương đương bằng cùng proposal/response lưu sẵn; test replay không thay thế kiểm thử Qwen thật. Bên tích hợp phải lưu bài gốc cùng ngữ cảnh đúng phiên bản và cho giáo viên xem/sửa cả kết quả đã chấm tự động, không chỉ các câu review.

## 9. Bằng chứng và giới hạn hiện tại

- Source đã cung cấp chạy qua 113 test offline trong lần kiểm tra ngày 19/11/2026. Đây là kiểm tra code/mock, không phải độ chính xác AI.
- Hai report người dùng gửi gần nhất của bộ P01–P10 và N01–N10 cho 19/20 khớp đồng thời nhãn và kỹ năng; 19/20 tự động. Đây là các bộ giả lập đã dùng chỉnh hệ thống, không phải tập kiểm thử độc lập chưa từng dùng.
- Bộ cũ: 9/10 khớp, P07 review do Qwen đưa nội dung rubric vào evidence. Bảo vệ nguồn trích dẫn đã chặn output này.
- Bộ mới: 10/10 khớp nhãn/kỹ năng nhưng N07 vẫn đánh sai một nhận định đúng trước khi tới lỗi thật. Do cùng gắn A009, chỉ số nhãn/kỹ năng không phản ánh lỗi chẩn đoán này.
- P09 kết luận thiếu trình bày đúng chính sách, nhưng model vẫn có thể công nhận một lời khẳng định chưa chứng minh như một bước đúng. Tách bước và description chưa luôn chính xác.
- Trung bình hai report tương ứng khoảng 27,55 và 27,59 giây/câu; không suy ra SLA hoặc hiệu năng ổn định trên máy khác.
- Điều kiện tự thỏa, phương pháp khác mẫu, nội dung tự nhiên và kỹ năng lỗi vẫn phụ thuộc hiểu biết của Qwen. Không cam kết chấm đúng tuyệt đối.

Đóng băng bản này làm mốc thử nghiệm phục vụ tích hợp. Các lỗi đã biết phải đi cùng tài liệu bàn giao; không âm thầm ghi thành đã giải quyết.

## 10. Tiêu chí bàn giao bước tiếp theo

- [x] Source standalone, luồng xử lý và giới hạn đã đối chiếu.
- [x] Dữ liệu mẫu chuyển sang bài tự luận nguyên khối và kết quả gọn hiện tại.
- [x] Feedback chỉ ở cấp đề; các bước sau điểm dừng không tự có kết quả.
- [ ] Tách module dùng lại được, giữ hành vi bản đã chốt.
- [ ] Kiểm tra replay tương đương giữa module và runner.
- [ ] Thống nhất output với Data Lead/API; xác định ánh xạ version đề và lưu trữ.
- [ ] Nối source chính khi nhóm ổn định; kiểm tra luồng nộp bài và giáo viên xem/sửa.
- [ ] Kiểm thử thêm dữ liệu chưa dùng chỉnh hệ thống và ghi kết quả thật.
- [ ] Vẽ workflow tích hợp theo code sau khi điểm nối đã triển khai.

## 11. Nhật ký cập nhật tài liệu

19/11/2026: thay thiết kế cũ bằng cơ chế correctness hiện tại; đồng bộ input/output với source chốt; bổ sung phân biệt proposal/log và JSON nghiệp vụ, ghi nhận giới hạn P07/N07 và phần tích hợp còn chờ. Chỉ cập nhật hai tài liệu, không sửa thuật toán chấm hoặc source team.
