#!/usr/bin/env python3

import os
import sys
import json
import argparse
from pathlib import Path
from textwrap import dedent
from typing import List, Dict, Any, Optional
from openai import OpenAI
from pydantic import BaseModel
from dotenv import load_dotenv
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.style import Style

from utils import (
    console,
    read_local_file,
    create_file,
    show_diff_table,
    apply_diff_edit,
    try_handle_add_command,
    ensure_file_in_context,
    guess_files_in_message,
    confirm_action,
)

# --------------------------------------------------------------------------------
# 1. Configure OpenAI client and load environment variables
# --------------------------------------------------------------------------------
load_dotenv()  # Load environment variables from .env file

SUPPORTED_MODELS = {
    "deepseek-chat": {
        "name": "DeepSeek Chat",
        "env_key": "DEEPSEEK_API_KEY",
        "api_url": "https://api.deepseek.com"
    },
    "gpt-4o-mini": {
        "name": "GPT-4o-Mini",
        "env_key": "OPENAI_API_KEY",
        "api_url": "https://api.openai.com/v1"
    },
    "gemini-2.0-flash-exp": {
        "name": "Gemini 2.0 Flash",
        "env_key": "GEMINI_API_KEY",
        "api_url": "https://generativelanguage.googleapis.com/v1beta/openai"
    }
}

class ModelChoiceError(Exception):
    pass

def validate_model_choice(model_name: str) -> str:
    if model_name not in SUPPORTED_MODELS:
        available_models = "\n  • ".join([""] + [f"{k} ({v['name']})" for k, v in SUPPORTED_MODELS.items()])
        raise ModelChoiceError(
            f"Invalid model '{model_name}'. Available models:{available_models}"
        )
    return model_name

# NEW: Argument parser for command line options
parser = argparse.ArgumentParser(description="Select the model to use.")
parser.add_argument(
    "--model",
    type=validate_model_choice,
    choices=SUPPORTED_MODELS.keys(),
    default="gpt-4o-mini",
    help=f"Choose the model to use. Default is 'gpt-4o-mini'."
)

try:
    args = parser.parse_args()
    model_config = SUPPORTED_MODELS[args.model]
    
    # Get API key and configuration
    api_key = os.getenv(model_config["env_key"])
    model_name = args.model
    api_url = model_config["api_url"]

    # Check if the API key is available
    if not api_key:
        console.print(
            f"[red]✗[/red] API key for {model_config['name']} not found.\n"
            f"Please add {model_config['env_key']} to your .env file.", 
            style="red"
        )
        sys.exit(1)

    client = OpenAI(api_key=api_key, base_url=api_url)  # Configure for the selected API

except ModelChoiceError as e:
    console.print(f"[red]✗[/red] {str(e)}", style="red")
    sys.exit(1)
except Exception as e:
    console.print(f"[red]✗[/red] Error initializing model: {str(e)}", style="red")
    sys.exit(1)

# --------------------------------------------------------------------------------
# 2. Define our schema using Pydantic for type safety
# --------------------------------------------------------------------------------
class FileToCreate(BaseModel):
    path: str
    content: str

# NEW: Diff editing structure
class FileToEdit(BaseModel):
    path: str
    original_snippet: str
    new_snippet: str

class AssistantResponse(BaseModel):
    assistant_reply: str
    files_to_create: Optional[List[FileToCreate]] = None
    # NEW: optionally hold diff edits
    files_to_edit: Optional[List[FileToEdit]] = None


# --------------------------------------------------------------------------------
# 3. System prompt and conversation state
# --------------------------------------------------------------------------------
try:
    system_PROMPT = read_local_file("system_prompts/deepseek_engineer.md")
except FileNotFoundError:
    console.print("[red]✗[/red] System prompt file not found: 'system_prompts/deepseek_engineer.md'", style="red")
    sys.exit(1)

conversation_history = [
    {"role": "system", "content": system_PROMPT}
]

# --------------------------------------------------------------------------------
# 4. OpenAI API interaction with streaming
# --------------------------------------------------------------------------------
def stream_openai_response(user_message: str):
    """
    Streams the chat completion response and handles structured output.
    Returns the final AssistantResponse.
    """
    # Attempt to guess which file(s) user references
    potential_paths = guess_files_in_message(user_message)
    valid_files = {}

    # Try to read all potential files before the API call
    for path in potential_paths:
        try:
            content = read_local_file(path)
            valid_files[path] = content  # path is already normalized
            file_marker = f"Content of file '{path}'"
            # Add to conversation if we haven't already
            if not any(file_marker in msg["content"] for msg in conversation_history):
                conversation_history.append({
                    "role": "system",
                    "content": f"{file_marker}:\n\n{content}"
                })
        except OSError:
            error_msg = f"Cannot proceed: File '{path}' does not exist or is not accessible"
            console.print(f"[red]✗[/red] {error_msg}", style="red")
            continue

    conversation_history.append({"role": "user", "content": user_message})

    try:
        stream = client.chat.completions.create(
            model=model_name,
            messages=conversation_history,
            response_format={"type": "json_object"},
            max_completion_tokens=8000,
            stream=True
        )

        console.print("\nAssistant> ", style="bold blue", end="")
        full_content = ""

        for chunk in stream:
            if chunk.choices[0].delta.content:
                content_chunk = chunk.choices[0].delta.content
                full_content += content_chunk
                console.print(content_chunk, end="")

        console.print()

        try:
            parsed_response = json.loads(full_content)
            
            # Ensure assistant_reply is present
            if "assistant_reply" not in parsed_response:
                parsed_response["assistant_reply"] = ""

            # If assistant tries to edit files not in valid_files, remove them
            if "files_to_edit" in parsed_response and parsed_response["files_to_edit"]:
                new_files_to_edit = []
                for edit in parsed_response["files_to_edit"]:
                    try:
                        edit_abs_path = str(Path(edit["path"]).resolve())
                        # If we have the file in context or can read it now
                        if edit_abs_path in valid_files or ensure_file_in_context(edit_abs_path, conversation_history):
                            edit["path"] = edit_abs_path  # Use normalized path
                            new_files_to_edit.append(edit)
                    except (OSError, ValueError):
                        console.print(f"[yellow]⚠[/yellow] Skipping invalid path: '{edit['path']}'", style="yellow")
                        continue
                parsed_response["files_to_edit"] = new_files_to_edit

            response_obj = AssistantResponse(**parsed_response)

            # Save the assistant's textual reply to conversation
            conversation_history.append({
                "role": "assistant",
                "content": response_obj.assistant_reply
            })

            return response_obj

        except json.JSONDecodeError:
            error_msg = "Failed to parse JSON response from assistant"
            console.print(f"[red]✗[/red] {error_msg}", style="red")
            return AssistantResponse(
                assistant_reply=error_msg,
                files_to_create=[]
            )

    except Exception as e:
        error_msg = f"API error: {str(e)}"
        console.print(f"\n[red]✗[/red] {error_msg}", style="red")
        console.print("[yellow]ℹ[/yellow] Please check the API key and model configuration.", style="yellow")
        return AssistantResponse(
            assistant_reply=error_msg,
            files_to_create=[]
        )

# --------------------------------------------------------------------------------
# 5. Main interactive loop
# --------------------------------------------------------------------------------
def main():
    console.print(Panel.fit(
        "[bold blue]Welcome to Decker[/bold blue] [green](with streaming)[/green]!🐋",
        border_style="blue"
    ))
    console.print(
        "To include a file in the conversation, use '[bold magenta]/add path/to/file[/bold magenta]'.\n"
        "Type '[bold red]exit[/bold red]' or '[bold red]quit[/bold red]' to end.\n"
    )

    while True:
        try:
            user_input = console.input("[bold green]You>[/bold green] ").strip()
        except (EOFError, KeyboardInterrupt):
            console.print("\n[yellow]Exiting.[/yellow]")
            break

        if not user_input:
            continue

        if user_input.lower() in ["exit", "quit"]:
            console.print("[yellow]Goodbye![/yellow]")
            break

        # If user is reading a file
        if try_handle_add_command(user_input, conversation_history):
            continue

        # Get streaming response from the model
        response_data = stream_openai_response(user_input)

        # Create any files if requested
        if response_data.files_to_create:
            for file_info in response_data.files_to_create:
                if not create_file(file_info.path, file_info.content, conversation_history):
                    console.print("[yellow]ℹ[/yellow] Skipping remaining file operations.", style="yellow")
                    break

        # Show and confirm diff edits if requested
        if response_data.files_to_edit:
            show_diff_table(response_data.files_to_edit)
            if confirm_action("Do you want to apply these changes?"):
                for edit_info in response_data.files_to_edit:
                    apply_diff_edit(edit_info.path, edit_info.original_snippet, edit_info.new_snippet, conversation_history)
            else:
                console.print("[yellow]ℹ[/yellow] Skipped applying diff edits.", style="yellow")

    console.print("[blue]Session finished.[/blue]")

if __name__ == "__main__":
    main()
