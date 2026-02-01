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
            "description": "Run shell command in project root or subfolder. Use for ls, pytest, npm install, pip install. For long commands (npm install, pip install) set timeout_seconds to 120-300.",
            "parameters": {
                "type": "object",
                "required": ["command"],
                "properties": {
                    "command": {"type": "string", "description": "Shell command to run"},
                    "cwd": {"type": "string", "description": "Subfolder relative to project root, e.g. 'bot' or 'frontend'"},
                    "timeout_seconds": {"type": "integer", "description": "Timeout in seconds (max 300). Use 120+ for npm install, pip install."},
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
    {
        "type": "function",
        "function": {
            "name": "get_index_status",
            "description": "Check if the project is indexed for code search. Use when user asks about codebase but search_rag returns nothing — then suggest or call index_workspace.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "index_workspace",
            "description": "Index the project for semantic code search. Call when user needs to search the codebase but project is not indexed (user may have forgotten).",
            "parameters": {
                "type": "object",
                "properties": {
                    "incremental": {"type": "boolean", "description": "If true (default), only new/changed files; if false, full reindex."},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "run_project_analysis",
            "description": "Run deep project analysis (architecture, quality, recommendations). Saves report to docs/ANALYSIS_REPORT.md. Use when user asks to analyze the project or 'проанализируй проект'.",
            "parameters": {
                "type": "object",
                "properties": {
                    "question": {"type": "string", "description": "Optional: specific question to answer in the report."},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "web_search",
            "description": "Search the internet for current information. Use for: news, best practices, documentation, recent APIs, refactoring advice, or any up-to-date information. Prefer this over claiming you have no internet.",
            "parameters": {
                "type": "object",
                "required": ["query"],
                "properties": {
                    "query": {"type": "string", "description": "Search phrase, e.g. 'Python asyncio best practices 2024', 'today news summary'"},
                },
            },
        },
    },
]

AGENT_SYSTEM_PROMPT_NATIVE = """You are an autonomous coding agent. You can read files, write files, search the codebase, run terminal commands, list directories, index the project, and search the web.

Your goal: accomplish the user's task step by step. Use tools when needed. Think before acting.

For current information (news, best practices, recent docs, refactoring advice): use web_search(query). Do not claim you have no internet — call web_search first.

If the user asks about the codebase (e.g. "how does X work?", "where is Y?") and search_rag returns no results, check get_index_status(). If the project is not indexed, call index_workspace() so you can search the code — the user may have forgotten to index.

If the user asks to analyze the project (e.g. "проанализируй проект", "analyze this project"), use run_project_analysis() to run deep analysis and save the report to docs/ANALYSIS_REPORT.md.

Rules:
- Use ONE tool at a time. After receiving the result, analyze it and either call another tool or give your final answer.
- After every tool result you MUST reply with a short summary or final answer to the user in plain text (e.g. "Tests passed: 12, failed: 0" or "Command completed. Output: ..."). Never end your turn with only a tool call — always add a brief text response for the user.
- For write_file: only suggest safe changes. Do not overwrite critical files without explicit user request.
- For run_terminal: use simple commands. Avoid destructive commands (rm -rf, etc).
- When done, respond with your final answer without calling any tool.
"""
