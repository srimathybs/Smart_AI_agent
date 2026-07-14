"""rag_tool.py — RAG (Retrieval-Augmented Generation) for large documents using chunking + ChromaDB"""
import os, hashlib, json

RAG_DIR  = "memory/rag_db"
CHUNK_SIZE = 800    # chars per chunk
CHUNK_OVERLAP = 100 # overlap between chunks

def _chunk_text(text: str, size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> list[str]:
    """Split text into overlapping chunks."""
    chunks, start = [], 0
    while start < len(text):
        end = min(start + size, len(text))
        # Prefer breaking at paragraph/sentence boundary
        if end < len(text):
            for sep in ["\n\n", "\n", ". ", " "]:
                idx = text.rfind(sep, start + size // 2, end)
                if idx != -1:
                    end = idx + len(sep)
                    break
        chunks.append(text[start:end].strip())
        start = end - overlap
    return [c for c in chunks if c.strip()]

def _get_collection(doc_id: str):
    try:
        import chromadb
        os.makedirs(RAG_DIR, exist_ok=True)
        client = chromadb.PersistentClient(path=RAG_DIR)
        safe_id = "rag_" + doc_id.replace("-","_").replace(".","_")[:40]
        return client.get_or_create_collection(safe_id, metadata={"hnsw:space": "cosine"})
    except ImportError:
        return None

class RAGTool:
    name = "rag_search"
    description = (
        "Retrieve relevant passages from large indexed documents. "
        "INPUT: JSON with 'action' and fields. "
        "Actions: index (doc_id, content, filename) to index a document, "
        "search (doc_id, query, top_k) to find relevant chunks, "
        "list_docs to see all indexed documents. "
        "Use this instead of dumping full file content for large PDFs/docs (>2000 chars)."
    )

    def _run(self, input_str: str) -> str:
        try:
            data = json.loads(input_str) if isinstance(input_str, str) else input_str
        except Exception:
            return "ERROR: Input must be valid JSON."

        action = data.get("action", "search")

        if action == "index":
            doc_id   = data.get("doc_id", "")
            content  = data.get("content", "")
            filename = data.get("filename", doc_id)
            if not doc_id or not content:
                return "ERROR: 'doc_id' and 'content' are required."

            col = _get_collection(doc_id)
            if col is None:
                # Fallback: save chunks as JSON
                os.makedirs(RAG_DIR, exist_ok=True)
                chunks = _chunk_text(content)
                path = os.path.join(RAG_DIR, f"{doc_id}.json")
                with open(path, "w") as f:
                    json.dump({"filename": filename, "chunks": chunks}, f)
                return f"✅ Indexed '{filename}' ({len(chunks)} chunks) [fallback JSON mode — install chromadb for semantic search]"

            # Check if already indexed
            try:
                existing = col.count()
                if existing > 0:
                    col.delete(where={"doc_id": doc_id})
            except Exception:
                pass

            chunks = _chunk_text(content)
            ids  = [f"{doc_id}_chunk_{i}" for i in range(len(chunks))]
            metas = [{"doc_id": doc_id, "filename": filename, "chunk_idx": i} for i in range(len(chunks))]
            # Batch insert (ChromaDB limit: 5461 per batch)
            batch = 500
            for i in range(0, len(chunks), batch):
                col.add(documents=chunks[i:i+batch], metadatas=metas[i:i+batch], ids=ids[i:i+batch])
            return f"✅ Indexed '{filename}': {len(chunks)} chunks, ready for semantic search."

        elif action == "search":
            doc_id = data.get("doc_id", "")
            query  = data.get("query", "")
            top_k  = int(data.get("top_k", 5))
            if not doc_id or not query:
                return "ERROR: 'doc_id' and 'query' are required."

            col = _get_collection(doc_id)

            if col is None or col.count() == 0:
                # Try JSON fallback
                path = os.path.join(RAG_DIR, f"{doc_id}.json")
                if os.path.exists(path):
                    with open(path) as f:
                        data2 = json.load(f)
                    # Simple keyword match fallback
                    q_lower = query.lower()
                    scored = [(c, sum(w in c.lower() for w in q_lower.split())) for c in data2["chunks"]]
                    scored.sort(key=lambda x: -x[1])
                    hits = [c for c, s in scored[:top_k] if s > 0] or [c for c, _ in scored[:top_k]]
                    result = f"🔍 TOP {len(hits)} PASSAGES from '{data2['filename']}' (keyword match):\n\n"
                    result += "\n\n---\n\n".join(f"[Chunk {i+1}]\n{h}" for i, h in enumerate(hits))
                    return result
                return f"ERROR: Document '{doc_id}' not found. Index it first with action='index'."

            results = col.query(query_texts=[query], n_results=min(top_k, col.count()))
            docs = results.get("documents", [[]])[0]
            metas = results.get("metadatas", [[]])[0]
            if not docs:
                return f"No relevant passages found for: {query}"
            result = f"🔍 TOP {len(docs)} PASSAGES (semantic search):\n\n"
            result += "\n\n---\n\n".join(
                f"[Chunk {m.get('chunk_idx',i)+1} from '{m.get('filename', doc_id)}']\n{d}"
                for i, (d, m) in enumerate(zip(docs, metas))
            )
            return result

        elif action == "list_docs":
            os.makedirs(RAG_DIR, exist_ok=True)
            # List JSON fallback files
            json_docs = [f.replace(".json","") for f in os.listdir(RAG_DIR) if f.endswith(".json")]
            # Try ChromaDB collections
            chroma_docs = []
            try:
                import chromadb
                client = chromadb.PersistentClient(path=RAG_DIR)
                chroma_docs = [c.name.replace("rag_","") for c in client.list_collections()]
            except Exception:
                pass
            all_docs = list(set(json_docs + chroma_docs))
            if not all_docs:
                return "No documents indexed yet. Use action='index' first."
            return "📚 INDEXED DOCUMENTS:\n" + "\n".join(f"  - {d}" for d in all_docs)

        else:
            return f"ERROR: Unknown action '{action}'. Use: index, search, list_docs"
