# Rà soát phần sinh đề trước thực nghiệm — 14/11/2026

## Kết luận

Các kiểm tra kỹ thuật được chạy đều đạt sau khi sửa các lỗi dưới đây. Chưa thể
xác nhận toàn bộ phần Qwen/Ollama hoặc chất lượng đề thật vì không kết nối được
Ollama tại endpoint cấu hình `http://127.0.0.1:11434`.

Kết quả không phải báo cáo chất lượng chuyên môn và không phải điểm W06.
Chưa chạy suy luận Qwen trong đợt kiểm tra này.

## Phạm vi

Đọc lại planner, chọn nguồn, template, validator, Qwen transport, fallback,
assembly, Quality Gate, API duyệt/regenerate và lưu revision. Giữ các thay đổi
W06 đã có trong working tree, không sửa database nguồn hoặc policy cá nhân hóa.

## Các lỗi đã sửa

| Phát hiện | Sửa và bằng chứng hồi quy |
|---|---|
| Báo cáo có thể thành PASS nếu kiểm tra nguồn gặp lỗi hạ tầng nhưng có đủ điểm HUMAN | Giữ RULE RETRYABLE_FAIL là lỗi chặn, điểm HUMAN không được ghi đè; contract báo cáo cũng từ chối hạ cấp lỗi. API trước đó còn có kiểm tra nguồn riêng nên không đồng nhất lỗi báo cáo này với việc chắc chắn duyệt lọt qua API. |
| Evaluator chưa đối chiếu identity của context được truyền vào | Hồ sơ/yêu cầu phải khớp học sinh, lớp, mode, số câu, thời lượng và scope của đề; không nhận điểm để che context sai. |
| So sánh policy bằng tiền tố có thể nhận nhầm policy có tên gần giống | Chỉ nhận version bằng nhau hoặc hậu tố quan hệ kỹ năng phân cách bằng dấu `+`; version khác được chuyển người xem. |
| QwenClient nhận timeout NaN/Infinity và attempts kiểu boolean/float | Timeout phải là số hữu hạn dương; attempts phải là số nguyên 1–3. Lỗi cấu hình bị phát hiện trước gọi model. |
| Chỉ kiểm tra done=true, có thể nhận completion bị cắt dù JSON vẫn parse được | Khi provider gửi done_reason, chỉ nhận `stop`; lý do khác vào nhánh INVALID_QWEN_OUTPUT/retry hiện có. Giữ tương thích envelope cũ không có trường này. |

Đối chiếu contract `done` và `done_reason` với [API Generate chính thức của Ollama](https://docs.ollama.com/api/generate).
Không thay đổi nhiệt độ, prompt, ngân sách thử, bảng độ khó hoặc cơ chế fallback.

UI có thêm thông báo tiếng Việt cho các mã lỗi Quality Gate. Quyết định đã
phê duyệt vẫn giữ nguyên: NEEDS_REVIEW có thể được duyệt thủ công, không biến
thành PASS hoặc tự nhận điểm.

## Kết quả kiểm tra

- **582/582 test Python đạt**, trong đó có bộ gọi **20 tình huống UI**.
- Test duyệt đồng thời dùng hai kết nối SQLite độc lập: một yêu cầu thành công,
  một nhận EXAM_REVISION_CONFLICT; chỉ có revision 1 và 2, báo cáo khớp revision.
- Một cảnh báo deprecation có sẵn của Starlette/httpx; không đổi dependency.
- `git diff --check` không phát hiện lỗi khoảng trắng.

Ma trận chỉ đọc trên snapshot dữ liệu hiện hành:

| Nội dung | Kết quả |
|---|---:|
| Hồ sơ | 20 |
| Số câu mỗi đề | 1–10 |
| Seed | 0, 42, 2026 |
| Ca sinh đề offline | 600/600 đạt |
| Replay cùng seed, so sánh nội dung/nguồn/điểm, bỏ qua UUID | 20/20 đạt |
| Regenerate template và đối chiếu nguồn, contract, Quality Gate | 20/20 đạt |
| Nguồn ngân hàng đủ metadata | 121 câu |
| Định nghĩa template | 18 |
| Tổng lượt câu của 600 ca | 3.300, gồm 2.397 ngân hàng và 903 template |
| Kết quả báo cáo W06 | 600 NEEDS_REVIEW, không tự cấp điểm |
| Số lần gọi Qwen | 0 |

3.300 là lượt câu, không phải số câu độc nhất. Chế độ fake dùng template/backend
để kiểm tra toán, nguồn và luồng; không kiểm tra cách diễn đạt do model tạo.
SHA-256 của hai database nguồn trước/sau không đổi.

Kết quả máy đọc được, hash database và mã nguồn, commit và trạng thái working
tree nằm trong [exam_generation_preflight.json](../../eval/results/exam_generation_preflight.json).
Working tree có thay đổi chưa commit nên kết quả gắn với hash mã nguồn trong
artifact, không chỉ với commit HEAD.

## Kiểm tra lại trên máy chạy thực nghiệm

```powershell
.\.venv\Scripts\python.exe -B tools/check_exam_readiness.py
```

Lệnh chạy kiểm tra offline và đọc `/api/version`, `/api/tags`; không gọi
`/api/generate`, không lưu đề runtime và không ghi database nguồn. Chỉ ghi JSON
báo cáo. Trả mã thoát khác 0 khi nguồn/kiểm tra lỗi hoặc Ollama/model chưa sẵn sàng.

```powershell
# Chỉ kiểm tra backend, không thăm dò Ollama:
.\.venv\Scripts\python.exe -B tools/check_exam_readiness.py --offline

# Kiểm tra nhanh với ít cấu hình:
.\.venv\Scripts\python.exe -B tools/check_exam_readiness.py --counts 1 4 10 --seeds 42
```

AVAILABLE chỉ xác nhận endpoint phản hồi và có model được cấu hình, chưa xác
nhận suy luận hoặc chất lượng nội dung. Hiện kết quả thực tế là UNAVAILABLE
(kết nối bị từ chối), ready_to_attempt_live_generation=false.

## Điều kiện còn lại trước thu kết quả chất lượng

1. Khởi động Ollama và cung cấp đúng model cấu hình; chạy lại preflight.
2. Khởi động lại backend để nhận bản sửa; UI cũ đang chạy không tự reload module Python.
3. Chạy một đề adaptive bằng Qwen thật, kiểm tra nguồn nào thực sự gọi model và
   mọi fallback; giữ riêng kết quả strict và experimental Indirect.
4. Có người kiểm tra toán/ngữ nghĩa và chấm W06. Ngưỡng trùng lặp/độ khó nghiêm
   trọng vẫn chưa được chốt; không tự suy diễn từ kiểm tra kỹ thuật.

Không có thay đổi Student Profile sau chấm bài. Không kết luận chất lượng
Qwen, hiệu quả học tập hoặc đạt 80/100 từ các kết quả offline ở trên.
