# Decker 🐋

## Overview

Decker is a versatile command-line coding agent that integrates with various Large Language Models (LLMs) to assist with coding tasks. Through an intuitive command-line interface, it can read local file contents, create new files, and apply diff edits to existing files in real time.

## Key Features

1. Multi-LLM Support
   - Currently supports multiple LLM providers:
     • DeepSeek Chat
     • GPT-4o-Mini
     • Gemini 2.0 Flash
   - Easily configurable through command-line arguments
   - Extensible architecture for adding new LLM providers

2. Data Models
   - Leverages Pydantic for type-safe handling of file operations, including:
     • FileToCreate – describes files to be created or updated
     • FileToEdit – describes specific snippet replacements in an existing file
     • AssistantResponse – structures chat responses and potential file operations

3. Interactive File Operations
   - "/add" command to include file contents in the conversation
   - Real-time file creation and modification
   - Visual diff previews before applying changes
   - Smart context management for referenced files

4. Rich Terminal Interface
   - Streaming responses with syntax highlighting
   - Interactive diff tables
   - Clear success/error indicators
   - Progress feedback for all operations

## Getting Started

1. Set up your environment variables:
   - Copy `.env.example` to `.env`:
     ```bash
     cp .env.example .env
     ```
   - Edit `.env` and add your API keys:
     ```bash
     # For DeepSeek
     DEEPSEEK_API_KEY=your_deepseek_key_here
     
     # For GPT-4-Mini
     OPENAI_API_KEY=your_openai_key_here

     # For Gemini
     GEMINI_API_KEY=your_gemini_key_here
     ```
   Note: You only need to set the API key for the model you plan to use.

2. Install dependencies (choose one method):

   ### Using pip
   ```bash
   pip install -r requirements.txt
   ```

   ### Using uv (faster alternative)
   ```bash
   uv venv
   ```

3. Run Decker with your preferred model:

   ### Using DeepSeek
   ```bash
   python main.py --model deepseek-chat
   ```

   ### Using GPT-4-Mini
   ```bash
   python main.py --model gpt-4o-mini
   ```

   ### Using Gemini
   ```bash
   python main.py --model gemini-2.0-flash-exp
   ```

## Usage

1. Start a conversation with your chosen model
2. Use "/add path/to/file" to include files in the conversation
3. Ask questions or request changes to your code
4. Review and approve any suggested file modifications
5. Type "exit" or "quit" to end the session

## Commands

- `/add path/to/file` - Add a file's contents to the conversation
- `exit` or `quit` - End the session

## Example Session
```
$ python main.py --model deepseek-chat
Welcome to Decker! 🐋
You> /add main.py
✓ Added file 'main.py' to conversation.
You> Help me optimize this file
Assistant> [Assistant analyzes and suggests optimizations...]
```