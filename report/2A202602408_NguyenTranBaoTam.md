# Báo cáo cá nhân — Nguyễn Trần Bảo Tâm

| Mục | Thông tin |
|---|---|
| MSSV | 2A202602408 |
| Lớp | K4-L3B |
| Nhóm | Dangcaps |
| Vai trò theo `docs/PHAN_CONG.md` | P3 — Observability & Reporting |
| Ngày thực hiện | 2026-09-26 |

## Phần việc đã thực hiện

- Hoàn thiện `run_data_quality_checks` trong `src/observability/quality.py` bằng Great Expectations 1.x: kiểm tra số dòng, giá trị null, ID duy nhất, độ dài title và summary. Kết quả trả về có `success`, `row_count`, từng expectation và freshness; suite và báo cáo được ghi JSON.
- Hoàn thiện `build_freshness_report`: đếm bài có `age_days > 180`, tính tỷ lệ stale, và đánh dấu không đạt khi tỷ lệ vượt 25%.
- Hoàn thiện hai hàm trong `src/observability/reporting.py`: báo cáo baseline và bảng so sánh baseline/corrupted/repaired. Giá trị metric được lấy từ tham số, không điền tay.
- Viết `script/check_observability.py` để kiểm tra quality gate trên snapshot 24 bản ghi và dữ liệu cố ý làm lỗi. Script dùng thư mục tạm, không tạo metrics bài nộp.

## Hỗ trợ ngoài phạm vi chính

- Kiểm thử MiniLM sinh vector 384 chiều, ba collection ChromaDB đều nạp được 24 tài liệu từ snapshot và QA trả đúng tác giả. Đây là kiểm tra tạm, không thay đổi code retrieval của thành viên khác.
- Phát hiện manifest embedding lưu đường dẫn Chroma tuyệt đối. Khi nhóm chuyển repo sang máy khác, cần tái tạo index hoặc điều chỉnh đường dẫn khi mở lại.

## Bằng chứng kiểm tra

```powershell
.\.venv\Scripts\python.exe -c "import chromadb, great_expectations, sentence_transformers; print('Environment Ready!')"
.\.venv\Scripts\python.exe script/check_observability.py
```

- Kiểm tra môi trường in `Environment Ready!`.
- Baseline tạm từ raw snapshot: 24 dòng, 8/8 expectations đạt, 1/24 bài stale (4,17%), freshness đạt.
- Chỉ làm cũ 8/24 bài (33,33%) khiến gate thất bại dù các expectations khác vẫn đạt. Khi thêm ID trùng, title `abc` và summary rỗng, gate cũng thất bại. Hai báo cáo Markdown thử được sinh thành công trong thư mục tạm.
- Ba collection thử `papers-baseline`, `papers-corrupted`, `papers-repaired` có 24 tài liệu mỗi collection; QA trả `Minh Nguyen, Hoang Le` cho bài thử. Đây là kiểm tra hạ tầng retrieval trong thư mục tạm, không phải metrics của pipeline chính.

## Giải thích kỹ thuật

Quality Gate kiểm tra cấu trúc và nội dung từng bản ghi; freshness đo tuổi của toàn bộ tập dữ liệu. `success` chỉ đúng khi cả validation GX và freshness đều đạt. Điều này ngăn trường hợp dữ liệu đúng schema nhưng đã quá cũ vẫn đi vào index.

Luồng đầy đủ của nhóm là Crossref → raw records → cleaning → MiniLM/ChromaDB → test set và đánh giá → corruption → đánh giá lại → repair từ raw → so sánh. Ba trạng thái phải dùng cùng test set và cùng cấu hình để chênh lệch metric phản ánh thay đổi dữ liệu. Repair chỉ được kết luận thành công khi dữ liệu, quality/freshness và metrics sau repair khớp bằng chứng thực tế.

## Phạm vi chưa xác minh

`src/ingestion/cleaning.py` và hai pipeline chính hiện còn `NotImplementedError`, nên chưa có baseline/corrupted/repaired metrics cuối cùng. Báo cáo cá nhân này chưa kết luận mức suy giảm hoặc phục hồi của RAG. Khi các phần đó hoàn thành, cần chạy hai entrypoint, đọc artifact thực tế và cập nhật phần phân tích kết quả của nhóm.
