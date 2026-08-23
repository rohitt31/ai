"""
Retriever with document precedence logic and conflict detection.
Handles re-ranking based on metadata (active vs superseded, customer vs internal).
"""

from src.rag.vector_store import search
from src.config import TOP_K


# Precedence weights for re-ranking
STATUS_WEIGHT = {
    "active": 1.0,
    "superseded": 0.3,  # Heavy penalty for superseded docs
}

AUDIENCE_WEIGHT = {
    "customer": 1.0,
    "internal": 0.4,  # Internal docs should rarely surface to customers
}

DOC_TYPE_WEIGHT = {
    "policy": 1.0,
    "product": 0.95,
    "guide": 0.9,
    "internal": 0.3,
    "unknown": 0.7,
}


def retrieve(query: str, top_k: int | None = None) -> list[dict]:
    """
    Retrieve relevant passages with document precedence applied.
    
    Precedence rules:
    1. Active documents are strongly preferred over superseded ones.
    2. Customer-facing documents are preferred over internal ones.
    3. Policy documents are preferred for policy questions.
    4. Results are re-ranked after initial retrieval.
    """
    k = top_k or TOP_K
    
    # Fetch more than needed so we can re-rank
    raw_results = search(query, top_k=k * 2)
    
    if not raw_results:
        return []
    
    # Apply precedence-based re-ranking
    for result in raw_results:
        base_score = result["score"]
        
        status = result.get("status", "active")
        audience = result.get("audience", "customer")
        doc_type = result.get("document_type", "unknown")
        
        status_w = STATUS_WEIGHT.get(status, 0.5)
        audience_w = AUDIENCE_WEIGHT.get(audience, 0.7)
        doc_type_w = DOC_TYPE_WEIGHT.get(doc_type, 0.7)
        
        # Weighted score
        result["adjusted_score"] = base_score * status_w * audience_w * doc_type_w
        result["is_superseded"] = status == "superseded"
        result["is_internal"] = audience == "internal"
    
    # Sort by adjusted score
    raw_results.sort(key=lambda x: x["adjusted_score"], reverse=True)
    
    # Take top_k results
    results = raw_results[:k]
    
    # Detect conflicts between active sources
    conflicts = detect_conflicts(results)
    if conflicts:
        for result in results:
            result["has_conflicts"] = True
            result["conflict_info"] = conflicts
    
    return results


def detect_conflicts(results: list[dict]) -> list[str]:
    """
    Detect genuine conflicts between current authoritative sources.
    Returns a list of conflict descriptions.
    """
    conflicts = []
    
    # Check for conflicting active policies on the same topic
    active_policies = [r for r in results if r.get("status") == "active" and r.get("document_type") == "policy"]
    
    # Look for return window conflicts in general policy docs (exclude membership perks)
    return_windows = set()
    for policy in active_policies:
        src = policy.get("source", "").lower()
        if "membership" in src or "trailplus" in src:
            continue
        content = policy.get("content", "").lower()
        # Simple pattern matching for return windows
        import re
        window_matches = re.findall(r'(\d+)[- ]day(?:s)?\s+(?:return\s+)?window', content)
        for match in window_matches:
            return_windows.add((int(match), policy.get("source", "unknown")))
    
    if len(return_windows) > 1:
        windows_str = ", ".join(f"{days} days ({src})" for days, src in return_windows)
        conflicts.append(f"Multiple return windows found: {windows_str}")
    
    return conflicts


def format_context_for_prompt(results: list[dict]) -> str:
    """
    Format retrieved results into a context string for the LLM prompt.
    Includes metadata annotations to help the model make informed decisions.
    """
    if not results:
        return "No relevant documents found in the knowledge base."
    
    context_parts = []
    for i, result in enumerate(results, 1):
        status_note = ""
        if result.get("is_superseded"):
            superseded_by = result.get("superseded_by", "unknown")
            status_note = f" [⚠️ SUPERSEDED — replaced by {superseded_by}]"
        
        audience_note = ""
        if result.get("is_internal"):
            audience_note = " [🔒 INTERNAL DOCUMENT — do not share content with customers]"
        
        header = f"--- Source {i}: {result['source']} > {result['heading']}{status_note}{audience_note} ---"
        metadata = f"[Type: {result['document_type']} | Status: {result['status']} | Effective: {result.get('effective_date', 'N/A')}]"
        
        context_parts.append(f"{header}\n{metadata}\n{result['content']}")
    
    context = "\n\n".join(context_parts)
    
    # Add conflict warnings
    for result in results:
        if result.get("has_conflicts"):
            conflict_info = result.get("conflict_info", [])
            if conflict_info:
                context += "\n\n⚠️ CONFLICT DETECTED: " + "; ".join(conflict_info)
                context += "\nInstruction: Surface this conflict to the customer and recommend contacting support for clarification."
            break
    
    return context
