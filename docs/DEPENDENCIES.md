# Migration Agent: dependencies

Planned only. Nothing installed yet. Versions are "pin at setup": the setup task looks up the current version,
the human approves, then the exact pin goes here with a source (DOCUMENTED, URL, date) before install.

## Python packages (direct)
| Package | Version | Why |
|---|---|---|
| litellm | pin at setup | One API for local Qwen, Gemini, Groq, NVIDIA NIM |
| mcp | pin at setup | Python MCP client to talk to the TS server over stdio |
| pydantic | pin at setup | Typed source records, mapping plan, checkpoint |
| typer | pin at setup | CLI (plan, dry-run, run, validate, report) |
| tzdata | pin at setup | Time zones on Windows |
| pytest (dev) | pin at setup | Tests |
| pytest-xdist (dev) | pin at setup | Optional parallel offline tests |

## Node packages (direct, in server/)
| Package | Version | Why |
|---|---|---|
| @modelcontextprotocol/sdk | pin at setup | Official MCP TypeScript SDK |
| zod | pin at setup | Tool input schemas (the SDK uses it) |
| better-sqlite3 | pin at setup | SQLite store (UNVERIFIED: prebuilt binary for this Node version on Windows) |
| typescript (dev) | pin at setup | Compiler |
| vitest (dev) | pin at setup | TS tests |
| @types/node (dev) | pin at setup | Node types |

## Runtime tools (not installed by this project)
| Tool | Version | Notes |
|---|---|---|
| Python 3.12 | managed by uv | |
| uv | pin at setup | |
| Node LTS | pin at setup | Check with `node --version` at setup |
| llama.cpp `llama-server` + Qwen GGUF | measure at setup | Optional; path set in `migration-agent.toml` |

## Environment variables (never in files)
GEMINI_API_KEY, GROQ_API_KEY, NVIDIA_NIM_API_KEY. Free tiers only. Limits UNVERIFIED; check at setup.

Rule: npm installs use `npm ci` with a committed lock file; Python installs use `uv sync --locked`.
