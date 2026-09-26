from __future__ import annotations

from datetime import datetime
import pandas as pd

from ingestion.crossref import PaperRecord


def build_text_for_embedding(row) -> str:
    """Ghép text_for_embedding 5 phần theo Data Contract; corruption.py dùng lại hàm này."""
    return (
        f"Title: {row['title']}\n"
        f"Authors: {row['authors_joined']}\n"
        f"Published: {row['published']}\n"
        f"Categories: {row['categories_joined']}\n"
        f"Summary: {row['summary']}"
    )


def build_clean_dataframe(records: list[PaperRecord], run_date: datetime) -> pd.DataFrame:
    """
    Làm sạch dữ liệu raw records thành pandas.DataFrame sẵn sàng để embedding.
    """
    if not records:
        return pd.DataFrame()

    # 1. Chuyển đổi danh sách PaperRecord dataclass thành DataFrame
    df = pd.DataFrame([r.__dict__ for r in records])

    # 2. Xử lý khoảng trắng và chuẩn hóa cột văn bản
    for col in ['title', 'summary']:
        df[col] = df[col].astype(str).str.strip().replace(r'\s+', ' ', regex=True)

    # Nối danh sách tác giả và danh mục thành chuỗi phân tách bằng dấu phẩy
    df['authors_joined'] = df['authors'].apply(lambda x: ', '.join(x) if isinstance(x, list) else str(x))
    df['categories_joined'] = df['categories'].apply(lambda x: ', '.join(x) if isinstance(x, list) else str(x))
    
    # 3. Tính toán tuổi đời dữ liệu (age_days)
    # Cố gắng chuyển string 'published' sang datetime, gán NaT nếu lỗi
    df['published_dt'] = pd.to_datetime(df['published'], errors='coerce')

    # run_date có thể là timezone-aware (UTC) trong khi published_dt là naive.
    # Chuẩn hóa về naive trước khi tính chênh lệch ngày.
    run_ts = pd.Timestamp(run_date)
    if run_ts.tzinfo is not None:
        run_ts = run_ts.tz_localize(None)

    df['age_days'] = (run_ts - df['published_dt']).dt.days
    # Các bản ghi không có ngày hợp lệ sẽ được gán giá trị mặc định (ví dụ: 0)
    df['age_days'] = df['age_days'].fillna(0).astype(int)

    # 4. Tính toán độ dài summary
    df['summary_chars'] = df['summary'].str.len()

    # 5. Tạo cột tổng hợp text_for_embedding
    df['text_for_embedding'] = df.apply(build_text_for_embedding, axis=1)

    # 6. Khử trùng lặp và lọc dòng lỗi
    # Bỏ qua các dòng không có paper_id
    df = df.dropna(subset=['paper_id'])
    # Giữ lại bản ghi đầu tiên khi gặp trùng lặp id
    df = df.drop_duplicates(subset=['paper_id'], keep='first')
    
    # Lọc tùy chọn: Loại bỏ các bài báo không có summary hoặc quá ngắn để embed
    df = df[df['summary_chars'] > 20]

    # 7. Sắp xếp lại dataframe theo ngày xuất bản mới nhất và dọn dẹp
    df = df.sort_values(by='published_dt', ascending=False, na_position='last')
    
    # Bỏ cột tạm thời dùng cho tính toán
    df = df.drop(columns=['published_dt'])

    return df.reset_index(drop=True)