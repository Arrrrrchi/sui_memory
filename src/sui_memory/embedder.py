import numpy as np

from .config import MODEL_NAME, QUERY_PREFIX, DOC_PREFIX


class Embedder:
    _instance = None

    @classmethod
    def get(cls) -> "Embedder":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def __init__(self):
        import torch
        from sentence_transformers import SentenceTransformer

        # Force CPU to avoid MPS out-of-memory on Apple Silicon
        self.model = SentenceTransformer(MODEL_NAME, device=torch.device("cpu"))

    def embed_document(self, text: str) -> np.ndarray:
        return self.model.encode(
            DOC_PREFIX + text, normalize_embeddings=True
        )

    def embed_documents(self, texts: list[str]) -> np.ndarray:
        prefixed = [DOC_PREFIX + t for t in texts]
        return self.model.encode(prefixed, normalize_embeddings=True)

    def embed_query(self, text: str) -> np.ndarray:
        return self.model.encode(
            QUERY_PREFIX + text, normalize_embeddings=True
        )
