import hashlib
import json
from pathlib import Path

from rank_bm25 import BM25Okapi

from .config import Settings
from .corpus import CorpusError, Registry, atomic_json, chunks, extract_pages, tokens
from .schemas import Evidence


class OllamaEmbeddings:
    def __init__(self, settings: Settings):
        import ollama
        self.client = ollama.Client(host=settings.host, timeout=settings.timeout)
        self.model = settings.embed_model

    def embed(self, texts, query=False):
        prefix = "search_query: " if query else "search_document: "
        if not self.model.startswith("nomic-embed-text"):
            prefix = ""
        response = self.client.embed(model=self.model, input=[prefix + t for t in texts], truncate=False)
        return response.embeddings


def chroma_client(path: Path):
    import chromadb
    from chromadb.config import Settings as ChromaSettings
    return chromadb.PersistentClient(str(path), settings=ChromaSettings(anonymized_telemetry=False))


def ingest(settings: Settings, lexical_only=False, strict=False):
    registry = Registry(settings.data_dir)
    count = len(registry.docs)
    if strict and (registry.manifest.synthetic or not 20 <= count <= 30):
        raise CorpusError("Submission ingestion requires 20–30 real, individually registered documents.")
    records = []
    for doc in registry.docs.values():
        doc_count = 0
        for locator, text in extract_pages(registry.path(doc)):
            for i, text_chunk in enumerate(chunks(text)):
                doc_count += 1
                key = hashlib.sha256(f"{doc.id}|{locator}|{i}|{text_chunk}".encode()).hexdigest()[:20]
                records.append(Evidence(id="doc_" + key, document_id=doc.id, title=doc.title,
                    locator=f"{locator}, chunk {i + 1}", text=text_chunk,
                    source_url=doc.source_url, synthetic=doc.synthetic,
                    applicability_note=doc.notes).model_dump())
        if doc_count == 0:
            raise CorpusError(f"{doc.id}: document has no extractable text.")
    if not records:
        raise CorpusError("No documents to index.")
    fingerprint = registry.fingerprint()
    signature = hashlib.sha256((fingerprint + settings.embed_model + str(lexical_only)).encode()).hexdigest()[:20]
    collection_name = "academic_" + signature
    if not lexical_only:
        client = chroma_client(settings.state_dir / "chroma")
        collection = client.get_or_create_collection(collection_name, embedding_function=None,
                                                     metadata={"hnsw:space": "cosine"})
        embedder = OllamaEmbeddings(settings)
        for start in range(0, len(records), 16):
            batch = records[start:start + 16]
            vectors = embedder.embed([r["text"] for r in batch])
            collection.upsert(ids=[r["id"] for r in batch], embeddings=vectors,
                              documents=[r["text"] for r in batch],
                              metadatas=[{"document_id": r["document_id"]} for r in batch])
    # Only publish the catalogue after ALL documents and embeddings succeed.
    catalogue = {"fingerprint": fingerprint, "embedding_model": settings.embed_model,
                 "lexical_only": lexical_only, "collection": collection_name,
                 "documents": count, "records": records}
    atomic_json(settings.state_dir / "catalogue.json", catalogue)
    return {"documents": count, "chunks": len(records), "synthetic": registry.manifest.synthetic,
            "retrieval": "lexical-only ablation" if lexical_only else "dense + BM25 + reciprocal rank fusion"}


class Retriever:
    def __init__(self, settings: Settings, registry: Registry):
        self.settings, self.registry = settings, registry
        path = settings.state_dir / "catalogue.json"
        if not path.exists():
            raise CorpusError("The corpus has not been indexed. Run helpdesk ingest first.")
        self.catalogue = json.loads(path.read_text())
        if self.catalogue["fingerprint"] != registry.fingerprint():
            raise CorpusError("Documents or CSVs changed after indexing. Run helpdesk ingest again.")
        if not self.catalogue["lexical_only"] and self.catalogue["embedding_model"] != settings.embed_model:
            raise CorpusError("Embedding model changed. Re-ingest before querying.")
        self.records = {r["id"]: Evidence.model_validate(r) for r in self.catalogue["records"]
                        if registry.applicable(r["document_id"], settings.semester, settings.programme,
                                               settings.cohort, settings.branch)}
        self.ids = list(self.records)
        self.bm25 = BM25Okapi([tokens(self.records[i].text) for i in self.ids]) if self.ids else None

    def search(self, query: str, limit=6, categories=None):
        eligible = {i for i in self.ids if categories is None or
                    self.registry.docs[self.records[i].document_id].category in categories}
        for override in self.registry.manifest.topic_overrides:
            if any(term.lower() in query.lower() for term in override.get("keywords", [])):
                replacing = override.get("preferred_document_ids", [])
                if any(self.registry.applicable(d, self.settings.semester, self.settings.programme,
                                               self.settings.cohort, self.settings.branch) for d in replacing):
                    excluded = set(override.get("excluded_document_ids", []))
                    eligible = {i for i in eligible if self.records[i].document_id not in excluded}
        if not eligible:
            return []
        scores = self.bm25.get_scores(tokens(query))
        lexical = sorted(zip(self.ids, scores), key=lambda item: item[1], reverse=True)
        # BM25 can return zero/negative scores for very small corpora; token overlap is the fallback gate.
        query_tokens = set(tokens(query))
        lexical = [(i, s) for i, s in lexical if i in eligible and
                   query_tokens & set(tokens(self.records[i].text))]
        ranks = {}
        for rank, (key, _) in enumerate(lexical[:30], 1):
            ranks[key] = 1 / (60 + rank)
        if not self.catalogue["lexical_only"]:
            vector = OllamaEmbeddings(self.settings).embed([query], query=True)
            collection = chroma_client(self.settings.state_dir / "chroma").get_collection(
                self.catalogue["collection"], embedding_function=None)
            valid_docs = list({self.records[i].document_id for i in eligible})
            result = collection.query(query_embeddings=vector, n_results=min(30, len(eligible)),
                                      where={"document_id": {"$in": valid_docs}}, include=["distances"])
            for rank, (key, distance) in enumerate(zip(result["ids"][0], result["distances"][0]), 1):
                # Similarity is a retrieval heuristic, never a probability of truth.
                if key in self.records and distance < 0.75:
                    ranks[key] = ranks.get(key, 0) + 1 / (60 + rank)
        selected = sorted(ranks, key=ranks.get, reverse=True)
        return [self.records[i] for i in selected[:limit]]
