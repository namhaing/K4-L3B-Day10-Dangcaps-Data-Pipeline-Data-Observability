# Member Role Report — Day 10: Data Pipeline & Data Observability

## 1. Thông tin cá nhân

| Thông tin | Nội dung |
| --- | --- |
| Họ và tên | Nguyễn Đình Anh |
| MSSV | 2A202602573 |
| Khóa/Lớp | K4 |
| Tên nhóm | Dangcaps |
| Vai trò chính | P2 — Data Model & Evaluation-set Owner |
| Repository | https://github.com/namhaing/K4-L3B-Day10-Dangcaps-Data-Pipeline-Data-Observability/tree/anh02573 |
| Ngày hoàn thành | 2026-09-26 |

## 2. Vai trò và phạm vi công việc

Tôi phụ trách CP1 Cleaning và CP2 Evaluation Test Set.

| Phần việc | File/hàm | Input | Output | Trạng thái |
| --- | --- | --- | --- | --- |
| Dựng text embedding | `src/ingestion/cleaning.py`: `build_text_for_embedding` | Row đã clean | Chuỗi 5 phần | Đã implement và kiểm tra |
| Cleaning | `src/ingestion/cleaning.py`: `build_clean_dataframe` | `list[PaperRecord]`, `run_date` UTC | DataFrame 16 cột | Đã kiểm tra 24 dòng trên snapshot |
| Evaluation set | `src/evaluation/testset.py`: `build_test_set` | Clean DataFrame, output path | 10 câu hỏi và ground truth | Đã implement và kiểm tra |

Tôi phối hợp kiểm tra contract P1 → P2, phát hiện ngày `updated` rỗng ở snapshot P1 và xác minh lại sau khi P1 sửa. Tôi giữ public helper dựng text để P4 tái sử dụng, đồng thời phân tích conflict khi tích hợp main và kiểm tra các điểm gọi của P1/P4.

Fetch/parse Crossref thuộc P1; quality/freshness và reporting tự động thuộc P3; orchestration, corruption và repair thuộc P4. Tôi không nhận các implementation này là đóng góp của mình.

## 3. Kết quả theo vai trò

| Nội dung | Kết quả đã xác minh | Cách kiểm tra |
| --- | --- | --- |
| Cleaning | 24 dòng, 16 cột, 24 ID unique | Loader P1 → cleaning P2 trên snapshot thật |
| Schema/text | Ngày dạng chuỗi, không null, text đủ 5 phần | Kiểm tra DataFrame và từng row |
| Ca biên | HTML/entities, whitespace, null/list, ngày lỗi, field rỗng, duplicate, input rỗng | Assertions trực tiếp |
| Test set | 10 câu: 3 summary, 3 authors, 2 date, 2 categories | Đếm loại câu, đối chiếu DOI/title/ground truth |
| Tính tái lập | Chạy lại hoặc đảo thứ tự input vẫn cùng kết quả | So sánh items và JSON |
| QA | Đáp án khớp ground truth trong kiểm tra extraction/lookup | Dùng QA thực tế với index giả lập phần lookup |
| P4 | Corruption gọi helper được, kể cả summary rỗng | Chạy kiểm tra với ghi log được mock |

Artifacts đã đọc để xác nhận số lượng: `data/clean/papers_clean.json` có 24 dòng/16 cột và `data/eval/test_set.json` có 10 câu đúng phân bổ. Các kiểm tra ca biên được chạy trực tiếp, chưa được đóng gói thành bộ pytest lưu trong repo.

## 4. Giải thích phần kỹ thuật đã thực hiện

### CP1 — Cleaning

1. Chuyển dataclass bằng `asdict`, giữ 11 trường raw.
2. Xử lý null text; strip ID; bỏ tag JATS/HTML, `html.unescape` và normalize whitespace cho title/summary.
3. Strip từng phần tử authors/categories, bỏ phần tử rỗng và xử lý list null.
4. Parse published/updated với `errors="coerce"`; loại dòng nếu một trong hai ngày không hợp lệ; xuất ngày thành `YYYY-MM-DD`.
5. Tính `age_days = (run_date.date() - published.date()).days`.
6. Tạo `authors_joined`, `categories_joined`, `summary_chars`, `text_for_embedding`.
7. Deduplicate theo `paper_id`, giữ bản đầu tiên; loại ID/title/summary rỗng.
8. Sort ổn định theo published giảm dần rồi paper_id tăng dần; reset index.

Hàm public dựng text được dùng chung với P4:

```text
Title: <title>
Authors: <authors_joined>
Published: <published>
Categories: <categories_joined>
Summary: <summary>
```

Helper vẫn dựng dòng `Summary: ` khi summary rỗng để phục vụ corruption. Cleaning không tự loại bài cũ theo freshness hoặc summary chỉ vì ngắn hơn một ngưỡng tùy ý.

### CP2 — Evaluation set

Hàm yêu cầu ít nhất 10 dòng và đủ 10 ứng viên hợp lệ. Title có nháy đơn, trùng khi so sánh không phân biệt hoa thường, hoặc có keyword gây QA phân loại nhầm được bỏ qua. Các field làm câu hỏi/đáp án phải là chuỗi không rỗng.

Các paper được sort theo ngày và ID, chọn 10 vị trí trải đều, gồm hai đầu mới nhất/cũ nhất và cả bài gốc lẫn “Advanced Perspectives”. Nếu cần, thay một vị trí giữa để bổ sung nhóm còn thiếu; nếu không thể đáp ứng contract thì báo `ValueError`. Không dùng random.

| Loại | Số câu | Ground truth |
| --- | ---: | --- |
| summary | 3 | `first_sentence(row["summary"])` |
| authors | 3 | `row["authors_joined"]` |
| date | 2 | `row["published"]` |
| categories | 2 | `row["categories_joined"]` |

Mỗi item có `id`, `question_type`, `question`, `ground_truth`, `ground_truth_doc_ids`. Title nằm trong nháy đơn đúng regex QA; document ID là `paper_id`, không phải ID nội bộ Chroma. Kết quả ghi bằng `write_json`.

### Lệnh tái kiểm tra CP1

Chạy từ thư mục gốc project sau khi cài môi trường:

```bash
uv run python -c "from datetime import datetime, timezone; from core.config import load_settings; from ingestion.crossref import load_raw_records; from ingestion.cleaning import build_clean_dataframe; s=load_settings(); df=build_clean_dataframe(load_raw_records(s.paths.raw_records_json), datetime.now(timezone.utc)); print('rows=', len(df)); print('columns=', len(df.columns)); print('unique_ids=', df['paper_id'].nunique())"
```

Kết quả mong đợi trên snapshot đã kiểm tra: `rows=24`, `columns=16`, `unique_ids=24`.

## 5. Một quyết định kỹ thuật quan trọng

Tôi tách `build_text_for_embedding` thành public helper để baseline và corruption dùng cùng format. Điều này giúp tránh thay đổi cấu trúc text ngoài ý muốn khi so sánh tác động của dữ liệu hỏng.

Test set chọn paper tất định và có bài mới nhất để `drop_latest` có thể tác động đến evaluation. Ground truth summary dùng cùng `first_sentence` với QA để tránh lệch cách trích đáp án.

QA ưu tiên lookup theo title chính xác, nên kiểm tra lookup thành công chưa chứng minh chất lượng vector search độc lập. Baseline đầy đủ cần được đo qua pipeline của P4.

## 6. Một lỗi hoặc blocker đã xử lý

- **Triệu chứng:** snapshot ban đầu của P1 đủ 24 DOI nhưng cả 24 `updated` đều rỗng.
- **Nguyên nhân:** parser chưa lấy `created.date-time` và chưa fallback updated về published.
- **Tác động:** cleaning chuyển ngày rỗng thành `NaT` và loại cả 24 dòng.
- **Phối hợp xử lý:** tôi xác định lỗi contract; P1 sửa parser và sinh lại snapshot. Tôi không sửa module P1.
- **Xác minh:** sau sửa, cả hai ngày parse được 24/24; loader P1 qua cleaning P2 cho 24 dòng, 16 cột.
- **Bài học:** phải kiểm tra đúng phiên bản dữ liệu và loader của thành viên cung cấp đầu vào; PASS trên snapshot local chưa đủ để khẳng định tích hợp thành công.

## 7. Hiểu biết về luồng end-to-end

1. P1 lấy snapshot/API và tạo `PaperRecord`; P2 clean; P4 lưu artifacts và gọi embedding/index có sẵn.
2. P2 tạo test set từ clean DataFrame. Evaluation đối chiếu DOI retrieved với ground-truth IDs để tính hit rate, so đáp án với ground truth để tính token F1.
3. P3 kiểm tra quality và freshness. Freshness dùng ngưỡng 180 ngày, tỷ lệ stale cho phép 25% theo contract nhóm.
4. P4 tạo corruption, re-index, evaluate, rồi repair từ raw và evaluate lại. Ba trạng thái dùng nguyên một test set để so sánh công bằng.
5. P2 hỗ trợ so `paper_id + text_for_embedding` giữa baseline và repaired. Nếu run_date khác ngày, `age_days` có thể thay đổi; phép so này không chứng minh mọi field giống hệt.

## 8. Phân tích kết quả

| Signal | Kết quả đã xác minh |
| --- | --- |
| Clean rows / columns | 24 / 16 |
| Unique paper IDs | 24 |
| Evaluation items | 10 |
| Phân bổ summary/authors/date/categories | 3 / 3 / 2 / 2 |
| QA extraction/lookup | Khớp ground truth trong kiểm tra trực tiếp |
| Metrics baseline/corrupted/repaired đầy đủ | Chưa xác minh trong phạm vi kiểm tra này |
| So artifacts repaired với baseline | Còn cần kiểm tra sau khi P4 chạy flow |

Chưa có cơ sở từ các kiểm tra module này để ghi hit rate hoặc token F1 end-to-end bằng 1.0, hay kết luận repair đã phục hồi metrics.

Review corruption phải xét cả paper và loại câu hỏi: blank summary có thể làm sai câu summary nhưng không làm sai câu authors; duplicate có thể làm quality fail mà không giảm mọi metric QA.

## 9. Điều học được và hướng cải thiện

- Contract cần thống nhất tên field, kiểu dữ liệu và cách xử lý giá trị thiếu.
- Evaluation cần tái lập được, phủ nhiều paper và tương thích logic QA.
- Phải phân biệt kiểm tra module, tích hợp và end-to-end; chỉ báo cáo kết quả đã xác minh.
- Phối hợp P1 đưa các ca biên cleaning/testset vào pytest.
- Cùng P4 đối chiếu corruption log với test set, kiểm tra repaired và bổ sung metrics ba trạng thái khi có kết quả thực tế.

## 10. Cam kết của thành viên

Thành viên tự đánh dấu sau khi đọc và xác nhận:

- [ ] Nội dung phản ánh đúng phần việc và mức hiểu của tôi.
- [ ] Tôi có thể giải thích cleaning, evaluation và luồng end-to-end.
- [ ] Tôi phân biệt rõ phần đã kiểm tra với phần còn chờ tích hợp.
- [ ] Các kết luận có code, artifact hoặc kết quả kiểm tra để đối chiếu.
- [ ] Báo cáo không chứa thông tin bí mật và không nhận công việc của người khác là của mình.

**Họ và tên:** Nguyễn Đình Anh
**Ngày xác nhận:** Chờ thành viên xác nhận.
