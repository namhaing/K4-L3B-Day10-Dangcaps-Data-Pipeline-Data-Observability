# Group Report — Day 10: Data Pipeline & Data Observability

## 1. Thông tin bài nộp

| Thông tin         | Nội dung                  |
| ------------------ | -------------------------- |
| Khóa/Lớp         | K4 — L3B |
| Tên nhóm         | Dangcaps |
| Repository         | https://github.com/namhaing/K4-L3B-Day10-Dangcaps-Data-Pipeline-Data-Observability |
| Ngày hoàn thành | 2026-09-26 |

### Thành viên và phân công

| STT | Họ và tên | MSSV | Vai trò chính | Module/deliverable sở hữu |
| --: | --- | --- | --- | --- |
| 1 | Nguyễn Hải Nam | 2A202602476 | Trưởng nhóm — Corruption & Integration | `src/ingestion/corruption.py`, `src/pipelines/phase1.py`, `src/pipelines/corruption_flow.py`, bonus B2 (self-healing), dashboard `script/demo_dashboard.py` (B1), chạy bản cuối |
| 2 | Đồng Mạnh Hùng | 2A202602412 | Source Owner — Ingestion & Raw Lineage | `src/ingestion/crossref.py`, `data/raw/` |
| 3 | Nguyễn Đình Anh | 2A202602573 | Data Model & Evaluation-set Owner | `src/ingestion/cleaning.py`, `src/evaluation/testset.py`, `data/eval/test_set.json` |
| 4 | Nguyễn Trần Bảo Tâm | 2A202602408 | Observability & Reporting Owner | `src/observability/quality.py`, `src/observability/reporting.py`, `script/check_observability.py`, `data/quality/` |

Phân công chi tiết, timeline và Data Contract dùng chung: `docs/PHAN_CONG.md`; tự khai đóng góp từng người: `docs/TEAM.md`.

## 2. Tóm tắt kết quả

**Tóm tắt của nhóm:**

Nhóm đã hoàn thành toàn bộ pipeline bắt buộc và hai hạng mục bonus. Ingestion đọc 24 bài từ Crossref (mặc định dùng snapshot để tái lập được, có retry/backoff và fallback offline). Cleaning bỏ tag JATS, tính `age_days`, sinh `text_for_embedding` 5 phần. Dữ liệu được index bằng `all-MiniLM-L6-v2` vào ChromaDB, đánh giá trên bộ 10 câu hỏi cố định thuộc 4 loại, và kiểm định bằng Great Expectations 1.x (8 expectation) kết hợp Freshness SLA.

Pha 1 sinh đủ artifact: 2 file raw, cleaned CSV/JSON, collection `papers-baseline`, `test_set.json`, `baseline_metrics.json`, quality/freshness report và `phase1_report.md`. Baseline đạt hit rate 1.000, token F1 1.000, judge accuracy 1.000, Quality Gate PASS.

Tiêm 6 loại lỗi làm Quality Gate FAIL 3/8 expectation cùng freshness (40.9% bài cũ, vượt ngưỡng 25%). Nếu vẫn đưa dữ liệu này vào index, hit rate giảm còn 0.700 và judge accuracy còn 0.600, trong khi pipeline vẫn exit 0 — đây là silent failure. Tác động rõ nhất đến từ `drop_latest` và `truncate_title` (làm mất tài liệu đúng khỏi top-4); còn `inject_noise` không bị Quality Gate phát hiện.

Gate fail tự động kích hoạt repair từ raw snapshot; cả 4 metric và Quality Gate trở về đúng baseline. Giới hạn chính: judge dùng LLM nên lời nhận xét không hoàn toàn tất định, và trạng thái freshness phụ thuộc ngày chạy.

## 3. Kiến trúc và luồng dữ liệu

### Luồng end-to-end

```text
Crossref snapshot (mặc định) / Crossref API (REFRESH_SOURCE=1)
    -> data/raw/crossref_response.json + crossref_records.json          [crossref.py]
    -> cleaning + data modeling -> data/clean/papers_clean.{csv,json}   [cleaning.py]
    -> Quality Gate GX 1.x + Freshness SLA -> data/quality/             [quality.py]
    -> embedding MiniLM + ChromaDB "papers-baseline"                    [index.py]
    -> test set 10 câu (tạo 1 lần, dùng chung) -> data/eval/            [testset.py]
    -> evaluate -> baseline_metrics.json -> phase1_report.md            [metrics.py, reporting.py]
    -> corrupt 6 lỗi -> Quality Gate FAIL -> index "papers-corrupted" -> evaluate
    -> self-healing: gate FAIL => repair từ raw snapshot -> gate lại => PASS
    -> index "papers-repaired" -> evaluate -> corruption_report.md      [corruption_flow.py]
```

### Trách nhiệm của từng khối

| Khối             | Input          | Xử lý chính             | Output/artifact          | Owner          |
| ----------------- | -------------- | -------------------------- | ------------------------ | -------------- |
| Ingestion         | Crossref snapshot hoặc API | Parse DOI/title/abstract/authors/subject/dates; retry 5 lần + backoff; fallback offline | `data/raw/crossref_response.json`, `data/raw/crossref_records.json` | Đồng Mạnh Hùng |
| Cleaning          | `list[PaperRecord]` | Bỏ tag JATS/HTML, unescape, chuẩn hóa whitespace; parse ngày ISO; `age_days`; dedup `paper_id`; lọc trường bắt buộc rỗng; `text_for_embedding` | `data/clean/papers_clean.{csv,json}` | Nguyễn Đình Anh |
| Embedding/index   | Clean dataframe | `all-MiniLM-L6-v2` (384 chiều, normalize), ChromaDB cosine, 3 collection riêng | `data/chroma/`, `data/embeddings/*.json` | Có sẵn (starter); Nguyễn Hải Nam tích hợp |
| Evaluation        | Clean dataframe, index | Test set 10 câu / 4 loại; hit rate, token F1, LLM judge | `data/eval/test_set.json`, `data/results/*_metrics.json`, `*_answers.json` | Nguyễn Đình Anh (test set); metrics có sẵn |
| Observability     | Dataframe từng trạng thái | 8 expectation GX 1.x + Freshness SLA (`age_days > 180`, tối đa 25%) | `data/quality/*_quality_report.json`, `*_freshness_report.json`, `gx/*_suite.json` | Nguyễn Trần Bảo Tâm |
| Corruption/repair | Clean dataframe, raw snapshot | 6 lỗi có seed 42; repair = cleaning lại từ raw | `data/clean/papers_clean_{corrupted,repaired}.*`, `corruption_log.json`, `self_healing_log.json` | Nguyễn Hải Nam |
| Orchestration     | Hàm của các module trên | Thứ tự chạy 2 flow, gate trước index, cùng test set cho 3 trạng thái | `phase1_report.md`, `corruption_report.md`, bảng console | Nguyễn Hải Nam |

## 4. Cách tái hiện kết quả

### Cấu hình không chứa secret

| Biến/cấu hình             | Giá trị sử dụng |
| ---------------------------- | ------------------- |
| `LLM_PROVIDER`             | `openai` |
| `LLM_MODEL`                | `gpt-4.1-mini` |
| Embedding model              | `sentence-transformers/all-MiniLM-L6-v2` |
| Số lượng Crossref records | 24 |
| Retrieval `top_k`           | 4 |
| Freshness threshold          | `age_days > 180` là stale; `is_fresh` khi tỷ lệ stale ≤ 25% |
| Random seed, nếu có        | 42 (corruption) |
| `REFRESH_SOURCE` | Không đặt (đọc snapshot) |

### Lệnh cài đặt

```bash
uv sync
```

### Lệnh chạy

```bash
uv run python script/run_phase1.py
uv run python script/run_corruption_flow.py
# Dashboard demo (bonus B1)
uv run streamlit run script/demo_dashboard.py
```

Trên Windows nên đặt `PYTHONUTF8=1` trước khi chạy để in được tiếng Việt ra console.

### Kết quả tái hiện

| Lệnh             | Trạng thái                                    | Thời điểm chạy gần nhất | Bằng chứng                         |
| ----------------- | ----------------------------------------------- | ----------------------------- | ------------------------------------ |
| Baseline pipeline | Thành công (exit 0) | 2026-09-26 12:08 GMT+7 (`run_at` trong `phase1_report.md`) | `data/results/baseline_metrics.json`, `data/reports/phase1_report.md` |
| Corruption flow   | Thành công (exit 0) | 2026-09-26 11:49 GMT+7 | `data/results/{corrupted,repaired}_metrics.json`, `data/results/self_healing_log.json`, `data/reports/corruption_report.md` |

Phase 1 được chạy lại lúc 12:08 sau lần chạy corruption flow; `baseline_metrics.json` không đổi, `test_set.json` giữ nguyên (SHA-256 `54dfe7c8966e…`), nên cả 3 trạng thái vẫn so sánh trên cùng test set.

## 5. Ingestion, cleaning và data contract

### Nguồn dữ liệu

| Thuộc tính | Giá trị thực tế |
| --- | --- |
| Source | Crossref REST API: `https://api.crossref.org/works` |
| Query | `query.title=agentic retrieval augmented generation large language model` |
| Filter | `from-pub-date:<hôm nay − 180 ngày>,has-abstract:true` (tính động theo freshness threshold) |
| Giới hạn kết quả | 24 records (`rows=24`) |
| Số record nhận được | 24 trong `data/raw/crossref_records.json` |
| Thời điểm lấy dữ liệu | Snapshot offline đi kèm repo; mặc định pipeline đọc snapshot này, chỉ gọi API khi `REFRESH_SOURCE=1` |
| Timeout và retry | Timeout 30 giây; tối đa 5 lần thử. Retry các lỗi request/HTTP/JSON; status 429, 500, 502, 503, 504 được xử lý là retryable. |
| Backoff | Delay tuyến tính `1.5 × số lần thử`: 1.5, 3, 4.5 và 6 giây giữa các lần thử; không phải exponential backoff. |
| Offline fallback | Khi gọi API thất bại: parse lại `crossref_response.json`, sau đó đọc `settings.paths.raw_records_json`. Đã kiểm tra: chặn mạng + `REFRESH_SOURCE=1` vẫn trả về đủ 24 bài. |
| Raw artifacts | `data/raw/crossref_response.json` (response API) và `data/raw/crossref_records.json` (parsed records) |

### Raw record schema từ ingestion

| Trường | Kiểu | Bắt buộc trong record đầu ra? | Ý nghĩa / xử lý khi thiếu |
| --- | --- | --- | --- |
| `paper_id` | `str` | Có | DOI; item thiếu DOI bị bỏ qua. |
| `title` | `str` | Có | Nối title parts và chuẩn hóa khoảng trắng; title rỗng bị bỏ qua. |
| `summary` | `str` | Không | Abstract; bỏ JATS/XML tags và chuẩn hóa whitespace; nếu thiếu thì chuỗi rỗng. |
| `authors` | `list[str]` | Không | Ghép `given` + `family`; author không hợp lệ bị bỏ qua. |
| `categories` | `list[str]` | Không | Danh sách Crossref `subject`; mặc định danh sách rỗng. |
| `primary_category` | `str` | Không | Subject đầu tiên; mặc định `General` nếu không có subject. |
| `published` | `str` | Không | Ngày ISO `YYYY-MM-DD` từ `date-time` hoặc `date-parts`; fallback sang `updated` nếu thiếu. |
| `updated` | `str` | Không | Đọc từ `updated`, fallback sang `created`, rồi `published`. |
| `abs_url` | `str` | Không | Crossref `URL`; fallback `https://doi.org/<DOI>`. |
| `pdf_url` | `str` | Không | URL link có content type PDF; nếu không có thì fallback sang item URL. |
| `comment` | `str` | Không | Sinh theo mẫu `Crossref record <DOI>`. |

Parser bỏ item không phải object, thiếu DOI hoặc thiếu title. Raw response được lưu nguyên payload trước khi parse; `crossref_records.json` chứa schema đã parse để downstream sử dụng.

### Quy tắc cleaning

| Quy tắc                                 | Quality dimension liên quan | Số record bị tác động | Cách xác minh      |
| ---------------------------------------- | ---------------------------- | -------------------------: | -------------------- |
| Bỏ tag JATS/HTML trong abstract, `html.unescape`, chuẩn hóa whitespace | Validity / Consistency | 24 (cả 24 abstract trong response có `<jats:p>`) | `crossref_response.json` so với `papers_clean.json`: không còn ký tự `<` |
| Parse `published`/`updated`, loại dòng có ngày không hợp lệ, trả về chuỗi `YYYY-MM-DD` | Validity | 0 bị loại | 24 → 24 dòng |
| Khử trùng lặp theo `paper_id` (giữ bản đầu) | Uniqueness | 0 | GX `expect_column_values_to_be_unique(paper_id)` PASS |
| Loại dòng có `paper_id`/`title`/`summary` rỗng | Completeness | 0 | GX not-null + length PASS |
| Làm sạch danh sách authors/categories (bỏ phần tử rỗng) | Completeness | 0 | `authors_joined`, `categories_joined` không rỗng |
| Sắp xếp ổn định theo `published` giảm dần, rồi `paper_id` | Consistency (tái lập) | 24 | Chạy lại ra cùng thứ tự |

Giải thích cách nhóm tạo `text_for_embedding`, document ID và `age_days`:

- **Document ID:** `paper_id` = DOI của Crossref, ổn định qua mọi lần chạy và là khóa để đối chiếu `ground_truth_doc_ids`. Trong ChromaDB, mỗi vector có `record_id = "<paper_id>::<vị trí>"` để các dòng trùng (khi bị corrupt) vẫn index được mà không ghi đè nhau.
- **`age_days`** = `(run_date.date() − published.date()).days`, với `run_date` là thời điểm chạy (UTC). Trên snapshot, `age_days` nằm trong khoảng 66–182 ngày.
- **`text_for_embedding`** gồm 5 dòng có nhãn, được tạo bởi hàm public `build_text_for_embedding(row)` để cleaning và corruption dùng chung một công thức:

```text
Title: {title}
Authors: {authors_joined}
Published: {published}
Categories: {categories_joined}
Summary: {summary}
```

## 6. Evaluation setup

| Thành phần                             | Cấu hình thực tế          |
| ---------------------------------------- | ----------------------------- |
| Số câu hỏi                            | 10 |
| Các `question_type`                    | `summary` (3), `authors` (3), `date` (2), `categories` (2) |
| Ground-truth document ID                 | `paper_id` của bài được hỏi; `retrieval_hit` = bài đó có trong top-4 kết quả |
| Embedding model                          | `sentence-transformers/all-MiniLM-L6-v2` |
| Vector store/collection                  | ChromaDB persistent (`data/chroma/`), cosine; `papers-baseline`, `papers-corrupted`, `papers-repaired` |
| Retrieval `top_k`                       | 4 |
| LLM provider/model                       | `openai` / `gpt-4.1-mini` (LLM judge); câu trả lời QA được trích xuất bằng luật trong `retrieval/qa.py` |
| Test set dùng chung cho ba trạng thái | `data/eval/test_set.json` (SHA-256 `54dfe7c8966e…`) |

Câu hỏi được chọn tất định, phủ cả bài mới nhất và nhóm bài "Advanced Perspectives on …"; bỏ các title có dấu `'` hoặc trùng tên để việc tra bài theo title trong `qa.py` không nhập nhằng. Judge không fallback sang heuristic ở câu nào (0/10 cho cả 3 file `*_answers.json`).

Giải thích vì sao test set được giữ nguyên khi đánh giá baseline, corrupted và repaired:

Test set chỉ được tạo một lần ở Phase 1 (không tạo lại nếu đã tồn tại, trừ khi `REFRESH_TEST_SET=1`), và `corruption_flow.py` không bao giờ tạo lại nó. Nhờ vậy câu hỏi, đáp án chuẩn và `ground_truth_doc_ids` giống hệt nhau ở cả 3 trạng thái: mọi thay đổi metric chỉ có thể đến từ dữ liệu, không phải do đổi đề.

## 7. Kết quả baseline

### Artifact checklist

| Artifact                 | Đường dẫn thực tế                | Trạng thái | Ghi chú   |
| ------------------------ | -------------------------------------- | ------------ | ---------- |
| Raw response/records     | `data/raw/`                          | Có | 24 items / 24 records |
| Cleaned dataset          | `data/clean/`                        | Có | 24 dòng; kèm bản `_corrupted` (22) và `_repaired` (24) |
| Embedding manifest/index | `data/embeddings/`, `data/chroma/`   | Có | 3 manifest + 3 collection |
| Evaluation set           | `data/eval/`                         | Có | 10 câu |
| Baseline metrics         | `data/results/baseline_metrics.json` | Có | Kèm `baseline_answers.json`, `agent_demo_answers.json` |
| Quality/freshness        | `data/quality/`                      | Có | Quality + freshness report cho 3 trạng thái, 3 GX suite trong `gx/` |
| Baseline report          | `data/reports/phase1_report.md`      | Có | Sinh tự động từ artifact |

### Baseline metrics

| Metric                 |       Giá trị | Diễn giải                             |
| ---------------------- | --------------: | --------------------------------------- |
| `retrieval_hit_rate` | 1.000 | 10/10 câu có bài đúng trong top-4 |
| `mean_token_f1`      | 1.000 | Câu trả lời khớp hoàn toàn với đáp án chuẩn |
| `judge_accuracy`     | 1.000 | LLM judge chấm đúng cả 10 câu |
| `mean_judge_score`   | 5.00 | Điểm tối đa trên thang 1–5 |
| Ragas, nếu có        | N/A | Không bật (`RUN_RAGAS` không đặt) để tiết kiệm thời gian và chi phí API |

Baseline đạt tối đa vì QA trích xuất đúng trường metadata của bài được tra theo title; đây là mốc chuẩn để đo mức suy giảm, không phải thước đo năng lực tổng quát của agent.

## 8. Data quality và freshness

### Quality checks

| Check        | Quality dimension | Ngưỡng/kỳ vọng | Kết quả baseline      | Bằng chứng |
| ------------ | ----------------- | ------------------ | ----------------------- | ------------ |
| `ExpectTableRowCountToBeBetween` | Completeness | 21–24 dòng | PASS (24) | `data/quality/baseline_quality_report.json` |
| `ExpectColumnValuesToNotBeNull(paper_id)` | Completeness | 0 null | PASS (0/24) | như trên |
| `ExpectColumnValuesToNotBeNull(title)` | Completeness | 0 null | PASS (0/24) | như trên |
| `ExpectColumnValuesToNotBeNull(summary)` | Completeness | 0 null | PASS (0/24) | như trên |
| `ExpectColumnValuesToNotBeNull(published)` | Completeness | 0 null | PASS (0/24) | như trên |
| `ExpectColumnValuesToBeUnique(paper_id)` | Uniqueness | 0 trùng | PASS (0/24) | như trên |
| `ExpectColumnValueLengthsToBeBetween(title)` | Validity | ≥ 8 ký tự | PASS (0/24 vi phạm) | như trên |
| `ExpectColumnValueLengthsToBeBetween(summary)` | Validity | ≥ 50 ký tự | PASS (0/24 vi phạm) | như trên |
| Freshness SLA | Timeliness | ≤ 25% bài có `age_days > 180` | PASS (1/24 = 4.2%) | `data/quality/freshness_report.json` |

Quality Gate chỉ PASS khi cả 8 expectation GX **và** freshness cùng đạt (`success = validation.success and is_fresh`). Cú pháp dùng GX 1.x: ephemeral context → pandas data source → dataframe asset → batch definition → `batch.validate(suite)`; suite được lưu ở `data/quality/gx/`.

### Freshness

| Thuộc tính               | Giá trị                           |
| -------------------------- | ----------------------------------- |
| Freshness được đo tại | Clean dataframe (cột `age_days`), trước khi index |
| Timestamp mới nhất       | `published` mới nhất 2026-07-22; cũ nhất 2026-03-28 |
| Ngưỡng freshness         | `age_days > 180` là stale; tối đa 25% bài stale |
| Trạng thái baseline      | Fresh |
| Lý do                     | Chỉ 1/24 bài (4.2%) quá 180 ngày, thấp hơn nhiều so với ngưỡng 25% |

## 9. Corruption scenarios và repair

| Corruption         | Cách tạo | Record bị tác động | Quality signal kỳ vọng | Tác động thực tế | Cách repair   |
| ------------------ | ---------- | ---------------------: | ------------------------ | --------------------- | -------------- |
| `drop_latest` | Bỏ 20% bài có `published` mới nhất | 5 | Row count giảm | Row count **vẫn PASS** (22 nằm trong 21–24 vì dòng trùng bù lại); q01, q02 mất bài đúng khỏi index (hit = False) | Cleaning lại từ raw |
| `blank_summary` | `summary = ""` | 5 | Độ dài summary < 50 | Length(summary) FAIL; q05 token F1 = 0 | Cleaning lại từ raw |
| `inject_noise` | Chèn token rác ở đầu summary và sau mỗi 4 từ | 5 | Không có check tương ứng | **Không bị GX phát hiện**; q09 bị judge chấm sai (F1 0.89) | Cleaning lại từ raw |
| `truncate_title` | Cắt title còn 6 ký tự | 5 | Độ dài title < 8 | Length(title) FAIL; q07 trả lời sai ngày (F1 0), q10 mất bài đúng khỏi top-4 | Cleaning lại từ raw |
| `stale_date` | Lùi `published` 400 ngày, tính lại `age_days` | 7 | Freshness stale | Stale 9/22 = 40.9% > 25% → freshness FAIL | Cleaning lại từ raw |
| `duplicate_rows` | Nhân bản nguyên dòng | 3 | Unique `paper_id` fail | Unique(paper_id) FAIL (6 giá trị vi phạm) | Cleaning lại từ raw (dedup) |

Ba lỗi nội dung (`blank_summary`, `inject_noise`, `truncate_title`) đánh vào ba nhóm dòng không trùng nhau để truy vết được tác động riêng của từng lỗi.

Corruption log:

- Đường dẫn: `data/results/corruption_log.json`
- Trạng thái: Có
- Nhận xét: Log ghi `seed = 42`, `input_rows = 24`, `output_rows = 22`, và với từng loại lỗi: mô tả, số dòng, danh sách `affected_paper_ids`. Nhờ danh sách này nhóm đối chiếu được từng câu sai với lỗi gây ra (Mục 10).

Giải thích cách repair đảm bảo dữ liệu được phục hồi từ nguồn đáng tin cậy thay vì chỉ che kết quả lỗi:

Repair không vá từng dòng bẩn mà bỏ toàn bộ dữ liệu corrupted, đọc lại `data/raw/crossref_records.json` (không bao giờ bị sửa) và chạy lại đúng hàm `build_clean_dataframe` của Phase 1. Cách này phục hồi được cả những lỗi không thể vá ngược (như chèn nhiễu hay mất bản ghi). Repair **idempotent**: raw bất biến, seed cố định, và `LocalEmbeddingIndex.build()` xóa collection cũ trước khi tạo lại nên không có ghost vectors; chạy lại flow cho cùng số liệu.

Repair được kích hoạt **tự động** (bonus B2): khi Quality Gate của dữ liệu corrupted FAIL, `corruption_flow.py` tự chạy repair, rồi chạy lại Quality Gate trên dữ liệu đã sửa. Nếu vẫn FAIL, pipeline dừng (`SystemExit`) và không publish vào index. Chuỗi quyết định được ghi trong `data/results/self_healing_log.json`: gate corrupted FAIL → repair (`auto: quality gate failed`, nguồn `crossref_records.json`) → gate repaired PASS.

## 10. So sánh baseline, corrupted và repaired

| Metric/signal            | Baseline | Corrupted | Repaired | Thay đổi do corruption | Mức phục hồi | Nhận xét   |
| ------------------------ | -------: | --------: | -------: | -----------------------: | --------------: | ------------ |
| `retrieval_hit_rate`   | 1.000 | 0.700 | 1.000 | −0.300 | 100% | 3/10 câu mất bài đúng khỏi top-4 |
| `mean_token_f1`        | 1.000 | 0.763 | 1.000 | −0.237 | 100% | Giảm ít hơn hit rate vì có câu đúng chữ nhưng sai tài liệu |
| `judge_accuracy`       | 1.000 | 0.600 | 1.000 | −0.400 | 100% | Giảm mạnh nhất: 4/10 câu sai |
| `mean_judge_score`     | 5.00 | 3.80 | 5.00 | −1.20 | 100% | |
| Quality checks pass/fail | 8/8 PASS | 5/8 (FAIL) | 8/8 PASS | −3 expectation | 100% | Fail: unique `paper_id`, length `title`, length `summary` |
| Freshness status         | Fresh (4.2%) | Stale (40.9%) | Fresh (4.2%) | +36.7 điểm % | 100% | `stale_date` vượt ngưỡng 25% |

Phân tích từng câu (đối chiếu `corrupted_answers.json` với `affected_paper_ids` trong `corruption_log.json`):

| Câu | Loại | Tìm đúng bài | Token F1 | Judge | Lỗi tác động vào bài được hỏi |
| --- | --- | :---: | ---: | :---: | --- |
| q01 | summary | ❌ | 0.74 | ❌ | `drop_latest` |
| q02 | authors | ❌ | 1.00 | ✅ | `drop_latest` |
| q03 | date | ✅ | 1.00 | ✅ | — |
| q04 | categories | ✅ | 1.00 | ✅ | `truncate_title`, `stale_date`, `duplicate_rows` |
| q05 | summary | ✅ | 0.00 | ❌ | `blank_summary` |
| q06 | authors | ✅ | 1.00 | ✅ | `duplicate_rows` |
| q07 | date | ✅ | 0.00 | ❌ | `truncate_title` |
| q08 | categories | ✅ | 1.00 | ✅ | `inject_noise` |
| q09 | summary | ✅ | 0.89 | ❌ | `inject_noise`, `stale_date` |
| q10 | authors | ❌ | 1.00 | ✅ | `truncate_title` |

Nêu ít nhất hai kết luận có quan hệ nhân quả được hỗ trợ bởi artifacts:

1. **Corruption → quality/freshness signal → metric:** 6 lỗi (24 → 22 dòng) làm Quality Gate fail 3/8 expectation và freshness chuyển sang stale (40.9%). Khi dữ liệu này vẫn được index, hit rate giảm 1.000 → 0.700 và judge accuracy 1.000 → 0.600, trong khi cả hai script đều exit 0: agent suy giảm mà không báo lỗi (silent failure).
2. **Repair → quality/freshness recovery → metric recovery:** gate fail tự kích hoạt repair từ raw snapshot; dữ liệu repaired pass lại 8/8 expectation, freshness về 4.2%, và cả 4 metric về đúng giá trị baseline trên cùng test set.

Kết quả khác kỳ vọng và cách nhóm kiểm tra:

- **Đúng chữ nhưng sai tài liệu:** q02 và q10 có `retrieval_hit = False` nhưng token F1 = 1.0 và judge chấm đúng. Kiểm tra `retrieved_doc_ids` cho thấy retrieval lấy bài "Advanced Perspectives on …" tương ứng, và bài này có **cùng tác giả** với bài gốc (snapshot có 12 cặp bài như vậy). Vì vậy chỉ nhìn token F1 hay judge sẽ đánh giá quá cao chất lượng; phải xem cả hit rate.
- **Hai lỗi che nhau:** `ExpectTableRowCountToBeBetween` không phát hiện việc mất 5 bài, vì 3 dòng nhân bản bù lại số dòng (22 vẫn trong khoảng 21–24). Lỗi mất dữ liệu chỉ lộ ra qua `retrieval_hit_rate`.
- **`inject_noise`** không có expectation nào phát hiện được (summary vẫn đủ dài), nhưng vẫn làm q09 sai: minh họa rằng Quality Gate cần đi kèm đánh giá chất lượng câu trả lời.

## 11. Vấn đề tích hợp quan trọng

- **Triệu chứng:** Khi ghép `crossref.py` vào Phase 1, mỗi lần chạy `run_phase1.py` đều gọi Crossref API live và ghi đè `data/raw/crossref_response.json` + `crossref_records.json`. API trả về các bài khác snapshot, nên `test_set.json` (tạo từ snapshot) không còn khớp dữ liệu và số liệu không tái lập được trên máy khác. Cùng lúc đó, `corruption.py` không import được `build_text_for_embedding` vì bản cleaning ban đầu chưa tách hàm này.
- **Nguyên nhân:** `fetch_source_records()` không đọc cờ `settings.refresh_source` có sẵn trong config, và dùng đường dẫn tương đối `Path("data/raw/...")` cho fallback (phụ thuộc thư mục đang đứng khi chạy). Công thức `text_for_embedding` lại được viết inline trong cleaning nên module khác không dùng lại được.
- **Cách xử lý:** Integration fix trong `crossref.py`: mặc định đọc snapshot, chỉ gọi API khi `REFRESH_SOURCE=1`; fallback dùng `settings.paths.raw_records_json`. Cleaning tách hàm public `build_text_for_embedding(row)` theo Data Contract; bản cleaning cuối của P2 giữ đúng hàm này.
- **Cách xác minh:** Kiểm tra offline có chặn mạng: `fetch_source_records` trả 24 bài và `crossref_records.json` không đổi; với `REFRESH_SOURCE=1` + mất mạng vẫn fallback đủ 24 bài. Sau đó `run_phase1.py` và `run_corruption_flow.py` đều exit 0.

## 12. Giới hạn và hướng cải thiện

| Giới hạn hiện tại | Ảnh hưởng   | Hướng cải thiện có thể kiểm chứng |
| --------------------- | -------------- | ----------------------------------------- |
| Không có expectation nào phát hiện `inject_noise` | Dữ liệu nhiễu lọt qua Quality Gate (q09 sai) | Thêm expectation tỷ lệ ký tự không phải chữ cái / regex token rác trên `summary`; kiểm chứng: gate corrupted fail thêm 1 expectation |
| Row-count check bị che bởi dòng trùng | Mất 5 bài không bị gate phát hiện | Đếm số `paper_id` **duy nhất** thay vì số dòng; kiểm chứng: gate bắt được `drop_latest` |
| Freshness phụ thuộc ngày chạy | Chạy lại sau khoảng 2026-11-29, baseline sẽ vượt 25% stale và repair bị chặn | Truyền `run_date` cố định qua biến môi trường khi chấm; hoặc refresh snapshot bằng `REFRESH_SOURCE=1` |
| LLM judge không hoàn toàn tất định | Lời nhận xét (`reasoning`) đổi giữa các lần chạy dù điểm không đổi | Cố định model + temperature 0 (đã làm); lưu kèm hash câu trả lời; so sánh bằng hit rate / token F1 tất định |
| QA trích xuất theo luật, test set 10 câu | Baseline 1.000 phản ánh luật trích xuất hơn là năng lực agent | Mở rộng test set, bật `RUN_RAGAS=1` để có faithfulness / context precision |
| `data/embeddings/*.json` lưu `persist_path` tuyệt đối (do `index.py` của starter) | Manifest phụ thuộc máy; pipeline không bị ảnh hưởng vì luôn build lại index | Lưu đường dẫn tương đối so với `project_dir` |

## 13. Checklist trước khi nộp

- [x] Thông tin nhóm và repository chính xác.
- [x] Phân công khớp với module, artifact và kết quả thực tế.
- [x] Lệnh tái hiện đã được chạy lại trên phiên bản dùng để nộp.
- [x] Baseline, corrupted và repaired dùng cùng evaluation set.
- [x] Bảng metrics khớp với các file trong `data/results/`.
- [x] Quality/freshness conclusions khớp với `data/quality/`.
- [x] Các đường dẫn báo cáo và artifact truy cập được.
- [x] Mỗi thành viên đã hoàn thành báo cáo vai trò riêng (`report/2A2026024xx_*.md`, `report/2A202602573_NguyenDinhAnh.md`).
- [x] Không có `.env`, API key, token hoặc secret trong source, report, log hay ảnh.
