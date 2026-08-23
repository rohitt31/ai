"""
CLI interface for the Aster & Row support agent.
Provides an interactive REPL with colored output and debug mode.
"""

import argparse
import json
import sys

from rich.console import Console
from rich.panel import Panel
from rich.markdown import Markdown
from rich.text import Text

from src.agent.agent import SupportAgent
from src.config import DEBUG


console = Console()


def print_welcome():
    """Print the welcome banner."""
    console.print()
    console.print(Panel.fit(
        "[bold blue]Aster & Row[/bold blue] [dim]AI Support Agent[/dim]\n"
        "[dim]Type your question below. Type 'quit' to exit, 'reset' to clear history.[/dim]",
        border_style="blue",
    ))
    console.print()


def print_response(response: str):
    """Print the agent's response in a formatted panel."""
    console.print()
    console.print(Panel(
        Markdown(response),
        title="[bold green]Aster & Row Support[/bold green]",
        border_style="green",
        padding=(1, 2),
    ))
    console.print()


def print_trace(trace: dict):
    """Print the debug trace."""
    if not trace:
        return
    
    console.print()
    console.print(Panel(
        Text(json.dumps(trace, indent=2, default=str)),
        title="[bold yellow]Debug Trace[/bold yellow]",
        border_style="yellow",
        padding=(0, 1),
    ))


def main():
    parser = argparse.ArgumentParser(description="Aster & Row AI Support Agent CLI")
    parser.add_argument("--debug", action="store_true", default=DEBUG, help="Enable debug mode with trace output")
    args = parser.parse_args()
    
    agent = SupportAgent(debug=args.debug)
    session_id = "cli-session"
    
    print_welcome()
    
    while True:
        try:
            user_input = console.input("[bold blue]You:[/bold blue] ").strip()
        except (KeyboardInterrupt, EOFError):
            console.print("\n[dim]Goodbye! 👋[/dim]")
            break
        
        if not user_input:
            continue
        
        if user_input.lower() in ("quit", "exit", "q"):
            console.print("[dim]Goodbye! 👋[/dim]")
            break
        
        if user_input.lower() == "reset":
            agent.reset_session(session_id)
            console.print("[dim]Conversation history cleared.[/dim]")
            continue
        
        if user_input.lower() == "trace":
            trace = agent.get_last_trace()
            if trace:
                print_trace(trace)
            else:
                console.print("[dim]No trace available. Ask a question first.[/dim]")
            continue
        
        # Process the message
        with console.status("[bold blue]Thinking...[/bold blue]"):
            response = agent.chat(user_input, session_id)
        
        print_response(response)
        
        # Show trace in debug mode
        if args.debug:
            print_trace(agent.get_last_trace())


if __name__ == "__main__":
    main()
