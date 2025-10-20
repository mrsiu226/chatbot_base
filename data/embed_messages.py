import os
import pickle
from sentence_transformers import SentenceTransformer

MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"
MODEL_PATH = "data/embedder.pkl"


class Embedder:
    def __init__(self):
        self.model = None
        if os.path.exists(MODEL_PATH):
            # Load model đã lưu sẵn (nếu có)
            with open(MODEL_PATH, "rb") as f:
                self.model = pickle.load(f)
        else:
            # Nếu chưa có thì load từ Hugging Face
            self.model = SentenceTransformer(MODEL_NAME)
            os.makedirs("data", exist_ok=True)
            with open(MODEL_PATH, "wb") as f:
                pickle.dump(self.model, f)

    def embed(self, text: str):
        """Sinh embedding cho 1 câu"""
        if not self.model:
            raise ValueError("Model chưa sẵn sàng.")
        return self.model.encode(text, convert_to_numpy=True)


embedder = Embedder()
