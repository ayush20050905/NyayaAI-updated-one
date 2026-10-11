from pathlib import Path

# ==========================================================
# PROJECT ROOT
# ==========================================================

ROOT_DIR = Path(__file__).resolve().parents[2]

# ==========================================================
# DATA
# ==========================================================

DATA_DIR = ROOT_DIR / "data"

RAW_DIR = DATA_DIR / "raw"

PROCESSED_DIR = DATA_DIR / "processed"

# ==========================================================
# PERMANENT DATA
# ==========================================================

PERMANENT_RAW = RAW_DIR / "permanent"

PERMANENT_CLEANED = PROCESSED_DIR / "permanent" / "cleaned"

PERMANENT_CHUNKS = PROCESSED_DIR / "permanent" / "chunks"

PERMANENT_EMBEDDINGS = PROCESSED_DIR / "permanent" / "embeddings"

# ==========================================================
# DYNAMIC DATA
# ==========================================================

DYNAMIC_RAW = RAW_DIR / "dynamic"

DYNAMIC_CLEANED = PROCESSED_DIR / "dynamic" / "cleaned"

DYNAMIC_CHUNKS = PROCESSED_DIR / "dynamic" / "chunks"

DYNAMIC_EMBEDDINGS = PROCESSED_DIR / "dynamic" / "embeddings"

DYNAMIC_PROFILES = PROCESSED_DIR / "dynamic" / "profiles"

# ==========================================================
# VECTOR DATABASES
# ==========================================================

VECTOR_DB = ROOT_DIR / "vector_db"

PERMANENT_DB = VECTOR_DB / "permanent" / "chroma"

DYNAMIC_DB = VECTOR_DB / "dynamic" / "chroma"

# ==========================================================
# CORE LAWS
# ==========================================================

CORE_LAWS = {

    "Constitution",

    "BNS",

    "BNSS",

    "BSA"

}

# ==========================================================
# MODEL
# ==========================================================

EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"

RERANK_MODEL = "cross-encoder/ms-marco-MiniLM-L-6-v2"

OLLAMA_MODEL = "llama3.2:3b"

# ==========================================================
# CHUNKING
# ==========================================================

CHUNK_SIZE = 900

CHUNK_OVERLAP = 150

# ==========================================================
# RETRIEVAL
# ==========================================================

TOP_K = 5

RERANK_TOP_K = 3

CONFIDENCE_THRESHOLD = 0.60