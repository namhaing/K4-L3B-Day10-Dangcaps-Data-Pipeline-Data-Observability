# Kịch bản demo thuyết trình

## Mở đầu

> Nhóm em xây dựng pipeline RAG trên 24 bài báo. Nhóm kiểm tra dữ liệu, đo chất lượng khi dữ liệu bị lỗi và tự phục hồi từ raw snapshot.

Luồng: `Raw → Clean → Embedding/ChromaDB → Baseline → Corruption → Quality Gate → Repair`.

## Baseline

Chạy tại thư mục gốc:

```powershell
.\.venv\Scripts\python.exe script\run_phase1.py
```

Giải thích: đọc raw, cleaning, quality gate, embedding, ChromaDB, evaluation set 10 câu hỏi, metrics và report.

Kết quả cần chỉ:

```text
raw=24 clean=24
retrieval_hit_rate=1.0000
mean_token_f1=1.0000
judge_accuracy=1.0000
mean_judge_score=5.0000
quality_gate=PASS
is_fresh=True
```

> Baseline đạt toàn bộ chỉ số. Dữ liệu sạch đủ điều kiện đưa vào serving.

## Phần Observability của Tâm

Mở `data/quality/baseline_quality_report.json` và nói:

> Quality Gate dùng Great Expectations 1.x để kiểm tra số dòng, dữ liệu null, ID trùng và độ dài title/summary. Freshness kiểm tra bài có `age_days > 180`. Baseline có 24 dòng, 1/24 bài stale, khoảng 4,17%, thấp hơn ngưỡng 25%, nên gate PASS.

Các expectation gồm: số dòng 21–24; bốn cột chính không null; `paper_id` unique; title ít nhất 8 ký tự; summary ít nhất 50 ký tự.

## Corruption và repair

Chạy:

```powershell
.\.venv\Scripts\python.exe script\run_corruption_flow.py
```

Nói:

> Pipeline tạo dữ liệu bẩn, kiểm tra Quality Gate, vẫn đánh giá corrupted để đo silent failure, sau đó tự động repair từ `data/raw/crossref_records.json` và đánh giá lại.

Mở `data/results/corruption_log.json`:

> Sáu lỗi gồm xóa 5 bài mới nhất, làm rỗng 5 summary, chèn noise vào 5 summary, cắt title của 5 bài, lùi ngày 7 bài 400 ngày và thêm 3 dòng trùng. Seed 42 giúp kết quả tái lập.

## Bảng kết quả

Mở `data/reports/corruption_report.md`:

| Metric | Baseline | Corrupted | Repaired |
|---|---:|---:|---:|
| Retrieval hit rate | 1.0000 | 0.7000 | 1.0000 |
| Mean token F1 | 1.0000 | 0.7630 | 1.0000 |
| Judge accuracy | 1.0000 | 0.8000 | 1.0000 |
| Mean judge score | 5.0000 | 3.8000 | 5.0000 |
| Quality Gate | PASS | FAIL | PASS |

Câu kết luận:

> Dữ liệu bẩn làm hit rate giảm từ 1.0 xuống 0.7 và judge score giảm từ 5 xuống 3.8. Pipeline vẫn chạy nhưng Quality Gate phát hiện dữ liệu không an toàn. Repair dựng lại 24 dòng từ raw và khôi phục metrics về baseline.

## Câu hỏi thường gặp

**Vì sao dùng cùng test set?** Để so sánh công bằng giữa ba trạng thái.

**Vì sao Quality Gate cần khi pipeline không crash?** Vì dữ liệu bẩn có thể không gây lỗi chương trình nhưng làm câu trả lời sai; đó là silent failure.

**Vì sao repair đọc raw?** Raw là nguồn đáng tin cậy; dựng lại từ raw tránh bỏ sót lỗi và có tính idempotent.

**`age_days > 180` là gì?** Bài báo đã quá 180 ngày. Nếu hơn 25% bài stale thì Freshness fail.

**ChromaDB làm gì?** Lưu vector embedding và tìm tài liệu gần nhất với câu hỏi. Ba trạng thái dùng `papers-baseline`, `papers-corrupted`, `papers-repaired`.

## Files cần mở

- `data/reports/phase1_report.md`
- `data/reports/corruption_report.md`
- `data/results/corruption_log.json`
- `data/results/self_healing_log.json`
