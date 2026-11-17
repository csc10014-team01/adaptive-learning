# Thực nghiệm sinh đề W06 — kết quả thu thập ngày 14/11/2026

## Trạng thái

Đã chạy Qwen thật và thu đủ 30/30 đề trong mẫu chính thức, sau một pilot 3 ca
riêng. Chưa có điểm W06 hoặc tỷ lệ đạt chất lượng: hai người chấm chưa điền
phiếu. 30/30 ở đây là tỷ lệ hoàn thành sinh đề, không xác nhận toán/ngữ nghĩa.

Thời gian mẫu chính thức: **17:38:33–17:44:49, Asia/Bangkok, 14/11/2026**.
Mã nguồn, rubric, model và database giữ nguyên trong đợt thu thập, đã đối chiếu
hash sau chạy. Không ghi database nguồn, không cập nhật Student Profile hoặc
tự duyệt các đề này trong ứng dụng.

## Mẫu và cấu hình

- 5 hồ sơ: ST016, ST003, ST004, ST008, ST010.
- 3 seed: 0, 42, 2026; 2 cấu hình: strict và experimental; mỗi đề 10 câu.
- Model `qwen3:1.7b`, quantization Q4_K_M, Ollama **0.40.16**.
- Model digest: `8f68893c685c3ddff2aa3fffce2aa60a30bb2da65ca488b61fff134a4d1730e7`.
- Timeout 45 giây/lần, deadline 180 giây/đề, tối đa 2 lần thử/presentation.
- Context quan sát được 4096; Ollama báo size_vram=0. Máy báo 18 CPU logic,
  RAM hệ thống khoảng 31,6 GiB. Số liệu máy trong artifact riêng, không phải
  bộ nhớ độc quyền của model.
- Strict/verified temperature 0; experimental temperature 0.7. Giữ seed/prompt
  và luồng chọn nguồn theo mã hiện hành; không tinh chỉnh giữa các ca chính thức.
- Warmup và pilot tách riêng. Đây là mẫu tình huống có chủ đích trên hồ sơ mẫu,
  không đại diện một quần thể học sinh hoặc chứng minh hiệu quả học tập.

## Kết quả vận hành quan sát được

| Chỉ số | Strict | Experimental | Tổng |
|---|---:|---:|---:|
| Yêu cầu đã chạy | 15 | 15 | 30 |
| Đề hoàn chỉnh | 15 | 15 | 30 |
| Ca lỗi toàn bộ | 0 | 0 | 0 |
| Lần gọi Qwen thật | 42 | 60 | 102 |
| Output bị validator loại | 0 | 18 | 18 |
| Lần thử lại trong cùng presentation | 0 | 11 | 11 |
| Lần chuyển Indirect sang Direct sau hết lượt | 0 | 7 | 7 |
| Câu ngân hàng trong đề cuối | 108 | 108 | 216 |
| Câu template được Qwen diễn đạt trong đề cuối | 42 | 42 | 84 |
| Câu mang nhãn Indirect thử nghiệm trong đề cuối | 0 | 11 | 11 |
| Đề thực sự chứa nhãn Indirect thử nghiệm | 0 | 10 | 10 |
| Thời gian trung bình/đề, giây | 8,354 | 15,476 | — |
| Trung vị thời gian/đề, giây | 9,464 | 14,508 | — |
| Nhỏ nhất–lớn nhất, giây | 3,283–12,862 | 2,082–29,658 | — |

Không có lỗi transport trong 102 lượt gọi đã ghi nhận. 73 output Direct qua
kiểm tra hữu hạn; 11 Indirect được giữ ở NEEDS_REVIEW; 18 Indirect bị loại.
7 lần fallback xảy ra trong 5 đề. Các đầu ra bị loại là attempt, không phải
18 bài toán riêng biệt. 11 retry cộng với 7 lượt Direct fallback tạo thêm 18
lượt gọi ở cấu hình experimental.

Thời gian trên gồm sinh đề core, đối chiếu nguồn và W06 evaluator; không gồm
warmup hoặc thao tác UI/FastAPI/auth. Đây là thống kê mô tả trên máy/cỡ mẫu này,
không phải SLA. Không tách riêng tác động của nhiệt độ, thứ tự, cache và Indirect.

## Mức độ đa dạng đầu ra thực tế

300 là lượt câu xuất hiện trong 30 đề. Có **41 nội dung khác nhau** sau chuẩn
hóa Unicode, hoa/thường và khoảng trắng; phép so này chưa phát hiện trùng ý
tưởng. Các đề cuối sử dụng **15 question_id ngân hàng** khác nhau và **17
chữ ký instance toán học template** khác nhau.

Chỉ 84/300 lượt câu có phần câu chữ do Qwen viết; đáp án/lời giải vẫn do nguồn
hoặc backend cung cấp. Do đó không mô tả kết quả như 300 câu toán mới do LLM
tự tạo. Cần tách đánh giá toàn đề và đánh giá phần Qwen khi chấm/tổng hợp.

ST004 ở cả 6 ca vẫn yêu cầu focus=4 nhưng đạt focus=1. Đây là giới hạn nguồn
A005 đã biết, cần phân tích riêng khi chấm C4. Cả 3 ca ST004 cấu hình experimental
không có Indirect cuối cùng vì chỉ có một template được chọn, nằm ở vị trí Direct.

## Nhận xét nội dung sơ bộ — chưa phải chấm HUMAN

Pilot đã quan sát một câu EA0017 đổi mục tiêu từ số cách xếp sang số loại sản
phẩm cần chuẩn bị, trong khi backend vẫn trả 120. Pilot được giữ riêng và không
tính vào kết quả mẫu chính thức. Trong mẫu chính thức có các điểm cần giáo viên
đặc biệt xem:

| Ca | Template | Nội dung cần kiểm tra |
|---|---|---|
| C04_ST003_s0_experimental | EA0013 | Model kể chuyện 5 cuốn sách, mỗi cặp được trưng bày với 12 cách, rồi hỏi số trang catalogue; cần đối chiếu cấu trúc với nguồn và đáp án 120. |
| C20_ST010_s42_experimental | EA0012 | Nguồn là chọn một cặp không thứ tự từ 7 đối tượng, đáp án 21. Model hỏi số lần chọn một loại đồ ăn trong 7 loại trước khi lặp lại; nghi ngờ thay đổi phép đếm và không khớp đáp án. |
| C30_ST010_s2026_experimental | EA0018 | Model hỏi số cấu hình để A/B không gặp nhau trong mọi buổi diễn; cần kiểm tra điều kiện xếp hàng và mục tiêu đếm có còn được giữ như nguồn, đáp án 30240 hay không. |

Các câu trên vượt qua kiểm tra số liệu/cấu trúc hữu hạn và được gắn NEEDS_REVIEW.
Nhận xét này do assistant sàng lọc, chưa được ghi điểm, chưa gắn Hard-Fail HUMAN.
Không suy ra tỷ lệ sai toán hoặc pass W06 chỉ từ các ví dụ này.

## Mở dữ liệu và chấm

- [Danh mục 30 đề, đáp án, hồ sơ và JSON](../../eval/results/w06/20261114_formal_01/review_index.md).
- [Phiếu W06 R1](../../eval/results/w06/20261114_formal_01/grading_R1.csv),
  [phiếu W06 R2](../../eval/results/w06/20261114_formal_01/grading_R2.csv): mỗi file
  120 dòng, 4 tiêu chí x 30 đề, điểm đang để trống.
- [Kiểm tra từng câu R1](../../eval/results/w06/20261114_formal_01/question_review_R1.csv),
  [kiểm tra từng câu R2](../../eval/results/w06/20261114_formal_01/question_review_R2.csv):
  mỗi file 300 dòng.
- [Hướng dẫn và quy tắc điền phiếu](../plans/W06_Live_Experiment_Protocol.md).

Hai người chấm độc lập theo rubric snapshot, giữ nguyên ID/fingerprint. Chấm
C1/C2/C3/C4 theo mức tối đa 35/25/20/20 và ghi bằng chứng; Hard-Fail xác nhận
phải có lý do. Tiêu chí chưa đủ căn cứ để trống, không mặc định đủ điểm. Có
bất đồng kết luận cần đối chiếu, không lấy trung bình để bỏ qua lỗi nghiêm trọng.

Sau khi điền phiếu:

```powershell
.\.venv\Scripts\python.exe -B tools/run_w06_experiment.py --summarize eval/results/w06/20261114_formal_01
```

## Dấu vết và kiểm chứng

- [Manifest, hash và cấu hình](../../eval/results/w06/20261114_formal_01/run.json).
- [Tổng hợp máy đọc được](../../eval/results/w06/20261114_formal_01/summary.json).
- [Đối chiếu 102 attempt, 30 đề, số dòng phiếu và hash](../../eval/results/w06/20261114_formal_01/evidence_audit.json).
- [Ví dụ cần xem lại, kèm nguyên đề nguồn và đầu ra](../../eval/results/w06/20261114_formal_01/assistant_advisory_examples.json).
- [Thông tin máy và runtime](../../eval/results/w06/machine_20261114.json).
- [Pilot riêng](../../eval/results/w06/20261114_pilot_01/report.md),
  [nhận xét pilot](../../eval/results/w06/20261114_pilot_01/pilot_review.json).

Đã xác minh mỗi lượt gọi có request và response gốc, số file attempt khớp
qwen_calls, không có attempt còn RUNNING ở kết quả cuối; hash code/rubric và
hai database nguồn khớp manifest. Bộ test chuẩn bị đạt 590 ca; các test trace
được chạy lại sau bổ sung metadata template và vẫn đạt.

Hash trong manifest ghi nhận byte tại thời điểm chạy trên Windows, trước khi
commit. Git có thể đổi LF/CRLF của mã nguồn khi checkout trên máy khác, nên
hash byte của source có thể khác dù nội dung tương đương; cần đối chiếu cả
newline khi kiểm chứng. `.gitattributes` giữ nguyên byte của bộ bằng chứng W06
và snapshot hồ sơ được chọn. Không sửa manifest để khớp commit được tạo sau
thực nghiệm.

Phần thu thập dữ liệu đã hoàn thành. Phần đánh giá chất lượng chuyên môn còn
PENDING; chưa có cơ sở kết luận đạt ngưỡng 80/100 hoặc tỷ lệ Hard-Fail cuối cùng.
