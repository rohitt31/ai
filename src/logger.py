"""
Structured logging with observability for the support agent.
Provides debug-mode traces for: user messages, history, retrieved passages,
tool calls, responses, errors, and fallbacks.
"""

import json
import logging
import sys
from datetime import datetime, timezone
from typing import Any

from src.config import LOG_LEVEL, DEBUG


def setup_logger(name: str = "aster_agent") -> logging.Logger:
    """Set up a structured JSON logger."""
    logger = logging.getLogger(name)
    
    if logger.handlers:
        return logger
    
    level = logging.DEBUG if DEBUG else getattr(logging, LOG_LEVEL.upper(), logging.INFO)
    logger.setLevel(level)
    
    handler = logging.StreamHandler(sys.stderr)
    handler.setLevel(level)
    
    formatter = StructuredFormatter()
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    
    return logger


class StructuredFormatter(logging.Formatter):
    """Format log records as structured JSON for observability."""
    
    def format(self, record: logging.LogRecord) -> str:
        log_entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "component": record.name,
            "message": record.getMessage(),
        }
        
        # Add extra structured data if present
        if hasattr(record, "data"):
            log_entry["data"] = record.data
            
        return json.dumps(log_entry, default=str)


class AgentTrace:
    """
    Collects trace information for a single agent invocation.
    Provides structured observability into the agent's decision-making process.
    """
    
    def __init__(self):
        self.logger = setup_logger("aster_agent.trace")
        self.trace_data: dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "steps": [],
        }
    
    def log_user_message(self, message: str) -> None:
        """Log the current user message."""
        step = {"step": "user_message", "content": message}
        self.trace_data["steps"].append(step)
        self.logger.debug("User message", extra={"data": step})
    
    def log_conversation_history(self, history: list[dict]) -> None:
        """Log relevant conversation history sent to the model."""
        # Truncate long messages for logging
        truncated = []
        for msg in history:
            truncated.append({
                "role": msg.get("role", "unknown"),
                "content": msg.get("content", "")[:200] + ("..." if len(msg.get("content", "")) > 200 else ""),
            })
        step = {"step": "conversation_history", "turns": len(history), "history": truncated}
        self.trace_data["steps"].append(step)
        self.logger.debug("Conversation history", extra={"data": step})
    
    def log_retrieval(self, query: str, results: list[dict]) -> None:
        """Log retrieved passages with metadata and scores."""
        passages = []
        for r in results:
            passages.append({
                "source": r.get("source", "unknown"),
                "heading": r.get("heading", ""),
                "score": r.get("score", 0),
                "status": r.get("status", "unknown"),
                "snippet": r.get("content", "")[:150] + "...",
            })
        step = {"step": "retrieval", "query": query, "num_results": len(results), "passages": passages}
        self.trace_data["steps"].append(step)
        self.logger.debug("Retrieved passages", extra={"data": step})
    
    def log_tool_call(self, tool_name: str, arguments: dict, result: Any) -> None:
        """Log tool calls and their sanitized results."""
        # Sanitize result to remove any internal fields
        sanitized_result = result
        if isinstance(result, dict):
            sanitized_result = {k: v for k, v in result.items() 
                              if k not in ("customer_email", "shipping_address", "internal_notes", "risk_score")}
        
        step = {
            "step": "tool_call",
            "tool": tool_name,
            "arguments": arguments,
            "result": sanitized_result,
        }
        self.trace_data["steps"].append(step)
        self.logger.debug("Tool call", extra={"data": step})
    
    def log_response(self, response: str) -> None:
        """Log the final response sent to the user."""
        step = {"step": "response", "content": response[:500] + ("..." if len(response) > 500 else "")}
        self.trace_data["steps"].append(step)
        self.logger.info("Agent response", extra={"data": step})
    
    def log_error(self, error: str, context: str = "") -> None:
        """Log errors and fallbacks."""
        step = {"step": "error", "error": error, "context": context}
        self.trace_data["steps"].append(step)
        self.logger.error("Agent error", extra={"data": step})
    
    def log_handoff(self, reason: str) -> None:
        """Log when the agent recommends human handoff."""
        step = {"step": "handoff", "reason": reason}
        self.trace_data["steps"].append(step)
        self.logger.warning("Human handoff recommended", extra={"data": step})
    
    def get_trace(self) -> dict:
        """Return the complete trace data."""
        return self.trace_data
