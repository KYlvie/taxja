#!/usr/bin/env python3
"""Standalone Steuerbuch PDF ingestion. No app dependency."""
import os, sys, re, hashlib
from pathlib import Path
from typing import List, Dict, Any
try:
    import fitz
except ImportError:
    sys.exit("ERROR: pip install PyMuPDF")
try:
    import chromadb
except ImportError:
    sys.exit("ERROR: pip install chromadb")
try:
    from sentence_transformers import SentenceTransformer
except ImportError:
    sys.exit("ERROR: pip install sentence-transformers")

PDF_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "steuerbuch")
CHROMA_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "chroma")
COLLECTION = "steuerbuch_guides"
CHUNK_SIZE = 1500
CHUNK_OVERLAP = 200

def extract_text(p):
    d = fitz.open(p); t = [pg.get_text("text") for pg in d]; d.close(); return "\n".join(t)

def clean_text(t):
    t = re.sub(r"\n{3,}", "\n\n", t)
    t = re.sub(r"^\s*\d{1,3}\s*$", "", t, flags=re.MULTILINE)
    return re.sub(r"[ \t]{3,}", "  ", t).strip()

def split_chunks(text):
    paras = re.split(r"\n\n+", text)
    chunks, cur = [], ""
    for p in paras:
        p = p.strip()
        if not p: continue
        if len(cur) + len(p) + 2 <= CHUNK_SIZE:
            cur = (cur + "\n\n" + p).strip() if cur else p
        else:
            if cur: chunks.append(cur)
            if len(p) > CHUNK_SIZE:
                ws = p.split(); cur = ""
                for w in ws:
                    if len(cur)+len(w)+1 <= CHUNK_SIZE: cur = (cur+" "+w).strip() if cur else w
                    else:
                        if cur: chunks.append(cur)
                        cur = w
            else: cur = p
    if cur: chunks.append(cur)
    if CHUNK_OVERLAP > 0 and len(chunks) > 1:
        ov = [chunks[0]]
        for i in range(1, len(chunks)):
            ov.append(chunks[i-1][-CHUNK_OVERLAP:] + "\n" + chunks[i])
        chunks = ov
    return [c for c in chunks if len(c) > 50]


def parse_fn(fn):
    m = re.match(r"steuerbuch_(\d{4})_(de|en)\.pdf", fn, re.I)
    if m: return {"year": int(m.group(1)), "language": m.group(2)}
    y, l = 2026, "de"
    for yr in (2024,2025):
        if str(yr) in fn: y = yr
    if "en" in fn.lower(): l = "en"
    return {"year": y, "language": l}

def fhash(p):
    h = hashlib.sha256()
    with open(p,"rb") as f: h.update(f.read(65536))
    return h.hexdigest()[:16]

def main():
    force = "--force" in sys.argv
    print("="*60+"\nSteuerbuch PDF Ingestion\n"+"="*60)
    pdf_dir = Path(PDF_DIR)
    if not pdf_dir.exists(): sys.exit(f"ERROR: {pdf_dir} not found")
    pdfs = sorted(pdf_dir.glob("*.pdf"))
    if not pdfs: sys.exit(f"ERROR: No PDFs in {pdf_dir}")
    print(f"Dir: {pdf_dir.resolve()}")
    print(f"ChromaDB: {Path(CHROMA_DIR).resolve()}")
    print(f"PDFs: {', '.join(f.name for f in pdfs)}\nForce: {force}\n")
    os.makedirs(CHROMA_DIR, exist_ok=True)
    client = chromadb.PersistentClient(path=CHROMA_DIR)
    try:
        coll = client.get_collection(COLLECTION)
        if force:
            client.delete_collection(COLLECTION)
            coll = client.get_or_create_collection(COLLECTION, metadata={"hnsw:space":"cosine"})
            print("Collection reset\n")
    except Exception:
        coll = client.get_or_create_collection(COLLECTION, metadata={"hnsw:space":"cosine"})
    print("Loading embedding model...")
    model = SentenceTransformer("paraphrase-multilingual-MiniLM-L12-v2")
    print("Loaded.\n")
    total = 0
    for pp in pdfs:
        meta = parse_fn(pp.name); fh = fhash(str(pp))
        if not force:
            try:
                ex = coll.get(where={"file_hash": fh}, limit=1)
                if ex and ex.get("ids") and len(ex["ids"])>0:
                    print(f"[SKIP] {pp.name}"); continue
            except Exception: pass
        print(f"[INGEST] {pp.name} (year={meta['year']}, lang={meta['language']})")
        text = clean_text(extract_text(str(pp)))
        if not text: print("  Empty, skip"); continue
        chunks = split_chunks(text)
        print(f"  {len(text):,} chars -> {len(chunks)} chunks")
        docs, metas, ids = [], [], []
        for i, ch in enumerate(chunks):
            docs.append(ch)
            metas.append({"source":f"BMF Steuerbuch {meta['year']}","year":meta["year"],
                "language":meta["language"],"file":pp.name,"file_hash":fh,
                "chunk_index":i,"category":"steuerbuch"})
            ids.append(f"sb_{meta['year']}_{meta['language']}_{i:04d}")
        print("  Embedding...")
        embs = model.encode(docs).tolist()
        coll.add(embeddings=embs, documents=docs, metadatas=metas, ids=ids)
        total += len(chunks)
        print(f"  Done ({len(chunks)} chunks)")
    print(f"\nComplete: {total} chunks in {Path(CHROMA_DIR).resolve()}")

if __name__ == "__main__":
    main()
