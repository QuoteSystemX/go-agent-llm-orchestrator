# Connecting an agent to the bug-tracker MCP server

The tracker serves MCP over streamable HTTP at `POST <base>/mcp`, read-only, with plain JSON replies
(no sessions, no streams). Access is by a **per-project agent token** (`gbta_…`).

## 1. Get the address and the token

- An admin of the tracker creates the token in **Project settings → Agent access (MCP)**. The value is
  shown **once**; the same page shows the MCP address. Create one token per agent (they can be
  revoked one by one).
- The address is the one the page shows. In the cluster it is the Service port reserved for MCP, for
  example `http://<release>-bug-tracker.<namespace>.svc.cluster.local:8081/mcp`. The MCP port serves
  only `/mcp` and `/healthz`; the UI and the admin API are not on it.
- A token belongs to **one project** and works **only** on `/mcp`. An agent that needs two projects gets
  two tokens and two server entries (different names, same URL), or — simpler — one agent per project.

## 2. The server entry

Claude Code (`.mcp.json`) and Multica (`agent.mcp_config`) take the same server entry:

```json
{
  "mcpServers": {
    "bug-tracker-emulator": {
      "type": "http",
      "url": "http://bug-tracker.bug-tracker.svc.cluster.local:8081/mcp",
      "headers": { "Authorization": "Bearer gbta_REPLACE_WITH_THE_TOKEN" }
    }
  }
}
```

Two projects for one agent:

```json
{
  "mcpServers": {
    "bug-tracker-emulator":  { "type": "http", "url": ".../mcp", "headers": { "Authorization": "Bearer gbta_<token of emulator>" } },
    "bug-tracker-recipient": { "type": "http", "url": ".../mcp", "headers": { "Authorization": "Bearer gbta_<token of the other project>" } }
  }
}
```

## 3. Where the token must NOT go

- **Not into a shared MCP server registry** (for example Multica's `mcp_server` records): headers there are
  visible to every workspace member and are not delivered to agents through that path anyway.
- **Not into the task description, a comment, a commit or a log.** `agent.mcp_config` is the only path
  to the agent; it is not encrypted at rest and is hidden when read back, so treat the token as a secret
  of the operator, rotate it when an agent is retired, and revoke it in the tracker's UI.
- A token in a repository (even a private one) is a leaked token: revoke it.

## 4. Check the connection

```bash
curl -s -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/list"}' "$MCP_URL"
```

The reply lists three read-only tools (evidence, issue list, event list). Expected errors:

| Reply | Meaning |
|---|---|
| 401 | no token, wrong token, revoked token, or the project is being deleted |
| 403 | a request with a foreign `Origin` header (an agent sends none) |
| 413 / 415 | body over 64 KiB / compressed body (agents must send plain JSON) |
| 429 | over 120 requests a minute for this token; wait |
| tool result with `isError` | "No such issue (or event) in this project" — wrong project for this token, or a wrong id |

## 5. Limits worth knowing

120 requests per minute per token; a batch of at most 5 requests; the markdown view is about 8 KiB by
default (up to 64 KiB with `budget_bytes`). Every call is written to the tracker's log with the token id,
project, tool and issue — never the answer and never the token value.
