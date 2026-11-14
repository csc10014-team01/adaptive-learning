# W06 — AI Grading Design (Draft cập nhật)

**Project:** MIRA — Mastery-Informed Review Assistant  
**Use case:** UC-03 — Grade Submitted Practice Exam  
**Owner:** N04 — AI & Algorithms Lead (Phạm Yến Trân)  
**Status:** Draft — cần nhóm Data / Architecture / API xác nhận  
**Cập nhật:** 14/11/2026

Tài liệu mô tả đánh giá đúng/sai, nhận xét bài làm và chuyển giáo viên khi chưa xác minh được. Cấu trúc API chính thức chưa hoàn thành. Các ví dụ dưới đây là dữ liệu minh họa, không phải contract đã chốt.

## 1. Mục tiêu và phạm vi

Đánh giá từng câu tự luận tổ hợp lớp 10 theo nội dung câu, đáp án tham chiếu và quy tắc đánh giá của đúng đề đã được duyệt.

Khi đủ căn cứ, bộ chấm trả kết luận đúng/sai và nhận xét cho các bước đã phân tích. Khi chưa đủ căn cứ, bộ chấm trả trạng thái cần giáo viên, giữ những nhận xét đã có cơ sở và chỉ rõ phần chưa xác minh.

Một câu có thể có bước đúng, bước sai hoặc bước chưa xác định. Không đồng nhất kết luận toàn câu với kết quả của mọi bước. Cách tổng hợp trường hợp đúng một phần thành một trạng thái toàn câu cần nhóm thống nhất; chưa tự bổ sung trạng thái chính thức ngoài mẫu dữ liệu đã cung cấp.

Phạm vi danh mục kỹ năng hiện tại là A001–A009. Kỹ năng chính/phụ của câu cung cấp ngữ cảnh; không có nghĩa mọi kỹ năng liên quan đều sai khi câu trả lời sai.

## 2. Luồng xử lý

1. Backend nhận và lưu bài làm nguyên bản của học sinh.
2. Bước phân tích AI dùng Qwen nhận diện các bước trong bài làm. Trường `description` diễn giải ý nghĩa của từng bước: học sinh đang xác định điều kiện, chọn phương pháp, thực hiện phép tính hay kết luận. Không yêu cầu `description` chép nguyên văn bài làm; AI không được sửa lỗi hoặc thay ý nghĩa hành động học sinh đã thực hiện. Một bước có thể chỉ chứa lời văn, một phép tính hoặc nhiều phép tính liên quan.
3. Bộ chấm nhận danh sách bước sau phân tích cùng câu hỏi, đáp án và quy tắc đánh giá của đề đã duyệt.
4. Bộ chấm ánh xạ và kiểm tra các bước theo phạm vi được hỗ trợ.
5. Trả kết quả từng bước, kết luận toàn câu khi xác minh được, hoặc yêu cầu giáo viên khi còn phần chưa xác minh.
6. Backend tiếp nhận và lưu kết quả theo contract được nhóm thống nhất. Việc lưu trữ, phân quyền và trạng thái toàn bài thuộc phần tích hợp, không do module ánh xạ tự quyết định.

**Phạm vi đang triển khai:** bước ánh xạ và kiểm tra sau khi AI đã tách bài. Chưa có kết luận rằng bước Qwen tách văn bản nguyên khối đã hoàn thành hay được kiểm thử đầy đủ.

## 3. Dữ liệu đầu vào

### 3.1 Bài làm sau phân tích AI

```json
{
  "question_id": "QA0007",
  "answer": [
    {
      "step": 1,
      "description": "Xác định bốn nhóm lựa chọn theo phương tiện, với số chuyến tương ứng là 10, 5, 3 và 2."
    },
    {
      "step": 2,
      "description": "Áp dụng quy tắc cộng để tổng hợp số chuyến của bốn phương tiện; học sinh tính 10 + 5 + 3 + 2 và ghi kết quả 20."
    }
  ]
}
```

`description` mô tả hành động toán học học sinh thực sự thực hiện, không tự viết lại thành phương pháp đúng theo đáp án mẫu. Ví dụ học sinh ghi `7 + 8 = 16`, phần mô tả phải giữ thông tin học sinh cộng 7 với 8 và ghi kết quả 16; không sửa thành 15.

Bài làm nguyên bản được lưu riêng; cách truy lại đoạn gốc hoặc phép toán gốc theo từng bước cần được thống nhất khi nối bước phân tích. Việc diễn giải ý nghĩa không thay thế bằng chứng gốc để kiểm chứng.

Mảng `answer` chưa có đánh giá đúng/sai, feedback hoặc kết luận toàn câu. Những thông tin đó do bộ chấm tạo ra.

Số `step` là định danh bước của học sinh, không phải số bước tương ứng trong lời giải mẫu. Đầu ra bước phân tích cần có cách truy lại bài làm nguyên bản để phát hiện nội dung bị AI sửa, thêm hoặc bỏ sót. Cách biểu diễn liên kết này cần nhóm xác nhận.

### 3.2 Dữ liệu tham chiếu do hệ thống cung cấp

| Thành phần | Mục đích |
|---|---|
| Nội dung câu hỏi | Xác định chính xác yêu cầu và điều kiện |
| Đáp án cuối | Kiểm tra kết luận của bài làm |
| Lời giải tham chiếu | Cung cấp phương pháp và lập luận đã xác nhận |
| Rubric / quy tắc đánh giá | Quy định bằng chứng cần có để kết luận đúng/sai |
| Kỹ năng chính/phụ | Giới hạn ngữ cảnh kỹ năng của câu |
| Thông tin nhận diện đề đã duyệt | Backend bảo đảm dữ liệu tham chiếu đúng với đề học sinh đã làm |

Tên trường và cách truyền dữ liệu tham chiếu chờ contract API. Không tự yêu cầu thêm các trường phiên bản vào output chính thức khi nhóm chưa chốt; kiểm tra tính nhất quán của dữ liệu vẫn cần được thực hiện ở lớp thích hợp.

Trong DB nguồn đã kiểm tra, lời giải Question là khối văn bản trong `answers.explaination`, chưa có mốc gắn kỹ năng riêng. Template có `answer_rule` và `solution_rule`. Phương án thêm JSON phân tích đáp án đã được thử nghiệm, nhưng chưa phải thay đổi schema chính thức của nhóm.

Thiếu hoặc mâu thuẫn dữ liệu tham chiếu là vấn đề dữ liệu/hệ thống; không được biến thành lỗi của học sinh.

## 4. Nguyên tắc ánh xạ và kiểm tra

### 4.1 Ánh xạ theo nội dung

Không ghép cứng bước 1 của học sinh với bước 1 của đáp án mẫu. Học sinh có thể đổi thứ tự trình bày, gộp bước hoặc dùng cách giải khác.

Thiết kế cần hướng tới ánh xạ một hoặc nhiều bước theo vai trò toán học. Khả năng này chỉ được coi là có khi implementation và kiểm thử đã hỗ trợ; không suy từ mục tiêu thiết kế thành chức năng đã hoàn thành.

### 4.2 Kiểm chứng toán học

Kiểm tra phép tính, biểu thức và điều kiện áp dụng bằng code khi có bộ kiểm tra phù hợp. Không chạy nội dung học sinh bằng `eval` hoặc `exec`.

Cùng đáp số hoặc biểu thức tương đương về giá trị chưa đủ chứng minh lập luận đúng. Cần xem biểu thức đang đếm đối tượng nào và có đáp ứng điều kiện đề không. Phần chưa xác minh được phải giữ trạng thái chưa xác định.

### 4.3 Đánh giá bước và kỹ năng liên quan

Không phân loại lỗi gốc hoặc lỗi kéo theo. Khi một bước được xác định sai, ghi nhận bước sai và kỹ năng tương ứng với thao tác toán học của bước đó, không cần truy nguyên lỗi từ bước trước.

Không tự đánh sai mọi kỹ năng chính/phụ của câu. Chỉ gắn kỹ năng có căn cứ từ bước đã phân tích. Nếu chưa xác định được bước đúng/sai hoặc chưa đủ căn cứ xác định kỹ năng, giữ trạng thái chưa xác định và chuyển giáo viên theo phạm vi hỗ trợ. Cách biểu diễn kỹ năng lỗi trong output vẫn chờ nhóm thống nhất.

### 4.4 Vai trò AI

AI hỗ trợ đọc hiểu và tách bước. Việc AI mô tả một bước là đúng chưa phải bằng chứng đã xác minh.

Ở phạm vi bộ ánh xạ đang triển khai, đầu vào đã là danh sách bước. Module không cần gọi lại Qwen chỉ để tách cùng bài làm lần nữa. Nếu sau này bổ sung AI ánh xạ ngữ nghĩa, phải phân biệt kết quả model đề xuất với kết quả đã có căn cứ kiểm tra.

### 4.5 Phương pháp khác mẫu

Không kết luận sai chỉ vì cách giải khác lời giải tham chiếu. Cách khác được bộ kiểm tra hỗ trợ có thể được xác minh; chưa hỗ trợ hoặc chưa đủ căn cứ thì chuyển giáo viên.

Không coi thiếu một mốc của lời giải mẫu là bằng chứng chắc chắn học sinh sai kỹ năng đó.

## 5. Kết quả trả về theo mẫu dữ liệu hiện có

| Trường | Ý nghĩa |
|---|---|
| `grading_status` | `AI_GRADED` hoặc `NEEDS_REVIEW` theo mẫu nhóm cung cấp |
| `requires_teacher` | Có cần giáo viên xem lại không |
| `overall_result` | `CORRECT`, `INCORRECT` hoặc `UNCERTAIN` |
| `final_answer_correct` | `true`, `false` hoặc `null` khi chưa xác minh |
| `step_results` | Kết quả và nhận xét từng bước học sinh |
| `errors` | Những lỗi đã có căn cứ xác định |
| `missing_steps` | Phần bằng chứng/lập luận còn thiếu; chưa đồng nghĩa lỗi kỹ năng |
| `teacher_comment` | Nhận xét của giáo viên; chưa có thì `null` |

`AI_GRADED` là tên trạng thái trong mẫu, không tự chứng minh có một lượt gọi model trong module ánh xạ. Cần ghi nhận cách xử lý thực tế trong log khi tích hợp.

Không bắt buộc bổ sung `errors[].skill_ids` lúc này: đây là đề xuất người phụ trách đang trao đổi với nhóm. Tương tự, `cause_steps`, các trường phiên bản và `review_reason` chưa được chốt làm trường output chính thức.

Issue W07 có yêu cầu “cờ cần giáo viên kèm mã lý do”, trong khi mẫu hiện tại chưa có trường này và nhóm chưa thống nhất sử dụng. Đây là điểm phải làm rõ giữa issue và contract; không âm thầm thêm thành yêu cầu đã duyệt hoặc tự xóa yêu cầu khỏi issue.

## 6. Ví dụ kết quả

### 6.1 Đã xác minh được

```json
{
  "grading_status": "AI_GRADED",
  "requires_teacher": false,
  "overall_result": "CORRECT",
  "final_answer_correct": true,
  "step_results": [
    {
      "step": 1,
      "result": "CORRECT",
      "feedback": "Xác định đúng bốn nhóm lựa chọn."
    },
    {
      "step": 2,
      "result": "CORRECT",
      "feedback": "Áp dụng quy tắc cộng phù hợp; 10 + 5 + 3 + 2 = 20."
    }
  ],
  "errors": [],
  "missing_steps": [],
  "teacher_comment": null
}
```

Đây là minh họa kết quả khi phương pháp và điều kiện đã được kiểm tra; không phải tuyên bố mọi lời văn tương tự đều được implementation xác minh.

### 6.2 Cần giáo viên xem lại

```json
{
  "grading_status": "NEEDS_REVIEW",
  "requires_teacher": true,
  "overall_result": "UNCERTAIN",
  "final_answer_correct": null,
  "step_results": [
    {
      "step": 1,
      "result": "UNCERTAIN",
      "feedback": "Cách lập luận chưa được bộ kiểm tra hiện tại hỗ trợ; cần giáo viên xác nhận."
    }
  ],
  "errors": [],
  "missing_steps": [],
  "teacher_comment": null
}
```

Nếu một số bước đã được xác minh, có thể giữ kết quả của các bước đó dù toàn câu còn `UNCERTAIN`. Không mặc định đánh sai các bước chưa xác định.

## 7. Kiểm tra trước khi lưu kết quả

- Kết quả gắn đúng bài nộp, câu hỏi và đề đã duyệt.
- Các bước được tham chiếu tồn tại và không trùng định danh.
- Phân biệt bài làm học sinh với đáp án tham chiếu; AI không được chép lời giải mẫu thành bước học sinh.
- Kết luận đúng/sai có căn cứ kiểm tra trong phạm vi implementation hỗ trợ.
- Kết quả chưa xác minh không được tự đổi thành `INCORRECT`.
- Lỗi dữ liệu, lỗi định dạng hoặc lỗi xử lý không được quy thành lỗi kiến thức của học sinh.
- Model không được sửa nội dung câu, đáp án hoặc rubric đã duyệt.
- Backend kiểm tra định dạng kết quả theo contract và xử lý việc lưu lặp khi có retry.

## 8. Giáo viên và ranh giới tích hợp

Các câu chưa xác minh được được đưa vào luồng giáo viên. Giáo viên xem bài nguyên bản, kết quả phân tích, đề và dữ liệu tham chiếu để đưa ra nhận xét/kết luận theo quyền được nhóm thống nhất.

Chưa xác nhận rằng giáo viên được sửa mọi câu đã chấm tự động. Quyền thao tác với câu đã có kết quả tự động, trạng thái toàn bài và quy tắc hoàn tất bài phải theo workflow/API nhóm chốt; tài liệu này không tự mở thêm chức năng override.

Contract chưa hoàn thành không ngăn việc phát triển hàm ánh xạ nội bộ. Adapter sẽ chuyển dữ liệu vào/ra theo contract sau khi thống nhất. Không tự coi giao diện nội bộ hiện tại là API chính thức.

## 9. Hiện trạng implementation và thử nghiệm

### 9.1 Bộ thử JSON trước đó

Bản thử đầu đạt 5/10 nhãn tổng thể. Bản thử v2 đạt 9/10 trong lần chạy người dùng báo lại, tự động kết luận 6/10 ca. Một số ca được code xử lý trực tiếp; không được dùng kết quả đó để kết luận khả năng Qwen tách bước đạt 90%.

Bản v2 chuyển dư ca T06 đúng sang giáo viên. Cách chặn T09 là thu hẹp phạm vi tự động với lời văn chưa xác minh, chưa phải giải quyết tổng quát việc hiểu lập luận.

### 9.2 Module nội bộ sau bước tách

File `src/ai/answer_grading.py` hiện có prototype nhận danh sách `step`/`description`. Module kiểm tra ngữ cảnh tham chiếu và ánh xạ vào các phát biểu mẫu đã khai báo, trả review nếu chưa đủ căn cứ. Phần phân loại nguyên nhân giữa các bước trong prototype cũ cần được bỏ để khớp thiết kế hiện tại.

Đối chiếu hiện tại là chuẩn hóa và khớp phát biểu tham chiếu, chưa phải ánh xạ ngữ nghĩa tổng quát. Prototype trước đó dùng `description` như phát biểu bài làm; cần điều chỉnh dữ liệu tham chiếu và bộ ánh xạ khi chuyển sang `description` mô tả ý nghĩa bước. Việc cập nhật tài liệu này chưa đồng thời sửa code prototype. Cách diễn đạt mới hoặc cách gộp/tách chưa hỗ trợ sẽ chuyển giáo viên. Reference bổ sung trong demo là dữ liệu giả lập; không có nghĩa DB nhóm đã có cấu trúc đó.

Đã chạy 14 test kỹ thuật trên prototype. Bốn fixture cho kết luận tổng thể đúng, đúng, sai và chưa xác định tương ứng QA0007, QA0038, QA0064 và QA0102. Đây là kiểm tra các mẫu đã hỗ trợ, không phải đánh giá độc lập trên bài mới.

Prototype có một số trường nội bộ và kiểm tra bổ sung chưa được nhóm chốt. Cần nối/chỉnh qua adapter trước khi xem output là contract chính thức.

### 9.3 Vị trí file thử nghiệm

- `scripts/grading/run_demo.py`: chạy demo sau bước tách.
- `tests/test_grading.py`: test kỹ thuật module.
- `tests/fixtures/grading/demo_inputs.json`: dữ liệu đầu vào giả lập.
- `tests/fixtures/grading/gold.json`: nhãn kỳ vọng, không truyền vào bộ chấm.
- `eval/results/grading/demo_results.json`: kết quả được tạo khi chạy demo.

`expected_result` trong mẫu dữ liệu là nhãn đánh giá bộ chấm; khi chạy thật, hệ thống tự sinh kết quả từ bài làm và dữ liệu tham chiếu.

## 10. Các điểm còn chờ nhóm thống nhất

| Nội dung | Hiện trạng |
|---|---|
| Contract API chính thức | Chưa hoàn thành; giao diện nội bộ chỉ là tạm |
| Rubric dùng cho kết luận đúng/sai | Cần dữ liệu/quy tắc rõ cho từng câu hoặc dạng bài |
| Cấu trúc đáp án có mốc | Đang thử JSON; chưa chốt thay đổi DB |
| Kỹ năng lỗi trong output | Đang trao đổi; chưa bắt buộc `errors[].skill_ids` |
| Mã lý do chuyển giáo viên | Issue yêu cầu, mẫu chưa có; cần giải quyết trước bàn giao chính thức |
| Kết luận toàn câu khi có bước đúng và sai | Chưa chốt trạng thái “đúng một phần” |
| Bài trống hoặc chỉ có đáp số | Cần thống nhất theo quy tắc đánh giá; prototype xử lý thận trọng |
| Thời gian xử lý và retry | Đo riêng phân tích AI và ánh xạ; chưa chốt ngưỡng thời gian |
| Quyền giáo viên với kết quả tự động | Theo workflow và contract được nhóm duyệt |

## 11. Checklist trước khi nghiệm thu

- [ ] Chốt contract với người phụ trách API.
- [ ] Xác nhận dữ liệu đề và đáp án tham chiếu không mâu thuẫn.
- [ ] Xác định phạm vi phương pháp/lời văn có thể tự động kiểm tra.
- [ ] Kiểm thử bước Qwen tách văn bản nguyên khối riêng với bước ánh xạ.
- [ ] Kiểm thử cách giải khác, gộp/tách bước và lập luận sai nhưng đáp số đúng.
- [ ] Đánh giá độ đúng của từng bước, lỗi nhận sai/đúng, lỗi chuyển giáo viên và thời gian xử lý.
- [ ] Có tập bài mới chưa dùng để điều chỉnh implementation.
- [ ] Xác nhận output chính thức với Data / Architecture / API.

**Tài liệu liên quan:** `W06_Grading_Workflow_and_Acceptance_Criteria.md`, mẫu dữ liệu W07 do nhóm cung cấp và yêu cầu bàn giao `src/ai/answer_grading.py`. Tài liệu này không tự xác nhận các thiết kế cũ trong tài liệu liên quan là quyết định hiện hành.
