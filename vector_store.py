"""
FAISS Vector Index Builder
Creates a vector search index from the Arduino knowledge base
for retrieval-augmented generation (RAG).
"""
import json
import numpy as np
import os
import sys
from pathlib import Path
import sqlite3
import hashlib


class ArduinoVectorStore:
    """FAISS + SQLite vector store for Arduino documentation."""

    def __init__(self, data_dir="docs_data"):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(exist_ok=True)
        self.db_path = self.data_dir / "arduino_docs.db"
        self.index_path = self.data_dir / "arduino_faiss.index"
        self.index = None
        self.embedder = None
        self.dimension = 384  # MiniLM embedding dimension

    def _init_db(self):
        """Initialize SQLite database for document storage."""
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS documents (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                doc_hash TEXT UNIQUE,
                title TEXT,
                category TEXT,
                content TEXT,
                source TEXT DEFAULT 'builtin'
            )
        """)
        conn.commit()
        return conn

    def _get_embedder(self):
        """Lazy-load the sentence transformer model."""
        if self.embedder is None:
            try:
                from sentence_transformers import SentenceTransformer
                print("  Loading embedding model (all-MiniLM-L6-v2)...", file=sys.stderr)
                self.embedder = SentenceTransformer('all-MiniLM-L6-v2')
                print("  Embedding model loaded.", file=sys.stderr)
            except ImportError:
                print("  ERROR: sentence-transformers not installed.")
                print("  Run: pip install sentence-transformers")
                raise
        return self.embedder

    def _hash_doc(self, doc):
        """Create a hash for deduplication."""
        text = f"{doc['title']}|{doc['content']}"
        return hashlib.md5(text.encode()).hexdigest()

    def build_index(self, knowledge_base_path=None):
        """Build FAISS index from the knowledge base JSON file."""
        try:
            import faiss
        except ImportError:
            print("  ERROR: faiss-cpu not installed. Run: pip install faiss-cpu")
            raise

        # Load knowledge base
        if knowledge_base_path is None:
            knowledge_base_path = self.data_dir / "arduino_knowledge_base.json"

        if not knowledge_base_path.exists():
            print(f"  Knowledge base not found at {knowledge_base_path}")
            print("  Run scraper.py first to build the knowledge base.")
            return False

        with open(knowledge_base_path, "r", encoding="utf-8") as f:
            docs = json.load(f)

        print(f"\n=== Building FAISS Vector Index ===\n")
        print(f"  Documents to index: {len(docs)}")

        # Store documents in SQLite
        conn = self._init_db()
        cursor = conn.cursor()

        stored_ids = []
        for doc in docs:
            doc_hash = self._hash_doc(doc)
            try:
                cursor.execute(
                    "INSERT OR IGNORE INTO documents (doc_hash, title, category, content, source) VALUES (?, ?, ?, ?, ?)",
                    (doc_hash, doc['title'], doc['category'], doc['content'], doc.get('source', 'builtin'))
                )
                # Get the ID
                cursor.execute("SELECT id FROM documents WHERE doc_hash = ?", (doc_hash,))
                row = cursor.fetchone()
                if row:
                    stored_ids.append(row[0])
            except Exception as e:
                print(f"  Warning: Could not store doc '{doc['title']}': {e}")

        conn.commit()
        print(f"  Stored {len(stored_ids)} documents in SQLite")

        # Generate embeddings
        embedder = self._get_embedder()

        # Prepare texts for embedding (title + content for better retrieval)
        texts = []
        for doc in docs:
            text = f"{doc['title']}. {doc['category']}. {doc['content']}"
            texts.append(text)

        print(f"  Generating embeddings for {len(texts)} documents...")
        embeddings = embedder.encode(texts, show_progress_bar=True, convert_to_numpy=True)
        embeddings = embeddings.astype('float32')

        # Normalize embeddings for cosine similarity
        faiss.normalize_L2(embeddings)

        # Build FAISS index
        self.dimension = embeddings.shape[1]
        self.index = faiss.IndexFlatIP(self.dimension)  # Inner Product = cosine sim after normalization
        self.index.add(embeddings)

        # Save the index
        faiss.write_index(self.index, str(self.index_path))
        print(f"  FAISS index saved: {self.index_path}")
        print(f"  Index contains {self.index.ntotal} vectors of dimension {self.dimension}")

        # Save ID mapping
        id_map_path = self.data_dir / "id_mapping.json"
        with open(id_map_path, "w") as f:
            json.dump({"db_ids": stored_ids, "dimension": self.dimension}, f)

        conn.close()
        print(f"\n  Vector store built successfully!")
        return True

    def load_index(self):
        """Load an existing FAISS index."""
        try:
            import faiss
        except ImportError:
            print("ERROR: faiss-cpu not installed.")
            return False

        if not self.index_path.exists():
            print(f"  No index found at {self.index_path}. Build it first.")
            return False

        self.index = faiss.read_index(str(self.index_path))
        print(f"  Loaded FAISS index with {self.index.ntotal} vectors", file=sys.stderr)
        return True

    def search(self, query, top_k=5):
        """Search the vector store for relevant documents."""
        try:
            import faiss
        except ImportError:
            return []

        if self.index is None:
            if not self.load_index():
                return []

        embedder = self._get_embedder()

        # Embed the query
        query_vec = embedder.encode([query], convert_to_numpy=True).astype('float32')
        faiss.normalize_L2(query_vec)

        # Search
        scores, indices = self.index.search(query_vec, top_k)

        # Load ID mapping
        id_map_path = self.data_dir / "id_mapping.json"
        if not id_map_path.exists():
            return []

        with open(id_map_path) as f:
            id_map = json.load(f)

        db_ids = id_map['db_ids']

        # Retrieve documents from SQLite
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()

        results = []
        for i, (score, idx) in enumerate(zip(scores[0], indices[0])):
            if idx < 0 or idx >= len(db_ids):
                continue
            db_id = db_ids[idx]
            cursor.execute("SELECT title, category, content FROM documents WHERE id = ?", (db_id,))
            row = cursor.fetchone()
            if row:
                results.append({
                    "rank": i + 1,
                    "score": float(score),
                    "title": row[0],
                    "category": row[1],
                    "content": row[2]
                })

        conn.close()
        return results


def build_vector_store():
    """Build the complete vector store."""
    store = ArduinoVectorStore()
    success = store.build_index()
    if success:
        # Test with a sample query
        print("\n=== Testing Search ===\n")
        test_queries = [
            "blink an LED",
            "read temperature sensor",
            "servo motor control",
            "I2C communication",
            "PWM pins on Arduino Uno"
        ]
        for query in test_queries:
            results = store.search(query, top_k=3)
            print(f"  Query: '{query}'")
            for r in results:
                print(f"    [{r['score']:.3f}] {r['title']} ({r['category']})")
            print()


if __name__ == "__main__":
    build_vector_store()
