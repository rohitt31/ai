"""
Unit tests for the conversation manager.
Runs without API key.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from src.agent.conversation import ConversationSession, ConversationManager


class TestConversationSession:
    """Test conversation session management."""
    
    def test_add_messages(self):
        session = ConversationSession(session_id="test")
        session.add_user_message("Hello")
        session.add_assistant_message("Hi there!")
        
        history = session.get_history()
        assert len(history) == 2
        assert history[0]["role"] == "user"
        assert history[1]["role"] == "assistant"
    
    def test_history_trimming(self):
        session = ConversationSession(session_id="test", max_turns=3)
        for i in range(10):
            session.add_user_message(f"Message {i}")
            session.add_assistant_message(f"Response {i}")
        
        history = session.get_history()
        assert len(history) <= 6  # 3 turns * 2 messages
    
    def test_clear(self):
        session = ConversationSession(session_id="test")
        session.add_user_message("Hello")
        session.clear()
        assert len(session.get_history()) == 0


class TestConversationManager:
    """Test multi-session management."""
    
    def test_create_session(self):
        manager = ConversationManager()
        session = manager.get_or_create_session("session-1")
        assert session.session_id == "session-1"
    
    def test_sessions_are_independent(self):
        manager = ConversationManager()
        s1 = manager.get_or_create_session("s1")
        s2 = manager.get_or_create_session("s2")
        
        s1.add_user_message("Hello from s1")
        
        assert len(s1.get_history()) == 1
        assert len(s2.get_history()) == 0
    
    def test_delete_session(self):
        manager = ConversationManager()
        manager.get_or_create_session("temp")
        manager.delete_session("temp")
        
        # Should create a new empty session
        session = manager.get_or_create_session("temp")
        assert len(session.get_history()) == 0
