"""
Build or rebuild the vector store index from knowledge base documents.
Run this before using the agent for the first time.
"""

import argparse
import sys
import os
from pathlib import Path

# Fix Windows console encoding
if sys.platform == "win32":
    os.environ.setdefault("PYTHONIOENCODING", "utf-8")
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from src.config import KNOWLEDGE_BASE_DIR
from src.rag.chunker import chunk_all_documents
from src.rag.vector_store import build_index


def main():
    parser = argparse.ArgumentParser(description="Build the knowledge base index")
    parser.add_argument("--rebuild", action="store_true", help="Force rebuild the index")
    args = parser.parse_args()
    
    print(f"[INDEX] Processing knowledge base files from: {KNOWLEDGE_BASE_DIR}")
    
    # Chunk all documents
    chunks = chunk_all_documents(KNOWLEDGE_BASE_DIR)
    print(f"[INDEX] Created {len(chunks)} chunks from {len(list(KNOWLEDGE_BASE_DIR.glob('*.md')))} documents")
    
    # Display chunk summary
    for chunk in chunks:
        status_icon = "[OK]" if chunk.status == "active" else "[SUPERSEDED]"
        audience_icon = "[PUBLIC]" if chunk.audience == "customer" else "[INTERNAL]"
        print(f"  {status_icon} {audience_icon} {chunk.source_file} > {chunk.heading[:50]}")
    
    # Build index
    print(f"\n[INDEX] Building vector index...")
    build_index(chunks, force_rebuild=args.rebuild)
    print("[INDEX] Index built successfully!")


if __name__ == "__main__":
    main()
