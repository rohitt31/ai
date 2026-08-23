"""
Document chunker for the Aster & Row knowledge base.
Parses Markdown files with YAML front matter, splits by headings,
and preserves metadata for each chunk.
"""

import re
from pathlib import Path
from dataclasses import dataclass, field

import frontmatter


@dataclass
class Chunk:
    """A single chunk of content with metadata."""
    content: str
    source_file: str
    heading: str
    document_title: str
    document_type: str  # policy, guide, product, internal
    status: str  # active, superseded
    audience: str  # customer, internal
    effective_date: str
    tags: list[str] = field(default_factory=list)
    supersedes: str = ""
    superseded_by: str = ""
    chunk_id: str = ""
    
    def __post_init__(self):
        if not self.chunk_id:
            # Generate a deterministic chunk ID from source + heading
            safe_heading = re.sub(r'[^a-z0-9]+', '-', self.heading.lower()).strip('-')
            safe_source = Path(self.source_file).stem
            self.chunk_id = f"{safe_source}--{safe_heading}" if safe_heading else safe_source
    
    def to_metadata_dict(self) -> dict:
        """Convert metadata to a flat dict for ChromaDB storage."""
        return {
            "source_file": self.source_file,
            "heading": self.heading,
            "document_title": self.document_title,
            "document_type": self.document_type,
            "status": self.status,
            "audience": self.audience,
            "effective_date": self.effective_date,
            "tags": ",".join(self.tags),
            "supersedes": self.supersedes,
            "superseded_by": self.superseded_by,
        }


def parse_markdown_file(file_path: Path) -> tuple[dict, str]:
    """Parse a markdown file, extracting YAML front matter and body."""
    post = frontmatter.load(str(file_path))
    metadata = dict(post.metadata)
    content = post.content
    return metadata, content


def split_by_headings(content: str, min_chunk_size: int = 50) -> list[tuple[str, str]]:
    """
    Split markdown content by H2 headings.
    Returns list of (heading, content) tuples.
    Small sections are merged with the adjacent sections.
    """
    # Split on H1 and H2 headings (# ... or ## ...)
    pattern = r'^(#{1,3})\s+(.+)$'
    lines = content.split('\n')
    
    sections: list[tuple[str, str]] = []
    current_heading = ""
    current_lines: list[str] = []
    
    for line in lines:
        match = re.match(pattern, line)
        if match and len(match.group(1)) <= 2:  # H1 or H2
            # Save previous section
            if current_lines:
                section_text = '\n'.join(current_lines).strip()
                if section_text:
                    sections.append((current_heading, section_text))
            current_heading = match.group(2).strip()
            current_lines = [line]
        else:
            current_lines.append(line)
    
    # Don't forget the last section
    if current_lines:
        section_text = '\n'.join(current_lines).strip()
        if section_text:
            sections.append((current_heading, section_text))
    
    # Merge small sections
    merged: list[tuple[str, str]] = []
    for heading, text in sections:
        if not text.strip():
            continue
        if merged and (len(text) < min_chunk_size or len(merged[-1][1]) < min_chunk_size):
            prev_heading, prev_text = merged[-1]
            use_heading = heading if (not prev_heading or prev_heading.lower() == "overview") else prev_heading
            merged[-1] = (use_heading, prev_text + '\n\n' + text)
        else:
            merged.append((heading, text))
    
    return merged


def chunk_document(file_path: Path) -> list[Chunk]:
    """
    Process a single knowledge base document into chunks.
    Each chunk preserves the document's front matter metadata.
    """
    metadata, content = parse_markdown_file(file_path)
    
    # Extract metadata with defaults
    doc_title = metadata.get("title", file_path.stem)
    doc_type = metadata.get("document_type", "")
    if not doc_type:
        fname = file_path.name.lower()
        if "policy" in fname or "policy" in doc_title.lower() or "warranty" in fname:
            doc_type = "policy"
        elif "product" in fname or "card" in fname:
            doc_type = "product"
        elif "internal" in fname or "migration" in fname or "escalation" in fname:
            doc_type = "internal"
        else:
            doc_type = "guide"
            
    status = metadata.get("status", "active")
    audience = metadata.get("audience", "customer")
    effective_date = metadata.get("effective_date", "")
    tags = metadata.get("tags", [])
    supersedes = metadata.get("supersedes", "")
    superseded_by = metadata.get("superseded_by", "")
    
    # Split content by headings
    sections = split_by_headings(content)
    
    chunks = []
    for heading, section_content in sections:
        chunk = Chunk(
            content=section_content,
            source_file=file_path.name,
            heading=heading,
            document_title=doc_title,
            document_type=doc_type,
            status=status,
            audience=audience,
            effective_date=str(effective_date),
            tags=tags if isinstance(tags, list) else [tags],
            supersedes=str(supersedes),
            superseded_by=str(superseded_by),
        )
        chunks.append(chunk)
    
    return chunks


def chunk_all_documents(knowledge_base_dir: Path) -> list[Chunk]:
    """Process all markdown files in the knowledge base directory."""
    all_chunks = []
    
    for md_file in sorted(knowledge_base_dir.glob("*.md")):
        try:
            chunks = chunk_document(md_file)
            all_chunks.extend(chunks)
        except Exception as e:
            print(f"Warning: Failed to process {md_file.name}: {e}")
    
    return all_chunks
