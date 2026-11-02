
import logging
import time
import uuid

from google import genai
from google.genai import types
from qdrant_client import QdrantClient, models

from .config import settings

logger = logging.getLogger(__name__)


class AIService:
    """Gemini embedding and text-generation service."""

    def __init__(self):
        if not settings.google_api_key:
            raise RuntimeError("GOOGLE_API_KEY is not configured")

        self.client = genai.Client(
            api_key=settings.google_api_key
        )

    def embed(self, text: str, task_type: str) -> list[float]:
        """Generate Gemini embeddings with retry handling."""

        last_error = None

        for attempt in range(3):
            try:
                result = self.client.models.embed_content(
                    model=settings.gemini_embedding_model,
                    contents=text,
                    config=types.EmbedContentConfig(
                        output_dimensionality=settings.embedding_dimension,
                        task_type=task_type,
                    ),
                )

                values = (
                    result.embeddings[0].values
                    if result.embeddings
                    else None
                )

                if (
                    not values
                    or len(values) != settings.embedding_dimension
                ):
                    raise RuntimeError(
                        "Embedding response has unexpected dimensions"
                    )

                return list(values)

            except Exception as exc:
                last_error = exc

                if attempt < 2:
                    time.sleep(0.5 * (2 ** attempt))

        raise RuntimeError(
            "Embedding provider failed after retries"
        ) from last_error

    def generate(self, prompt: str) -> str:
        """Generate an answer using Gemini."""

        result = self.client.models.generate_content(
            model=settings.gemini_chat_model,
            contents=prompt,
            config=types.GenerateContentConfig(
                temperature=0.1
            ),
        )

        return result.text or ""


class VectorStore:
    """
    Qdrant local persistent vector store.

    No Docker or separate database server is required.
    """

    def __init__(self):
        self.client = QdrantClient(
            path=settings.qdrant_path
        )

        self.name = settings.qdrant_collection

        if not self.client.collection_exists(self.name):
            self.client.create_collection(
                collection_name=self.name,
                vectors_config=models.VectorParams(
                    size=settings.embedding_dimension,
                    distance=models.Distance.COSINE,
                ),
            )

    def insert(
        self,
        rows: list[dict],
        vectors: list[list[float]],
    ):
        """Insert document chunks and embeddings into Qdrant."""

        points = []

        for row, vector in zip(rows, vectors, strict=True):
            points.append(
                models.PointStruct(
                    id=str(uuid.uuid4()),
                    vector=vector,
                    payload=row,
                )
            )

        # Insert in batches of 64.
        for offset in range(0, len(points), 64):
            self.client.upsert(
                collection_name=self.name,
                points=points[offset:offset + 64],
                wait=True,
            )

    def search(
        self,
        vector: list[float],
        departments: list[str],
        clearance: str,
        limit: int,
    ):
        """Search vectors with department-level filtering."""

        if not departments:
            return []

        access_filter = models.Filter(
            must=[
                models.FieldCondition(
                    key="department",
                    match=models.MatchAny(
                        any=departments
                    ),
                )
            ]
        )

        result = self.client.query_points(
            collection_name=self.name,
            query=vector,
            query_filter=access_filter,
            limit=limit,
            with_payload=True,
        )

        # Maintain the hit structure expected by graph.py.
        return [
            {
                "entity": point.payload or {},
                "distance": point.score or 0.0,
            }
            for point in result.points
        ]

    def close(self):
        """Close the local Qdrant client."""

        self.client.close()
