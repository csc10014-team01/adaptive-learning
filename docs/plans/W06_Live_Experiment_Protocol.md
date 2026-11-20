# Thực nghiệm sinh đề W06 bằng Qwen thật

## Phạm vi và mẫu cố định

Nguồn chọn mẫu: [w06_selected_profiles.json](../../eval/benchmarks/w06_selected_profiles.json).
Năm hồ sơ ST016, ST003, ST004, ST008, ST010; mỗi hồ sơ dùng seed 0, 42, 2026;
hai cấu hình strict/experimental. Tổng 30 yêu cầu, mỗi yêu cầu 10 câu, 45 phút.
Đây là mẫu tình huống có chủ đích, không phải 30 học sinh độc lập hoặc mẫu
đại diện quần thể. Số lượt câu tối đa là 300, không mặc định 300 câu độc nhất.

Strict đặt KORO_EXPERIMENTAL_INDIRECT=0. Experimental đặt bằng 1. Nhiệt độ và
seed gửi model giữ đúng QwenClient: strict/verified temperature 0; experimental
temperature 0.7, variation seed theo instance và attempt. Vì nhiều thiết lập
khác nhau, so sánh là giữa hai cấu hình, không quy mọi chênh lệch riêng cho
cách diễn đạt Indirect. Thứ tự chạy cố định: từng seed, từng hồ sơ, strict rồi
experimental. Chưa thực hiện làm mù người chấm hoặc ngẫu nhiên hóa thứ tự; cần
ghi giới hạn ảnh hưởng cache/thứ tự trong báo cáo.

ST004 là ca thiếu nguồn có chủ đích: A005 chỉ có một câu ngân hàng, không có
template; preview focus đạt 1/4. Phân tích riêng sai lệch quota và chất lượng
câu chữ của model, không gộp giới hạn bao phủ nguồn thành lỗi của Qwen.

## Chạy và giữ bằng chứng

```powershell
# Pilot ba ca đầu, tách khỏi mẫu chính thức:
.\.venv\Scripts\python.exe -B tools/run_w06_experiment.py --phase pilot --limit 3

# Sau khi kiểm tra các file pilot, chạy đủ 30 ca:
.\.venv\Scripts\python.exe -B tools/run_w06_experiment.py --phase formal
```

Mặc định model qwen3:1.7b, timeout mỗi lần 45 giây, deadline đề 180 giây và
tối đa 2 lần thử mỗi presentation. Đây là cấu hình ứng dụng hiện hành, không
thay giữa chừng để loại kết quả lỗi. Thay cấu hình sau pilot cần run mới.

Script không có chế độ fake; gọi ExamService và các validator hiện có, rồi
chạy W06 evaluator. Không tự duyệt đề, không ghi database nguồn hoặc runtime
exams.db. Sửa tên hiển thị thành student_id trong snapshot thực nghiệm; mastery,
evidence và lịch sử giữ nguyên. Mỗi run lưu:

- `run.json`, `selection.json`, `rubric_snapshot.md`: cấu hình, model digest,
  Ollama version, hash mã nguồn/rubric/database và mẫu đã chọn.
- Warmup riêng, loại khỏi thời gian ca chính. Metadata model đang nạp được lưu
  sau warmup; số liệu RAM/VRAM chỉ là mẫu toàn hệ thống khi đo được, không phải
  phần bộ nhớ riêng của Ollama. Không đo được thì để null.
- `cases/<id>/execution_01/`: hồ sơ, request, preview, đề JSON, đề/đáp án/lời giải
  dạng text, kết quả W06 và kết quả chạy.
- `attempts/`: request model nguyên bản, response HTTP dạng `.bin`, output model,
  lý do validator nhận/loại, lỗi transport, thời gian và metrics Ollama. Giữ cả
  các attempt bị loại và wording được chấp nhận nhưng không dùng trong đề cuối.
- `summary.json`, `report.md`: số ca, lỗi, retry và kết quả theo cấu hình/hồ sơ.

Một đề trả về đầy đủ có thể hoàn toàn từ ngân hàng sau fallback. Báo cáo ghi
riêng số lần thật sự gọi Qwen và số câu template dùng ở đề cuối. Không coi 30
HTTP/generation requests thành 30 đề thành công hoặc coi mọi câu đều do Qwen viết.
Thời gian đo gồm core generation, kiểm tra nguồn và W06; không đo overhead
FastAPI/auth hoặc thời gian người dùng thao tác UI.

Đang chạy mà mã, rubric, model digest hoặc nguồn thay đổi thì batch bị dừng.
Kết quả đã thu giữ nguyên. Mất kết nối trước ca mới ghi NOT_RUN, không giả lập.
Ca đã thực hiện và thất bại ghi FAILED. GENERATION_COMPLETE nghĩa đã xử lý hết
mẫu, không đồng nghĩa mọi ca thành công hay chất lượng đạt 80/100.

```powershell
# Tiếp tục run bị gián đoạn, với đúng cấu hình cũ:
.\.venv\Scripts\python.exe -B tools/run_w06_experiment.py --resume eval/results/w06/<run>
```

Các ca GENERATED/FAILED không chạy lại để chọn kết quả đẹp hơn. Ca bị gián đoạn
tạo execution mới và giữ execution cũ. Nếu run cũ dùng timeout/model khác mặc
định, truyền lại các tùy chọn cũ để kiểm tra frozen config khớp.

## Phiếu chấm cho hai người độc lập

Mỗi run tạo `grading_R1.csv`, `grading_R2.csv` và hai file
`question_review_R1.csv`, `question_review_R2.csv`. Mở bằng Excel/Sheets hoặc
trình soạn CSV hỗ trợ UTF-8. Các ô điểm và kết luận ban đầu để trống.

1. Xem đề, đáp án, lời giải, nguồn và snapshot hồ sơ. Với từng câu, ghi kiểm tra
   toán, giữ nghĩa, kỹ năng, độ khó, trùng lặp và hiển thị; ghi bằng chứng cụ thể.
2. Đánh giá đủ các mục con của W06 rồi nhập tổng nhóm C1<=35, C2<=25, C3<=20,
   C4<=20. Cả 30 ca đều adaptive, nên C4 áp dụng. Ghi lý do trừ điểm/evidence;
   không chấm đủ điểm chỉ vì phần mềm không báo lỗi.
3. `hard_fail_confirmed`: nhập `yes` hoặc `no`; nếu yes phải có
   `hard_fail_reason`. Một Hard-Fail được xác nhận cho tổng 0 theo W06, các ô
   tiêu chí chưa đánh giá vẫn để trống. Nếu chưa xác nhận được thì giữ trống
   và ghi nghi ngờ trong notes, không tự đặt ngưỡng nghiêm trọng.
4. Giữ nguyên ID, exam_id, fingerprint, reviewer và các cột metadata. Điểm phải
   gắn đúng đề đã xem. Hai người chấm riêng, đối chiếu bất đồng sau đó; script
   không tự lấy trung bình hai kết luận để che lỗi nghiêm trọng.

```powershell
# Sau khi điền phiếu, cập nhật thống kê và báo cáo:
.\.venv\Scripts\python.exe -B tools/run_w06_experiment.py --summarize eval/results/w06/<run>
```

Lệnh tổng hợp giữ lại các ô người chấm đã điền. Score ngoài miền, NaN, thiếu
bằng chứng hoặc chưa xác nhận yes/no đều không được tính là đã chấm xong.
Kết quả hai người được báo cáo riêng, kèm số đề đã chấm/tổng đề sinh được.
Kết luận đạt khác nhau cần đối chiếu; không có điểm chất lượng tự động trong
báo cáo khi phiếu còn trống. Đây là đánh giá ngoài luồng duyệt, không làm đổi
trạng thái đề hay hồ sơ học sinh trong ứng dụng.

## Điều kiện vận hành tại máy này

Ollama portable được tải từ release chính thức, kiểm tra SHA-256 trước giải nén.
Runtime/model nằm trong `data/runtime/ollama/` (được gitignore), service chỉ nghe
localhost. Model tải bằng Ollama và lưu digest trong run. Dịch vụ này không
được cài thành Windows Service. Hướng dẫn portable:
[Ollama Windows](https://docs.ollama.com/windows).

Việc chạy mã hoàn tất không thay thế chấm chuyên môn. Rubric vẫn có các phần
đang draft, đặc biệt mức độ trùng lặp/độ khó "nghiêm trọng". Báo cáo cần nêu
giới hạn dữ liệu hồ sơ dựng sẵn, nguồn ngân hàng, thang chấm và cỡ mẫu nhỏ.
