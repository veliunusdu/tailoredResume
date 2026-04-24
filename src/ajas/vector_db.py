import chromadb

from ajas.logger import log


class VectorDB:
    def __init__(self, db_path: str = "data/chroma_db"):
        """Initialize ChromaDB client."""
        log.info("Initializing ChromaDB connection...")
        try:
            self.client = chromadb.PersistentClient(path=db_path)
            self.collection = self.client.get_or_create_collection(
                name="job_descriptions"
            )
        except Exception as e:
            log.error(f"Failed to initialize ChromaDB: {e}")
            self.collection = None

    def add_job(self, job_id: str, job_text: str, metadata: dict = None):
        """Add a job description to the vector database."""
        if not self.collection:
            return

        # We assume the user has hundreds of JDs for Phase 5 to be relevant
        self.collection.upsert(
            documents=[job_text], metadatas=[metadata or {}], ids=[job_id]
        )
        log.info(f"Added job {job_id} to vector DB.")

    def find_similar_jobs(self, query_text: str, n_results: int = 5):
        """Find jobs mathematically similar to the query text (e.g., a past successful JD)."""
        if not self.collection:
            return []

        results = self.collection.query(query_texts=[query_text], n_results=n_results)

        # Format results for easier consumption
        matches = []
        if results and "documents" in results and results["documents"]:
            for i, doc in enumerate(results["documents"][0]):
                meta = results["metadatas"][0][i] if "metadatas" in results else {}
                dist = results["distances"][0][i] if "distances" in results else 0.0
                job_id = results["ids"][0][i]
                matches.append(
                    {"id": job_id, "text": doc, "metadata": meta, "distance": dist}
                )
        return matches
