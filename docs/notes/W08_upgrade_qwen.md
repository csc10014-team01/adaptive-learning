# W08 — Nâng cấp Qwen cho luồng sinh đề

- **Ngày quyết định:** 16/11/2026.
- **Người lập báo cáo và ra quyết định:** Phạm Yến Trân — AI & Algorithm Lead.
- **Phạm vi:** Đổi model mặc định cho thành phần AI viết câu chữ trong luồng sinh đề adaptive.
- **Model trước:** `qwen3:1.7b`.
- **Model sau:** `qwen3:4b-q4_K_M`.

Với vai trò AI & Algorithm Lead, tôi quyết định chuyển model mặc định của luồng sinh đề adaptive sang Qwen3 4B từ ngày 16/11/2026. Báo cáo này ghi lại cơ sở lựa chọn và kết quả kiểm tra cấu hình cập nhật ngày 20/11/2026; ngày quyết định được phân biệt với ngày kiểm thử và tích hợp.

## 1. Lý do thay đổi

Qua quá trình sử dụng và xem xét câu sinh ra, tôi nhận thấy model nhỏ viết đề còn chưa tốt: cách diễn đạt thiếu tự nhiên, có câu khó hiểu hoặc không truyền đạt rõ ý nghĩa toán học mong muốn. Tôi quyết định chuyển sang Qwen3 4B với mục tiêu cải thiện cách viết câu chữ và làm rõ ngữ cảnh của đề.

Tôi đưa ra quyết định dựa trên nhận xét sử dụng và các thử nghiệm hiện có. Chưa có phép đo đối chứng cùng bộ đề, prompt, máy và cấu hình để khẳng định mức cải thiện chất lượng của 4B so với 1.7B.

## 2. Bằng chứng hiện có và cách diễn giải

### 2.1 Model cũ đã chạy được, nhưng kiểm tra cấu trúc chưa chứng minh chất lượng lời văn

Tôi sử dụng log `eval/results/baseline_spike_output.json` làm nguồn đối chiếu cho model cũ.

Log ghi model `qwen3:1.7b`. Ca C01 yêu cầu chọn 3 học sinh từ 8 học sinh, không xét thứ tự, không hoàn lại. Output lưu trong log:

> Lớp học có 8 học sinh. Cần chọn 3 học sinh để làm nhiệm vụ. Hỏi có bao nhiêu cách chọn?

Log ghi đáp án 56, `json_valid=true`, không có lỗi validation cấu trúc/số và trạng thái `needs_teacher_review`. Ca này cho thấy model cũ có thể tạo câu đơn giản hợp lệ theo các kiểm tra đó; bản thân nó không phải bằng chứng về lỗi diễn đạt, cũng không chứng minh model mới tốt hơn.

Nhận xét “câu khó hiểu hoặc không rõ nghĩa” ở mục 1 là đánh giá định tính của tôi. Tôi chưa có tập ca lỗi được gắn nhãn đủ để tính tần suất hoặc công bố tỷ lệ lỗi.

### 2.2 Qwen3 4B đã có log thử nghiệm viết câu chữ

Tôi đưa vào báo cáo kết quả benchmark được lưu trong bản source trước (`adaptive-learning (1).zip`), tại:

- `scripts/benchmarks/qwen3_4b/results/20261110T023525_555047Z/summary.md`.
- `scripts/benchmarks/qwen3_4b/results/20261110T023525_555047Z/results.json`.

Tôi phân biệt bộ log lưu trữ này với source tích hợp hiện tại (`adaptive-learning (1)(1).zip`): các file kết quả trên chưa có trong bản source tích hợp. Việc dẫn nguồn không đồng nghĩa đưa các log đó vào PR nâng cấp model.

| Thuộc tính | Kết quả ghi trong log |
| --- | --- |
| Model | `qwen3:4b-q4_K_M` |
| Tác vụ | Phraser — viết câu chữ đề |
| Cấu hình | `think=false`, `num_predict=256`, `temperature=0`, `num_ctx=4096`, `seed=42` |
| Số ca warm đo chính | 10; không tính warmup |
| Tỷ lệ đúng schema | 10/10 |
| Trạng thái của bộ kiểm tra | 8 `needs_review`, 2 `incorrect_result` |
| Thời gian trung bình | 5,806 giây/câu |
| Trung vị | 5,963 giây/câu |

Tôi sử dụng kết quả này để xác nhận 4B đã chạy được tác vụ Phraser với output đúng schema trong bộ thử nhỏ. **Tôi không xem 8 `needs_review` là 8 câu đã được xác nhận đúng**, cũng không dùng tỷ lệ schema làm tỷ lệ đúng ngữ nghĩa. Log vẫn ghi các cảnh báo về dữ kiện số, ràng buộc và cách hỏi Indirect.

Cấu hình benchmark dùng giới hạn 256 tokens; client tích hợp hiện dùng 1800 tokens. Số thời gian trên không phải cam kết tốc độ của API/UI hiện tại.

### 2.3 Kiểm tra cấu hình tích hợp sau thay đổi

Tôi ghi nhận các kết quả kiểm tra offline ngày 20/11/2026 trên bản source sau thay đổi, được thực hiện trong môi trường hỗ trợ rà soát bằng ChatGPT:

- `python -m pytest tests/generator -q`: **432 passed**.
- Khởi tạo `QwenClient()` chọn `qwen3:4b-q4_K_M`.
- API không có biến `QWEN_MODEL` chọn cùng model 4B.
- Khi đặt `QWEN_MODEL`, API vẫn tôn trọng giá trị ghi đè.

Các kiểm tra này xác nhận thay đổi cấu hình và tính tương thích của code. Chúng không gọi model thật và không chứng minh chất lượng câu sinh ra tốt hơn. Chưa chạy lại inference 4B qua UI/API trong đợt sửa cấu hình này.

## 3. Thay đổi trong source

| File | Thay đổi |
| --- | --- |
| `src/exam_generator/ai/qwen_client.py` | Đổi model mặc định của `QwenClient` từ 1.7B sang 4B. |
| `src/api/main.py` | Đổi model dự phòng khi biến môi trường `QWEN_MODEL` chưa được đặt. |
| `.env.example` | Cập nhật ví dụ `QWEN_MODEL=qwen3:4b-q4_K_M`. |
| `README.md` | Cập nhật model mặc định của luồng sinh đề. |
| `docs/notes/W08_upgrade_qwen.md` | Ghi quyết định, lý do, bằng chứng và giới hạn của thay đổi. |

Tôi giới hạn thay đổi ở tên model mặc định và tài liệu liên quan, giữ nguyên prompt, timeout, retry, validator, logic Planner và logic tính đáp án/lời giải. `qwen_spike.py` là script thử nghiệm độc lập, không phải nơi cấu hình model cho luồng sinh đề chính; script đó không được đổi trong đợt sửa source mới này.

## 4. Vai trò của Qwen trong sinh đề

- `python -m src.ui` không có `--fake` chọn backend Qwen.
- API chạy riêng vẫn mặc định backend `fake`; cần cấu hình `EXAM_BACKEND=qwen` để chọn luồng Qwen.
- Luồng adaptive dùng template có thể gọi Qwen để viết câu chữ. Backend giữ trách nhiệm tính đáp án và lời giải.
- Câu lấy từ ngân hàng giữ nguyên; không phải mọi câu trong đề đều gọi AI.
- Luồng `default_blueprint` hiện vẫn dùng cơ chế fake.

Tôi tiếp tục giữ các kiểm tra hiện có vì thay đổi model không tự bảo đảm câu chữ đúng nghĩa.

## 5. Chạy thử bằng Git Bash

Chạy từ thư mục gốc repository, sau khi cài dependencies:

```bash
ollama pull qwen3:4b-q4_K_M
export QWEN_MODEL=qwen3:4b-q4_K_M
python -m src.ui
```

Ollama cần đang hoạt động. Chọn luồng adaptive có câu template khi kiểm tra inference; không thêm `--fake`. Ứng dụng không tự nạp `.env`, vì vậy biến môi trường phải được export trong terminal chạy ứng dụng.

## 6. Kết luận của quyết định

Tôi quyết định sử dụng `qwen3:4b-q4_K_M` làm model mặc định cho thành phần viết câu chữ trong luồng sinh đề adaptive, với mục tiêu cải thiện chất lượng diễn đạt. Cơ sở hiện tại gồm nhận xét sử dụng, log thử nghiệm 4B và kết quả kiểm tra cấu hình tích hợp. Tôi chưa công bố mức cải thiện độ chính xác ngữ nghĩa so với 1.7B vì chưa có thử nghiệm đối chứng tương ứng.
