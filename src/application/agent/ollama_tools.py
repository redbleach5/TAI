"""Ollama native tools schema - for models with tool calling (GLM 4.7, Qwen, Llama 3.1)."""

# Ollama/OpenAI tools format
OLLAMA_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Read file content. path: relative to project root.",
            "parameters": {
                "type": "object",
                "required": ["path"],
                "properties": {
                    "path": {"type": "string", "description": "File path relative to project root"},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "write_file",
            "description": "Write content to file. path: relative to project root.",
            "parameters": {
                "type": "object",
                "required": ["path", "content"],
                "properties": {
                    "path": {"type": "string", "description": "File path relative to project root"},
                    "content": {"type": "string", "description": "Content to write"},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_rag",
            "description": "Search codebase semantically.",
            "parameters": {
                "type": "object",
                "required": ["query"],
                "properties": {
                    "query": {"type": "string", "description": "Search question"},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "run_terminal",
            "description": "Run shell command. Use simple commands like ls, pytest, git status.",
            "parameters": {
                "type": "object",
                "required": ["command"],
                "properties": {
                    "command": {"type": "string", "description": "Shell command to run"},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_files",
            "description": "List files in directory.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Directory path, default '.'"},
                },
            },
        },
    },
]

AGENT_SYSTEM_PROMPT_NATIVE = """You are an autonomous coding agent. You can read files, write files, search the codebase, run terminal commands, and list directories.

Your goal: accomplish the user's task step by step. Use tools when needed. Think before acting.

Rules:
- Use ONE tool at a time. After receiving the result, analyze it and either call another tool or give your final answer.
- For write_file: only suggest safe changes. Do not overwrite critical files without explicit user request.
- For run_terminal: use simple commands. Avoid destructive commands (rm -rf, etc).
- When done, respond with your final answer without calling any tool.
"""
