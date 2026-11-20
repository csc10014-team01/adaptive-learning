# Chất lượng và lựa chọn hồ sơ thực nghiệm W06 — 14/11/2026

## Kết luận

Dữ liệu đủ để làm thực nghiệm có kiểm soát về luồng sinh đề trên các hồ sơ mẫu.
Chưa đủ để kết luận hiệu quả cá nhân hóa trên học sinh thực hoặc hiệu quả học
tập theo thời gian. Số học sinh và số điểm mastery khác nhau không phản ánh
trực tiếp số tình huống khác nhau mà planner thực sự xử lý.

Chọn năm hồ sơ: **ST016, ST003, ST004, ST008, ST010**. Có một ca thiếu nguồn
câu được giữ riêng để đo giới hạn của hệ thống hiện tại.

## Nguồn và cách kiểm tra

- Đọc hai SQLite nguồn bằng kết nối `mode=ro`, `PRAGMA query_only=ON`.
- `quick_check=ok`, không có lỗi từ `foreign_key_check` ở cả hai database.
- Đối chiếu skill catalogue qua adapter, các question_id trong lịch sử với ngân hàng.
- Đọc mastery/evidence thật từ database, phân loại bằng RuleBasedPlanner hiện hành.
- So sánh nguồn câu, target skill, cognitive level và chữ ký instance ở đề 10 câu,
  seed 0, 42, 2026, không bật policy quan hệ kỹ năng tùy chọn.
- Không gọi Qwen, không sinh thêm dữ liệu và không sửa database.

Ngưỡng đang áp dụng: evidence>=3 mới đủ căn cứ phân loại WEAK/ACHIEVED;
mastery<2.0/4 là WEAK, mastery>=2.0 là ACHIEVED khi đủ evidence. Điểm cao nhưng
evidence chỉ 1–2 vẫn PARTIAL. ACHIEVED không đồng nghĩa học sinh giỏi toàn diện.

## Chất lượng dữ liệu hiện có

| Kiểm tra | Kết quả |
|---|---|
| Học sinh | 20 |
| Bản ghi mastery thực trong database | 135, ở ST001–ST015 |
| Hồ sơ không có bản ghi mastery hoặc bài kiểm tra | ST016–ST020; adapter trả 9 kỹ năng NO_DATA, mastery null/evidence 0 |
| Bản ghi cùng mastery=2.0, evidence=1 | 92/135, khoảng 68,1%; đây cũng là cặp giá trị mặc định của schema |
| Bản ghi có evidence>=3 | 19/135, khoảng 14,1% |
| Lịch sử | 11 bài kiểm tra, tổng 40 lượt trả lời câu hỏi |
| Tham chiếu câu trong lịch sử | 40/40 question_id riêng biệt có trong ngân hàng; is_correct đều thuộc 0/1 |
| Có mastery/evidence nhưng không có bài kiểm tra được lưu | ST011, ST012, ST013, ST014, ST015 |
| Cách rẽ nhánh theo hồ sơ | 16 diagnostic_review, 3 focused_practice, 1 advanced_review |
| Hồ sơ có ít nhất 2 kỹ năng WEAK đáng tin cậy | Không có |

92 cặp giá trị trùng mặc định là dấu hiệu dữ liệu mẫu đồng đều, không phải bằng
chứng rằng cả 92 bản ghi đều sai. Tương tự, thiếu lịch sử không chứng minh mastery
sai: hiện không có đủ dữ liệu để tái dựng hoặc kiểm chứng cách tính các điểm đó.
Ví dụ ST010 có 34 evidence cộng theo kỹ năng nhưng chỉ có 1 bài/3 lượt câu được
lưu. Không suy ra 34 evidence này đã được tạo từ 3 câu hiện có.

## Đa dạng đầu vào và đa dạng hành vi

Ở cả ba seed đã đối chiếu, nhóm sau cho cùng thứ tự nguồn, cùng target skill,
level và chữ ký template instance, bỏ qua student_id:

`ST001, ST002, ST005, ST007, ST009, ST016, ST017, ST018, ST019, ST020`.

Năm hồ sơ PARTIAL đầu nhóm có các giá trị mastery khác nhau; năm hồ sơ cuối
NO_DATA. Tuy vậy, chúng cùng dùng phân bổ diagnostic mặc định. Đây là hành vi
đúng với policy thiếu evidence, nhưng không tạo thành mười tình huống sinh đề
khác nhau. Vì vậy không dùng đồng thời ST001 và ST016 trong bộ năm ca chính.
Chọn một đại diện NO_DATA; giữ ca PARTIAL làm kiểm tra phụ khi cần xác nhận
không cá nhân hóa quá sớm, thay vì xem đó là một nhóm đầu ra độc lập.

## Năm hồ sơ được chọn

| ID | Căn cứ lựa chọn | Kế hoạch đề 10 câu quan sát được |
|---|---|---|
| ST016 | Không có bản ghi mastery, không có lịch sử; đại diện cold start | Diagnostic 10/10; mức L1/L2/L3/L4 = 3/3/3/1 |
| ST003 | A002 Quy tắc nhân: mastery 1.8, evidence 3; tám kỹ năng còn lại PARTIAL; có 1 bài/4 lượt câu | Focus A002 4 câu, review 6; mức 3/4/3/0 |
| ST004 | A005 Sơ đồ hình cây: mastery 0.2, evidence 3; tám kỹ năng còn lại PARTIAL; có 1 bài/3 lượt câu | Yêu cầu focus 4 câu nhưng thực đạt 1; review tăng 6 lên 9; mức toàn đề vẫn 3/4/2/1 |
| ST008 | A002: 2.9/evidence 3; A003 Hoán vị: 4.0/evidence 5; bảy kỹ năng PARTIAL; có 1 bài/4 lượt câu | Diagnostic 6, maintenance 4; chia maintenance 2 A002 + 2 A003; mức 2/3/4/1 |
| ST010 | Cả 9 kỹ năng đủ evidence 3–6 và mastery>=2.0; điểm nằm trong 2.0–3.8; có 1 bài/3 lượt câu | Advanced review 10; mức 2/4/3/1. Không coi là tất cả kỹ năng mastery=4 |

Các vector mức độ khó và quota nhóm trên giữ nguyên ở seed 0, 42, 2026 trong
lần kiểm tra này; câu và tham số template có thể thay đổi theo seed. Đây là
preview offline, không phải cam kết kết quả cuối giống hệt khi Qwen thất bại
và hệ thống chọn fallback khác.

### Diễn giải riêng ST004

Ngân hàng hiện chỉ có **1 câu primary_skill=A005**, ở mức understanding, và
không có template liên kết A005. Do đó không thể lấy đủ 4 câu khác nhau cho
focus skill này từ nguồn hiện có. Cả ba seed đều ghi focus thực đạt 1/4.

Giữ hồ sơ này như một ca kiểm tra thiếu nguồn có chủ đích, báo cáo riêng:
đây là giới hạn bao phủ ngân hàng/chọn nguồn, không thể quy riêng cho Qwen
hoặc thay prompt để khắc phục. Trước chạy cần ghi rõ vai trò ca này, giữ nguyên
nguồn và đo sai lệch quota thực tế.

ST003 là ca focus có đủ nguồn để đối chiếu với ST004. ST008 kiểm tra phối hợp
nhiều kỹ năng đã đạt với các kỹ năng thiếu bằng chứng. Các hồ sơ này có lịch sử
được lưu, nên ưu tiên hơn ST011–ST015 cho bộ chính.

## Những gì bộ năm hồ sơ chưa bao phủ

- Nhánh hai kỹ năng yếu với focus 60%: dữ liệu hiện không có hồ sơ phù hợp.
- Hồ sơ có cả WEAK và ACHIEVED đủ evidence, hoặc yếu ở nhiều miền khác nhau.
- Diễn biến mastery qua nhiều lần đánh giá và nhận diện lỗi tư duy: lịch sử quá mỏng,
  adapter hiện chỉ đưa danh sách câu sai, chưa có observation level hoặc lỗi tư duy.
- Hiệu quả học tập thực tế và tính đại diện của một nhóm học sinh ngoài đời.

Nếu cần phủ thêm các nhánh này, tạo fixture thực nghiệm riêng có nhãn synthetic
và nguồn gốc rõ ràng, không sửa hồ sơ gốc để thay đổi kết quả thử nghiệm. Khi đó
cần điều chỉnh số ca hoặc xác định lại phạm vi bộ năm trước khi chạy chính thức.

## Artifact cho script thực nghiệm

[w06_selected_profiles.json](../../eval/benchmarks/w06_selected_profiles.json)
lưu ID, vai trò ca, snapshot mastery/evidence/lịch sử (bỏ tên cá nhân), policy,
hash hai database và preview quota ở ba seed. Chưa chứa kết quả Qwen hoặc điểm
chấm W06.

Khi xây script 30 ca, dùng 5 ID này x 3 seed x 2 cấu hình strict/experimental.
Kiểm tra lại hash nguồn trước chạy. Chấm chất lượng theo từng hồ sơ và tách
chất lượng câu Qwen thực sự viết khỏi câu ngân hàng. Không xem các lần lặp
của một hồ sơ là các học sinh độc lập.
