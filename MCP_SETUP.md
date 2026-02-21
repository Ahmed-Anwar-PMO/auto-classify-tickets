# MCP Tools Setup

Your Cursor IDE is now configured with **Model Context Protocol (MCP)** servers. These extend the AI's capabilities with external tools.

## Installed servers

| Server | Purpose |
|--------|---------|
| **filesystem** | Read/write files, list directories, search files. Scoped to this project + your user folder. |
| **sequential-thinking** | Step-by-step reasoning for complex problems. |
| **playwright** | Browser automation: navigate, fill forms, take screenshots, scrape pages. |
| **memory** | Persistent knowledge graph for remembering facts across conversations. |

## Important: restart Cursor

MCP servers only load at startup. **Quit Cursor completely and reopen it** for changes to take effect.

## How to use

1. Open Cursor chat (`Ctrl+L`) or Composer.
2. Use natural language that implies a tool:
   - *"Take a screenshot of example.com"* → Playwright
   - *"List the files in the worker folder"* → Filesystem
   - *"Walk me through debugging this step by step"* → Sequential thinking
   - *"Remember that we use Zendesk for tickets"* → Memory

The AI will automatically choose and use the right MCP tools when they fit your request.

## Add more servers (optional)

Edit `C:\Users\Anwer\.cursor\mcp.json` to add more. Examples:

### GitHub (requires token)
```json
"github": {
  "command": "npx",
  "args": ["-y", "@modelcontextprotocol/server-github"],
  "env": { "GITHUB_PERSONAL_ACCESS_TOKEN": "ghp_your_token" }
}
```

### Brave Search (requires API key)
```json
"brave-search": {
  "command": "npx",
  "args": ["-y", "@modelcontextprotocol/server-brave-search"],
  "env": { "BRAVE_API_KEY": "your_key" }
}
```

### Notion, Linear, Slack, Postgres, Docker
Search [mcp-awesome.com](https://mcp-awesome.com) or [registry.modelcontextprotocol.io](https://registry.modelcontextprotocol.io) for more servers and their configs.

## Verify

1. **Settings → Tools & MCP** — you should see the servers listed.
2. Ask the AI: *"What MCP tools do you have available?"*
