"""
Phase 2 — Cosine similarity scorer.
Embeddings are cached to .npy files keyed on the YAML content hash,
so bullets are only re-embedded when master.yaml changes.
"""

import hashlib
from pathlib import Path

import httpx
import numpy as np

from ajas.logger import log

_CACHE_DIR = Path("data/.embed_cache")


def _yaml_hash(yaml_path: str) -> str:
    """Return a short hash of the master YAML content for cache keying."""
    content = Path(yaml_path).read_bytes() if Path(yaml_path).exists() else b""
    return hashlib.md5(content).hexdigest()[:12]


class Scorer:
    def __init__(self, model_name: str = "nomic-embed-text"):
        """Initialize the scorer with Ollama embedding model."""
        self.model_name = model_name
        self.url = "http://localhost:11434/api/embeddings"
        _CACHE_DIR.mkdir(parents=True, exist_ok=True)

    def _cache_path(self, key: str) -> Path:
        return _CACHE_DIR / f"{key}.npy"

    def get_embeddings(
        self, texts: list[str], cache_key: str | None = None
    ) -> np.ndarray:
        """
        Compute embeddings for a list of texts via Ollama.
        If cache_key is provided, results are loaded/saved as a .npy file
        so re-embedding is skipped when the source content hasn't changed.
        """
        if cache_key:
            cache_file = self._cache_path(cache_key)
            if cache_file.exists():
                log.info(f"Loading cached embeddings from {cache_file}")
                return np.load(str(cache_file))

        embeddings = []
        for text in texts:
            payload = {"model": self.model_name, "prompt": text}
            try:
                response = httpx.post(self.url, json=payload, timeout=30)
                response.raise_for_status()
                embeddings.append(response.json()["embedding"])
            except Exception as e:
                log.warning(
                    f"Ollama embedding failed for text '{text[:30]}...': {e}. Using zero vector."
                )
                embeddings.append(np.zeros(768).tolist())  # nomic-embed-text dimension

        arr = np.array(embeddings, dtype=np.float32)

        if cache_key:
            np.save(str(self._cache_path(cache_key)), arr)
            log.info(f"Cached {len(texts)} embeddings → {self._cache_path(cache_key)}")

        return arr

    def top_bullets(
        self,
        bullets: list[dict],
        job_description: str,
        k: int = 5,
        yaml_path: str | None = None,
    ) -> list[dict]:
        """
        Find top-k bullets by cosine similarity to the job description.
        Returns the bullet dicts with an added 'relevance_score' field.
        Bullets below threshold 0.45 are logged as mismatches.
        """
        if not bullets or not job_description:
            return []

        bullet_texts = [b.get("text", "") for b in bullets]

        # Build cache key from YAML hash (bullets stay stable between calls)
        cache_key = f"bullets_{_yaml_hash(yaml_path)}" if yaml_path else None

        # 1. Embed job description (not cached — unique per call)
        jd_emb = self.get_embeddings([job_description])

        # 2. Embed bullets (cached when yaml_path provided)
        bullet_embs = self.get_embeddings(bullet_texts, cache_key=cache_key)

        # 3. Cosine similarity (normalize first)
        def _normalize(v: np.ndarray) -> np.ndarray:
            norms = np.linalg.norm(v, axis=1, keepdims=True)
            return v / (norms + 1e-9)

        b_norm = _normalize(bullet_embs)
        jd_norm = _normalize(jd_emb)
        sims = np.dot(b_norm, jd_norm.T).flatten()

        # 4. Weight boost from master YAML weight field (1–10 → 1–10% boost)
        for i, b in enumerate(bullets):
            weight = b.get("weight", 5)
            sims[i] *= 1.0 + (weight / 100.0)

        # 5. Threshold logging — start at 0.45 as CLAUDE.md specifies
        THRESHOLD = 0.45
        for i, (b, score) in enumerate(zip(bullets, sims)):
            if score < THRESHOLD:
                log.debug(
                    f"Low relevance ({score:.3f} < {THRESHOLD}): {b.get('text', '')[:60]}"
                )

        # 6. Return top k with relevance_score attached
        top_indices = sims.argsort()[-k:][::-1]
        result = []
        for idx in top_indices:
            bullet = dict(bullets[idx])
            bullet["relevance_score"] = float(sims[idx])
            result.append(bullet)

        return result

    def get_ats_score(self, cv_text: str, jd_text: str) -> float:
        """
        ATS keyword scorer — extracts text from the final sent PDF/markdown
        and scores matched_keywords / total_jd_keywords × 100.
        Warns if score < 60%.
        """
        import re

        def extract_keywords(text: str) -> set[str]:
            # Remove common stop words to avoid noise
            STOP = {
                "the",
                "and",
                "for",
                "with",
                "are",
                "this",
                "that",
                "have",
                "will",
                "you",
                "our",
                "has",
                "its",
                "was",
                "but",
                "not",
                "from",
                "your",
                "all",
                "can",
                "they",
                "been",
                "their",
            }
            words = re.findall(r"\b[a-zA-Z]{3,}\b", text.lower())
            return {w for w in words if w not in STOP}

        cv_words = extract_keywords(cv_text)
        jd_words = extract_keywords(jd_text)

        if not jd_words:
            return 0.0

        matches = cv_words.intersection(jd_words)
        score = (len(matches) / len(jd_words)) * 100

        if score < 60:
            log.warning(
                f"Low ATS score: {score:.1f}%. "
                f"Matched {len(matches)}/{len(jd_words)} unique JD keywords."
            )
        return score
