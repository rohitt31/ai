

import json
from openai import OpenAI

from src.config import OPENAI_API_KEY, MODEL_NAME, LLM_BASE_URL, LLM_PROVIDER
from src.agent.prompts import SYSTEM_PROMPT, TOOLS
from src.agent.conversation import ConversationSession, ConversationManager
from src.rag.retriever import retrieve, format_context_for_prompt
from src.tools.order_lookup import lookup_order
from src.logger import AgentTrace


class SupportAgent:
    """
    Aster & Row AI Support Agent.
    Handles customer queries using RAG and order lookup tools.
    Works with OpenAI, Groq, or Google Gemini.
    """
    
    def __init__(self, debug: bool = False):
        # Build client kwargs — only include base_url if set
        client_kwargs = {"api_key": OPENAI_API_KEY}
        if LLM_BASE_URL:
            client_kwargs["base_url"] = LLM_BASE_URL
        
        self.client = OpenAI(**client_kwargs)
        self.model = MODEL_NAME
        self.provider = LLM_PROVIDER
        self.conversation_manager = ConversationManager()
        self.debug = debug
        self.last_trace: AgentTrace | None = None
        self.last_tool_calls: list[dict] = []  # Track tool calls for evaluation
    
    def _call_llm(self, messages: list[dict], tools: list[dict] | None = TOOLS, max_retries: int = 5):
        """Call LLM with automatic retry and backoff on rate limits."""
        import time, re
        kwargs = {
            "model": self.model,
            "messages": messages,
            "temperature": 0.1,
        }
        if tools:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = "auto"
            
        for attempt in range(max_retries):
            try:
                return self.client.chat.completions.create(**kwargs)
            except Exception as e:
                err_str = str(e)
                if ("429" in err_str or "RESOURCE_EXHAUSTED" in err_str or "quota" in err_str.lower()) and attempt < max_retries - 1:
                    # Look for retry delay hint in error message
                    delay = 5 * (attempt + 1)
                    match = re.search(r'retry in (\d+(?:\.\d+)?)s', err_str, re.IGNORECASE)
                    if match:
                        delay = float(match.group(1)) + 1.0
                    else:
                        match2 = re.search(r'retryDelay\':\s*\'(\d+)s\'', err_str)
                        if match2:
                            delay = float(match2.group(1)) + 1.0
                    print(f"  [Rate limited, waiting {delay:.1f}s before retry {attempt+1}/{max_retries}]")
                    time.sleep(delay)
                else:
                    raise e

    def chat(self, user_message: str, session_id: str = "default") -> str:
        """
        Process a user message and return the agent's response.
        Handles the full tool-calling loop.
        """
        trace = AgentTrace()
        self.last_trace = trace
        self.last_tool_calls = []
        
        # Get or create conversation session
        session = self.conversation_manager.get_or_create_session(session_id)
        
        # Log user message
        trace.log_user_message(user_message)
        
        # Add user message to history
        session.add_user_message(user_message)
        
        # Build messages for the API call
        messages = [{"role": "system", "content": SYSTEM_PROMPT}]
        messages.extend(session.get_history())
        
        # Log history
        trace.log_conversation_history(session.get_history())
        
        try:
            # Call the model with tools
            response = self._call_llm(messages, tools=TOOLS)
            
            assistant_message = response.choices[0].message
            
            # If the model called tools, execute them and get the final response
            if assistant_message.tool_calls:
                # Process each tool call
                tool_messages = []
                for tool_call in assistant_message.tool_calls:
                    tool_name = tool_call.function.name
                    raw_args = tool_call.function.arguments
                    if isinstance(raw_args, str):
                        try:
                            tool_args = json.loads(raw_args) if raw_args.strip() else {}
                        except Exception:
                            tool_args = {"query": raw_args, "order_id": raw_args}
                    elif isinstance(raw_args, dict):
                        tool_args = raw_args
                    else:
                        tool_args = {}
                    
                    if not isinstance(tool_args, dict):
                        tool_args = {"query": str(tool_args), "order_id": str(tool_args)}
                    
                    # Execute the tool
                    tool_result = self._execute_tool(tool_name, tool_args, trace)
                    
                    # Track for evaluation
                    self.last_tool_calls.append({
                        "name": tool_name,
                        "arguments": tool_args,
                        "result": tool_result,
                    })
                    
                    # Add tool call and result to conversation
                    tool_messages.append({
                        "role": "tool",
                        "tool_call_id": tool_call.id or "call_default",
                        "content": json.dumps(tool_result, default=str),
                    })
                
                # Append assistant message with tool calls using model_dump
                messages.append(assistant_message.model_dump(exclude_unset=True))
                messages.extend(tool_messages)
                
                # Call the model with tool results
                response = self._call_llm(messages, tools=TOOLS)
                assistant_message = response.choices[0].message
            
            # Extract final response
            final_response = assistant_message.content or "I apologize, but I wasn't able to generate a response. Please try again or contact support at support@asterandrow.com."
            
            # Log the response
            trace.log_response(final_response)
            
            # Add to conversation history
            session.add_assistant_message(final_response)
            
            return final_response
            
        except Exception as e:
            error_msg = f"I'm sorry, I encountered an error processing your request. Please try again or contact our support team at support@asterandrow.com or 1-800-555-ASTER."
            trace.log_error(str(e), "chat_completion")
            session.add_assistant_message(error_msg)
            return error_msg
    
    def _execute_tool(self, tool_name: str, arguments: dict, trace: AgentTrace) -> dict:
        """Execute a tool call and return the result."""
        if isinstance(arguments, str):
            try:
                arguments = json.loads(arguments)
            except Exception:
                arguments = {"query": arguments, "order_id": arguments}
        if not isinstance(arguments, dict):
            arguments = {"query": str(arguments), "order_id": str(arguments)}
        
        if tool_name == "search_knowledge_base":
            query = arguments.get("query", "")
            results = retrieve(query)
            trace.log_retrieval(query, results)
            
            # Format for the model
            context = format_context_for_prompt(results)
            
            return {
                "retrieved_context": context,
            }
        
        elif tool_name == "lookup_order":
            order_id = arguments.get("order_id", "")
            result = lookup_order(order_id)
            trace.log_tool_call("lookup_order", arguments, result)
            return result
        
        else:
            trace.log_error(f"Unknown tool: {tool_name}", "tool_execution")
            return {"error": f"Unknown tool: {tool_name}"}
    
    def get_last_trace(self) -> dict | None:
        """Get the trace from the last invocation."""
        if self.last_trace:
            return self.last_trace.get_trace()
        return None
    
    def get_last_tool_calls(self) -> list[dict]:
        """Get the tool calls from the last invocation (for evaluation)."""
        return self.last_tool_calls
    
    def reset_session(self, session_id: str = "default") -> None:
        """Reset a conversation session."""
        self.conversation_manager.delete_session(session_id)
