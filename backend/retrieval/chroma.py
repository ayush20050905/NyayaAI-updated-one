import re

import chromadb
from sentence_transformers import SentenceTransformer

from backend.utils.config import (
    PERMANENT_DB,
    DYNAMIC_DB,
    EMBEDDING_MODEL
)

PERMANENT_COLLECTION = "legal_documents"
DYNAMIC_COLLECTION = "uploaded_document"

print("Loading embedding model...")
model = SentenceTransformer(EMBEDDING_MODEL)
print("✓ Embedding model loaded")

# ==========================================================
# Permanent DB
# ==========================================================

permanent_client = chromadb.PersistentClient(path=str(PERMANENT_DB))
permanent_collection = permanent_client.get_or_create_collection(PERMANENT_COLLECTION)

print("✓ Connected to Permanent ChromaDB")


# ==========================================================
# Dynamic DB
# ==========================================================

def get_dynamic_collection():

    try:

        client = chromadb.PersistentClient(path=str(DYNAMIC_DB))

        return client.get_or_create_collection(DYNAMIC_COLLECTION)

    except Exception:

        return None


print("✓ Dynamic collection loader ready")


# ==========================================================
# Query Parser
# ==========================================================

def parse_query(query):

    q = query.upper()

    law = None

    if "BNSS" in q:
        law = "BNSS"

    elif "BNS" in q:
        law = "BNS"

    elif "BSA" in q:
        law = "BSA"

    elif "CONSTITUTION" in q or "ARTICLE" in q:
        law = "Constitution"

    article = re.search(r"ARTICLE\s+(\d+[A-Z]?)", q)

    section = re.search(r"SECTION\s+(\d+[A-Z]?)", q)

    return law, article, section


# ==========================================================
# Direct Lookup
# ==========================================================

def direct_lookup(query, collection):

    law, article, section = parse_query(query)

    if article:

        number = article.group(1)

        where = (
            {
                "$and": [
                    {"law": law},
                    {"section": f"Article {number}"}
                ]
            }
            if law
            else
            {"section": f"Article {number}"}
        )

        result = collection.get(where=where)

        if result["ids"]:

            return {
                "documents": [result["documents"]],
                "metadatas": [result["metadatas"]],
                "distances": [[0.0] * len(result["documents"])]
            }

    if section:

        number = section.group(1)

        where = (
            {
                "$and": [
                    {"law": law},
                    {"section": f"Section {number}"}
                ]
            }
            if law
            else
            {"section": f"Section {number}"}
        )

        result = collection.get(where=where)

        if result["ids"]:

            return {
                "documents": [result["documents"]],
                "metadatas": [result["metadatas"]],
                "distances": [[0.0] * len(result["documents"])]
            }

    return None


# ==========================================================
# Semantic Search
# ==========================================================

def semantic_search(query, collection, top_k=5):

    embedding = model.encode(query).tolist()

    return collection.query(
        query_embeddings=[embedding],
        n_results=top_k
    )


# ==========================================================
# Retrieve
# ==========================================================

def retrieve(query, top_k=5, mode="permanent"):

    # ---------------- Dynamic ----------------

    if mode == "dynamic":

        dynamic_collection = get_dynamic_collection()

        if dynamic_collection is None:

            return {
                "documents": [[]],
                "metadatas": [[]],
                "distances": [[]]
            }

        result = direct_lookup(query, dynamic_collection)

        if result:
            return result

        return semantic_search(query, dynamic_collection, top_k)

    # ---------------- Both ----------------

    if mode == "both":

        permanent = semantic_search(
            query,
            permanent_collection,
            top_k
        )

        dynamic_collection = get_dynamic_collection()

        if dynamic_collection:

            dynamic = semantic_search(
                query,
                dynamic_collection,
                top_k
            )

            return {

                "documents": [
                    permanent["documents"][0]
                    + dynamic["documents"][0]
                ],

                "metadatas": [
                    permanent["metadatas"][0]
                    + dynamic["metadatas"][0]
                ],

                "distances": [
                    permanent["distances"][0]
                    + dynamic["distances"][0]
                ]

            }

        return permanent

    # ---------------- Permanent ----------------

    result = direct_lookup(query, permanent_collection)

    if result:
        return result

    return semantic_search(
        query,
        permanent_collection,
        top_k
    )


# ==========================================================
# Test
# ==========================================================

if __name__ == "__main__":

    while True:

        q = input("\nAsk : ")

        if q.lower() == "exit":
            break

        results = retrieve(q, mode="both")

        for meta, doc in zip(
            results["metadatas"][0],
            results["documents"][0]
        ):

            print("=" * 60)
            print(meta.get("law"))
            print(meta.get("section"))
            print(doc[:500])