# Kịch bản demo thuyết trình nhóm

## Mở đầu

> Nhóm em xây dựng pipeline RAG dùng metadata của 24 bài báo. Mục tiêu là kiểm tra dữ liệu, đo mức suy giảm khi dữ liệu bị lỗi và tự phục hồi từ raw snapshot.

Luồng: `Raw → Clean → Embedding/ChromaDB → Baseline → Corruption → Quality Gate → Repair`.

## Baseline

Chạy tại thư mục gốc:

```powershell
.\.venv\Scripts\python.exe script\run_phase1.py
```

> Pipeline đọc 24 raw records, làm sạch, chạy Quality Gate, tạo embedding bằng `all-MiniLM-L6-v2`, nạp `papers-baseline`, dùng evaluation set 10 câu hỏi và ghi metrics.

Kết quả cần nói:

```text
raw=24 clean=24
retrieval_hit_rate=1.0000
mean_token_f1=1.0000
judge_accuracy=1.0000
mean_judge_score=5.0000
quality_gate=PASS
is_fresh=True
```

## Phần P3 — Observability

> Quality Gate dùng Great Expectations 1.x để kiểm tra số dòng, giá trị null, ID trùng và độ dài title/summary. Freshness kiểm tra bài có `age_days > 180`. Baseline có 1/24 bài stale, khoảng 4,17%, thấp hơn ngưỡng 25%, nên gate PASS.

Các kiểm tra gồm số dòng 21–24; bốn cột chính không null; `paper_id` unique; title ít nhất 8 ký tự; summary ít nhất 50 ký tự.

Mở `data/quality/baseline_quality_report.json` để chứng minh kết quả.

## Corruption và repair

Chạy:

```powershell
.\.venv\Scripts\python.exe script\run_corruption_flow.py
```

> Pipeline tạo dữ liệu bẩn, chạy Quality Gate, vẫn đánh giá corrupted để đo silent failure, sau đó repair từ `data/raw/crossref_records.json` và đánh giá lại.

Mở `data/results/corruption_log.json`:

> Sáu lỗi gồm xóa 5 bài mới nhất, làm rỗng 5 summary, chèn noise vào 5 summary, cắt title của 5 bài còn 6 ký tự, lùi ngày 7 bài 400 ngày và thêm 3 dòng trùng. Seed 42 giúp kết quả tái lập.

## Repair

> Khi Quality Gate corrupted fail, pipeline không sửa thủ công từng dòng. Nó đọc raw snapshot, cleaning lại, tạo repaired dataframe, embedding mới và collection `papers-repaired`. Đây là rollback từ nguồn chuẩn và có tính idempotent.

Mở `data/results/self_healing_log.json` và chỉ:

```text
corrupted gate: false
repair trigger: auto: quality gate failed
repaired gate: true
```

## Bảng kết quả

Mở `data/reports/corruption_report.md`:

| Metric | Baseline | Corrupted | Repaired |
|---|---:|---:|---:|
| Retrieval hit rate | 1.0000 | 0.7000 | 1.0000 |
| Mean token F1 | 1.0000 | 0.7630 | 1.0000 |
| Judge accuracy | 1.0000 | 0.8000 | 1.0000 |
| Mean judge score | 5.0000 | 3.8000 | 5.0000 |
| Quality Gate | PASS | FAIL | PASS |

> Dữ liệu bẩn làm hit rate giảm từ 1 xuống 0,7 và judge score giảm từ 5 xuống 3,8. Sau repair, 24 dòng được dựng lại từ raw, Quality Gate pass và metrics quay về baseline.

## Kết luận

> RAG cần dữ liệu đáng tin cậy. Observability phát hiện dữ liệu không an toàn trước khi nhóm tin vào agent. Repair từ raw snapshot giúp pipeline phục hồi có kiểm soát và tái lập.

## Câu hỏi thường gặp

**Vì sao dùng cùng test set?** Để so sánh công bằng giữa baseline, corrupted và repaired.

**Vì sao Quality Gate cần khi pipeline không crash?** Vì chương trình có thể chạy thành công nhưng câu trả lời đã sai. Đó là silent failure.

**Vì sao repair từ raw không vô nghĩa?** Mục tiêu là kiểm tra rollback và rebuild từ nguồn chuẩn. Nếu raw cũng sai, hệ thống thực tế cần backup phiên bản khác hoặc re-fetch.

**Freshness khác Quality checks thế nào?** Quality checks kiểm tra tính hợp lệ của dòng và cột; Freshness kiểm tra tuổi dữ liệu trên toàn bộ tập.

**Vì sao dùng ba collection?** Để cô lập `papers-baseline`, `papers-corrupted`, `papers-repaired` và so sánh công bằng.
