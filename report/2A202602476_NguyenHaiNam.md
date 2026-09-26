# Member Role Report — Day 10: Data Pipeline & Data Observability

## 1. Thông tin cá nhân

| Thông tin         | Nội dung                  |
| ------------------ | -------------------------- |
| Họ và tên       | Nguyễn Hải Nam |
| MSSV               | 2A202602476 |
| Khóa/Lớp         | K4 / L3B|
| Tên nhóm         | Dangcaps |
| Vai trò chính    | Trưởng nhóm — Corruption & Integration Owner (P4) |
| Repository         | https://github.com/namhaing/K4-L3B-Day10-Dangcaps-Data-Pipeline-Data-Observability |
| Ngày hoàn thành | 2026-09-26 |

## 2. Vai trò và phạm vi công việc

### Phần việc sở hữu

| Module/deliverable | File/hàm phụ trách | Input nhận vào | Output bàn giao  | Trạng thái |
| ------------------ | --------------------- | ---------------- | ----------------- | ---------- |
| Corruption suite | `src/ingestion/corruption.py` — `corrupt_clean_dataframe` | Clean dataframe (schema theo Data Contract) | Dataframe bị tiêm 6 lỗi + `data/results/corruption_log.json` | Code xong, đã test bằng dữ liệu tạm; chờ chạy với dữ liệu thật |
| Baseline orchestration | `src/pipelines/phase1.py` — `main`, `save_clean_artifacts` | Hàm của P1 (ingestion), P2 (cleaning, test set), P3 (quality, report) | `papers_clean.*`, collection `papers-baseline`, `baseline_metrics.json`, `phase1_report.md` | Code xong; chờ P1/P2/P3 để chạy thật |
| Corruption → Repair flow | `src/pipelines/corruption_flow.py` — `main` | Artifact của phase 1 + raw snapshot | `corrupted_metrics.json`, `repaired_metrics.json`, `corruption_report.md`, bảng 3 trạng thái trên console | Code xong; chờ chạy thật |
| Bonus B2 — Self-healing | `src/pipelines/corruption_flow.py` | Kết quả Quality Gate | Tự kích hoạt repair khi gate fail, chặn publish nếu repair vẫn fail, `data/results/self_healing_log.json` | Code xong; chờ chạy thật |
| Multi-provider alias | `src/core/config.py` — `normalized_provider` | Biến `LLM_PROVIDER` | Chấp nhận `google` như `gemini` | Hoàn thành |
| Bonus B1 — Dashboard demo | `script/demo_dashboard.py` (Streamlit) | Artifact trong `data/` + 3 collection ChromaDB | 9 tab theo checkpoint: trạng thái CP0–CP5, bảng expectation 3 trạng thái, histogram `age_days` với ngưỡng 180 ngày, bảng ảnh hưởng từng câu, biểu đồ so sánh 3 trạng thái, hỏi thử cùng câu trên 3 collection, checklist nộp bài; nút chạy pipeline thật | Hoàn thành (smoke test headless: không lỗi) |

### Việc hỗ trợ ngoài phạm vi chính

| Hoạt động | Thành viên/module được hỗ trợ | Kết quả |
| --------- | ----------------------------- | ------- |
| Chốt Data Contract (raw schema, clean schema, test set, quality result, đường dẫn artifact) | Cả nhóm | `docs/PHAN_CONG.md` mục 1.2 |
| Phân công và timeline theo checkpoint | Cả nhóm | `docs/PHAN_CONG.md` |
| Phát hiện lỗi in tiếng Việt trên Git Bash và cách khắc phục | Cả nhóm (mọi lệnh "Tín hiệu hoàn thành") | Ghi chú trong checklist; xem Mục 6 |
| Review tích hợp `crossref.py` (P1): parse/load offline khớp 100% snapshot 24 bài; phát hiện `fetch_source_records` bỏ qua `REFRESH_SOURCE` (luôn gọi API live, ghi đè snapshot) và đường dẫn fallback tương đối | P1 — `src/ingestion/crossref.py` | Tự sửa (integration fix, đã báo P1): đọc snapshot khi `REFRESH_SOURCE` tắt, fallback dùng `settings.paths.raw_records_json`. Kiểm tra offline có chặn mạng: 24 bài, `crossref_records.json` không đổi |
| Tách hàm `build_text_for_embedding(row)` theo Data Contract | Cleaning — `src/ingestion/cleaning.py` | Integration fix; `text_for_embedding` giữ nguyên công thức. Phase 1 và corruption flow chạy exit 0 với code thật của crossref + cleaning (quality/report/test set vẫn là stub) |
| Review tích hợp `quality.py` + `reporting.py` (P3): chạy `script/check_observability.py` pass; chạy phase 1 + corruption flow với code thật P1/cleaning/P3 (chỉ test set là stub): exit 0, gate baseline PASS / corrupted FAIL / repaired PASS, sinh đủ 3 GX suite | P3 — `src/observability/` | Chỉnh `corruption_flow._gate` dùng `quality["freshness"]` của P3 thay vì tính lại |
| Merge + review `cleaning.py` + `testset.py` (P2, nhánh `anh02573`): giải quyết conflict cleaning bằng bản của P2 (có sẵn `build_text_for_embedding` đúng format). Kiểm tra: clean 24 dòng, không NaN/trùng id; test set 10 câu (3/3/2/2), chạy lại giống hệt, có bài mới nhất + bài Advanced | P2 — `cleaning.py`, `testset.py` | Không cần sửa code P4 |

## 3. Kết quả theo vai trò

| Nhiệm vụ đã thực hiện | File/hàm/artifact liên quan | Kết quả bàn giao | Cách xác minh |
| --------------------- | --------------------------- | ---------------- | ------------- |
| Tiêm 6 loại lỗi có kiểm soát (seed 42), ghi log chi tiết từng lỗi | `src/ingestion/corruption.py` | 24 dòng → 22 dòng; log đủ 6 mục, mỗi mục có `affected_paper_ids` | Đọc `corruption_log.json`; kiểm tra dữ liệu bẩn có `paper_id` trùng, title < 8 ký tự, stale_ratio > 25%, không có NaN |
| Nối pipeline baseline 7 bước | `src/pipelines/phase1.py` | Toàn bộ artifact phase 1 | `uv run python script/run_phase1.py` |
| Nối flow corrupted → repair → so sánh | `src/pipelines/corruption_flow.py` | 3 file metrics + report + bảng console | `uv run python script/run_corruption_flow.py` |
| Self-healing (B2) | `src/pipelines/corruption_flow.py` | `self_healing_log.json`: gate FAIL → repair → gate PASS | Đọc log sau khi chạy flow |

Output cụ thể phần việc của tôi tạo ra:

Bảng so sánh 3 trạng thái trong `data/reports/corruption_report.md` (lần chạy 26/09 11:49): retrieval hit rate 1.000 → 0.700 → 1.000, judge accuracy 1.000 → 0.600 → 1.000; Quality Gate PASS → FAIL → PASS. `self_healing_log.json` ghi lại chuỗi gate FAIL → auto repair → gate PASS.

## 4. Giải thích phần kỹ thuật đã thực hiện

### Vấn đề cần giải quyết

Khi dữ liệu nạp vào RAG bị hỏng, pipeline **vẫn chạy bình thường** (exit code 0) nhưng câu trả lời sai: đây là *silent failure*. Phần của tôi phải (1) tái hiện có kiểm soát các sự cố dữ liệu thường gặp, (2) đo được mức thiệt hại lên RAG, (3) chứng minh Quality Gate phát hiện được và pipeline tự phục hồi về đúng trạng thái ban đầu. Ngoài ra, với vai trò tích hợp, tôi nối các module của cả nhóm thành 2 lệnh chạy end-to-end.

### Cách triển khai

**Corruption (`corruption.py`)**: làm trên bản sao của dataframe, dùng `random.Random(42)` để mọi lần chạy chọn đúng các dòng giống nhau:

1. `drop_latest`: bỏ 20% bài có `published` mới nhất (giả lập batch ingestion bị thiếu).
2. Ba lỗi nội dung đánh vào **3 nhóm dòng không trùng nhau**, để tác động của mỗi lỗi truy vết được riêng:
   - `blank_summary`: `summary = ""`. Dùng chuỗi rỗng, không dùng `None`, vì ChromaDB metadata không nhận null.
   - `inject_noise`: chèn token rác ở đầu và sau mỗi 4 từ. Summary vẫn dài nên kiểm tra độ dài không bắt được: đây là silent failure điển hình.
   - `truncate_title`: cắt title còn 6 ký tự, dưới ngưỡng 8 của GX, và làm hỏng việc tra đúng bài theo title trong `qa.py`.
3. `stale_date`: lùi ngày xuất bản 400 ngày ở 35% số dòng rồi cộng lại `age_days`. Tỷ lệ 35% được chọn để **vượt ngưỡng 25%** của Freshness SLA.
4. `duplicate_rows`: nhân bản 3 dòng, phá tính unique của `paper_id` và chiếm chỗ trong top-k.
5. Tính lại `summary_chars` và `text_for_embedding` (dùng chung hàm `build_text_for_embedding` với cleaning), để index embed đúng nội dung đã bị hỏng.

**Orchestration (`phase1.py`)**: fetch → clean → lưu CSV/JSON (`orient="records"`) → Quality Gate + freshness → build index `papers-baseline` → test set (tạo mới chỉ khi chưa có, để giữ cố định cho cả 3 trạng thái) → evaluate → report. Demo agent được bọc `try/except`, vì không có API key thì agent không chạy được nhưng không được làm hỏng pipeline.

**Corruption flow (`corruption_flow.py`)**:

- Corrupt → Quality Gate → vẫn index và evaluate dữ liệu bẩn, để **đo thiệt hại nếu không có gate**.
- Gate fail → **tự động repair**: dựng lại từ `crossref_records.json` bằng chính hàm cleaning.
- Chạy Quality Gate lần nữa. Nếu vẫn fail thì `SystemExit`, không publish vào index.
- Nếu pass thì index `papers-repaired`, evaluate, sinh report so sánh.

Cả 3 trạng thái dùng **cùng** `test_set.json` và 3 collection ChromaDB riêng.

### Input, output và contract

| Thành phần | Mô tả |
| ---------- | ----- |
| Input | Clean dataframe gồm 11 trường `PaperRecord` + `age_days`, `authors_joined`, `categories_joined`, `summary_chars`, `text_for_embedding`; raw snapshot `data/raw/crossref_records.json`; `data/eval/test_set.json` |
| Output | `corruption_log.json`, `papers_clean_{corrupted,repaired}.{csv,json}`, 3 collection ChromaDB, `{baseline,corrupted,repaired}_metrics.json`, `self_healing_log.json`, `phase1_report.md`, `corruption_report.md` |
| Module phụ thuộc | `ingestion/crossref.py` (P1), `ingestion/cleaning.py` + `evaluation/testset.py` (P2), `observability/quality.py` + `reporting.py` (P3), `retrieval/index.py`, `evaluation/metrics.py` (có sẵn) |
| Module sử dụng output | `observability/reporting.py` (đọc metrics/quality để viết report); demo và báo cáo nhóm |
| Điều kiện lỗi cần xử lý | Chưa có baseline khi chạy flow (dừng với thông báo rõ ràng); repair vẫn fail gate (dừng, không publish); không có API key (agent demo ghi lỗi, pipeline vẫn chạy); không để `None`/`NaN` lọt vào metadata ChromaDB |

### Cách xác minh

Trong lúc P1/P2/P3 chưa push code, tôi thay các hàm chưa có bằng hàm giả (stub) theo đúng Data Contract, chạy ở thư mục tạm để không ghi đè `data/` thật:

```bash
python harness.py phase1   # phase1.main với load_settings trỏ sang thư mục tạm
python harness.py flow     # corruption_flow.main, chạy 2 lần để so sánh
```

- **Kết quả mong đợi:** cả 2 flow exit 0; bản corrupted fail gate và điểm giảm; bản repaired pass gate và điểm bằng baseline; chạy flow 2 lần ra cùng số liệu.
- **Kết quả thực tế (với stub):** đạt cả 4 điều trên; `self_healing_log.json` ghi đúng chuỗi gate FAIL → repair → gate PASS. *Số liệu stub không dùng cho báo cáo.*
- **Kết quả thực tế (code thật, 26/09 11:48):** `python script/run_phase1.py` và `python script/run_corruption_flow.py` đều exit 0; gate baseline PASS, corrupted FAIL, repaired PASS; metrics repaired bằng baseline (xem Mục 8).
- **Artifact/log:** `data/results/{baseline,corrupted,repaired}_metrics.json`, `data/results/corruption_log.json`, `data/results/self_healing_log.json`, `data/quality/*_quality_report.json`, `data/reports/corruption_report.md`.

## 5. Một quyết định kỹ thuật quan trọng

- **Bối cảnh:** Sau khi phát hiện dữ liệu bẩn, cần chọn cách repair.
- **Các phương án đã cân nhắc:**
  1. Vá từng lỗi trên dữ liệu bẩn: xóa dòng trùng, khôi phục title/summary, sửa ngày.
  2. Bỏ toàn bộ dữ liệu bẩn, dựng lại từ raw snapshot bất biến bằng chính hàm cleaning của phase 1.
- **Phương án đã chọn:** Phương án 2.
- **Lý do:**
  - Vá từng lỗi đòi hỏi phải biết trước mọi loại lỗi. Lỗi như chèn nhiễu hay xóa bản ghi thì không thể vá từ dữ liệu đã hỏng.
  - Dựng lại từ raw đảm bảo **idempotent**: raw không đổi, `LocalEmbeddingIndex.build()` xóa collection cũ trước khi tạo lại (không còn ghost vectors), nên chạy N lần cho cùng kết quả.
  - Đây cũng là lý do phải lưu raw snapshot (data lineage).
- **Bằng chứng quyết định phù hợp:** Lần chạy thật cho `repaired_metrics.json` bằng đúng `baseline_metrics.json` (hit rate 1.000, token F1 1.000, judge accuracy 1.000, judge score 5.00), và `repaired_quality_report.json` pass 8/8. Trong đó có lỗi `inject_noise` mà không thể vá ngược từ dữ liệu bẩn. Tính idempotent đã kiểm chứng ở lần chạy thử: chạy flow 2 lần ra cùng số liệu.

## 6. Một lỗi hoặc blocker đã xử lý

- **Triệu chứng/lỗi nguyên văn:** `UnicodeEncodeError: 'charmap' codec can't encode characters in position 6-7: character maps to <undefined>`
- **Lệnh hoặc bước tái hiện:** Chạy trong Git Bash trên Windows: `uv run python -c "import chromadb, great_expectations, sentence_transformers; print('Môi trường sẵn sàng')"`
- **Nguyên nhân gốc:** Khi stdout không phải console UTF-8, Python trên Windows dùng codepage mặc định (cp1252) để encode output. Codepage này không có ký tự tiếng Việt như "ô", "ư".
- **Cách xử lý:** Bật UTF-8 mode của Python: `PYTHONUTF8=1 uv run python ...`
- **Cách xác minh sau khi sửa:** Chạy lại lệnh trên với `PYTHONUTF8=1`, in ra đúng `Môi trường sẵn sàng`.
- **Điều học được:** Lỗi do môi trường có thể trông giống lỗi code. Mọi lệnh "Tín hiệu hoàn thành" của bài đều in tiếng Việt, nên tôi báo cả nhóm để không ai mất thời gian debug nhầm chỗ.

## 7. Hiểu biết về luồng end-to-end

**Câu trả lời:**

1. **Từ Crossref đến vector index:**
   - `crossref.py` lấy payload từ API; nếu lỗi 429/503 hoặc mất mạng thì fallback về snapshot. Payload được parse thành `PaperRecord` và lưu 2 file raw.
   - `cleaning.py` bỏ tag JATS, chuẩn hóa text, tính `age_days`, khử trùng theo `paper_id`, ghép `text_for_embedding` 5 phần.
   - `index.py` embed cột đó bằng `all-MiniLM-L6-v2` (384 chiều, đã normalize) và lưu vào ChromaDB với khoảng cách cosine, kèm metadata để trả lời.
2. **Evaluation set:** mỗi câu hỏi có `ground_truth` (đáp án) và `ground_truth_doc_ids` (bài đúng).
   - `retrieval_hit_rate`: bài đúng có nằm trong top-4 kết quả tìm được không.
   - `mean_token_f1`: độ trùng từ giữa câu trả lời và đáp án.
   - `judge_accuracy` / `mean_judge_score`: LLM (hoặc heuristic khi không có key) chấm đúng/sai.
3. **Quality checks và freshness khác nhau ở đâu:** Quality checks (GX) kiểm tra **cấu trúc và tính hợp lệ** của từng dòng/cột: số dòng, null, unique, độ dài. Freshness kiểm tra **độ mới của cả tập dữ liệu**: tỷ lệ bài có `age_days > 180` không được vượt 25%. Dữ liệu có thể hoàn toàn hợp lệ về schema nhưng vẫn lỗi thời.
4. **Vì sao cùng test set:** Nếu đổi test set thì điểm thay đổi có thể do câu hỏi khác, không phải do dữ liệu. Giữ test set cố định thì thay đổi metric chỉ còn đến từ dữ liệu.
5. **Repair thành công khi:** `repaired_quality_report` có `success = true`, freshness `is_fresh = true`, và `repaired_metrics.json` bằng `baseline_metrics.json` trên cùng test set; `self_healing_log.json` ghi lại quá trình.

## 8. Phân tích kết quả

> Lần chạy bản cuối 26/09 lúc 11:48–11:49, `LLM_PROVIDER=openai`, `LLM_MODEL=gpt-4.1-mini`, cùng `data/eval/test_set.json` (10 câu) cho cả 3 trạng thái. Judge không fallback câu nào (0/10 ở cả 3 file `*_answers.json`). Nguồn: `data/results/*_metrics.json`, `data/quality/*_quality_report.json`.

### Metrics chính

| Metric/signal          | Baseline | Corrupted | Repaired | Nhận xét của cá nhân |
| ---------------------- | -------: | --------: | -------: | -------------------- |
| `retrieval_hit_rate` | 1.000 | 0.700 | 1.000 | 3/10 câu mất bài đúng khỏi top-4: 2 do `drop_latest`, 1 do `truncate_title` |
| `mean_token_f1`      | 1.000 | 0.763 | 1.000 | Giảm ít hơn hit rate vì có câu trả lời đúng chữ nhưng lấy từ bài khác (xem bên dưới) |
| `judge_accuracy`     | 1.000 | 0.600 | 1.000 | Giảm mạnh nhất: 4/10 câu bị chấm sai |
| `mean_judge_score`   | 5.00 | 3.80 | 5.00 | |
| Quality checks         | PASS (8/8) | FAIL (3/8) | PASS (8/8) | Fail: unique `paper_id`, độ dài `title`, độ dài `summary`. Row count vẫn pass (22 dòng, trong khoảng 21–24) |
| Freshness status       | fresh (stale 4.2%) | **stale** (40.9%) | fresh (4.2%) | `stale_date` đẩy tỷ lệ cũ vượt ngưỡng 25% |

### Kết luận từ số liệu

1. **Corruption → signal → metric:** 6 lỗi (24 → 22 dòng) làm Quality Gate fail 3/8 expectation và freshness chuyển sang stale (40.9% > 25%). Khi vẫn cho dữ liệu này vào index, hit rate giảm 1.000 → 0.700 và judge accuracy giảm 1.000 → 0.600. Pipeline vẫn exit 0, không báo lỗi: đây là silent failure.
2. **Repair → signal → metric:** gate fail tự kích hoạt repair (ghi trong `self_healing_log.json`). Dữ liệu dựng lại từ `crossref_records.json` pass lại 8/8 expectation, freshness về 4.2%, và cả 4 metric **trở về đúng baseline** (1.000 / 1.000 / 1.000 / 5.00).

Corruption nào ảnh hưởng rõ nhất và vì sao?

Truy từng câu trong `corrupted_answers.json` với `affected_paper_ids` trong `corruption_log.json`:

- **`drop_latest`** ảnh hưởng rộng nhất: q01, q02 mất bài đúng khỏi index (hit = False).
- **`blank_summary`** làm q05 có F1 = 0.
- **`truncate_title`** nguy hiểm nhất về độ đúng: tra title thất bại. q07 vẫn có bài đúng trong top-4 nhưng câu trả lời lấy từ bài đứng đầu (bài khác), nên ngày sai (F1 = 0); q10 mất bài đúng khỏi top-4.
- **`inject_noise`** là silent failure điển hình: **GX không bắt được** vì summary vẫn đủ dài, nhưng q09 bị judge chấm sai (F1 0.89).
- `stale_date` và `duplicate_rows` rơi vào q04, q06 nhưng không làm sai câu trả lời, vì các câu đó hỏi về categories/authors, không hỏi ngày.

Kết quả nào khác với kỳ vọng ban đầu?

- q02 và q10 có hit = False nhưng **token F1 = 1.0**, judge chấm đúng. Nguyên nhân: khi bài gốc bị xóa hoặc hỏng title, retrieval lấy bài "Advanced Perspectives on …" tương ứng, và bài đó **có cùng tác giả**. Câu trả lời trông đúng nhưng lấy từ sai tài liệu. Vì vậy chỉ nhìn token F1 hay judge sẽ đánh giá quá cao; cần xem cả retrieval hit rate.
- `ExpectTableRowCountToBeBetween` không bắt được việc mất 5 bài mới nhất, vì 3 dòng trùng lặp bù lại số dòng (22 vẫn nằm trong khoảng 21–24). Hai lỗi che nhau khi chỉ đếm số dòng.

## 9. Điều học được và hướng cải thiện

### Ba điều quan trọng nhất

1. *(điền cuối buổi)*
2. *(điền cuối buổi)*
3. *(điền cuối buổi)*

### Nếu có thêm thời gian

*(điền cuối buổi)*

## 10. Cam kết của thành viên

- [ ] Nội dung báo cáo phản ánh đúng phần việc và mức hiểu của tôi.
- [ ] Tôi có thể giải thích luồng end-to-end, không chỉ module mình phụ trách.
- [ ] Mọi kết luận về kết quả đều có artifact hoặc metric để đối chiếu.
- [ ] Tôi không ghi "đã chạy thành công" cho phần chưa được kiểm chứng.
- [ ] Báo cáo không chứa `.env`, API key, token hoặc secret.
- [ ] Báo cáo này không phải bản sao nguyên văn của báo cáo nhóm hoặc báo cáo thành viên khác.

**Họ và tên:** Nguyễn Hải Nam
**Ngày xác nhận:** 2026-09-26

---

<!-- Nhật ký cập nhật: xóa trước khi nộp nếu không cần -->
### Nhật ký cập nhật

| Thời điểm | Cập nhật |
| --------- | -------- |
| 26/09 ~11:00 | Viết mục 1–7: code P4 xong, test bằng stub, blocker UnicodeEncodeError. Mục 8–9 chờ chạy thật. |
| 26/09 ~11:15 | Merge code P1 (nhánh `Hung23020370`), review `crossref.py` và kiểm tra offline. Phát hiện `cleaning.py` chưa có `build_text_for_embedding`. |
| 26/09 ~11:30 | Tự sửa crossref.py + cleaning.py (integration fix). Chạy offline 2 flow với code thật P1/cleaning: exit 0. Chờ P3 merge + test set thật. |
| 26/09 ~11:50 | Lấy code P3 (nhánh `bao-tam`), review + chạy tích hợp offline: pass. Bỏ phần tính freshness trùng trong `corruption_flow.py`. Còn chờ `testset.py` (P2). |
| 26/09 ~12:05 | Merge P2 (`anh02573`), kiểm tra CP1 + CP2 đạt. Đủ code cả 4 phần, chờ chạy bản cuối với OpenAI. |
| 26/09 ~12:15 | Chạy bản cuối (OpenAI gpt-4.1-mini): 2 flow exit 0, judge 0 fallback. Điền Mục 3, 4, 5, 8 bằng số liệu thật + phân tích từng câu. |
| 26/09 ~12:25 | Điền `docs/TEAM.md` (4 thành viên, vai trò, phần đóng góp theo lịch sử git); các thành viên tự rà lại phần của mình. |
| 26/09 ~12:35 | Làm dashboard Streamlit `script/demo_dashboard.py` (bonus B1), thêm `streamlit` vào dependency; smoke test không lỗi, tab Tổng quan báo CP0–CP5 đều ✅. |
| 26/09 ~12:45 | Thêm tab "🎬 Demo 5 bước" vào dashboard: kể theo câu chuyện, số liệu dạng x/10 câu, ví dụ thật q07 trên 3 trạng thái, danh sách kiểm tra bằng lời thường. Smoke test không lỗi. |
| 26/09 ~13:00 | Viết `report/group_report.md` (giữ phần ingestion của Hùng, cập nhật theo integration fix); mọi số liệu lấy từ `data/`. |
| 26/09 ~13:10 | Việt hóa dashboard: tên lỗi, cách tạo, tên kiểm tra GX, loại câu hỏi, tên metric, tên tab; giữ mã gốc để đối chiếu. |
