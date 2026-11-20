# W08 — Nâng cấp Qwen cho luồng sinh đề

- **Ngày quyết định:** 16/11/2026.
- **Người ra quyết định:** Phạm Yến Trân — AI & Algorithm Lead.
- **Phạm vi:** Đổi model mặc định cho thành phần AI viết câu chữ trong luồng sinh đề adaptive.
- **Model trước:** `qwen3:1.7b`.
- **Model sau:** `qwen3:4b-q4_K_M`.

Ngày trên là ngày quyết định được người phụ trách xác nhận; không phải ngày chạy benchmark hay ngày tích hợp code. Việc cập nhật và kiểm tra source trong đợt bàn giao này diễn ra ngày 20/11/2026.

## 1. Lý do thay đổi

Theo nhận xét sử dụng của người phụ trách AI, model nhỏ viết đề còn chưa tốt: cách diễn đạt thiếu tự nhiên, có câu khó hiểu hoặc không truyền đạt rõ ý nghĩa toán học mong muốn. Nhóm quyết định chuyển sang Qwen3 4B để thử cải thiện khả năng viết câu chữ và làm rõ ngữ cảnh của đề.

Trong trao đổi, model cũ từng được gọi là “Qwen 1.5B”. Tuy nhiên, source và log được cung cấp ghi chính xác `qwen3:1.7b`; tài liệu này dùng tên model theo code để tránh nhầm cấu hình.

Đây là quyết định lựa chọn model dựa trên nhận xét của nhóm và các thử nghiệm hiện có. Chưa có phép đo đối chứng cùng bộ đề, prompt, máy và cấu hình để khẳng định mức cải thiện chất lượng của 4B so với 1.7B.

## 2. Bằng chứng hiện có và cách diễn giải

### 2.1 Model cũ đã chạy được, nhưng kiểm tra cấu trúc chưa chứng minh chất lượng lời văn

Nguồn: `eval/results/baseline_spike_output.json` trong source được bàn giao.

Log ghi model `qwen3:1.7b`. Ca C01 yêu cầu chọn 3 học sinh từ 8 học sinh, không xét thứ tự, không hoàn lại. Output lưu trong log:

> Lớp học có 8 học sinh. Cần chọn 3 học sinh để làm nhiệm vụ. Hỏi có bao nhiêu cách chọn?

Log ghi đáp án 56, `json_valid=true`, không có lỗi validation cấu trúc/số và trạng thái `needs_teacher_review`. Ca này cho thấy model cũ có thể tạo câu đơn giản hợp lệ theo các kiểm tra đó; bản thân nó không phải bằng chứng về lỗi diễn đạt, cũng không chứng minh model mới tốt hơn.

Nhận xét “câu khó hiểu hoặc không rõ nghĩa” ở mục 1 là phản hồi của người phụ trách, chưa có tập ca lỗi được gắn nhãn đủ để tính tần suất.

### 2.2 Qwen3 4B đã có log thử nghiệm viết câu chữ

Nguồn lưu trữ đã đọc: bản ZIP `adaptive-learning (1).zip` được cung cấp trước đó, tại:

- `scripts/benchmarks/qwen3_4b/results/20261110T023525_555047Z/summary.md`.
- `scripts/benchmarks/qwen3_4b/results/20261110T023525_555047Z/results.json`.

Các file này thuộc bản ZIP trước, không có sẵn trong bản ZIP tích hợp mới `adaptive-learning (1)(1).zip`. Khi cần đối chiếu, dùng đúng bản lưu trữ; không hiểu các đường dẫn trên là file đã được thêm vào source mới.

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

Đây là bằng chứng 4B đã chạy được tác vụ Phraser với output đúng schema trong bộ thử nhỏ. **Không diễn giải 8 `needs_review` thành 8 câu đã được xác nhận đúng**, và không dùng tỷ lệ schema làm tỷ lệ đúng ngữ nghĩa. Log vẫn ghi các cảnh báo về dữ kiện số, ràng buộc và cách hỏi Indirect.

Cấu hình benchmark dùng giới hạn 256 tokens; client tích hợp hiện dùng 1800 tokens. Số thời gian trên không phải cam kết tốc độ của API/UI hiện tại.

### 2.3 Kiểm tra cấu hình tích hợp sau thay đổi

Ngày 20/11/2026, kiểm tra offline trên bản source mới sau khi sửa:

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

Giữ nguyên prompt, timeout, retry, validator, logic Planner và logic tính đáp án/lời giải. `qwen_spike.py` là script thử nghiệm độc lập, không phải nơi cấu hình model cho luồng sinh đề chính; script đó không được đổi trong đợt sửa source mới này.

## 4. Vai trò của Qwen trong sinh đề

- `python -m src.ui` không có `--fake` chọn backend Qwen.
- API chạy riêng vẫn mặc định backend `fake`; cần cấu hình `EXAM_BACKEND=qwen` để chọn luồng Qwen.
- Luồng adaptive dùng template có thể gọi Qwen để viết câu chữ. Backend giữ trách nhiệm tính đáp án và lời giải.
- Câu lấy từ ngân hàng giữ nguyên; không phải mọi câu trong đề đều gọi AI.
- Luồng `default_blueprint` hiện vẫn dùng cơ chế fake.

Việc đổi model không tự bảo đảm câu chữ đúng nghĩa; các kiểm tra hiện có vẫn áp dụng. Tài liệu này không bổ sung chức năng giáo viên chỉnh sửa kết quả AI grading.

## 5. Chạy thử bằng Git Bash

Chạy từ thư mục gốc repository, sau khi cài dependencies:

```bash
ollama pull qwen3:4b-q4_K_M
export QWEN_MODEL=qwen3:4b-q4_K_M
python -m src.ui
```

Ollama cần đang hoạt động. Chọn luồng adaptive có câu template khi kiểm tra inference; không thêm `--fake`. Ứng dụng không tự nạp `.env`, vì vậy biến môi trường phải được export trong terminal chạy ứng dụng.

## 6. Kết luận của quyết định

Phạm Yến Trân — AI & Algorithm Lead quyết định chuyển mặc định sang Qwen3 4B để cải thiện chất lượng diễn đạt theo nhu cầu của nhóm. Log hiện có xác nhận model 4B đã chạy thử được và code tích hợp qua kiểm tra offline; chưa đủ bằng chứng đối chứng để khẳng định 4B có độ chính xác ngữ nghĩa cao hơn 1.7B hoặc cải thiện bao nhiêu phần trăm.
