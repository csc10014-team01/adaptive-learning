[Đã xong] Chẩn đoán và sửa triệt để vấn đề 3 màn Figma không hiển thị:
  1. Link "Xem hồ sơ chi tiết" nay tự cập nhật href (#/students/{id}) ngay sau khi connect và khi đổi học sinh.
  2. Skeleton màn 1 (Hồ sơ) nay tắt đúng khi lỗi tải (setLoading false trong catch).
  3. Link được nâng cấp thành button nổi bật .open-profile-link với CSS hover, disabled state đúng.
  4. pytest -q: 258 passed (100%), không break gì. Branch: try-mapping-ui.

[Đang làm dở] Không có phần nào làm dở. 3 màn Figma (#/students/{id} → generate → exams/{examId}) hoạt động đầy đủ.
  Màn 2: đổi số câu/thời gian → plan tự refresh (debounce 400ms), giữ config khi lỗi/thử lại ✓
  Màn 3: câu hỏi đầy đủ, điểm từng câu, Tạo lại (giữ config cũ), Chỉnh sửa cấu hình, Lưu bản nháp (kèm mã đề), Giao đề disabled ✓

[Việc tiếp theo] Kiểm thử thủ công trình duyệt: chạy `python -m src.ui --fake --port 8001`, mở browser, kết nối,
  chọn học sinh → click "Xem hồ sơ chi tiết (3 màn)" → xác nhận đủ 3 màn.
  Các học sinh demo: DEMO_SUFFICIENT_001 (đủ), DEMO_WEAK_001 (yếu), DEMO_EMPTY_001 (chưa có).
