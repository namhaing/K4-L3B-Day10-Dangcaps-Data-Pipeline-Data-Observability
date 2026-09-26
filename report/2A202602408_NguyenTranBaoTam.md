# Báo cáo cá nhân — Nguyễn Trần Bảo Tâm

## 1. Thông tin cá nhân

| Thông tin | Nội dung |
|---|---|
| Họ và tên | Nguyễn Trần Bảo Tâm |
| MSSV | 2A202602408 |
| Khóa/lớp | K4-L3B |
| Nhóm | Dangcaps |
| Vai trò | P3 — Observability & Reporting, theo `docs/PHAN_CONG.md` |
| Repository | https://github.com/namhaing/K4-L3B-Day10-Dangcaps-Data-Pipeline-Data-Observability |
| Ngày thực hiện | 2026-09-26 |

## 2. Vai trò và phạm vi công việc

| Phần việc | File/hàm trực tiếp thực hiện | Input | Output | Trạng thái |
|---|---|---|---|---|
| Quality Gate GX 1.x | `src/observability/quality.py` — `run_data_quality_checks` | DataFrame sạch hoặc bị làm bẩn; `Settings`; tên báo cáo | Kết quả `success`, từng expectation, JSON quality và GX suite | Hoàn thành, đã kiểm thử độc lập |
| Freshness SLA | `src/observability/quality.py` — `build_freshness_report` | `published`, `age_days`, ngưỡng trong `Settings` | JSON gồm số bài stale, tỷ lệ và `is_fresh` | Hoàn thành, đã kiểm thử độc lập |
| Báo cáo | `src/observability/reporting.py` — hai hàm `generate_*_report` | Source summary, metrics, quality, freshness | Markdown baseline và so sánh ba trạng thái | Hoàn thành hàm, đã kiểm thử với dữ liệu mẫu; chờ metrics thật |
| Kiểm chứng | `script/check_observability.py` | Snapshot raw 24 bài báo | Kết quả kiểm tra trong thư mục tạm | Hoàn thành |

Ngoài phạm vi chính, tôi thử mô hình MiniLM và ChromaDB bằng dữ liệu tạm: embedding dài 384 chiều; ba collection thử đều nạp được 24 tài liệu; QA trả đúng tác giả cho câu hỏi kiểm tra. Tôi không sửa module retrieval của thành viên khác. Tôi cũng phát hiện manifest embedding lưu đường dẫn Chroma tuyệt đối, nên khi chuyển máy cần tái tạo index hoặc xử lý lại đường dẫn.

## 3. Kết quả và bằng chứng

Tôi chạy trực tiếp:

```powershell
.\.venv\Scripts\python.exe -c "import chromadb, great_expectations, sentence_transformers; print('Environment Ready!')"
.\.venv\Scripts\python.exe script/check_observability.py
```

Lệnh thứ nhất in `Environment Ready!`. Script thứ hai dùng ngày chạy cố định **2026-09-26** và snapshot 24 bài báo để kết quả kiểm tra lặp lại được:

| Trường hợp thử | GX | Freshness | Quality Gate |
|---|---|---|---|
| Snapshot gốc | 8/8 expectation đạt | 1/24 bài quá 180 ngày = 4,17%, đạt | `success=True` |
| Chỉ làm cũ 8/24 bài | 8/8 expectation đạt | 33,33%, vượt mức 25% | `success=False` |
| ID trùng, title `abc`, summary rỗng, 8 bài cũ | Ít nhất ba expectation thất bại | 33,33%, không đạt | `success=False` |

Hai hàm báo cáo tạo Markdown thử trong thư mục tạm. Các con số metric trong bài thử là **fixture để kiểm tra định dạng và phép tính chênh lệch**, không phải kết quả đánh giá RAG của nhóm. Script không ghi đè `data/results/` hoặc `data/reports/`.

## 4. Giải thích kỹ thuật và data contract

Quality Gate tạo `gx.get_context(mode="ephemeral")`, một Pandas dataframe asset và batch cho mỗi lần gọi. Suite có bốn loại expectation: số dòng trong khoảng 90–100% của `max_results`; `paper_id`, `title`, `summary`, `published` không null; `paper_id` duy nhất; title dài ít nhất 8 ký tự và summary ít nhất 50 ký tự. Kết quả từng expectation được đổi thành cấu trúc ghi JSON được.

Freshness tính `stale_rows = count(age_days > 180)` và `stale_ratio = stale_rows / total_rows`. Tập dữ liệu đạt SLA khi tỷ lệ này **không vượt 25%**. Kết quả tổng `success` chỉ đúng khi cả GX và freshness đều đạt. Bài thử chỉ làm cũ 8 bài chứng minh freshness có thể chặn dữ liệu dù schema và nội dung vẫn hợp lệ.

`run_data_quality_checks` trả dict có `report_name`, `success`, `row_count`, `expectations`, `freshness`; đồng thời ghi báo cáo JSON và GX suite dưới `data/quality/` theo đường dẫn cấu hình. Hai hàm reporting nhận dict metrics/quality/freshness từ pipeline, tạo bảng Markdown và tính `Δ = corrupted − baseline` tại thời điểm sinh báo cáo. Chúng không tự tạo số liệu đánh giá.

Đầu vào của tôi phụ thuộc schema sạch do P2 tạo, đặc biệt `published` và `age_days`. P4 gọi quality và reporting trong hai pipeline. Khi dữ liệu lỗi bị phát hiện, P4 cần phục hồi từ raw snapshot rồi chạy lại cùng test set để so sánh công bằng.

## 5. Quyết định kỹ thuật quan trọng

Tôi gộp GX và freshness vào cùng tín hiệu `success`. Nếu chỉ dùng GX, một tập dữ liệu có đủ cột, ID duy nhất và văn bản hợp lệ vẫn có thể gồm quá nhiều bài đã cũ. Nếu tách freshness khỏi gate, pipeline tích hợp dễ bỏ qua cảnh báo. Bài thử stale-only giữ **8/8** expectation đạt nhưng tổng gate trả `False`, chứng minh điều kiện này hoạt động.

## 6. Lỗi và blocker đã xử lý

Khi cài môi trường bằng `uv sync`, PyTorch không giải nén được vì ổ C hết dung lượng (`There is not enough space on the disk`, `os error 112`). Tôi tạo môi trường và cache riêng của bài trên ổ D, liên kết `.venv` trong repo tới môi trường đó, rồi chạy lại lệnh kiểm tra import thành công. Đây là cách bố trí cục bộ trên máy, không phải đường dẫn hardcode trong mã dự án.

Một giới hạn còn lại là `GOOGLE_API_KEY` trong `.env` chưa được điền; tôi không có và không ghi key cá nhân vào Git. Kiểm thử phần P3 không cần gọi Gemini.

## 7. Hiểu biết về luồng end-to-end

Crossref API hoặc snapshot tạo raw records; P2 chuẩn hóa thành DataFrame và `text_for_embedding`; MiniLM tạo vector, ChromaDB lập chỉ mục; bộ câu hỏi có ground-truth document IDs cho phép đo hit rate, còn câu trả lời được đo token F1 và judge. P3 kiểm tra chất lượng, freshness và ghi báo cáo. P4 tạo corruption, đánh giá lại, rồi repair từ raw và so sánh ba trạng thái.

Ba trạng thái phải dùng cùng test set và cấu hình để biến động metric phản ánh thay đổi dữ liệu. Repair chỉ được xem là thành công khi bản ghi phục hồi, quality/freshness và metrics sau repair đều có artifact thực tế để đối chiếu.

## 8. Phân tích kết quả hiện có

| Metric/signal | Baseline | Corrupted | Repaired | Phạm vi kết luận |
|---|---|---|---|---|
| `retrieval_hit_rate` | Chưa có | Chưa có | Chưa có | Chờ pipeline và test set của nhóm |
| `mean_token_f1` | Chưa có | Chưa có | Chưa có | Chờ pipeline và test set của nhóm |
| `judge_accuracy` | Chưa có | Chưa có | Chưa có | Chờ pipeline và test set của nhóm |
| `mean_judge_score` | Chưa có | Chưa có | Chưa có | Chờ pipeline và test set của nhóm |
| Quality Gate | Đạt trên snapshot thử | Không đạt trên dữ liệu gây lỗi thử | Chưa kiểm chứng | Kiểm thử độc lập, chưa phải artifact pipeline |
| Freshness | 1/24 stale, đạt | 8/24 stale, không đạt | Chưa kiểm chứng | Kiểm thử độc lập ngày 2026-09-26 |

Thử nghiệm đã chứng minh chuỗi **dữ liệu bị làm cũ → tỷ lệ stale vượt 25% → Quality Gate báo lỗi**. Chưa có số liệu để kết luận tác động của lỗi này lên agent hoặc mức phục hồi sau repair. Hiện `cleaning.py` và hai pipeline chính còn `NotImplementedError`; khi nhóm hoàn thành, cần chạy `run_phase1.py`, `run_corruption_flow.py` và đối chiếu các JSON thật trước khi viết kết luận cuối.

## 9. Điều học được và hướng cải thiện

1. Kiểm tra schema và giá trị từng dòng chưa đủ để đo độ mới của toàn bộ tập dữ liệu.
2. Một quality gate nên trả kết quả có cấu trúc và lưu artifact để pipeline lẫn người chấm đều kiểm tra lại được.
3. Chênh lệch RAG chỉ có ý nghĩa khi baseline, corrupted và repaired dùng cùng câu hỏi, ground truth và cấu hình.

Khi có đầy đủ artifact của nhóm, tôi sẽ cập nhật phần kết quả bằng metrics thật và kiểm tra bảng Markdown khớp từng JSON nguồn. Dashboard chất lượng dữ liệu là phần bonus có thể làm sau khi ba trạng thái chạy ổn định.

## 10. Cam kết

Nội dung trên phản ánh phần việc và phép kiểm tra tôi trực tiếp thực hiện. Tôi phân biệt kết quả thử độc lập với kết quả end-to-end chưa có, không đưa API key hoặc secret vào báo cáo, và có thể giải thích luồng dữ liệu cùng vai trò của module P3.

**Nguyễn Trần Bảo Tâm — 2026-09-26**
