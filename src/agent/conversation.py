

from dataclasses import dataclass, field
from src.config import MAX_HISTORY_TURNS


@dataclass
class ConversationSession:
    """Manages a single conversation session with history."""
    
    session_id: str
    messages: list[dict] = field(default_factory=list)
    max_turns: int = MAX_HISTORY_TURNS
    
    def add_user_message(self, content: str) -> None:
        """Add a user message to the conversation."""
        self.messages.append({"role": "user", "content": content})
        self._trim_history()
    
    def add_assistant_message(self, content: str) -> None:
        """Add an assistant response to the conversation."""
        self.messages.append({"role": "assistant", "content": content})
        self._trim_history()
    
    def add_tool_call(self, tool_call_id: str, function_name: str, arguments: str) -> None:
        """Add a tool call message from the assistant."""
        self.messages.append({
            "role": "assistant",
            "content": None,
            "tool_calls": [{
                "id": tool_call_id,
                "type": "function",
                "function": {
                    "name": function_name,
                    "arguments": arguments,
                },
            }],
        })
    
    def add_tool_result(self, tool_call_id: str, result: str) -> None:
        """Add a tool result message."""
        self.messages.append({
            "role": "tool",
            "tool_call_id": tool_call_id,
            "content": result,
        })
    
    def get_history(self) -> list[dict]:
        """Get the conversation history for the LLM context."""
        return list(self.messages)
    
    def _trim_history(self) -> None:
        """
        Trim history to keep within the max_turns limit.
        Preserves the most recent turns, ensuring we don't break
        tool call / tool result pairs.
        """
        if len(self.messages) <= self.max_turns * 2:
            return
        
        # Keep the most recent messages, ensuring tool pairs stay together
        target_size = self.max_turns * 2
        
        while len(self.messages) > target_size:
            # Don't remove if the first message is a tool result (would orphan it)
            if self.messages[0].get("role") == "tool":
                # Remove the tool result and look for its call
                self.messages.pop(0)
            elif (self.messages[0].get("role") == "assistant" 
                  and self.messages[0].get("tool_calls")
                  and len(self.messages) > 1
                  and self.messages[1].get("role") == "tool"):
                # Remove tool call and its result together
                self.messages.pop(0)
                if self.messages and self.messages[0].get("role") == "tool":
                    self.messages.pop(0)
            else:
                self.messages.pop(0)
    
    def clear(self) -> None:
        """Clear the conversation history."""
        self.messages = []


class ConversationManager:
    """Manages multiple conversation sessions."""
    
    def __init__(self):
        self.sessions: dict[str, ConversationSession] = {}
    
    def get_or_create_session(self, session_id: str) -> ConversationSession:
        """Get an existing session or create a new one."""
        if session_id not in self.sessions:
            self.sessions[session_id] = ConversationSession(session_id=session_id)
        return self.sessions[session_id]
    
    def delete_session(self, session_id: str) -> None:
        """Delete a session."""
        self.sessions.pop(session_id, None)
