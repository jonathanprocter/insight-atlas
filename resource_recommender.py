import requests, os, json, platform, sys
import numpy as np

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
MEMORY_PATH = os.path.join(os.path.dirname(__file__), "resource_memory.json")

# ---------- AUTO-DETECT pCloud ----------

def find_pcloud():
    """Find pCloud mount path on macOS, Windows, or Linux."""
    override = os.getenv("PCLOUD_BASE")
    if override:
        p = os.path.expanduser(override)
        if os.path.isdir(p):
            return p

    home = os.path.expanduser("~")
    candidates = [
        os.path.join(home, "pCloud Drive"),       # macOS default
        os.path.join(home, "pCloudDrive"),         # macOS alternate
        os.path.join(home, "pCloud Sync"),         # Linux
        os.path.join(home, "pCloudSync"),          # Linux alternate
    ]
    if platform.system() == "Windows":
        for letter in "PDEFGHIJKLMNOPQRSTUVWXYZ":
            candidates.append(f"{letter}:\\pCloud")
            candidates.append(f"{letter}:\\")

    for path in candidates:
        if os.path.isdir(path):
            return path
    return None

PCLOUD_BASE = find_pcloud()

def _find_faiss_files():
    """Find FAISS index: check pCloud first, then Desktop fallback."""
    override_idx = os.getenv("FAISS_INDEX_PATH")
    override_meta = os.getenv("FAISS_META_PATH")
    if override_idx and override_meta:
        return os.path.expanduser(override_idx), os.path.expanduser(override_meta)

    locations = []
    if PCLOUD_BASE:
        locations.append(os.path.join(PCLOUD_BASE, "InsightAtlas"))
    locations.append(os.path.expanduser("~/Desktop"))
    locations.append(os.path.dirname(os.path.abspath(__file__)))

    for loc in locations:
        idx = os.path.join(loc, "book_index.faiss")
        meta = os.path.join(loc, "book_index_meta.json")
        if os.path.exists(idx) and os.path.exists(meta):
            return idx, meta
    return None, None

FAISS_INDEX_PATH, FAISS_META_PATH = _find_faiss_files()

# ---------- MEMORY ----------

def load_memory():
    if not os.path.exists(MEMORY_PATH):
        return {}
    with open(MEMORY_PATH) as f:
        return json.load(f)

def save_memory(data):
    with open(MEMORY_PATH, "w") as f:
        json.dump(data, f, indent=2)

# ---------- MODEL CALL ----------

def call_model(prompt, max_tokens=800):
    res = requests.post(
        "https://api.anthropic.com/v1/messages",
        headers={
            "x-api-key": ANTHROPIC_API_KEY,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json"
        },
        json={
            "model": "claude-sonnet-4-5",
            "max_tokens": max_tokens,
            "messages": [{"role": "user", "content": prompt}]
        },
        timeout=60
    )
    data = res.json()
    if "error" in data:
        return ""
    return data["content"][0]["text"]

# ---------- LEVEL 1: pCloud Library Scan ----------

def scan_pcloud_library():
    """Walk pCloud directories for clinical resources."""
    resources = []
    if not PCLOUD_BASE:
        return resources
    scan_dirs = [
        os.path.join(PCLOUD_BASE, d) for d in [
            "E-Book & Audiobook Library",
            "My Clinical Resources",
            "Handouts",
            "Psychology Tools",
            "Treatment Planners",
            "Therapy Cheat Sheets",
            "01 - Clinical Practice",
            "02 - Books & Summaries",
            "Card Decks - Therapy",
        ]
    ]
    valid_ext = (".pdf", ".txt", ".md", ".epub", ".docx")
    for base in scan_dirs:
        if not os.path.isdir(base):
            continue
        for root, _, files in os.walk(base):
            for f in files:
                if f.lower().endswith(valid_ext) and not f.startswith("."):
                    resources.append({
                        "title": os.path.splitext(f)[0],
                        "path": os.path.join(root, f),
                        "folder": os.path.basename(base)
                    })
    return resources

# ---------- LEVEL 2: Keyword Match ----------

def keyword_match(library, query, limit=10):
    """Simple keyword matching against library titles."""
    words = set(query.lower().split())
    # remove common words
    words -= {"the", "a", "an", "and", "or", "of", "in", "to", "for", "is", "on", "with", "that", "this"}

    scored = []
    for r in library:
        title_lower = r["title"].lower()
        hits = sum(1 for w in words if w in title_lower)
        if hits > 0:
            scored.append((hits, r))

    scored.sort(key=lambda x: x[0], reverse=True)
    return [r for _, r in scored[:limit]]

# ---------- LEVEL 3: Semantic Search (FAISS) ----------

_faiss_index = None
_faiss_meta = None
_embed_model = None

def _load_faiss():
    global _faiss_index, _faiss_meta
    if _faiss_index is not None:
        return True
    try:
        import faiss
        if not FAISS_INDEX_PATH or not FAISS_META_PATH:
            return False
        if not os.path.exists(FAISS_INDEX_PATH) or not os.path.exists(FAISS_META_PATH):
            return False
        _faiss_index = faiss.read_index(FAISS_INDEX_PATH)
        with open(FAISS_META_PATH) as f:
            _faiss_meta = json.load(f)
        return True
    except ImportError:
        return False

def _load_embedder():
    global _embed_model
    if _embed_model is not None:
        return True
    try:
        from sentence_transformers import SentenceTransformer
        _embed_model = SentenceTransformer("all-MiniLM-L6-v2")
        return True
    except ImportError:
        return False

def semantic_search(query, limit=10):
    """Search the FAISS book index semantically."""
    if not _load_faiss() or not _load_embedder():
        return []

    vec = _embed_model.encode([query])
    D, I = _faiss_index.search(np.array(vec).astype("float32"), limit)

    results = []
    for idx, dist in zip(I[0], D[0]):
        if idx < 0 or idx >= len(_faiss_meta):
            continue
        entry = _faiss_meta[idx].copy()
        entry["score"] = float(dist)
        results.append(entry)
    return results

# ---------- COMBINED RECOMMENDATION ----------

def recommend_resources(client_name, formulation, clusters):
    """
    Three-tier recommendation:
    1. Semantic search against FAISS book index
    2. Keyword match against pCloud library
    3. Claude-generated recommendations enriched with actual resources found
    """

    # Build search query from clinical content
    search_query = f"{clusters}\n{formulation}"

    # Tier 1: Semantic search
    semantic_results = semantic_search(search_query, limit=8)

    # Tier 2: Keyword scan of pCloud
    library = scan_pcloud_library()
    keyword_results = keyword_match(library, search_query, limit=8)

    # Deduplicate by title
    seen = set()
    all_resources = []
    for r in semantic_results + keyword_results:
        key = r["title"].lower()
        if key not in seen:
            seen.add(key)
            all_resources.append(r)

    # Format found resources for Claude
    if all_resources:
        resource_list = "\n".join(
            f"- {r['title']} ({r.get('path', 'N/A')})"
            for r in all_resources[:15]
        )
    else:
        resource_list = "(no local resources found)"

    # Tier 3: Claude synthesizes recommendations using actual library
    output = call_model(f"""You are a clinical resource recommender for a therapist.

Given the client's clinical clusters and formulation below, recommend the most relevant resources.

IMPORTANT: Prioritize resources from the therapist's OWN library listed below. For each recommendation, explain WHY it's clinically relevant to this client's patterns.

THERAPIST'S LIBRARY (matched resources):
{resource_list}

CLIENT CLUSTERS:
{clusters}

CLIENT FORMULATION:
{formulation}

For each recommended resource provide:
- Title
- Why it's relevant to this client
- Specific way to use it (chapter, exercise, handout)
- Therapeutic modality it supports

Also suggest any additional resources not in the library that would be valuable.""", 1200)

    # Build structured response
    found_section = ""
    if all_resources:
        found_section = "\n\nMATCHED FROM YOUR LIBRARY:\n" + "\n".join(
            f"  [{r['title']}] → {r.get('path', '')}"
            for r in all_resources[:10]
        )

    return [{
        "title": "Clinical Resources",
        "type": "semantic+AI",
        "content": output + found_section,
        "matched_resources": all_resources[:10]
    }]

# ---------- FEEDBACK ----------

def register_feedback(client, resource, helpful):
    memory = load_memory()
    memory.setdefault(client, {})
    memory[client].setdefault(resource, {"up": 0, "down": 0})
    if helpful:
        memory[client][resource]["up"] += 1
    else:
        memory[client][resource]["down"] += 1
    save_memory(memory)
    return {"status": "saved"}
