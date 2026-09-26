# Danh Sách Thành Viên & Báo Cáo Phân Công Nhóm

- **Tên Nhóm:** `Dangcaps`
- **Mã Nhóm / Lớp:** `K4-L3B-DAY10`
- **Tên Repository Nộp Bài:** `K4-L3B-Day10-Dangcaps-Data-Pipeline-Data-Observability`
- **Link Repository:** https://github.com/namhaing/K4-L3B-Day10-Dangcaps-Data-Pipeline-Data-Observability
- **Phân công chi tiết & Data Contract:** [`docs/PHAN_CONG.md`](PHAN_CONG.md)

---

## # Thành viên

| STT | Họ và tên | MSSV | Email | Vai trò & Phân công công việc | Báo cáo cá nhân |
|---:|---|---|---|---|---|
| 1 | Nguyễn Hải Nam | 2A202602476 | namhaii631@gmail.com | **Trưởng nhóm** — Corruption & Integration (`ingestion/corruption.py`, `pipelines/phase1.py`, `pipelines/corruption_flow.py`, bonus B2 auto-repair, tích hợp & chạy bản cuối) | `report/2A202602476_NguyenHaiNam.md` |
| 2 | Đồng Mạnh Hùng | 2A202602412 | donghung729@gmail.com | Source Owner — Ingestion & Raw Lineage (`ingestion/crossref.py`, `data/raw/`) | `report/2A202602412_DongManhHung.md` |
| 3 | Nguyễn Đình Anh | 2A202602573 | nguyenanhcx04@gmail.com | Data Model & Evaluation-set Owner (`ingestion/cleaning.py`, `evaluation/testset.py`) | `report/2A202602573_NguyenDinhAnh.md` |
| 4 | Nguyễn Trần Bảo Tâm | 2A202602408 | ntbtbaotam@gmail.com | Observability & Reporting Owner (`observability/quality.py` GX 1.x + Freshness SLA, `observability/reporting.py`) | `report/2A202602408_NguyenTranBaoTam.md` |

**Luồng phụ thuộc giữa các phần:** Hùng (raw records) → Anh (clean dataframe, test set) → Bảo Tâm (quality gate, report) → Nam (ghép thành `run_phase1.py` và `run_corruption_flow.py`). Toàn bộ nhánh cá nhân được merge vào nhánh tích hợp của trưởng nhóm, rồi vào `main`.

---

## # Cá nhân

### ## NguyenHaiNam-2A202602476
- **Vai trò:** Trưởng nhóm — Corruption & Integration Owner.
- **Công việc chi tiết đã hoàn thành:**
  - Lập phân công, timeline theo checkpoint và chốt Data Contract dùng chung (raw schema, clean schema, test set, kết quả quality) trong `docs/PHAN_CONG.md`.
  - Viết `src/ingestion/corruption.py`: tiêm 6 loại lỗi có kiểm soát (seed 42) — `drop_latest`, `blank_summary`, `inject_noise`, `truncate_title`, `stale_date` (≥ 35% số dòng để vượt ngưỡng Freshness 25%), `duplicate_rows` — và ghi `data/results/corruption_log.json` gồm các `paper_id` bị ảnh hưởng.
  - Viết `src/pipelines/phase1.py`: fetch → clean → Quality Gate + freshness → index `papers-baseline` → test set → evaluate → `phase1_report.md`; demo agent có xử lý lỗi khi thiếu API key.
  - Viết `src/pipelines/corruption_flow.py`: đánh giá 3 trạng thái trên cùng test set, in bảng so sánh ra console, sinh `corruption_report.md`.
  - **Bonus B2 (Self-healing):** Quality Gate fail thì tự động repair từ raw snapshot, kiểm tra lại gate, và chặn publish nếu vẫn fail; bằng chứng ở `data/results/self_healing_log.json`.
  - Tích hợp: merge 3 nhánh thành viên; integration fix trong `crossref.py` (mặc định đọc snapshot, chỉ gọi API khi `REFRESH_SOURCE=1`); thêm alias provider `google` → `gemini`; chạy bản cuối với `openai / gpt-4.1-mini`.
- **Kết quả / bằng chứng:** Baseline → Corrupted → Repaired: hit rate 1.000 → 0.700 → 1.000, judge accuracy 1.000 → 0.600 → 1.000; Quality Gate PASS → FAIL → PASS (`data/results/*_metrics.json`, `data/reports/corruption_report.md`).
- **Điều học được / Đóng góp chính:**
  - Repair an toàn phải dựng lại từ nguồn raw bất biến chứ không vá dữ liệu bẩn; đó là lý do cần lưu raw snapshot (data lineage) và lý do pipeline idempotent.
  - Có lỗi Quality Gate không bắt được (chèn nhiễu vào summary): phải đo cả metric của RAG, không chỉ kiểm tra schema.

### ## DongManhHung-2A202602412
- **Vai trò:** Source Owner — Ingestion & Raw Lineage.
- **Công việc chi tiết đã hoàn thành:**
  - Viết `parse_crossref_payload()` trong `src/ingestion/crossref.py`: đọc `message.items`, lấy DOI, title, abstract (bỏ tag JATS), authors, subject, ngày `published`/`updated`/`created`, URL/PDF; bỏ record thiếu DOI hoặc title.
  - Viết `fetch_source_records()`: gọi Crossref REST API, retry tối đa 5 lần với backoff khi gặp 429/5xx hoặc lỗi mạng, fallback về snapshot `data/raw/crossref_response.json` → `crossref_records.json`; lưu 2 file raw artifact.
  - Viết `load_raw_records()` để map JSON snapshot thành `PaperRecord`.
  - Viết phiên bản cleaning đầu tiên để kiểm tra đầu ra ingestion trước khi có bản chính thức của P2.
- **Kết quả / bằng chứng:** Parse snapshot ra 24 bài, khớp 100% `data/raw/crossref_records.json`; khi mất mạng vẫn fallback đủ 24 bài. Tín hiệu CP0: `Đã tải 24 bài báo`.
- **Điều học được / Đóng góp chính:**
  - Bảo toàn raw snapshot trước mọi bước biến đổi để truy vết nguồn gốc dữ liệu và phục hồi khi cần.
  - Thiết kế ingestion chịu lỗi (retry, backoff, fallback offline) để pipeline không phụ thuộc vào tình trạng mạng.

### ## NguyenDinhAnh-2A202602573
- **Vai trò:** Data Model & Evaluation-set Owner.
- **Công việc chi tiết đã hoàn thành:**
  - Viết `build_clean_dataframe()` trong `src/ingestion/cleaning.py`: bỏ tag JATS/HTML, `html.unescape`, chuẩn hóa khoảng trắng; làm sạch danh sách authors/categories; parse ngày và loại dòng có ngày lỗi, trả về dạng `YYYY-MM-DD`; tính `age_days`, `authors_joined`, `categories_joined`, `summary_chars`; khử trùng theo `paper_id`; lọc dòng thiếu trường bắt buộc; sắp xếp ổn định.
  - Tách hàm public `build_text_for_embedding(row)` (5 phần Title / Authors / Published / Categories / Summary), dùng chung cho cleaning và corruption.
  - Viết `build_test_set()` trong `src/evaluation/testset.py`: 10 câu (3 summary, 3 authors, 2 date, 2 categories), ground truth khớp logic trích xuất của `qa.py`; bỏ các title không an toàn cho QA (có dấu `'`, chứa từ khóa, trùng tên); chọn tất định, phủ cả bài mới nhất lẫn nhóm "Advanced Perspectives".
- **Kết quả / bằng chứng:** Tín hiệu CP1 `Clean thành công 24 dòng` (không NaN, không trùng id); CP2 `Sinh được 10 câu hỏi test`, chạy lại ra cùng bộ câu hỏi; baseline hit rate 1.000 trên test set này.
- **Điều học được / Đóng góp chính:**
  - Chất lượng `text_for_embedding` và schema sạch quyết định trực tiếp chất lượng retrieval.
  - Test set phải cố định và có ground-truth document ID thì mới so sánh công bằng được giữa các trạng thái dữ liệu.

### ## NguyenTranBaoTam-2A202602408
- **Vai trò:** Observability & Reporting Owner.
- **Công việc chi tiết đã hoàn thành:**
  - Viết `run_data_quality_checks()` trong `src/observability/quality.py` theo chuẩn **Great Expectations 1.x** (ephemeral context → pandas data source → dataframe asset → batch definition → batch, `batch.validate(suite)`), gồm 8 expectation thuộc 4 loại bắt buộc: row count, not null (`paper_id`, `title`, `summary`, `published`), unique `paper_id`, độ dài `title` ≥ 8 và `summary` ≥ 50.
  - Tích hợp Freshness SLA vào Quality Gate (`success = GX pass và is_fresh`); `build_freshness_report()` tính `stale_ratio` với ngưỡng `age_days > 180` và tối đa 25%.
  - Ghi quality report, freshness report và GX suite JSON vào `data/quality/` và `data/quality/gx/`.
  - Viết `generate_phase1_report()` và `generate_corruption_report()` trong `src/observability/reporting.py`: mọi số liệu lấy từ tham số truyền vào, không viết cứng.
  - Viết script tự kiểm tra `script/check_observability.py`.
- **Kết quả / bằng chứng:** Baseline PASS 8/8 và fresh (stale 4.2%); corrupted FAIL 3/8 (unique `paper_id`, độ dài `title`, độ dài `summary`) và stale 40.9%; repaired PASS 8/8 (`data/quality/*_quality_report.json`).
- **Điều học được / Đóng góp chính:**
  - Quality Gate phải chặn dữ liệu xấu trước khi vào serving layer; freshness là tín hiệu riêng, khác với kiểm tra schema.
  - Báo cáo chỉ nên sinh từ artifact thực tế để tránh sai lệch số liệu.
