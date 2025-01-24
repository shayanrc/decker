"""
Utility functions for file operations and model configuration.
"""

import os
from pathlib import Path
from typing import List, Dict, Any
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.markdown import Markdown

# Initialize Rich console
console = Console()

def read_local_file(file_path: str) -> str:
    """Return the text content of a local file."""
    with open(file_path, "r", encoding="utf-8") as f:
        return f.read()

def show_file_preview(path: str, content: str) -> None:
    """Show a preview of the file to be created."""
    console.print(f"\n[bold]Preview of file to create:[/bold] [cyan]{path}[/cyan]")
    
    # If the content looks like markdown, render it as markdown
    if path.endswith(('.md', '.markdown')):
        console.print(Panel(Markdown(content), title="Content Preview", border_style="green"))
    else:
        console.print(Panel(content, title="Content Preview", border_style="green"))

def confirm_action(prompt: str) -> bool:
    """Ask for user confirmation with a yes/no prompt."""
    response = console.input(f"\n{prompt} ([green]y[/green]/[red]n[/red]): ").strip().lower()
    return response == 'y'

def create_file(path: str, content: str, conversation_history: List[Dict[str, Any]], require_confirmation: bool = True) -> bool:
    """
    Create (or overwrite) a file at 'path' with the given 'content'.
    Returns True if the file was created, False if creation was cancelled.
    """
    file_path = Path(path)
    
    if require_confirmation:
        # Show preview and get confirmation
        show_file_preview(str(file_path), content)
        if file_path.exists():
            if not confirm_action(f"File '[cyan]{file_path}[/cyan]' already exists. Do you want to overwrite it?"):
                console.print("[yellow]ℹ[/yellow] File creation cancelled.", style="yellow")
                return False
        else:
            if not confirm_action(f"Do you want to create '[cyan]{file_path}[/cyan]'?"):
                console.print("[yellow]ℹ[/yellow] File creation cancelled.", style="yellow")
                return False

    # Create parent directories if they don't exist
    file_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Write the file
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(content)
    console.print(f"[green]✓[/green] Created/updated file at '[cyan]{file_path}[/cyan]'")
    
    # Record the action
    conversation_history.append({
        "role": "assistant",
        "content": f"✓ Created/updated file at '{file_path}'"
    })
    
    # Add the actual content to conversation context
    normalized_path = normalize_path(str(file_path))
    conversation_history.append({
        "role": "system",
        "content": f"Content of file '{normalized_path}':\n\n{content}"
    })
    
    return True

def show_diff_table(files_to_edit: List[Any]) -> None:
    """Show a table of proposed file edits."""
    if not files_to_edit:
        return
    
    # Enable multi-line rows by setting show_lines=True
    table = Table(title="Proposed Edits", show_header=True, header_style="bold magenta", show_lines=True)
    table.add_column("File Path", style="cyan")
    table.add_column("Original", style="red")
    table.add_column("New", style="green")

    for edit in files_to_edit:
        table.add_row(edit.path, edit.original_snippet, edit.new_snippet)
    
    console.print(table)

def apply_diff_edit(path: str, original_snippet: str, new_snippet: str, conversation_history: List[Dict[str, Any]]) -> None:
    """Apply a diff edit to a file."""
    try:
        content = read_local_file(path)
        if original_snippet in content:
            updated_content = content.replace(original_snippet, new_snippet, 1)
            create_file(path, updated_content, conversation_history)
            console.print(f"[green]✓[/green] Applied diff edit to '[cyan]{path}[/cyan]'")
            conversation_history.append({
                "role": "assistant",
                "content": f"✓ Applied diff edit to '{path}'"
            })
        else:
            # Add debug info about the mismatch
            console.print(f"[yellow]⚠[/yellow] Original snippet not found in '[cyan]{path}[/cyan]'. No changes made.", style="yellow")
            console.print("\nExpected snippet:", style="yellow")
            console.print(Panel(original_snippet, title="Expected", border_style="yellow"))
            console.print("\nActual file content:", style="yellow")
            console.print(Panel(content, title="Actual", border_style="yellow"))
    except FileNotFoundError:
        console.print(f"[red]✗[/red] File not found for diff editing: '[cyan]{path}[/cyan]'", style="red")

def try_handle_add_command(user_input: str, conversation_history: List[Dict[str, Any]]) -> bool:
    """Handle the /add command for including file contents in conversation."""
    prefix = "/add "
    if user_input.strip().lower().startswith(prefix):
        file_path = user_input[len(prefix):].strip()
        try:
            content = read_local_file(file_path)
            conversation_history.append({
                "role": "system",
                "content": f"Content of file '{file_path}':\n\n{content}"
            })
            console.print(f"[green]✓[/green] Added file '[cyan]{file_path}[/cyan]' to conversation.\n")
        except OSError as e:
            console.print(f"[red]✗[/red] Could not add file '[cyan]{file_path}[/cyan]': {e}\n", style="red")
        return True
    return False

def ensure_file_in_context(file_path: str, conversation_history: List[Dict[str, Any]]) -> bool:
    """Ensure file content is in conversation context."""
    try:
        normalized_path = normalize_path(file_path)
        content = read_local_file(normalized_path)
        file_marker = f"Content of file '{normalized_path}'"
        if not any(file_marker in msg["content"] for msg in conversation_history):
            conversation_history.append({
                "role": "system",
                "content": f"{file_marker}:\n\n{content}"
            })
        return True
    except OSError:
        console.print(f"[red]✗[/red] Could not read file '[cyan]{file_path}[/cyan]' for editing context", style="red")
        return False

def normalize_path(path_str: str) -> str:
    """Return a canonical, absolute version of the path."""
    return str(Path(path_str).resolve())

def guess_files_in_message(user_message: str) -> List[str]:
    """Attempt to guess which files the user might be referencing."""
    recognized_extensions = [".css", ".html", ".js", ".py", ".json", ".md"]
    potential_paths = []
    for word in user_message.split():
        if any(ext in word for ext in recognized_extensions) or "/" in word:
            path = word.strip("',\"")
            try:
                normalized_path = normalize_path(path)
                potential_paths.append(normalized_path)
            except (OSError, ValueError):
                continue
    return potential_paths 