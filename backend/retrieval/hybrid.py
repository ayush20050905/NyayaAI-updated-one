from typing import List, Dict, Any

from backend.retrieval.chroma import retrieve
from backend.retrieval.bm25 import keyword_search
from backend.utils.config import TOP_K

# Load permanent BM25 once
from backend.retrieval.bm25 import load_documents
load_documents()


def hybrid_search(
    query: str,
    mode: str = "permanent",
    semantic_k: int = TOP_K,
    keyword_k: int = TOP_K,
) -> List[Dict[str, Any]]:

    semantic = retrieve(
        query=query,
        top_k=semantic_k,
        mode=mode,
    )

    # Uploaded PDFs currently don't have a BM25 index.
    # Use semantic search only for them.
    if mode == "dynamic":
        keyword = []
    else:
        keyword = keyword_search(query, keyword_k)

    merged = []
    seen = set()

    if semantic and semantic.get("documents"):

        docs = semantic["documents"][0]
        metas = semantic["metadatas"][0]

        for doc, meta in zip(docs, metas):

            key = (
                meta.get("law"),
                meta.get("section"),
            )

            if key in seen:
                continue

            seen.add(key)

            merged.append(
                {
                    "document": doc,
                    "metadata": meta,
                }
            )

    for item in keyword:

        meta = item["metadata"]

        key = (
            meta.get("law"),
            meta.get("section"),
        )

        if key in seen:
            continue

        seen.add(key)

        merged.append(
            {
                "document": item["document"],
                "metadata": meta,
            }
        )

    if not merged:
        return []

    return merged[:3]