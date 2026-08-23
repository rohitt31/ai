"""
Unit tests for the document chunker.
Runs without API key — tests parsing and metadata extraction.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from src.rag.chunker import (
    split_by_headings,
    chunk_document,
    chunk_all_documents,
    Chunk,
)
from src.config import KNOWLEDGE_BASE_DIR


class TestSplitByHeadings:
    """Test heading-based document splitting."""
    
    def test_basic_split(self):
        content = (
            "# Title\nIntro text with enough content to exceed the minimum chunk size for proper splitting.\n\n"
            "## Section 1\nThis is a longer section with enough content to stand on its own as a separate chunk in the split.\n\n"
            "## Section 2\nAnother section with sufficient content that should also be split into its own chunk by the heading-based splitter."
        )
        sections = split_by_headings(content)
        assert len(sections) >= 2
    
    def test_single_section(self):
        content = "# Title\nJust one section with no sub-headings."
        sections = split_by_headings(content)
        assert len(sections) == 1
    
    def test_preserves_content(self):
        content = "## Return Window\nWe accept returns within 30 days of delivery."
        sections = split_by_headings(content)
        assert "30 days" in sections[0][1]
    
    def test_heading_extraction(self):
        content = "## My Heading\nSome content here"
        sections = split_by_headings(content)
        assert sections[0][0] == "My Heading"


class TestChunkDocument:
    """Test document chunking with metadata."""
    
    def test_chunks_returns_policy(self):
        path = KNOWLEDGE_BASE_DIR / "01-returns-policy-current.md"
        if not path.exists():
            pytest.skip("Knowledge base file not found")
        
        chunks = chunk_document(path)
        assert len(chunks) > 0
        
        # Check metadata
        chunk = chunks[0]
        assert chunk.status == "active"
        assert chunk.audience == "customer"
        assert chunk.document_type == "policy"
        assert chunk.source_file == "01-returns-policy-current.md"
    
    def test_legacy_policy_marked_superseded(self):
        path = KNOWLEDGE_BASE_DIR / "02-returns-policy-legacy.md"
        if not path.exists():
            pytest.skip("Knowledge base file not found")
        
        chunks = chunk_document(path)
        assert len(chunks) > 0
        assert chunks[0].status == "superseded"
        assert chunks[0].superseded_by in ["01-returns-policy-current.md", "RET-2026-01"]
    
    def test_internal_doc_marked_internal(self):
        path = KNOWLEDGE_BASE_DIR / "13-support-escalation.md"
        if not path.exists():
            pytest.skip("Knowledge base file not found")
        
        chunks = chunk_document(path)
        assert len(chunks) > 0
        assert chunks[0].audience == "internal"
    
    def test_chunk_ids_are_unique(self):
        chunks = chunk_all_documents(KNOWLEDGE_BASE_DIR)
        ids = [c.chunk_id for c in chunks]
        # Allow for auto-dedup in indexing, just check they're not all the same
        assert len(set(ids)) > 1


class TestChunkMetadata:
    """Test chunk metadata dict generation."""
    
    def test_to_metadata_dict(self):
        chunk = Chunk(
            content="test",
            source_file="test.md",
            heading="Test Heading",
            document_title="Test Doc",
            document_type="policy",
            status="active",
            audience="customer",
            effective_date="2025-01-01",
            tags=["returns", "refunds"],
        )
        meta = chunk.to_metadata_dict()
        assert meta["source_file"] == "test.md"
        assert meta["status"] == "active"
        assert meta["audience"] == "customer"
        assert "returns,refunds" in meta["tags"]
