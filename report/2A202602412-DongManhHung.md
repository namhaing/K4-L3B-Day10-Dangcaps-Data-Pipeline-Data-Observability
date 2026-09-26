# Member Role Report — Day 10: Data Pipeline & Data Observability

## 1. Thông tin cá nhân

| Thông tin | Nội dung |
| --- | --- |
| Họ và tên | Đồng Mạnh Hùng |
| MSSV | 2A202602412 |
| Khóa/Lớp | K4 |
| Tên nhóm | Dangcaps |
| Vai trò chính | Crossref source / ingestion owner |
| Repository | https://github.com/namhaing/K4-L3B-Day10-Dangcaps-Data-Pipeline-Data-Observability/tree/Hung23020370 |
| Ngày hoàn thành | 2026-09-26 |

## 2. Vai trò và phạm vi công việc

### Phần việc sở hữu

| Module/deliverable | File/hàm phụ trách | Input nhận vào | Output bàn giao | Trạng thái |
| --- | --- | --- | --- | --- |
| Thu thập và lưu raw data từ Crossref | `src/ingestion/crossref.py`: `parse_crossref_payload`, `fetch_source_records`, `load_raw_records` | Crossref REST API response hoặc raw JSON snapshot | `data/raw/crossref_response.json`, `data/raw/crossref_records.json` | Hoàn thành |

Phạm vi ownership của tôi chỉ gồm `src/ingestion/crossref.py`. Tôi không nhận ownership cho cleaning, quality, evaluation, retrieval hoặc pipeline orchestration.

## 3. Kết quả theo vai trò

| Nhiệm vụ | File/hàm/artifact | Kết quả | Cách xác minh |
| --- | --- | --- | --- |
| Parse Crossref payload | `parse_crossref_payload` | Ánh xạ `message.items` thành `PaperRecord`; bỏ item thiếu DOI hoặc title | Parse response snapshot |
| Fetch và retry request | `fetch_source_records` | Gọi Crossref theo query/filter cấu hình, có timeout và retry giới hạn | Lệnh fetch trả về 24 record |
| Lưu raw lineage | `fetch_source_records` | Lưu response API và parsed records thành hai JSON artifacts | Kiểm tra hai file trong `data/raw/` |
| Đọc snapshot | `load_raw_records` | Đọc JSON records thành danh sách `PaperRecord` | Snapshot hiện có 24 record |

Output thuộc phạm vi công việc:
- `data/raw/crossref_response.json`: payload response gốc.
- `data/raw/crossref_records.json`: danh sách record đã parse theo contract nội bộ.

## 4. Giải thích phần kỹ thuật đã thực hiện

### Vấn đề cần giải quyết

Pipeline cần lấy metadata học thuật từ Crossref và giữ lại cả response gốc lẫn record đã chuẩn hóa. Raw response hỗ trợ truy vết và parse lại; `PaperRecord` cung cấp schema ổn định cho module downstream.

### Cách triển khai

- `parse_crossref_payload` đọc các item trong `message.items`; trích xuất DOI, title, abstract, author, subject, ngày, URL và link.
- Parser chuẩn hóa whitespace, bỏ JATS/XML tags khỏi abstract, và bỏ item thiếu DOI hoặc title.
- Ngày được lấy từ `date-time` hoặc `date-parts`; `updated` fallback sang `created`, rồi `published`. Nếu thiếu `published`, dùng `updated`.
- `fetch_source_records` lấy query, filter và số lượng tối đa từ `Settings`, gọi `https://api.crossref.org/works`, đặt timeout 30 giây và thử tối đa 5 lần.
- Khi request thành công, response được lưu vào `crossref_response.json`; records sau parse được lưu vào `crossref_records.json`.
- Khi không có record từ API, hàm thử đọc response snapshot đã lưu, rồi fallback sang `data/raw/crossref_records.json` theo working directory hiện tại.

### Input, output và contract

| Thành phần | Mô tả |
| --- | --- |
| Input | Crossref response có `message.items`, hoặc JSON snapshot của parsed records |
| Output | `list[PaperRecord]` và hai raw artifacts trong `data/raw/` |
| Schema record | `paper_id`, `title`, `summary`, `authors`, `categories`, `primary_category`, `published`, `updated`, `abs_url`, `pdf_url`, `comment` |
| Module phụ thuộc | `src/core/config.py` cung cấp query, filter, giới hạn record và paths; package `requests` gọi API |
| Module sử dụng output | Các module downstream đọc `PaperRecord`/`crossref_records.json`; các module đó không thuộc ownership của tôi |
| Điều kiện lỗi | Request/HTTP error, JSON không hợp lệ, item thiếu DOI/title; offline fallback yêu cầu đúng working directory |

### Retry và backoff

Code retry các lỗi request/HTTP/JSON. Những status được nhận diện rõ là retryable gồm 429, 500, 502, 503 và 504. Delay hiện tại là tuyến tính `1.5 × attempt`: 1.5, 3, 4.5 và 6 giây giữa tối đa 5 lần gọi; đây không phải exponential backoff. Mỗi request có timeout 30 giây.

### Cách xác minh

```powershell
python -c "from core.config import load_settings; from ingestion.crossref import fetch_source_records; s=load_settings(); r=fetch_source_records(s); print(f'Tín hiệu hoàn thành: Đã tải {len(r)} bài báo')"
```

- Kết quả mong đợi: hàm trả về `PaperRecord` và ghi hai raw artifacts.
- Kết quả đã xác minh: lệnh fetch trả về `Đã tải 24 bài báo`; `data/raw/crossref_records.json` hiện có 24 record.
- Timestamp ingestion: hiện chưa được ghi thành metadata riêng trong artifacts.

## 5. Một quyết định kỹ thuật quan trọng

- **Bối cảnh:** Crossref có thể tạm lỗi hoặc giới hạn request; dừng job ngay sau lỗi đầu tiên sẽ khiến ingestion phụ thuộc vào mạng tại thời điểm chạy.
- **Các phương án đã cân nhắc:** dừng ngay khi request lỗi; hoặc retry có giới hạn rồi sử dụng snapshot offline nếu còn dữ liệu hợp lệ.
- **Phương án đã chọn:** tối đa 5 lần thử với timeout 30 giây và delay tuyến tính, sau đó thử đọc snapshot.
- **Lý do:** retry hỗ trợ vượt qua lỗi transient nhưng vẫn giới hạn thời gian chờ; giữ raw response giúp truy vết và tái xử lý.
- **Bằng chứng:** fetch trả về 24 record và parsed snapshot hiện có 24 record. Backoff hiện tại là tuyến tính, không phải exponential.

## 6. Một lỗi hoặc blocker đã xử lý

- **Triệu chứng:** `NotImplementedError: Student task: implement source fetching.`
- **Bước tái hiện:** gọi `fetch_source_records` từ venv ban đầu.
- **Nguyên nhân gốc:** editable-install path trong venv trỏ sang một thư mục clone cũ nên Python import bản stub thay vì file thuộc workspace hiện tại.
- **Cách xử lý:** sửa editable `.pth` trong venv sang `src` của repository hiện tại và xác minh lại đường dẫn module được import.
- **Cách xác minh sau sửa:** lệnh fetch chạy và trả về `Đã tải 24 bài báo`.
- **Điều học được:** với nhiều clone có tên gần giống nhau, kiểm tra `module.__file__` để chắc chắn đang chạy đúng source trước khi debug logic.

## 7. Hiểu biết về luồng end-to-end

1. Crossref trả payload API; ingestion lưu response gốc, parse các item thành `PaperRecord` và lưu parsed records. Các module downstream tiếp tục cleaning, embedding/index và retrieval; những module sau không thuộc phần tôi sở hữu.
2. Evaluation set gắn câu hỏi với ground-truth document IDs/answer để đo retrieval hit và answer quality.
3. Quality checks kiểm tra tính hợp lệ/schema; freshness theo dõi tuổi dữ liệu so với SLA.
4. Giữ cùng test set giữa baseline, corrupted và repaired để so sánh các trạng thái trên cùng câu hỏi và ground truth.
5. Repair cần được chứng minh bằng dữ liệu/schema sau sửa, quality/freshness signals và metrics so sánh với baseline.

## 8. Phân tích kết quả

Metrics baseline/corrupted/repaired không được báo cáo ở đây vì chúng không thuộc module Crossref ingestion và hiện chưa có artifact kết quả được xác minh trong phạm vi báo cáo cá nhân này.

Kết quả đã xác minh cho phần việc của tôi: lệnh fetch trả về 24 record; parsed snapshot `data/raw/crossref_records.json` cũng có 24 record. Tôi không suy diễn kết quả này thành kết quả cleaning, quality gate hoặc retrieval.

## 9. Điều học được và hướng cải thiện

### Ba điều quan trọng nhất

1. Raw API response và parsed records phục vụ hai mục tiêu khác nhau: lưu lineage/tái xử lý và cung cấp contract ổn định cho downstream.
2. Retry cần giới hạn số lần, timeout và backoff được mô tả đúng để kiểm soát tính ổn định lẫn thời gian chạy.
3. Import path là một phần của tính tái lập; chạy lệnh thành công chưa đủ nếu Python đang import nhầm clone.

### Nếu có thêm thời gian

Ghi thêm `fetched_at`, query/filter đã dùng và HTTP status thành ingestion metadata để xác định thời điểm và cấu hình lấy dữ liệu. Có thể chuyển retry delay sang cấu hình và cân nhắc exponential backoff có jitter; implementation hiện tại dùng delay tuyến tính cố định.

## 10. Cam kết của thành viên

- [x] Nội dung báo cáo chỉ nhận ownership cho phần việc tôi thực hiện.
- [x] Các kết luận về ingestion có output hoặc artifact để đối chiếu.
- [x] Không ghi thành công cho cleaning, quality, evaluation hoặc retrieval.
- [x] Báo cáo không chứa `.env`, API key, token hoặc secret.

**Họ và tên:** Đồng Mạnh Hùng

**Ngày xác nhận:** 2026-09-26