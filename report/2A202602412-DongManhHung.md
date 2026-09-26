# Member Role Report — Day 10: Data Pipeline & Data Observability

## 1. Thông tin cá nhân

| Thông tin | Nội dung |
| --- | --- |
| Họ và tên | Đồng Mạnh Hùng |
| MSSV | 2A202602412 |
| Khóa/Lớp | K4 |
| Tên nhóm | Dangcaps |
| Vai trò chính | Data ingestion & cleaning owner |
| Repository | https://github.com/namhaingK4-L3B-Day10-Dangcaps-Data-Pipeline-Data-Observability/tree/Hung23020370 |
| Ngày hoàn thành | 2026-09-26 |

## 2. Vai trò và phạm vi công việc

### Phần việc sở hữu

| Module/deliverable | File/hàm phụ trách | Input nhận vào | Output bàn giao | Trạng thái |
| --- | --- | --- | --- | --- |
| Raw ingestion | src/ingestion/crossref.py | Crossref API response hoặc local snapshot | Raw response JSON + raw records JSON | Hoàn thành |
| Cleaning + data modeling | src/ingestion/cleaning.py | Danh sách PaperRecord từ raw records | DataFrame sạch với age_days, summary_chars, text_for_embedding | Hoàn thành |

### Việc hỗ trợ ngoài phạm vi chính

| Hoạt động | Thành viên/module được hỗ trợ | Kết quả |
| --- | --- | --- |
| Debug môi trường Python | Project venv + import path | Sửa lỗi import sai project cũ, đảm bảo Python chạy đúng workspace hiện tại |
| Kiểm tra đúng contract schema | src/core/config.py + downstream modules | Đảm bảo dữ liệu thỏa contract `PaperRecord` và cột output cho bước tiếp theo |

## 3. Kết quả theo vai trò

| Nhiệm vụ đã thực hiện | File/hàm/artifact liên quan | Kết quả bàn giao | Cách xác minh |
| --- | --- | --- | --- |
| Tạo parser và fetch Crossref | src/ingestion/crossref.py | Raw API snapshot + raw records JSON được lưu đúng | Chạy `fetch_source_records(load_settings())`; kết quả: `Đã tải 24 bài báo` |
| Chuẩn hóa metadata | src/ingestion/crossref.py | DOI, title, summary, authors, categories, abs_url, pdf_url, published, updated | Chạy `parse_crossref_payload` trên file JSON; kết quả: `payload_count= 24` |
| Làm sạch dataset | src/ingestion/cleaning.py | DataFrame sạch có `age_days`, `summary_chars`, `text_for_embedding` | Chạy `build_clean_dataframe(...)`; kết quả: `rows= 24`, `unique_ids= 24` |

Output cụ thể mà tôi đã tạo ra hoặc xác minh:
- `data/raw/crossref_response.json`
- `data/raw/crossref_records.json`
- DataFrame sau cleaned có 24 dòng, chứa cột `text_for_embedding` và `age_days`

## 4. Giải thích phần kỹ thuật đã thực hiện

### Vấn đề cần giải quyết

Phần của tôi giải quyết hai vấn đề chính trong pipeline:
1. `fetch_source_records` phải fetch Raw data từ Crossref và lưu artifact để bảo toàn data lineage.
2. `build_clean_dataframe` phải chuẩn hóa PaperRecord thành DataFrame sẵn sàng để embedding, đồng thời tính `age_days` đúng với mô hình `datetime` và giữ schema thống nhất cho các module sau.

### Cách triển khai

Với `crossref.py`, tôi triển khai logic thực tế để:
- đọc payload từ Crossref `message.items`
- trích xuất DOI, title, abstract, author, subject, published/updated, URL
- bỏ record không hợp lệ
- lưu JSON raw response vào `data/raw/crossref_response.json`
- lưu danh sách `PaperRecord` vào `data/raw/crossref_records.json`
- fallback về snapshot local nếu API lỗi hoặc mất mạng

Với `cleaning.py`, tôi triển khai quy trình:
- biến từng `PaperRecord` thành DataFrame
- chuẩn hóa khoảng trắng trong title/summary
- ghép authors/categories thành chuỗi để dễ query và debug
- tính `age_days` dưới dạng số ngày từ ngày xuất bản đến `run_date`
- tính `summary_chars`
- tạo `text_for_embedding` theo template có 5 phần: Title, Authors, Published, Categories, Summary
- loại bỏ duplicate theo `paper_id` và bỏ các dòng quá ngắn hoặc thiếu metadata
- sắp xếp theo ngày xuất bản mới nhất

### Input, output và contract

| Thành phần | Mô tả |
| --- | --- |
| Input | Raw record list từ Crossref hoặc file snapshot `data/raw/crossref_records.json` |
| Output | Danh sách `PaperRecord`, DataFrame sạch, cột `text_for_embedding`, `age_days` |
| Module phụ thuộc | `src/core/config.py` định nghĩa `Settings` và `Paths` |
| Module sử dụng output | `src/ingestion/cleaning.py` được dùng cho embedding/index; module tiếp theo cần schema thống nhất |
| Điều kiện lỗi cần xử lý | Mạng API lỗi, timezone mismatch, record thiếu DOI, duplicate hoặc metadata rỗng |

### Cách xác minh

```bash
cd "H:\Vin\Day 10\K4-L3B-Day10-Dangcaps-Data-Pipeline-Data-Observability"
.\.venv\Scripts\python -c "from core.config import load_settings; from ingestion.crossref import fetch_source_records; s=load_settings(); r=fetch_source_records(s); print(f'Tín hiệu hoàn thành: Đã tải {len(r)} bài báo')"
```

```bash
cd "H:\Vin\Day 10\K4-L3B-Day10-Dangcaps-Data-Pipeline-Data-Observability"
.\.venv\Scripts\python -c "from datetime import datetime, timezone; from core.config import load_settings; from ingestion.crossref import load_raw_records; from ingestion.cleaning import build_clean_dataframe; s = load_settings(); df = build_clean_dataframe(load_raw_records(s.paths.raw_records_json), datetime.now(timezone.utc)); print('rows=', len(df)); print('cols=', list(df.columns)); print('age_days_minmax=', int(df['age_days'].min()), int(df['age_days'].max())); print('has_text=', 'text_for_embedding' in df.columns); print('unique_ids=', df['paper_id'].nunique());"
```

- Kết quả mong đợi: fetch thành công 24 bài báo; DataFrame có `age_days` và `text_for_embedding`.
- Kết quả thực tế: `Tín hiệu hoàn thành: Đã tải 24 bài báo`; `rows=24`, `unique_ids=24`, `has_text=True`.
- Artifact/log: `data/raw/crossref_response.json`, `data/raw/crossref_records.json`.

## 5. Một quyết định kỹ thuật quan trọng

- Bối cảnh: Khi chạy thử, Python import nhầm project cũ và code `NotImplementedError` vẫn chạy, làm sai lệch verification. Ngoài ra, `run_date` có timezone-aware nhưng `published_dt` là naive nên `age_days` bị lỗi ngay ở bước cleaning.
- Các phương án đã cân nhắc:
  1. Giữ nguyên stub và tiếp tục chờ team fix lại.
  2. Fix environment path + normalize timezone trước khi tính chênh lệch ngày.
- Phương án đã chọn: sửa cả environment và code DataFrame.
- Lý do: đây là cách đảm bảo dữ liệu đầu vào đúng project hiện tại, đồng thời giữ consistency giữa `run_date` và `published_dt`, tránh các lỗi runtime giả tạo ở giai đoạn sau.
- Bằng chứng quyết định phù hợp: Python import trỏ đúng file hiện tại; Clean pipeline chạy thành công với `rows=24`, `has_text=True`.

## 6. Một lỗi hoặc blocker đã xử lý

- Triệu chứng/lỗi nguyên văn: `NotImplementedError: Student task: implement source fetching.`
- Lệnh hoặc bước tái hiện: chạy `python -c "from core.config import load_settings; from ingestion.crossref import fetch_source_records; ..."` trong venv cũ.
- Nguyên nhân gốc: venv có entry editable cũ trỏ tới folder `H:\Vin\Day 10\K4-L3B-Day10-Data-Pipeline-Data-Observability\src`, không phải folder hiện tại `K4-L3B-Day10-Dangcaps...`.
- Cách xử lý: cập nhật file `.pth` trong `.venv\Lib\site-packages\__editable__...` về đúng đường dẫn thư mục hiện tại; sau đó triển khai hàm `fetch_source_records` và normalize datetime trong cleaning.
- Cách xác minh sau khi sửa: `Tín hiệu hoàn thành: Đã tải 24 bài báo`; `rows=24`, `unique_ids=24`.
- Điều học được: khi làm project có nhiều thư mục tương tự, phải kiểm tra import path và venv trước khi debug logic, vì lỗi “không rõ nguyên nhân” có thể là import sai project chứ không phải logic bug.

## 7. Hiểu biết về luồng end-to-end

1. Dữ liệu đi từ Crossref đến vector index như thế nào?
   - Crossref API trả raw payload JSON với metadata papers.
   - Raw data được parse và lưu vào `data/raw/crossref_records.json`.
   - Data được clean thành DataFrame, tạo `text_for_embedding` và các cột nghiệp vụ như `age_days`.
   - Sau đó dataset sạch sẽ được đưa vào embedding/index stage để build vector store.

2. Evaluation set và ground-truth document IDs dùng để đo retrieval/answer quality ra sao?
   - Evaluation set cần gắn câu hỏi với ground truth document IDs hoặc phương án đúng để so sánh candidate retrieval/answer.
   - Khi retrieval trả về đúng paper hoặc câu trả lời trùng khớp với ground truth, ta mới tính hit rate và token F1 chính xác.

3. Quality checks khác freshness monitoring ở điểm nào trong bài lab?
   - Quality checks tập trung vào integrity, schema, nulls, duplicate, và format dữ liệu.
   - Freshness monitoring tập trung vào độ mới/age của paper theo `age_days` và threshold SLA như `> 180` ngày.

4. Vì sao phải dùng cùng test set cho baseline, corrupted và repaired?
   - Nếu dùng test set khác nhau thì kết quả không còn comparable.
   - Chỉ khi dùng cùng evaluation set mới biết được corruption làm suy giảm như thế nào và repair phục hồi tới mức nào.

5. Repair được xem là thành công dựa trên artifact và metric nào?
   - Repair thành công nếu dữ liệu sau sửa lại gần baseline về schema, quality signal và metric retrieval/evaluation. Bằng chứng cần là artifact và report số liệu tương ứng ở `data/results` và `data/reports`.

## 8. Phân tích kết quả

### Metrics chính

| Metric/signal | Baseline | Corrupted | Repaired | Nhận xét của cá nhân |
| --- | ---: | ---: | ---: | --- |
| retrieval_hit_rate | N/A | N/A | N/A | Không thuộc module raw/cleaning trực tiếp; phần này do pipeline/evaluation phụ trách |
| mean_token_f1 | N/A | N/A | N/A | Không thuộc module raw/cleaning trực tiếp |
| judge_accuracy | N/A | N/A | N/A | Không thuộc module raw/cleaning trực tiếp |
| mean_judge_score | N/A | N/A | N/A | Không thuộc module raw/cleaning trực tiếp |
| Quality checks | N/A | N/A | N/A | Đây là phần observability, không phải raw/cleaning |
| Freshness status | N/A | N/A | N/A | Cần pipeline/quality đúng mới có kết quả chính xác |

### Kết luận từ số liệu

Trong phạm vi phần việc của tôi, bằng chứng thực tế đã kiểm chứng là:
1. Raw ingestion đã thành công: `Đã tải 24 bài báo`.
2. Cleaning đã thành công: `rows=24`, `unique_ids=24`, `has_text=True`.
3. Dữ liệu sạch đủ schema để truyền tiếp cho embedding và evaluation.

Không ghi nhận số liệu đánh giá tương ứng cho baseline/corrupted/repaired vì phần đó thuộc trách nhiệm của các module tiếp theo, không phải phần tôi chủ trì trực tiếp. Tôi chỉ ghi những kết quả đã có bằng chứng thực tế và đã chạy thành công.

## 9. Điều học được và hướng cải thiện

### Ba điều quan trọng nhất

1. Data pipeline cần giữ contract schema rõ ràng từ đầu, vì lỗi nhỏ ở raw hoặc cleaning sẽ làm toàn bộ pipeline sau sai.
2. Freshness và quality là hai khía cạnh khác nhau: quality giữ tính toàn vẹn dữ liệu, freshness giữ độ mới của dữ liệu.
3. Khi dữ liệu vào sai, agent RAG sẽ trả lời sai hoặc thiếu độ tin cậy dù model mạnh; vì vậy observability không phải optional mà là phần bắt buộc.

### Nếu có thêm thời gian

- Tối ưu hóa `build_clean_dataframe` để ghi rõ hơn `quality_flags` (null, duplicate, summary too short, age > threshold) để module observability dễ nhận input.
- Thêm unit test nhỏ cho `parse_crossref_payload` và `build_clean_dataframe` để kiểm tra contract trước khi chạy pipeline lớn.

## 10. Cam kết của thành viên

Đánh dấu sau khi tự kiểm tra:

- [x] Nội dung báo cáo phản ánh đúng phần việc và mức hiểu của tôi.
- [x] Tôi có thể giải thích luồng end-to-end, không chỉ module mình phụ trách.
- [x] Mọi kết luận về kết quả đều có artifact hoặc metric để đối chiếu.
- [x] Tôi không ghi “đã chạy thành công” cho phần chưa được kiểm chứng.
- [x] Báo cáo không chứa `.env`, API key, token hoặc secret.
- [x] Báo cáo này không phải bản sao nguyên văn của báo cáo nhóm hoặc báo cáo thành viên khác.

**Họ và tên:** Đồng Mạnh Hùng
**Ngày xác nhận:** 2026-09-26
