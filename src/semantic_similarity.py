"""Funciones para representar y comparar semantica de contenidos."""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
import re

import numpy as np
from sklearn.metrics.pairwise import cosine_similarity

from src.text_processing import clean_text


DEFAULT_SEMANTIC_MODEL_NAME = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
DEFAULT_EMBEDDING_BACKEND = "sentence_transformers_local"
DEFAULT_CHUNKING_STRATEGY = "line_sentence_windows"
MAX_CHUNK_CHARS = 450
MIN_CHUNK_CHARS = 120
MODEL_CACHE_DIR = Path("models/sentence_transformers")


class SemanticSimilarityError(RuntimeError):
    """Se lanza cuando la capa semantica no puede calcular similitud."""


@dataclass(frozen=True)
class SemanticChunkMatch:
    """Representa un emparejamiento semantico entre dos fragmentos."""

    origin_index: int
    target_index: int
    score: float
    origin_text: str
    target_text: str


@dataclass(frozen=True)
class SemanticSimilarityResult:
    """Contiene el resultado del calculo de similitud semantica."""

    score: float
    document_score: float
    model_name: str
    backend: str
    chunking_strategy: str
    origin_chunk_count: int
    target_chunk_count: int
    origin_best_match_mean: float
    target_best_match_mean: float
    top_matches: list[SemanticChunkMatch]


def split_text_into_semantic_chunks(
    text: str,
    *,
    max_chunk_chars: int = MAX_CHUNK_CHARS,
    min_chunk_chars: int = MIN_CHUNK_CHARS,
) -> list[str]:
    """Divide un texto en bloques adecuados para obtener embeddings."""
    cleaned = clean_text(text)
    if not cleaned:
        return []

    raw_units = [unit.strip() for unit in cleaned.split("\n") if unit.strip()]
    if not raw_units:
        raw_units = [cleaned]

    atomic_units: list[str] = []
    for unit in raw_units:
        if len(unit) <= max_chunk_chars:
            atomic_units.append(unit)
            continue
        atomic_units.extend(split_long_unit(unit, max_chunk_chars=max_chunk_chars))

    chunks: list[str] = []
    current_parts: list[str] = []
    current_length = 0

    for unit in atomic_units:
        separator_length = 1 if current_parts else 0
        projected_length = current_length + separator_length + len(unit)
        if current_parts and projected_length > max_chunk_chars:
            chunks.append(" ".join(current_parts).strip())
            current_parts = [unit]
            current_length = len(unit)
            continue

        current_parts.append(unit)
        current_length = projected_length

    if current_parts:
        chunks.append(" ".join(current_parts).strip())

    return merge_small_chunks(chunks, min_chunk_chars=min_chunk_chars)


def split_long_unit(unit: str, *, max_chunk_chars: int) -> list[str]:
    """Divide un fragmento largo utilizando oraciones como primera opcion."""
    sentence_like_units = [
        candidate.strip()
        for candidate in re.split(r"(?<=[.!?;:])\s+", unit)
        if candidate.strip()
    ]
    if len(sentence_like_units) <= 1:
        return [
            unit[index:index + max_chunk_chars].strip()
            for index in range(0, len(unit), max_chunk_chars)
            if unit[index:index + max_chunk_chars].strip()
        ]

    split_units: list[str] = []
    current_parts: list[str] = []
    current_length = 0
    for sentence in sentence_like_units:
        separator_length = 1 if current_parts else 0
        projected_length = current_length + separator_length + len(sentence)
        if current_parts and projected_length > max_chunk_chars:
            split_units.append(" ".join(current_parts).strip())
            current_parts = [sentence]
            current_length = len(sentence)
            continue

        current_parts.append(sentence)
        current_length = projected_length

    if current_parts:
        split_units.append(" ".join(current_parts).strip())

    return split_units


def merge_small_chunks(chunks: list[str], *, min_chunk_chars: int) -> list[str]:
    """Une bloques demasiado pequenos para evitar embeddings poco informativos."""
    if len(chunks) <= 1:
        return chunks

    merged_chunks: list[str] = []
    buffer = ""
    for chunk in chunks:
        if not buffer:
            buffer = chunk
            continue

        if len(buffer) < min_chunk_chars:
            buffer = f"{buffer} {chunk}".strip()
            continue

        merged_chunks.append(buffer)
        buffer = chunk

    if buffer:
        if merged_chunks and len(buffer) < min_chunk_chars:
            merged_chunks[-1] = f"{merged_chunks[-1]} {buffer}".strip()
        else:
            merged_chunks.append(buffer)

    return merged_chunks


@lru_cache(maxsize=4)
def load_semantic_model(model_name: str = DEFAULT_SEMANTIC_MODEL_NAME):
    """Carga y cachea el modelo de embeddings semanticos."""
    try:
        from sentence_transformers import SentenceTransformer
    except ModuleNotFoundError as exc:
        raise SemanticSimilarityError(
            "Falta la dependencia 'sentence-transformers'. "
            "Instala las dependencias de la V2 para habilitar la comparacion semantica."
        ) from exc

    MODEL_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    try:
        model = SentenceTransformer(
            model_name,
            cache_folder=str(MODEL_CACHE_DIR),
            local_files_only=True,
        )
    except Exception as local_exc:
        try:
            model = SentenceTransformer(
                model_name,
                cache_folder=str(MODEL_CACHE_DIR),
                local_files_only=False,
            )
        except Exception as exc:
            raise SemanticSimilarityError(
                f"No se ha podido cargar el modelo semantico '{model_name}'. "
                f"Intento local: {local_exc}. Intento con descarga: {exc}"
            ) from exc

    return model


def encode_semantic_chunks(
    chunks: list[str],
    *,
    model_name: str = DEFAULT_SEMANTIC_MODEL_NAME,
) -> np.ndarray:
    """Genera embeddings normalizados para una lista de bloques de texto."""
    if not chunks:
        return np.empty((0, 0), dtype=np.float32)

    model = load_semantic_model(model_name)
    try:
        embeddings = model.encode(
            chunks,
            convert_to_numpy=True,
            normalize_embeddings=True,
            show_progress_bar=False,
        )
    except Exception as exc:
        raise SemanticSimilarityError(
            f"No se han podido generar embeddings para los contenidos: {exc}"
        ) from exc

    return np.asarray(embeddings, dtype=np.float32)


def build_document_embedding(chunk_embeddings: np.ndarray) -> np.ndarray:
    """Agrega embeddings de bloques en un embedding representativo del documento."""
    if chunk_embeddings.size == 0:
        return np.empty((0,), dtype=np.float32)

    document_embedding = chunk_embeddings.mean(axis=0)
    norm = np.linalg.norm(document_embedding)
    if norm == 0:
        return document_embedding.astype(np.float32)
    return (document_embedding / norm).astype(np.float32)


def build_top_semantic_matches(
    origin_chunks: list[str],
    target_chunks: list[str],
    similarity_matrix: np.ndarray,
    *,
    limit: int = 3,
) -> list[SemanticChunkMatch]:
    """Selecciona los pares de fragmentos mas representativos de la comparacion."""
    if similarity_matrix.size == 0 or limit <= 0:
        return []

    candidates: list[tuple[float, int, int]] = []
    for origin_index in range(similarity_matrix.shape[0]):
        for target_index in range(similarity_matrix.shape[1]):
            score = float(similarity_matrix[origin_index, target_index])
            candidates.append((score, origin_index, target_index))

    candidates.sort(key=lambda item: item[0], reverse=True)

    selected: list[SemanticChunkMatch] = []
    used_origin: set[int] = set()
    used_target: set[int] = set()

    for score, origin_index, target_index in candidates:
        if origin_index in used_origin or target_index in used_target:
            continue
        selected.append(
            SemanticChunkMatch(
                origin_index=origin_index,
                target_index=target_index,
                score=score,
                origin_text=origin_chunks[origin_index],
                target_text=target_chunks[target_index],
            )
        )
        used_origin.add(origin_index)
        used_target.add(target_index)
        if len(selected) >= min(limit, len(origin_chunks), len(target_chunks)):
            break

    if len(selected) < limit:
        selected_pairs = {
            (match.origin_index, match.target_index)
            for match in selected
        }
        for score, origin_index, target_index in candidates:
            pair = (origin_index, target_index)
            if pair in selected_pairs:
                continue
            selected.append(
                SemanticChunkMatch(
                    origin_index=origin_index,
                    target_index=target_index,
                    score=score,
                    origin_text=origin_chunks[origin_index],
                    target_text=target_chunks[target_index],
                )
            )
            selected_pairs.add(pair)
            if len(selected) >= limit:
                break

    return selected


def compute_semantic_text_similarity(
    text_a: str,
    text_b: str,
    *,
    model_name: str = DEFAULT_SEMANTIC_MODEL_NAME,
) -> SemanticSimilarityResult:
    """Calcula similitud semantica bidireccional entre dos textos."""
    origin_chunks = split_text_into_semantic_chunks(text_a)
    target_chunks = split_text_into_semantic_chunks(text_b)

    if not origin_chunks or not target_chunks:
        return SemanticSimilarityResult(
            score=0.0,
            document_score=0.0,
            model_name=model_name,
            backend=DEFAULT_EMBEDDING_BACKEND,
            chunking_strategy=DEFAULT_CHUNKING_STRATEGY,
            origin_chunk_count=len(origin_chunks),
            target_chunk_count=len(target_chunks),
            origin_best_match_mean=0.0,
            target_best_match_mean=0.0,
            top_matches=[],
        )

    origin_embeddings = encode_semantic_chunks(origin_chunks, model_name=model_name)
    target_embeddings = encode_semantic_chunks(target_chunks, model_name=model_name)

    similarity_matrix = cosine_similarity(origin_embeddings, target_embeddings)
    similarity_matrix = np.clip(similarity_matrix, 0.0, 1.0)
    origin_best_match_mean = float(similarity_matrix.max(axis=1).mean())
    target_best_match_mean = float(similarity_matrix.max(axis=0).mean())
    score = (origin_best_match_mean + target_best_match_mean) / 2.0

    origin_document_embedding = build_document_embedding(origin_embeddings)
    target_document_embedding = build_document_embedding(target_embeddings)
    document_score = 0.0
    if origin_document_embedding.size and target_document_embedding.size:
        document_score = float(
            cosine_similarity(
                origin_document_embedding.reshape(1, -1),
                target_document_embedding.reshape(1, -1),
            )[0][0]
        )
        document_score = float(np.clip(document_score, 0.0, 1.0))

    return SemanticSimilarityResult(
        score=score,
        document_score=document_score,
        model_name=model_name,
        backend=DEFAULT_EMBEDDING_BACKEND,
        chunking_strategy=DEFAULT_CHUNKING_STRATEGY,
        origin_chunk_count=len(origin_chunks),
        target_chunk_count=len(target_chunks),
        origin_best_match_mean=origin_best_match_mean,
        target_best_match_mean=target_best_match_mean,
        top_matches=build_top_semantic_matches(
            origin_chunks,
            target_chunks,
            similarity_matrix,
        ),
    )
