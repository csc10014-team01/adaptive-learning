# Tích hợp Finalized Exam Generator vào repo nhóm

## Nguồn và baseline

- Target: `MIRA/adaptive-learning`, nhánh `main`, HEAD ban đầu `38cc46371a50069ba7bf33885d104bd79baa61e3`; working tree và index sạch.
- Source chỉ đọc: `MVP1/adaptive-learning`, HEAD `ad5ca7c`. Đã xác minh HEAD này có cùng tracked tree với `1a7147cd4671b42507ac5c5d6a3f525262eb903d`, tree `8256cc3ef8f2386c09b74ee905d910159df8f121`. Chọn nguồn sau khi kiểm tra lịch sử/recovery, không mặc định coi commit lịch sử là bản cuối.
- Đọc code bằng `git show` từ commit nguồn. Không sửa source cũ và không copy SQLite từ source.
- Baseline target: **88 passed, 1 warning**; Ruff **13 lỗi lint**, **11 file cần format**.
- Hash 69 file ban đầu: [integration_baseline.json](integration_baseline.json). Provenance từng module: [generator_source_manifest.json](generator_source_manifest.json).

## Mapping và bốn bất tương thích

| Yêu cầu finalized | Target trước tích hợp | Thay đổi | Ảnh hưởng / regression |
| --- | --- | --- | --- |
| Planner xử lý NO_DATA/PARTIAL theo từng skill | API chặn adaptive nếu root evidence < 3 | Bỏ gate trên nhánh adaptive trong `src/api/main.py`; gọi core qua `adaptive_generator.py` | Không đổi quy tắc Focus/Review. Test e0/e1/e2 và profile SQL hỗn hợp |
| Planner sở hữu adaptive blueprint | API so mọi đề với distribution trong request | Adaptive bỏ/null distribution; độc lập dựng allocation và kiểm tra requested/achieved summary, classification, nguồn thật | Non-adaptive vẫn dùng distribution cũ. Test provider giả mạo quota/answer và preview/generate |
| No evidence → nullable mastery | Schema chỉ nhận số | `SkillMastery` chuẩn hóa e0 thành null; positive evidence thiếu score là lỗi, 0.0 có evidence được giữ | SQL read-only, đủ chín skill ở response, không INSERT hoặc ước lượng |
| Review, approval, regeneration, provenance | Pending-only, không revision/proof | Bổ sung DTO lifecycle/proof, ba endpoint và CAS store; UI đã có của Generator được đưa vào file mới | Teacher token/CORS/no-store/error boundary giữ nguyên; duyệt thủ công toàn đề, Question Bank bất biến |

Core đặt riêng tại `src/exam_generator/`; không thay các module knowledge, script Data Lead hoặc `src/ai/qwen_spike.py` của nhóm. Public DTO vẫn dùng `student_name`; adapter chuyển sang `name` nội bộ. JSON legacy giữ root evidence/status và các consistency checks; SQL không có aggregate đó nên hai trường root là null, bằng chứng thật vẫn nằm ở từng skill. UI hiển thị null mastery là `--/4`.

Nhánh `default_blueprint` giữ assembler fake cũ, manual difficulty và scoring 10 điểm. Default API fake/JSON của nhóm được giữ; luồng Generator có launcher SQL/Qwen tường minh. Không có SQL-missing → JSON fallback. Những test cũ phản đối adaptive e0/e1/e2 được đổi sang kiểm tra diagnostic; manual adaptive distribution trong helper được bỏ; OpenAPI được cập nhật từ 5 lên 8 endpoint. Các assertion về bảo mật, isolation, scoring, source, lỗi và non-adaptive được giữ.

## File có sẵn đã sửa

| File | Lý do |
| --- | --- |
| `src/api/main.py` | Nối adapter/service, bỏ gate xung đột, validation adaptive, review/preview/regenerate, cấu hình backend/store và UI |
| `src/api/schemas.py` | Nullable mastery, optional root SQL metadata, lifecycle/provenance; giữ field tên học sinh và scoring |
| `src/api/data_adapter.py` | Chiếu learning history JSON để Planner dùng, không suy diễn evidence |
| `src/api/services.py` | Fake adaptive delegate sang finalized core; thêm CAS replace cho memory store; nhánh non-adaptive giữ nguyên |
| `tests/integration/test_fake_api.py` | Cập nhật đúng các giả định adaptive/OpenAPI đã lỗi thời và giữ input-mutation assertion khi distribution nullable |
| `.env.example` | Tài liệu biến môi trường của tích hợp, không có secret thật |
| `.gitignore` | Bỏ qua runtime drafts và pytest scratch mới |
| `README.md` | Cách gọi workflow, nguồn SQL, auth và hạn chế |

Chỉ format các file đã sửa/thêm; không format toàn repository.

## Kích hoạt và dữ liệu

Từ target với dependencies đã cài:

```powershell
python -m src.ui
python -m src.ui --fake
```

Launcher thứ nhất dùng SQL + Ollama/Qwen3; thứ hai dùng SQL + fake assembly, không inference. Launcher bật experimental Indirect bằng `setdefault`; `KORO_EXPERIMENTAL_INDIRECT=0` giữ strict verified-only. Plain API vẫn cần opt-in `EXAM_BACKEND=qwen`, `PROFILE_SOURCE=m3` và teacher token; `.env` không tự được load.

Default SQL nằm trong target: `data/sample/dataset/question_bank.db` và `data/sample/memory/student_profiles_sample.db`. Cả hai đã được track, có trong checkout CI; catalogue A001–A009, 121 Questions, 18 Templates. Các template không thực thi được tiếp tục theo fallback/warnings hiện có, không sửa database để ép coverage. Không phụ thuộc checkout `pre-work` bên cạnh. `EXAM_DB` riêng tại `data/runtime/exams.db`, không được trỏ vào hai canonical DB. Cấu hình quan hệ kỹ năng vẫn opt-in qua `SKILL_RELATIONSHIPS_FILE` như nguồn finalized.

## Kiểm chứng hành vi

- **30 module core**: kiểm tra AST và import bindings so với `git show` của commit nguồn, chỉ quy đổi namespace, ba root path và import/format layout.
- **48 đối chiếu source/reference**: NO_DATA, PARTIAL, mixed, một WEAK, hai WEAK, toàn ACHIEVED × N=1/4/7/10 × relationships off/on, seed 42. So cả plan và generated fake exam, bao gồm source, parameters, answer/solution/scoring; chỉ bỏ UUID exam/question vì chúng vốn ngẫu nhiên. Kết quả ở [integration_reference_comparison.json](integration_reference_comparison.json).
- Có thể tái lập: `python tools/compare_finalized_generator.py --source <old-repository>`; script chỉ đọc commit, không sửa repo nguồn hoặc database. CI không cần repo nguồn để chạy pytest.
- SQL-to-API kiểm tra bằng query SQLite độc lập, không hardcode mastery của Data Lead; fixture diagnostic dùng in-memory profile hoặc SQLite tạm, không thay ST011 thật.
- Mock Qwen kiểm tra Template-only calls, experimental metadata, answer/solution do backend, safe fallback, regenerate đổi instance/type, thất bại không persist, revision conflict, whole-exam approval không cần từng checkbox, và source/proof tampering bị chặn.
- Các test core giữ Focus/Review/difficulty, Template-first L1/L2, Question-only L3/L4, immutable Questions, verified registry và các numeric/constraint safeguards sẵn có.

## Kết quả kiểm tra

- Full pytest: **519 passed, 1 skipped, 1 warning**. Skip là wrapper tìm `node` trên PATH; warning Starlette/httpx đã có ở baseline.
- JavaScript chạy riêng bằng Node runtime khả dụng qua tool: **18/18 pass**, thực thi `app.js` thật với DOM/HTTP mock. Không phải browser E2E hoặc xác minh hình ảnh UI.
- Ruff phần tích hợp: lint pass, **69 file được check format đều pass**.
- Ruff toàn repo: còn **8 lỗi lint có sẵn** tại `data/sample/dataset/get_database.py`, `data/sample/memory/get_student_profiles.py`, `src/ai/qwen_spike.py`.
- Format toàn repo: còn **6 file baseline**: hai script Data Lead trên, `data/sample/memory/USAGE.md`, `src/ai/qwen_spike.py`, `src/knowledge/loader.py`, `src/knowledge/validator.py`. Không sửa ngoài phạm vi để làm xanh kết quả.
- `git diff --check`: pass. Không có staged changes hoặc history changes.
- Workflow GitHub hiện tại chạy `pytest -q`, không có Ruff step. Dependencies hiện có đủ cho các module mới; không thêm API/dependency ngoài. Chưa chạy job Linux trên GitHub thực tế.
- Verification dùng `.venv` đã có ở source cũ để đọc dependency, với `-B`; target mới chưa có `.venv`. Không sửa source/environment để chạy kiểm tra.

Suppression hẹp: giữ exception boundary có chủ ý (`BLE001` ở middleware); hai public compatibility re-export (`PLC0414`); trusted-commit in-memory execution trong tool đối chiếu (`S102`). Không tắt rule toàn cục.

## Ollama thật và giới hạn

Ollama local có `qwen3:1.7b`. Đã sinh **1 Direct + 2 experimental Indirect** từ instance EA0004 do backend tạo, không lưu đề hoặc thay canonical data. Cả ba qua safeguards hiện tại; Direct pass, hai Indirect `needs_review`, provenance `experimental`. Raw result ở [integration_local_qwen_smoke.json](integration_local_qwen_smoke.json).

**Không coi đây là chứng minh chất lượng ngữ nghĩa:** hai Indirect thực tế trùng wording dù chọn context khác; câu hỏi đổi sang “ít nhất bao nhiêu cuốn sách” không diễn đạt đúng rõ ràng bài toán đếm cặp ban đầu. Safeguards cơ bản vẫn chấp nhận, đúng với giới hạn experimental hiện hữu. Vì nhiệm vụ yêu cầu giữ prompt/policy finalized, không sửa generation strategy để che kết quả này. Backend answer/solution không bị Qwen ghi đè; giáo viên vẫn phải xem và chủ động duyệt. Chưa chứng minh semantic/cognitive equivalence, độ đa dạng ổn định, hay chất lượng một đề Qwen đầy đủ trong browser. Không triển khai Validator sáu lớp hoặc grading.

Tất cả SQLite và 61 file baseline còn lại giữ nguyên byte/hash. Không xóa file, không stage, commit, push, merge, reset hoặc thay lịch sử. Source repo cũ giữ sạch. Tích hợp có thể gọi qua UI/API hiện có; giới hạn còn lại là Ruff baseline và chất lượng diễn đạt experimental nêu trên.

## Danh sách toàn bộ file mới

Danh sách bên dưới được lập từ `git ls-files --others --exclude-standard`; không bao gồm runtime/cache bị ignore.

- `config/skill_relationships_a001_a009.json`
- `config/template_presentations.json`
- `docs/report/finalized_generator_integration.md`
- `docs/report/generator_source_manifest.json`
- `docs/report/integration_baseline.json`
- `docs/report/integration_local_qwen_smoke.json`
- `docs/report/integration_reference_comparison.json`
- `src/api/adaptive_generator.py`
- `src/api/exam_store.py`
- `src/exam_generator/__init__.py`
- `src/exam_generator/adaptation/__init__.py`
- `src/exam_generator/adaptation/contracts.py`
- `src/exam_generator/adaptation/difficulty_allocator.py`
- `src/exam_generator/adaptation/min_cost_flow.py`
- `src/exam_generator/adaptation/planner.py`
- `src/exam_generator/adaptation/policy.py`
- `src/exam_generator/adaptation/question_selector.py`
- `src/exam_generator/adaptation/selection_diagnostics.py`
- `src/exam_generator/adaptation/skill_relationships.py`
- `src/exam_generator/adaptation/source_selector.py`
- `src/exam_generator/ai/__init__.py`
- `src/exam_generator/ai/contracts.py`
- `src/exam_generator/ai/expression_planner.py`
- `src/exam_generator/ai/problem_spec.py`
- `src/exam_generator/ai/prompts.py`
- `src/exam_generator/ai/qwen_client.py`
- `src/exam_generator/ai/template_instantiator.py`
- `src/exam_generator/ai/template_presentations.py`
- `src/exam_generator/api/__init__.py`
- `src/exam_generator/api/data_adapter.py`
- `src/exam_generator/api/m3_adapter.py`
- `src/exam_generator/api/question_repository.py`
- `src/exam_generator/api/real_generator.py`
- `src/exam_generator/api/schemas.py`
- `src/exam_generator/api/services.py`
- `src/exam_generator/api/template_repository.py`
- `src/exam_generator/orchestration/__init__.py`
- `src/exam_generator/orchestration/exam_assembler.py`
- `src/exam_generator/orchestration/exam_service.py`
- `src/exam_generator/orchestration/question_generation.py`
- `src/exam_generator/orchestration/review_service.py`
- `src/exam_generator/orchestration/source_snapshot.py`
- `src/exam_generator/validation/__init__.py`
- `src/exam_generator/validation/math_validator.py`
- `src/exam_generator/validation/question_validator.py`
- `src/ui/__main__.py`
- `src/ui/routes.py`
- `src/ui/static/app.js`
- `src/ui/static/index.html`
- `src/ui/static/style.css`
- `tests/generator/__init__.py`
- `tests/generator/api_helpers.py`
- `tests/generator/doubles.py`
- `tests/generator/fixtures/missing_mastery_profile.json`
- `tests/generator/fixtures/nine_skill_relationships.json`
- `tests/generator/fixtures/structured_problem.json`
- `tests/generator/test_api_boundary.py`
- `tests/generator/test_indirect_api.py`
- `tests/generator/test_sql_boundary.py`
- `tests/generator/test_teacher_javascript.py`
- `tests/generator/test_teacher_routes.py`
- `tests/generator/unit/__init__.py`
- `tests/generator/unit/test_automatic_difficulty.py`
- `tests/generator/unit/test_coordinated_difficulty.py`
- `tests/generator/unit/test_diagnostic_quotas.py`
- `tests/generator/unit/test_exam_assembly.py`
- `tests/generator/unit/test_experimental_indirect.py`
- `tests/generator/unit/test_hybrid_sources.py`
- `tests/generator/unit/test_mastery_2of4_policy.py`
- `tests/generator/unit/test_modular_pipeline.py`
- `tests/generator/unit/test_planner.py`
- `tests/generator/unit/test_skill_relationship_policy.py`
- `tests/generator/unit/test_structured_problems.py`
- `tests/generator/unit/test_template_presentations.py`
- `tests/ui/teacher_review.test.cjs`
- `tools/compare_finalized_generator.py`
