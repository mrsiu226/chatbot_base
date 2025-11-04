import psycopg2
from dotenv import load_dotenv
from tqdm import tqdm
import os
import pickle
from datetime import datetime

load_dotenv()

EMB_DIR = "data/embeddings"
LOCAL_DB_URL = os.getenv("POSTGRES_URL")
TABLE_NAME = "whoisme.embeddings"

# --- Kết nối PostgreSQL local ---
conn = psycopg2.connect(LOCAL_DB_URL)
cursor = conn.cursor()
print("Đã kết nối tới PostgreSQL local thành công.")


def load_vector_files():
    return [f for f in os.listdir(EMB_DIR) if f.endswith(".pkl")]


def upload_embeddings():
    files = load_vector_files()
    if not files:
        print("Không có file embedding nào trong thư mục data/embeddings.")
        return

    for file in files:
        path = os.path.join(EMB_DIR, file)
        with open(path, "rb") as f:
            data = pickle.load(f)

        sheet_name = data.get("sheet_name", "unknown")
        embeddings_by_col = data.get("embeddings_by_col", {})
        df = data.get("df")
        data_hash = data.get("data_hash", "")
        updated_at = data.get("updated_at", datetime.now().isoformat())

        rows = []

        # Duyệt từng cột embedding
        for col_name, col_data in embeddings_by_col.items():
            if isinstance(col_data, dict):
                texts = col_data.get("texts", [])
                embs = col_data.get("embeddings", [])
            else:
                embs = col_data
                texts = (
                    df[col_name].astype(str).tolist()
                    if df is not None and col_name in df.columns
                    else []
                )

            if len(texts) != len(embs):
                print(f"Số lượng text và embedding không khớp trong cột {col_name}")
                continue

            for idx, (text, emb) in enumerate(zip(texts, embs)):
                if hasattr(emb, "tolist"):
                    emb = emb.tolist()

                metadata = {}
                level = None
                if df is not None and idx < len(df):
                    metadata = df.iloc[idx].to_dict()
                    level = metadata.get("Mức")

                row = (
                    sheet_name,
                    col_name,
                    idx,
                    text,
                    str(emb),  
                    data_hash,
                    updated_at,
                    level,
                )
                rows.append(row)

        print(f"\n📦 Upload {len(rows)} embeddings từ {file} ({len(embeddings_by_col)} cột)...")

        if not rows:
            print("⚠️ File không có dữ liệu hợp lệ, bỏ qua.")
            continue

        # Upload theo batch 500 bản ghi/lần
        batch_size = 500
        for i in tqdm(range(0, len(rows), batch_size), desc=f"{sheet_name}"):
            chunk = rows[i:i + batch_size]
            try:
                args_str = b",".join(
                    cursor.mogrify("(%s,%s,%s,%s,%s,%s,%s,%s)", row) for row in chunk
                )
                cursor.execute(
                    b"INSERT INTO " + TABLE_NAME.encode() +
                    b" (sheet_name, column_name, row_index, text, embedding, data_hash, updated_at, level) VALUES " +
                    args_str
                )
                conn.commit()
            except Exception as e:
                print("❌ Lỗi khi upload batch:", e)
                conn.rollback()

        print(f"✅ Hoàn tất upload {file} ({len(rows)} bản ghi)\n")


def main():
    print("🚀 Bắt đầu upload embeddings lên PostgreSQL local...")
    upload_embeddings()
    cursor.close()
    conn.close()
    print("🏁 Hoàn tất toàn bộ quá trình upload!")


if __name__ == "__main__":
    main()
