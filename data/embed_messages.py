import os
from functools import lru_cache
from typing import List
from sentence_transformers import SentenceTransformer
import numpy as np
import torch

MODEL_NAME = os.getenv("EMBED_MODEL", "intfloat/e5-small-v2")
# Bạn có thể đổi model nhanh hơn như:
# MODEL_NAME = "intfloat/e5-small-v2"
# MODEL_NAME = "nomic-ai/nomic-embed-text-v1.5"

class Embedder:
    def __init__(self):
        print(f"Loading embedding model: {MODEL_NAME}")
        # Ưu tiên GPU nếu có
        device = "cuda" if torch.cuda.is_available() else "cpu"
        self.model = SentenceTransformer(MODEL_NAME, device=device)
        print(f"Model loaded on {device}")

    @lru_cache(maxsize=10000)
    def embed_cached(self, text: str):
        if not text or not text.strip():
            return np.zeros((self.model.get_sentence_embedding_dimension(),), dtype=np.float32)
        vec = self.model.encode(
            text,
            convert_to_numpy=True,
            normalize_embeddings=True,
            show_progress_bar=False
        )
        return vec

    def embed(self, text: str):
        if not text or not text.strip():
            return np.zeros((self.model.get_sentence_embedding_dimension(),), dtype=np.float32)
        return self.model.encode(
            text,
            convert_to_numpy=True,
            normalize_embeddings=True,
            show_progress_bar=False
        )

    def embed_batch(self, texts: List[str], batch_size: int = 32):
        texts = [t.strip() for t in texts if t and t.strip()]
        if not texts:
            return np.array([], dtype=np.float32)
        return self.model.encode(
            texts,
            convert_to_numpy=True,
            normalize_embeddings=True,
            batch_size=batch_size,
            show_progress_bar=False
        )
embedder = Embedder()

if __name__ == "__main__":
    # Test nhanh
    print("Embedding test:", embedder.embed("Đồ ăn healthy là gì?")[:5])
