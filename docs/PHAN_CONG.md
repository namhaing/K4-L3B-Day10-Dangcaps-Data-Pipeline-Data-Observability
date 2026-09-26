# Phân Công Công Việc & Checklist — Nhóm 4 Người

> Tài liệu nội bộ của nhóm. Mỗi người đọc **Phần 0–2** (chung) và **phần của mình** ở Mục 3.
> Deadline LMS: **23:59:59 ngày 26/09/2026**. Mỗi người tự nộp link repo từ tài khoản của mình.

---

## 0. Tổng quan nhanh

**Đã có sẵn, KHÔNG cần viết:** `src/core/`, `src/retrieval/` (embedding MiniLM, ChromaDB, QA, agent, LLM router), `src/evaluation/metrics.py`.

**Còn 11 hàm `TODO(student)` cần viết:**

| File | Hàm | Người |
|---|---|:---:|
| `src/ingestion/crossref.py` | `parse_crossref_payload`, `fetch_source_records`, `load_raw_records` | **P1** |
| `src/ingestion/cleaning.py` | `build_clean_dataframe` | **P2** |
| `src/evaluation/testset.py` | `build_test_set` | **P2** |
| `src/observability/quality.py` | `run_data_quality_checks`, `build_freshness_report` | **P3** |
| `src/observability/reporting.py` | `generate_phase1_report`, `generate_corruption_report` | **P3** |
| `src/ingestion/corruption.py` | `corrupt_clean_dataframe` | **P4** |
| `src/pipelines/phase1.py` | `main` | **P4** |
| `src/pipelines/corruption_flow.py` | `main` | **P4** |

| Người | Vai trò | Bonus phụ trách (sau khi xong phần chính) |
|:---:|---|---|
| **P1** | Source Owner: Ingestion & Raw Lineage | B3: Pytest + script test một lệnh |
| **P2** | Data Model & Evaluation-set Owner | Hỗ trợ P4 kiểm tra dữ liệu corrupted/repaired |
| **P3** | Observability & Reporting Owner | B1: Dashboard HTML trạng thái quality/freshness |
| **P4** | Trưởng nhóm: Corruption & Integration | B2: Auto-repair khi Quality Gate fail |

**Luồng dữ liệu:**

```text
Crossref snapshot/API ─(P1)→ data/raw/*.json
  ─(P2)→ clean dataframe ─→ data/clean/papers_clean.{csv,json}
  ─(có sẵn)→ ChromaDB "papers-baseline"   ─(P2)→ data/eval/test_set.json
  ─(có sẵn)→ evaluate → baseline_metrics.json
  ─(P3)→ quality/freshness → data/quality/*   ─(P3)→ phase1_report.md
  ─(P4)→ corrupt (6 lỗi) → re-index "papers-corrupted" → corrupted_metrics.json
  ─(P4)→ repair từ data/raw → re-index "papers-repaired" → repaired_metrics.json
  ─(P3)→ corruption_report.md (Baseline vs Corrupted vs Repaired)
```

---

## 1. Việc chung — CẢ NHÓM làm trong 15 phút đầu

### 1.1 Cài môi trường (mỗi người trên máy mình)

- [ ] `uv sync --extra dev` (cài dependency + cài project dạng editable. Nếu thiếu bước này, `from pipelines...` / `from core...` sẽ lỗi import)
  - Không có uv: `python -m venv .venv` → kích hoạt → `pip install -e ".[dev]"`
- [ ] `cp .env.example .env` rồi điền key. Không có key thì đặt `LLM_PROVIDER=mock`: pipeline vẫn chạy vì QA không gọi LLM, còn judge tự fallback sang heuristic.
- [ ] Kiểm tra: `uv run python -c "import chromadb, great_expectations, sentence_transformers; print('Môi trường sẵn sàng')"`
- [ ] `git config user.name` / `user.email` đúng email tài khoản GitHub, để commit được tính vào **Insights → Contributors**.
- [ ] **Không bao giờ** `git add .env`. Trước mỗi commit, chạy `git status` để kiểm tra.

### 1.2 Chốt DATA CONTRACT (bắt buộc trước khi code)

**a) `PaperRecord`** (raw record, đã định nghĩa trong `crossref.py`):

| Trường | Kiểu | Lấy từ Crossref |
|---|---|---|
| `paper_id` | str | `DOI` |
| `title` | str | `title[0]` |
| `summary` | str | `abstract` (bỏ tag `<jats:...>`) |
| `authors` | list[str] | `author[*]` → `"given family"` |
| `categories` | list[str] | `subject` |
| `primary_category` | str | `subject[0]`, hoặc `"Uncategorized"` |
| `published` | str `YYYY-MM-DD` | `published.date-parts[0]` (thiếu tháng/ngày thì gán = 1) |
| `updated` | str `YYYY-MM-DD` | `created.date-time[:10]`, hoặc = `published` |
| `abs_url` | str | `URL` |
| `pdf_url` | str | `link[0].URL` nếu có, không thì = `URL` |
| `comment` | str | `f"Crossref record {DOI}"` |

**b) Clean dataframe** (đầu ra của `build_clean_dataframe`, đầu vào của mọi module sau):

| Cột | Kiểu | Ghi chú |
|---|---|---|
| 11 trường của `PaperRecord` | như trên | `published` **giữ dạng chuỗi** `YYYY-MM-DD` (ChromaDB metadata không nhận Timestamp) |
| `age_days` | int | `(run_date.date() - published.date()).days` |
| `authors_joined` | str | `", ".join(authors)` |
| `categories_joined` | str | `", ".join(categories)` |
| `summary_chars` | int | `len(summary)` |
| `text_for_embedding` | str | cấu trúc 5 phần, xem bên dưới |

`text_for_embedding` (5 phần, P2 viết thành hàm **`build_text_for_embedding(row) -> str`** để P4 import lại):

```text
Title: {title}
Authors: {authors_joined}
Published: {published}
Categories: {categories_joined}
Summary: {summary}
```

> `src/retrieval/index.py` dòng 44–66 đọc đúng các cột: `paper_id, title, text_for_embedding, published, authors_joined, categories_joined, summary, abs_url, pdf_url`. **Không đổi tên cột.**
> Mọi giá trị text **không được là `None`/`NaN`** (ChromaDB metadata sẽ lỗi), nên dùng `""`.

**c) Test set item** (`data/eval/test_set.json`, là list):

```json
{"id": "q01", "question_type": "summary|authors|date|categories",
 "question": "...", "ground_truth": "...", "ground_truth_doc_ids": ["10.xxxx/..."]}
```

**d) Kết quả quality** (`run_data_quality_checks` trả về dict, **bắt buộc có key `"success"`**):

```json
{"report_name": "baseline", "success": true, "row_count": 24,
 "expectations": [{"expectation": "expect_column_values_to_be_unique", "column": "paper_id", "success": true, "details": {...}}],
 "freshness": {...}}
```

**e) Freshness report:** `latest_published, oldest_published, stale_rows, total_rows, stale_ratio, threshold_days, max_stale_ratio, is_fresh`.

**f) Metrics** (do `metrics.py` sinh ra, không sửa): `samples, retrieval_hit_rate, mean_token_f1, judge_accuracy, mean_judge_score, ragas`.

**g) Đường dẫn:** chỉ dùng `settings.paths.*` trong `core/config.py`. **Cấm hardcode `D:\...` / `C:\...`** (trừ 5đ).

### 1.3 Quy ước Git

- Mỗi người chỉ sửa file mình sở hữu. Trước khi push: `git pull --rebase origin main`.
- Commit nhỏ, message rõ, ví dụ `feat(crossref): parse payload + fallback snapshot`.
- **Mỗi người phải có ít nhất 1 commit trên `main`**, không thì bị 0 điểm cá nhân.
- Artifact trong `data/` **phải commit**, vì giám khảo cần thấy chúng.

---

## 2. Timeline (ca 09:00 – 13:00)

| Giờ | CP | P1 | P2 | P3 | P4 |
|---|---|---|---|---|---|
| 09:00–09:30 | CP0 | **crossref.py** | Setup, viết khung cleaning | Setup, đọc API GX 1.x | Setup, chốt contract, `.env` |
| 09:30–10:05 | CP1 | Review, hỗ trợ P2 | **cleaning.py** | **quality.py** (test tạm bằng raw records) | **corruption.py** |
| 10:05–10:35 | CP2 | Bắt đầu B3 (tests) | **testset.py** | Hoàn thiện quality/freshness | **phase1.py** |
| 10:35–11:00 | CP3 | Test ingestion/cleaning | Kiểm tra QA trả đúng ground truth | **generate_phase1_report** | Chạy `run_phase1.py` end-to-end |
| 11:00–11:45 | CP4 | B3 tiếp | Kiểm tra dữ liệu corrupted | **generate_corruption_report** | **corruption_flow.py** (corrupt + eval) |
| 11:45–12:30 | CP5 | Chạy lại toàn bộ trên máy sạch | Kiểm tra repaired == baseline | B1 dashboard | Repair + B2 auto-repair, chốt artifacts |
| 12:30–13:00 | CP6 | Demo phần ingestion | Q&A cleaning/test set | Trình bày bảng 3 trạng thái | Chạy live demo |
| Chiều–23:59 | — | Báo cáo cá nhân | Báo cáo cá nhân | Báo cáo cá nhân + group report | Group report + TEAM.md + rà checklist nộp |

---

## 3. Việc chi tiết từng người

### 👤 P1 — Source Owner (Ingestion & Raw Lineage)

**File:** `src/ingestion/crossref.py` · **Rubric:** #2 (15đ), #1 (10đ) · **Bonus:** B3

#### Việc cần làm

- [ ] **`parse_crossref_payload(payload) -> list[PaperRecord]`**
  - [ ] Duyệt `payload["message"]["items"]`
  - [ ] Map từng trường theo bảng 1.2a
  - [ ] Làm sạch abstract: `re.sub(r"<[^>]+>", " ", text)` → `html.unescape` → `normalize_whitespace` (import từ `core.utils`)
  - [ ] Bỏ record thiếu `DOI`, `title` hoặc `abstract` (không crash)
  - [ ] Khử trùng DOI ngay khi parse (giữ bản đầu tiên)
- [ ] **`fetch_source_records(settings) -> list[PaperRecord]`**
  - [ ] Nếu `settings.refresh_source == False` **và** đã có `settings.paths.raw_api_response`, đọc snapshot (offline, tái lập được, ra đúng 24 bài)
  - [ ] Nếu không, gọi `GET https://api.crossref.org/works` với params `query=settings.source_query`, `filter=settings.source_filter`, `rows=settings.max_results`, header `User-Agent` có mailto
  - [ ] Retry tối đa 3 lần với backoff (1s, 2s, 4s) khi gặp status **429/503** hoặc timeout; nếu có header `Retry-After` thì tuân theo
  - [ ] Hết retry hoặc mất mạng: **fallback về snapshot** `raw_api_response`, log rõ "Fallback to local snapshot"
  - [ ] Chỉ ghi đè `raw_api_response` khi gọi API thành công
  - [ ] Luôn ghi `raw_records_json` = `[dataclasses.asdict(r) for r in records]` bằng `write_json`
- [ ] **`load_raw_records(path) -> list[PaperRecord]`**: `[PaperRecord(**item) for item in read_json(path)]`

#### ⚠️ Lưu ý

- API live trả về **bài báo thật, khác snapshot**. Khi demo/nộp bài, **không** bật `REFRESH_SOURCE=1`, nếu không snapshot 24 bài sẽ bị ghi đè và test set bị lệch.
- Snapshot `crossref_response.json` đã có sẵn trong repo, đừng xóa.

#### Tín hiệu hoàn thành (CP0)

```bash
uv run python -c "from core.config import load_settings; from ingestion.crossref import fetch_source_records; s=load_settings(); r=fetch_source_records(s); print(f'Tín hiệu hoàn thành: Đã tải {len(r)} bài báo')"
```

- [ ] In ra `Đã tải 24 bài báo`
- [ ] `data/raw/crossref_records.json` có 24 phần tử, đúng 11 trường
- [ ] Rút mạng (hoặc tạm đặt sai URL) rồi chạy lại vẫn ra 24 bài, nhờ fallback

#### Bonus B3 — Pytest (+5đ, sau CP2)

- [ ] Tạo `tests/`:
  - `test_crossref.py`: parse, bỏ record thiếu, fallback
  - `test_cleaning.py`: 24 dòng, không trùng `paper_id`, `age_days` ≥ 0, text 5 phần
  - `test_quality.py`: baseline `success=True`, df bị làm hỏng `success=False`
  - `test_corruption.py`: log đủ 6 loại
  - `test_retrieval.py`: search trả về top_k
- [ ] Script một lệnh `script/run_tests.sh` (hoặc `.ps1`): `uv run pytest --cov=src --cov-report=term`
- [ ] (Tuỳ chọn) `.github/workflows/ci.yml` chạy pytest
- [ ] Mục tiêu coverage > 80% (cần thêm `pytest-cov` vào nhóm dev)

#### Báo cáo cá nhân

- [ ] `report/<MSSV>_HoTen.md` (theo mẫu `report/individual_report.md`)
- [ ] Mục "Ingestion" trong `group_report.md` (mục 5: nguồn dữ liệu, raw schema, retry/backoff)

---

### 👤 P2 — Data Model & Evaluation-set Owner

**File:** `src/ingestion/cleaning.py`, `src/evaluation/testset.py` · **Rubric:** #3 (15đ), #6 (10đ)

#### Việc cần làm — Cleaning (CP1)

- [ ] **`build_text_for_embedding(row) -> str`**: tách thành hàm public theo mẫu 5 phần ở mục 1.2b (P4 import lại)
- [ ] **`build_clean_dataframe(records, run_date) -> pd.DataFrame`**
  - [ ] Chuyển `records` thành DataFrame (`[asdict(r) for r in records]`)
  - [ ] Normalize text: bỏ tag JATS/HTML, `html.unescape`, `normalize_whitespace` cho `title`, `summary`; strip từng phần tử của `authors`/`categories`, bỏ phần tử rỗng
  - [ ] Parse `published`/`updated` bằng `pd.to_datetime(..., errors="coerce")`; bỏ dòng parse lỗi; **ghi lại dạng chuỗi `YYYY-MM-DD`**
  - [ ] `age_days = (run_date.date() - published.date()).days` (run_date có tz UTC)
  - [ ] Tạo `authors_joined`, `categories_joined`, `summary_chars`, `text_for_embedding`
  - [ ] Khử trùng lặp theo `paper_id` (`drop_duplicates(subset="paper_id", keep="first")`)
  - [ ] Lọc dòng xấu: `paper_id`/`title`/`summary` rỗng
  - [ ] Sort ổn định: `published` giảm dần, rồi `paper_id`; `reset_index(drop=True)`
  - [ ] Đảm bảo không còn `NaN` trong cột text (`fillna("")`)

**Tín hiệu (CP1):**

```bash
uv run python -c "from datetime import datetime, timezone; from core.config import load_settings; from ingestion.crossref import load_raw_records; from ingestion.cleaning import build_clean_dataframe; s=load_settings(); df=build_clean_dataframe(load_raw_records(s.paths.raw_records_json), datetime.now(timezone.utc)); print(f'Tín hiệu hoàn thành: Clean thành công {len(df)} dòng')"
```

- [ ] In ra `Clean thành công 24 dòng`
- [ ] `df["text_for_embedding"].iloc[0]` có đủ 5 phần

#### Việc cần làm — Test set (CP2)

- [ ] **`build_test_set(df, output_path) -> list[dict]`**
  - [ ] Kiểm tra `len(df) >= 10`, không đủ thì `raise ValueError`
  - [ ] Sinh **đúng 10 câu**, phủ đủ 4 loại, ví dụ 3 summary + 3 authors + 2 date + 2 categories
  - [ ] Chọn paper **tất định** (không random, hoặc cố định seed) và **rải đều**: có cả bài mới nhất (để lỗi "drop latest" gây ảnh hưởng) lẫn bài gốc và bài "Advanced Perspectives"
  - [ ] Ghi JSON bằng `write_json(output_path, items)`

**🔑 Câu hỏi phải khớp logic trích xuất của `src/retrieval/qa.py` (dòng 20–33):**

| Loại | Mẫu câu hỏi (bắt buộc có cụm từ khóa) | `ground_truth` = |
|---|---|---|
| `authors` | `Who authored the paper '{title}'?` | `row["authors_joined"]` |
| `date` | `When was the paper '{title}' published?` | `row["published"]` |
| `categories` | `What categories does the paper '{title}' belong to?` | `row["categories_joined"]` |
| `summary` | `Summarize the main contribution of the paper '{title}'.` (**không** chứa các cụm từ khóa ở trên) | `first_sentence(row["summary"])` |

- Tiêu đề **đặt trong nháy đơn `'...'`**, vì `qa.py` dùng regex `'([^']+)'` để tra đúng bài theo title. Tiêu đề có sẵn dấu `'` thì bỏ qua bài đó.
- `ground_truth_doc_ids = [row["paper_id"]]`

**Tín hiệu (CP2):**

```bash
uv run python -c "from core.config import load_settings; from evaluation.testset import build_test_set; import pandas as pd; s=load_settings(); df=pd.read_json(s.paths.clean_json); ts=build_test_set(df, s.paths.eval_testset); print(f'Tín hiệu hoàn thành: Sinh được {len(ts)} câu hỏi test')"
```

- [ ] In ra `Sinh được 10 câu hỏi test`
- [ ] Sau khi P4 chạy phase1: baseline `retrieval_hit_rate = 1.0` và `mean_token_f1` ≈ 1.0. Nếu thấp hơn, kiểm tra lại câu hỏi/ground truth.

#### Hỗ trợ (CP4–CP5)

- [ ] Review `corruption.py` của P4: 6 lỗi có đánh trúng các paper nằm trong test set không
- [ ] Xác minh `papers_clean_repaired.json` **giống hệt** `papers_clean.json` (so sánh `paper_id` + `text_for_embedding`)

#### Báo cáo

- [ ] `report/<MSSV>_HoTen.md`
- [ ] Mục "Clean schema / cleaning rules" và "Evaluation set" trong `group_report.md`

---

### 👤 P3 — Observability & Reporting Owner

**File:** `src/observability/quality.py`, `src/observability/reporting.py` · **Rubric:** #7 (15đ), một phần #6/#8 · **Bonus:** B1

#### Việc cần làm — Quality Gate GX 1.x (CP1)

- [ ] **`run_data_quality_checks(df, settings, report_name) -> dict`**
  - [ ] Ephemeral context **đúng cú pháp 1.x** (dùng tên theo `report_name` để không đụng nhau khi gọi nhiều lần):

    ```python
    import great_expectations as gx
    context = gx.get_context(mode="ephemeral")
    data_source = context.data_sources.add_pandas(name=f"{report_name}_source")
    data_asset = data_source.add_dataframe_asset(name=f"{report_name}_asset")
    batch_def = data_asset.add_batch_definition_whole_dataframe(f"{report_name}_batch")
    batch = batch_def.get_batch(batch_parameters={"dataframe": df})
    suite = context.suites.add(gx.ExpectationSuite(name=f"{report_name}_suite"))
    ```

  - [ ] Thêm **4 loại expectation bắt buộc** bằng `suite.add_expectation(gx.expectations.XXX(...))`:
    - [ ] `ExpectTableRowCountToBeBetween(min_value=int(settings.max_results*0.9), max_value=settings.max_results)`
    - [ ] `ExpectColumnValuesToNotBeNull(column=...)` cho `paper_id`, `title`, `summary`, `published`
    - [ ] `ExpectColumnValuesToBeUnique(column="paper_id")`
    - [ ] `ExpectColumnValueLengthsToBeBetween(column="title", min_value=8)` và `(column="summary", min_value=50)`
  - [ ] `results = batch.validate(suite)` rồi chuyển thành dict JSON-serializable (`results.to_json_dict()` hoặc tự duyệt `results.results`: `r.expectation_config.type`, `r.expectation_config.kwargs`, `r.success`, `r.result`)
  - [ ] Tích hợp Freshness vào Quality Gate: `success = gx_success and freshness["is_fresh"]`
  - [ ] Ghi report ra `settings.paths.quality_dir / f"{report_name}_quality_report.json"` (khớp `baseline_quality_report` / `corrupted_quality_report` trong config)
  - [ ] Lưu suite ra `settings.paths.gx_dir / f"{report_name}_suite.json"` (bằng chứng GX suite)
  - [ ] ❌ **Cấm cú pháp cũ 0.x** (trừ 10đ): `ge.from_pandas`, `df.expect_...`, `context.sources`, `get_validator`, `great_expectations.dataset`
- [ ] **`build_freshness_report(df, settings, report_path) -> dict`**
  - [ ] `stale_rows = (df["age_days"] > settings.freshness_threshold_days).sum()`
  - [ ] `stale_ratio = stale_rows / total_rows`; **`is_fresh = stale_ratio <= 0.25`**
  - [ ] Payload theo mục 1.2e, ép kiểu `int()`/`float()` (numpy int64 không `json.dumps` được)
  - [ ] `write_json(report_path, payload)`

**Tín hiệu (CP1).** Nên chạy bằng Git Bash, vì PowerShell escape `\"` rất khó:

```bash
uv run python -c "from core.config import load_settings; from observability.quality import run_data_quality_checks; import pandas as pd; s=load_settings(); df=pd.read_json(s.paths.clean_json); res=run_data_quality_checks(df, s, 'test'); print(f'Tín hiệu hoàn thành: Quality check status = {res[\"success\"]}')"
```

- [ ] Baseline: `Quality check status = True`. Hiện tại chỉ 1/24 bài (4%) có `age_days > 180`, nên fresh.
- [ ] Tự thử với df bị làm hỏng bằng tay (thêm dòng trùng, title `"abc"`) thì phải ra `False` và **không crash**.

#### Việc cần làm — Reporting (CP3, CP5)

- [ ] **`generate_phase1_report(report_path, source_summary, metrics, quality, freshness)`**, ghi Markdown gồm:
  - [ ] Nguồn: API, query, filter, số record, thời điểm chạy (lấy từ `source_summary`, do P4 truyền vào)
  - [ ] Bảng metrics: hit rate, token F1, judge accuracy, judge score
  - [ ] Bảng từng expectation: pass/fail
  - [ ] Freshness: latest/oldest, stale_ratio, is_fresh
- [ ] **`generate_corruption_report(...)`**, ghi Markdown gồm:
  - [ ] **Bảng 3 cột Baseline | Corrupted | Repaired** cho 4 metric, kèm cột Δ (Corrupted − Baseline)
  - [ ] Bảng Quality Gate: từng expectation Corrupted vs Repaired (✅/❌)
  - [ ] Bảng Freshness: Corrupted vs Repaired
  - [ ] Phần tóm tắt corruption log: đọc `settings.paths.corruption_log`, hoặc nhờ P4 thêm tham số
  - [ ] Đoạn **phân tích tự sinh từ số liệu** (không viết cứng số), ví dụ: "Hit rate giảm X → Y; Quality Gate phát hiện N/M expectation fail; repair khôi phục về Z"
  - [ ] Ghi chú hiện tượng **Silent Failure**: pipeline vẫn chạy exit 0 nhưng chất lượng câu trả lời sụt
- [ ] **Mọi con số trong report phải lấy từ tham số truyền vào.** Cấm gõ tay (trừ 20đ).

#### Bonus B1 — Dashboard (+5đ, CP5)

- [ ] `generate_dashboard(...)` sinh `data/reports/dashboard.html` tĩnh, đọc từ các JSON trong `data/quality/` và `data/results/`
  - Trạng thái pass/fail của từng Quality Gate
  - Histogram `age_days`, có vạch ngưỡng 180
  - Biểu đồ cột 3 trạng thái metrics
- [ ] (Hoặc) `streamlit run` app nhỏ, nhưng sẽ phải thêm dependency

#### Báo cáo

- [ ] `report/<MSSV>_HoTen.md`
- [ ] Các mục Observability, Kết quả, Phân tích trong `group_report.md`

---

### 👤 P4 — Trưởng nhóm: Corruption & Integration Owner

**File:** `src/ingestion/corruption.py`, `src/pipelines/phase1.py`, `src/pipelines/corruption_flow.py` · **Rubric:** #8 (15đ), #4–#5 (tích hợp), #1 · **Bonus:** B2

#### Việc cần làm — Corruption (CP1–CP4)

- [ ] **`corrupt_clean_dataframe(df, output_log_path) -> pd.DataFrame`**
  - [ ] Làm việc trên `df.copy()`, dùng `seed = 42` cố định (`df.sample(..., random_state=42)`), để chạy lại nhiều lần vẫn ra kết quả giống nhau
  - [ ] **6 kịch bản** theo thứ tự, mỗi kịch bản ghi log `{"type", "description", "affected_paper_ids", "count"}`:
    1. [ ] `drop_latest`: bỏ 20% số bài có `published` mới nhất (24 bài → bỏ 5)
    2. [ ] `blank_summary`: `summary = ""` ở khoảng 25% số dòng (**không dùng `None`/`NaN`**)
    3. [ ] `inject_noise`: chèn ký tự rác (`"#@$%&*"`, token ngẫu nhiên) vào đầu/giữa `summary` ở khoảng 25% số dòng khác
    4. [ ] `truncate_title`: `title = title[:6]` (< 8 ký tự) ở khoảng 25% số dòng, làm hỏng việc tra đúng bài theo title
    5. [ ] `stale_date`: lùi `published` về quá khứ khoảng 400 ngày ở **≥ 35%** số dòng, rồi **tính lại `age_days`**. Phải vượt ngưỡng 25% thì Freshness mới báo `is_fresh=False`.
    6. [ ] `duplicate_rows`: nhân bản khoảng 3 dòng, làm `paper_id` không còn unique
  - [ ] Tính lại `summary_chars`, `authors_joined`, `categories_joined`, và `text_for_embedding` (import `build_text_for_embedding` từ `cleaning.py`)
  - [ ] Ghi log: `write_json(output_log_path, {"seed": 42, "input_rows": ..., "output_rows": ..., "corruptions": [...]})`
- [ ] Nhờ P2 kiểm tra các lỗi có đánh trúng paper nằm trong test set

#### Việc cần làm — `phase1.py` (CP2–CP3)

```python
settings = load_settings()
records = fetch_source_records(settings)                                  # P1
df = build_clean_dataframe(records, now_utc())                            # P2
write_csv(df, settings.paths.clean_csv)
df.to_json(settings.paths.clean_json, orient="records", indent=2, force_ascii=False)
index = LocalEmbeddingIndex.build(df, settings, settings.paths.embeddings_json)   # -> "papers-baseline"
if settings.refresh_test_set or not settings.paths.eval_testset.exists():
    build_test_set(df, settings.paths.eval_testset)                        # P2
bundle = evaluate_pipeline(settings, index, settings.paths.eval_testset,
                           settings.paths.baseline_metrics, settings.paths.baseline_answers)
quality = run_data_quality_checks(df, settings, "baseline")                # P3
freshness = build_freshness_report(df, settings, settings.paths.freshness_report)
generate_phase1_report(settings.paths.baseline_report, source_summary, bundle.summary, quality, freshness)
```

- [ ] `clean_json` **phải** dùng `orient="records"`, vì các lệnh kiểm tra CP1/CP2 đọc bằng `pd.read_json`
- [ ] `source_summary`: `source_api`, `source_query`, `source_filter`, `record_count`, `clean_rows`, `run_at`
- [ ] (Tuỳ chọn) Demo agent vài câu, ghi vào `settings.paths.demo_answers`. **Bọc trong `try/except`**, vì không có API key thì agent lỗi.
- [ ] In tóm tắt ra console; chạy `uv run python script/run_phase1.py` phải trả **exit code 0**

#### Việc cần làm — `corruption_flow.py` (CP4–CP5)

- [ ] Nạp `baseline_metrics` (`read_json`) và `df` từ `clean_json` (`pd.read_json(path, dtype=False, convert_dates=False)` để giữ nguyên kiểu)
- [ ] **Corrupted:** `corrupt_clean_dataframe` → lưu `corrupted_clean_csv/json` → `LocalEmbeddingIndex.build(..., settings.paths.corrupted_embeddings_json)` (collection `papers-corrupted`) → `evaluate_pipeline` → `corrupted_metrics` / `corrupted_answers`
- [ ] Chạy `run_data_quality_checks(corrupted, settings, "corrupted")` và freshness (ghi vào `quality_dir / "corrupted_freshness_report.json"`)
- [ ] **Repair (idempotent):** `load_raw_records(raw_records_json)` → `build_clean_dataframe` → lưu `repaired_clean_*` → build index với `repaired_embeddings_json` (collection `papers-repaired`) → evaluate → `repaired_metrics` / `repaired_answers` → quality `"repaired"` + freshness
  - Idempotent: repair **luôn dựng lại từ raw** (không vá dữ liệu bẩn), và `build()` xóa collection cũ trước khi tạo mới, nên chạy N lần vẫn cho cùng kết quả
- [ ] **Cùng một `test_set.json`** cho cả 3 trạng thái. Không sinh lại test set trong flow này.
- [ ] `generate_corruption_report(...)` (P3), rồi **in bảng 3 trạng thái ra console**
- [ ] `uv run python script/run_corruption_flow.py` trả **exit code 0**

#### Bonus B2 — Auto-repair (+5đ, CP5)

- [ ] Trong `corruption_flow`: `if not corrupted_quality["success"]:` thì log `"Quality Gate FAILED → auto-trigger repair"` và tự gọi repair, không cần thao tác tay
- [ ] Sau repair, chạy lại Quality Gate. Nếu vẫn fail thì dừng (`raise`/`exit 1`) và **không** publish dữ liệu
- [ ] Ghi lại quyết định (gate fail → repair → gate pass) vào report/log làm bằng chứng

#### Việc lặt vặt của trưởng nhóm

- [ ] (1 dòng) Thêm alias `"google" → "gemini"` trong `normalized_provider` (`core/config.py`), vì rubric #5 gọi provider là `google`
- [ ] Điền `docs/TEAM.md`: tên nhóm, 4 thành viên, MSSV, email, vai trò. **Phần tự khai đóng góp do từng người tự viết**, thiếu sẽ bị trừ 5đ mỗi người.
- [ ] Đặt tên repo theo quy ước: `K4-L3B-DAY10-<TenNhom>-DataPipelineDataObservability`
- [ ] Chạy lại toàn bộ trên clone sạch trước khi nộp (xem Mục 4)
- [ ] Ghi chú: `data/embeddings/*.json` lưu `persist_path` dạng đường dẫn tuyệt đối (do `index.py` có sẵn). Đây là artifact chứ không phải code, nhưng cần nói rõ khi Q&A.

#### Báo cáo

- [ ] `report/<MSSV>_HoTen.md`
- [ ] Chịu trách nhiệm chính `report/group_report.md` (tổng hợp phần mọi người viết), mục Cách tái hiện và Corruption/Repair

---

## 4. Checklist nghiệm thu cuối (P4 chủ trì, cả nhóm cùng rà)

### Chạy được end-to-end

- [ ] `uv run python script/run_phase1.py` trả exit 0
- [ ] `uv run python script/run_corruption_flow.py` trả exit 0
- [ ] Clone repo ra thư mục mới → `uv sync` → chạy lại 2 lệnh trên vẫn OK (không phụ thuộc file chỉ có trên máy mình)

### Artifacts đủ (commit lên Git)

- [ ] `data/raw/crossref_response.json`, `crossref_records.json`
- [ ] `data/clean/papers_clean.csv`, `papers_clean.json` (+ các bản `_corrupted`, `_repaired`)
- [ ] `data/chroma/` (3 collection: baseline / corrupted / repaired)
- [ ] `data/embeddings/*.json`
- [ ] `data/eval/test_set.json` (10 câu, 4 loại)
- [ ] `data/quality/`: baseline, corrupted, repaired quality + freshness reports, `gx/*_suite.json`
- [ ] `data/results/`: `baseline_metrics.json`, `corrupted_metrics.json`, `repaired_metrics.json`, `corruption_log.json` (+ `*_answers.json`)
- [ ] `data/reports/phase1_report.md`, `corruption_report.md` (bảng 3 trạng thái)

### Kết quả phải đúng logic

- [ ] Baseline: Quality `success=True`, `is_fresh=True`, hit rate cao
- [ ] Corrupted: Quality `success=False` (unique/length/freshness fail), metrics **giảm rõ rệt**
- [ ] Repaired: Quality `success=True`, metrics **trở về bằng baseline**
- [ ] Số trong report khớp 100% với file JSON

### Tài liệu & quy định

- [ ] `docs/TEAM.md` điền đủ, mỗi người **tự khai đóng góp**
- [ ] `report/group_report.md` đã thay hết `[ ]`
- [ ] 4 file `report/<MSSV>_HoTen.md`
- [ ] `docs/CHECKPOINTS.md`, `RUBRIC.md`, `SUBMISSION.md` còn nguyên (thiếu thì trừ 5đ mỗi file)
- [ ] `git log --all -p | grep -i "api_key="` không lộ key; `.env` không nằm trong repo
- [ ] Không có đường dẫn `C:\` / `D:\` trong `src/`, `script/`
- [ ] GitHub **Insights → Contributors**: đủ 4 người
- [ ] **Cả 4 người** tự nộp link repo lên VLearn LMS trước **23:59:59**

---

## 5. Chuẩn bị Q&A (ai cũng phải trả lời được)

1. **GX 1.x khác 0.x ở đâu?** Dùng context → data source → asset → batch definition → batch, và `batch.validate(suite)`; expectation là class `gx.expectations.*`, không gọi `df.expect_*`.
2. **Freshness SLA tính thế nào?** `age_days > 180` là stale; nếu stale_ratio > 25% thì `is_fresh=False`, và Quality Gate fail.
3. **Silent Failure là gì?** Pipeline không báo lỗi, vẫn exit 0, nhưng agent trả lời sai hoặc rỗng vì dữ liệu bẩn. Quality Gate tồn tại để bắt lỗi này *trước* khi dữ liệu vào index.
4. **Vì sao repair là idempotent?** Luôn dựng lại từ raw snapshot bất biến, và index được xóa rồi tạo lại, nên chạy N lần vẫn cùng kết quả.
5. **Vì sao tách 3 collection ChromaDB?** Để cô lập không gian vector, so sánh công bằng trên cùng test set.
6. **Lỗi nào làm metric giảm mạnh nhất, vì sao?** Trả lời bằng số liệu thật trong `corruption_report.md`.
7. **Embedding:** `all-MiniLM-L6-v2`, 384 chiều, normalize, khoảng cách cosine.
