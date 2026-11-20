# W07 Kết quả kiểm thử tích hợp (bản nháp chạy thử)

**Người phụ trách:** Hoài Thương · [Issue #60](https://github.com/csc10014-team01/adaptive-learning/issues/60)
**Ngày chạy:** 20/11/2026
**Trạng thái:** Bản nháp. Đã chạy phần sinh và duyệt đề ở chế độ giả lập, qua API và qua giao diện (Hoài Thương chạy tay). Phần chấm AI chưa chạy được vì chưa có API.

## 1. Cấu hình chạy

| Mục | Giá trị |
|---|---|
| Bản tích hợp | `main`, commit `bb8bf08` (sau PR #66, 20/11 10:30) |
| Chế độ sinh đề | **Giả lập** (`backend="fake"`, `profile_source="m3"`), không gọi Qwen |
| Cách chạy | Gọi API qua `TestClient` trong tiến trình, cùng `create_app` mà `python -m src.ui --fake` dùng. Giao diện trình duyệt do Hoài Thương chạy tay, xem mục 2b. |
| Indirect | `KORO_EXPERIMENTAL_INDIRECT=1` (mặc định của launcher) |
| Chế độ chấm bài | Chưa có. `main` không có endpoint nộp bài hay chấm bài |
| Môi trường | Python 3.13, FastAPI, môi trường sạch cài từ `requirements.txt` |
| Test của repo | Máy Hoài Thương (Windows, `.venv`, 20/11): `589 passed, 1 skipped, 1 warning in 52.31s` (`pytest -q`). Cảnh báo là `StarletteDeprecationWarning` về `httpx` trong `fastapi.testclient`, không ảnh hưởng kết quả. Môi trường thử cũng chạy 590 test đạt. Commit trên máy Hoài Thương: `bb8bf08`, trùng bản tích hợp ở dòng trên |

Đây là lần chạy trong môi trường thử, chỉ có giá trị tham khảo. Giao diện và pytest đã chạy lại trên máy Hoài Thương. Phần API giả lập qua TestClient vẫn do môi trường thử chạy.

## 2. Kết quả các ca đã chạy

| Ca | Kết quả | Quan sát |
|---|---|---|
| TC-W07-001 | Đạt | Đề default cho ST001 có 4 câu, trạng thái chờ giáo viên duyệt, revision 1 |
| TC-W07-003 | Đạt | ST001 và ST002 nhận đề riêng, `exam_id` khác nhau |
| TC-W07-004 | Đạt | Sinh lại một câu: revision 1 → 2, chỉ một câu bị thay, các câu khác giữ nguyên. **Câu sinh lại đổi sang ID mới** (`FQ_…` → `QT_…`) |
| TC-W07-005 | Đạt | Sinh lại 3 lần liên tiếp: revision 1, 2, 3, 4 |
| TC-W07-006 | Đạt | Duyệt revision 4 → trạng thái đã duyệt, revision 5. Nội dung đọc lại khớp bản đã duyệt |
| TC-W07-007 | Đạt | Duyệt bằng revision cũ → 409 `EXAM_REVISION_CONFLICT`. Đề không đổi trạng thái |
| TC-W07-010 | Đạt | Đề default (4 câu) và adaptive (6 câu) đều có câu hỏi, đáp án, lời giải, barem |
| TC-W07-037 | Một phần | Báo cáo chất lượng có trong phản hồi giáo viên (NEEDS_REVIEW, C1–C4). Chưa kiểm tra bản học sinh và giao diện |
| TC-W07-038 | Đạt | Đề default: tối đa C1/C2/C3 = 45/35/20, C4 không áp dụng. Gửi điểm C4 → 422 |
| TC-W07-039 | Đạt | Đề adaptive: tối đa 35/25/20/20. Chỉ gửi C1, C2 → tổng để trống, báo cáo vẫn NEEDS_REVIEW |
| TC-W07-040 | Đạt | Duyệt đề NEEDS_REVIEW được; báo cáo vẫn NEEDS_REVIEW, tổng để trống |
| TC-W07-041 | Đạt | Gửi đủ C1–C4 (30/20/15/15): tổng 80, báo cáo PASS, đề đã duyệt. Đọc lại vẫn giữ kết quả |
| TC-W07-042 | Đạt | Fingerprint sai, điểm vượt mức, tiêu chí trùng đều bị từ chối (422). Đề không được duyệt, không lưu đánh giá |
| TC-W07-044 | Đạt | Sinh lại sau khi có đánh giá: điểm thủ công cũ bị xóa, báo cáo mới gắn revision mới |
| TC-W07-045 | Đạt | 20 học sinh, đề adaptive 6 câu: số câu thực tế khớp kế hoạch mức độ khó ở cả 20 đề (lệch 0%) |

## 2b. Kết quả chạy tay trên giao diện (`python -m src.ui --fake`, 20/11)

Đề `FE_a17ffe576dd543fd9e638e7299f94850`, ST009, 5 câu, 30 phút.

| Ca | Kết quả | Quan sát |
|---|---|---|
| TC-W07-001, 010 | Đạt | Sinh đề, chờ duyệt, 5/5 câu đủ câu hỏi, đáp án, lời giải, barem |
| TC-W07-002 | Chưa chấm | Đáp án 5/5 câu đúng, câu 3 sinh lại n=7, 3, 12 đều đúng. Chưa chấm 0-4 |
| TC-W07-004, 005 | Đạt | Mỗi lần sinh lại chỉ đổi câu 3, phiên bản tăng 1. Log server có 6 yêu cầu regenerate cho đề này, 1 + 6 + 1 lần duyệt = phiên bản 8, bộ đếm đúng. Một lần sinh lại cho ra lại đúng n=8 |
| TC-W07-007 | Đạt | Tab cũ (phiên bản 6) báo "Phiên bản đã cũ", khóa nút duyệt khi tab khác đã sinh lại (7). Đề vẫn chờ duyệt. Log server có `POST …/approve 409 Conflict` ở tab cũ, rồi `approve 200 OK` ở bản mới nhất |
| TC-W07-006, 040 | Đạt | Duyệt ở phiên bản 7 → "Giáo viên đã duyệt đề", phiên bản 8, báo cáo vẫn "Cần giáo viên đánh giá", không tổng điểm. Chưa đối chiếu lại từng câu sau duyệt |
| TC-W07-037 | Một phần | Báo cáo hiển thị đủ C1-C4 ở giao diện giáo viên. Bản học sinh chưa kiểm tra |
| TC-W07-047 | Một phần | Lời giải hiện ký hiệu thô `A_5^3`, `n^2` |

Phát hiện thêm từ giao diện:
- Lưu ý hệ thống trong báo cáo chất lượng viết bằng tiếng Anh. Cảnh báo "Legacy bank prose has no supported mathematical specification" lặp 4 lần, không nêu câu nào. Danh sách kỹ năng hiện dạng thô, lỗi "1 tests".
- Mở đề bằng "Mở đề đã lưu" không đồng bộ ô học sinh và hồ sơ bên trái: đề ST009 nhưng hồ sơ hiện ST001.
- Giao diện chưa có chỗ nhập điểm C1-C4, các ca chấm chất lượng (039, 041, 042, 044) chỉ làm được qua API.
- Lời giải câu 3 luôn có câu thừa "Với n = 0, quy ước 0! = 1". Barem câu từ ngân hàng chỉ 1 bước.
- "Tạo lại câu này" có thể cho ra đúng câu cũ (n=8 hai lần liên tiếp) nhưng phiên bản vẫn tăng. Giáo viên có thể tưởng câu đã đổi.
- Token giao diện chỉ nằm trong bộ nhớ tab. Tải lại trang là mất kết nối, tab mới phải nhập token.

## 2c. Đối chiếu EA0004 và lỗi sinh từ 30 đề Qwen thật có sẵn (nhóm chạy 14/11)

Đây là kết quả của nhóm, chạy ngày 14/11 với `qwen3:1.7b` qua Ollama 0.40.16 (Q4_K_M), không phải lần chạy mới của Hoài Thương. Hoài Thương chỉ đối chiếu kết quả. Chấm người của bộ này vẫn ở trạng thái PENDING, đánh giá chính thức làm ở W09.

| Chỉ số | Giá trị |
|---|---|
| Số ca | 30 (15 cặp strict và experimental), 30/30 ra đề hoàn chỉnh |
| Gọi Qwen | 102 lần: 73 đạt, 11 cần xem lại, 18 bị loại, 0 lỗi kết nối |
| Thời gian | Khoảng 357 giây cho 30 đề (khoảng 12 giây mỗi đề) |
| Đề có EA0004 | 24/30 (12 strict, 12 experimental) |
| EA0004 trong đề cuối | 24/24 là câu Direct, đáp án đúng (n=9 → 72, n=3 → 6), strict và experimental giống hệt nhau |
| EA0004 Indirect | Chỉ thử ở 3/12 đề experimental (C04, C14, C24), mỗi đề 2 lần. Cả 6 lần bị loại: 4 lần sao chép câu Direct, 2 lần đổi hoặc thiếu số liệu. Sau đó quay về Direct |
| EA0004 đổi nghĩa lọt vào đề cuối | Không có |

Ý nghĩa cho TC-W07-012, 013:
- Với EA0004, bật hay tắt Indirect không làm đề cuối khác nhau. Bật Indirect chỉ thêm các lần gọi Qwen bị loại. Có thể báo Nghi chọn cấu hình strict cho demo nếu cần ổn định.
- Hệ thống chỉ kiểm số liệu và cấu trúc, không kiểm tương đương ngữ nghĩa. Cảnh báo này nằm sẵn trong báo cáo ("semantic and cognitive equivalence are NOT verified"), nên một câu Indirect đổi nghĩa mà giữ số liệu vẫn có thể lọt qua. Ca EA0004 bị loại ở lần này là nhờ kiểm số liệu và kiểm sao chép.
- Các mẫu khác bị loại nhiều hơn: EA0013 4/10, EA0012 3/15, EA0018 3/15, EA0017 2/20 (đều ở Indirect).

## 3. Ca chưa chạy và lý do

| Ca | Lý do |
|---|---|
| TC-W07-002 | Cần người đối chiếu đáp án và lời giải rồi chấm 0–4 theo rubric. Bộ sinh giả lập dùng câu có sẵn trong ngân hàng nên không thay cho kết quả Qwen thật |
| TC-W07-008, 043 | Chưa có cách gây lỗi sinh đề hoặc đề lỗi ở chế độ giả lập. TC-W07-009 chỉ có bằng chứng gián tiếp từ log 14/11 (mục 2c) |
| TC-W07-011 | Chặn: máy Hoài Thương chưa cài Ollama (tiêu chí 1 chỉ yêu cầu "nếu có Ollama"). Đã đối chiếu kết quả có sẵn 14/11 (mục 2c) |
| TC-W07-012, 013 | Đối chiếu từ kết quả có sẵn 14/11 (mục 2c), chưa tự chạy Qwen |
| TC-W07-014 | Chờ có kết quả Qwen thật để tách hai bảng |
| TC-W07-046 | Báo cáo tự động chỉ ghi "cần giáo viên đánh giá" cho C3, chưa có cảnh báo trùng lặp để đối chiếu. Cần người đọc toàn đề |
| TC-W07-047 | Cần mở giao diện trình duyệt để xem công thức |
| TC-W07-015 đến 036 | Chưa có API nộp bài và chấm bài |

## 4. Phát hiện cần báo nhóm

1. **Mã câu của bài nộp mẫu không trùng mã câu của đề sinh ra.** Bài mẫu dùng `QA0007`, `QA0038`, `QA0064`, `QA0102`, trong khi đề sinh ra dùng `question_id` dạng `FQ_…` (mã `QAxxxx` nằm ở `source_ref.id`). Trong 20 học sinh x 2 chế độ x đề 10 câu, bốn mã này không xuất hiện trong đề nào. Cả bốn có trong ngân hàng câu hỏi, nên cần dựng đề demo có đúng các câu này, hoặc quy định cách gắn bài mẫu với đề đã duyệt. Việc này ảnh hưởng GRD-01 và kịch bản demo bước 3. Người nên xử lý: Khánh Như và Ánh Dương.
2. **Sinh lại câu đổi ID câu.** Câu sinh lại nhận `question_id` mới. Bài nộp phải gắn theo đề đã duyệt cuối cùng, không dùng ID cũ.
3. **Sinh lại sau khi đã duyệt trả đề về trạng thái chờ duyệt** (revision tăng, đánh giá thủ công bị xóa, API trả 200). Có thể là chủ đích, nhưng giáo viên có thể mất bản đã duyệt mà không bị cảnh báo. Cần nhóm xác nhận.
4. **Gửi `quality_review` có tiêu chí trùng** trả mã `REQUEST_VALIDATION_ERROR`, khác mã `INVALID_QUALITY_REVIEW` của hai lỗi còn lại. Cả ba đều 422.
5. **Điểm PASS chỉ dựa vào phần bằng chứng giáo viên gửi.** Gửi điểm 30/20/15/15 kèm bằng chứng ngắn vẫn được PASS với tổng 80. Quality Gate cũng ghi hệ thống tin người dùng đã xác thực.

## 5. Lỗi chặn demo

- Không có API nộp bài và chấm bài trên `main` (chặn toàn bộ GRD-01 đến GRD-04 và demo bước 3, 4).
- `answer_grading.py` chỉ nằm ở nhánh `w07_grading`, chưa merge.
- Chưa có contract API, kết quả kiểm tra Indirect và tài liệu giao diện W07.
- Giao diện mới của Chi Mai ở nhánh `try-mapping-ui`, chưa merge, nên chưa kiểm tra giao diện.

## 6. Việc chuyển W08

[Người phụ trách và mốc cho chấm tay, chốt toàn bài và cập nhật hồ sơ PCM/EAP: chờ Nghi xác nhận]
