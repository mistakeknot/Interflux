# Quality Gate Verification: Agent Capability Discovery

**Date**: 2026-02-21
**Scope**: Critical correctness items from plan review
**Verdict**: ALL 7 ITEMS PASS

---

## 1. SQL NULL Guard — PASS

**File**: `core/intermute/internal/storage/sqlite/sqlite.go` (line 783)

The `json_each()` call is correctly wrapped with the full NULL guard:

```go
conditions = append(conditions,
    fmt.Sprintf("EXISTS (SELECT 1 FROM json_each(CASE WHEN capabilities_json IS NULL OR capabilities_json = '' OR capabilities_json = 'null' THEN '[]' ELSE capabilities_json END) WHERE json_each.value IN (%s))",
        strings.Join(capPlaceholders, ",")))
```

This handles all three problematic cases: SQL NULL, empty string, and the JSON literal `"null"`. Each maps to `'[]'` so `json_each()` returns zero rows instead of erroring.

---

## 2. No Breaking ListAgents Signature — PASS

**File**: `core/intermute/client/client.go` (lines 172, 200)

Original signature preserved:

```go
func (c *Client) ListAgents(ctx context.Context, project string) ([]Agent, error)
```

New method added alongside (not replacing):

```go
// DiscoverAgents lists agents filtered by capability tags.
// Capabilities uses OR matching — agents with any of the given capabilities are returned.
func (c *Client) DiscoverAgents(ctx context.Context, capabilities []string) ([]Agent, error)
```

Both methods exist. No existing callers of `ListAgents` need to change.

---

## 3. Handler Trailing-Comma Guard — PASS

**File**: `core/intermute/internal/http/handlers_agents.go` (lines 72-76)

The capability query parameter parsing correctly trims and filters:

```go
if capParam := r.URL.Query().Get("capability"); capParam != "" {
    for _, c := range strings.Split(capParam, ",") {
        if c = strings.TrimSpace(c); c != "" {
            capabilities = append(capabilities, c)
        }
    }
```

The `strings.TrimSpace` + empty check ensures:
- Trailing commas (e.g., `?capability=review:arch,`) produce no empty entries
- Leading/trailing whitespace around capabilities is stripped
- Multiple consecutive commas are handled gracefully

---

## 4. Registration Reads Per-Agent File — PASS

**File**: `interverse/interlock/scripts/interlock-register.sh` (lines 34-39)

Correctly reads from the per-agent config path:

```bash
# Extract capabilities from per-agent capability file (written by each plugin's session hook)
CAPABILITIES="[]"
CAPS_FILE="${HOME}/.config/clavain/capabilities-${AGENT_NAME}.json"
if [[ -f "$CAPS_FILE" ]]; then
    AGENT_CAPS=$(jq -c '.' "$CAPS_FILE" 2>/dev/null)
    if [[ -n "$AGENT_CAPS" ]] && [[ "$AGENT_CAPS" != "null" ]]; then
```

No reference to `CLAUDE_PLUGIN_ROOT` anywhere in the file (verified via grep — zero matches). The capability file path correctly uses the agent name suffix for per-agent isolation.

---

## 5. Interflux agentCapabilities Keys Match Agents Array — PASS

**File**: `interverse/interflux/.claude-plugin/plugin.json` (lines 30-67)

All 17 agents in the `agents` array have corresponding keys in `agentCapabilities`:

| agents entry | agentCapabilities key | Match |
|---|---|---|
| `./agents/review/fd-architecture.md` | `./agents/review/fd-architecture.md` | Yes |
| `./agents/review/fd-safety.md` | `./agents/review/fd-safety.md` | Yes |
| `./agents/review/fd-correctness.md` | `./agents/review/fd-correctness.md` | Yes |
| `./agents/review/fd-user-product.md` | `./agents/review/fd-user-product.md` | Yes |
| `./agents/review/fd-quality.md` | `./agents/review/fd-quality.md` | Yes |
| `./agents/review/fd-game-design.md` | `./agents/review/fd-game-design.md` | Yes |
| `./agents/review/fd-performance.md` | `./agents/review/fd-performance.md` | Yes |
| `./agents/review/fd-systems.md` | `./agents/review/fd-systems.md` | Yes |
| `./agents/review/fd-decisions.md` | `./agents/review/fd-decisions.md` | Yes |
| `./agents/review/fd-people.md` | `./agents/review/fd-people.md` | Yes |
| `./agents/review/fd-resilience.md` | `./agents/review/fd-resilience.md` | Yes |
| `./agents/review/fd-perception.md` | `./agents/review/fd-perception.md` | Yes |
| `./agents/research/framework-docs-researcher.md` | `./agents/research/framework-docs-researcher.md` | Yes |
| `./agents/research/repo-research-analyst.md` | `./agents/research/repo-research-analyst.md` | Yes |
| `./agents/research/git-history-analyzer.md` | `./agents/research/git-history-analyzer.md` | Yes |
| `./agents/research/learnings-researcher.md` | `./agents/research/learnings-researcher.md` | Yes |
| `./agents/research/best-practices-researcher.md` | `./agents/research/best-practices-researcher.md` | Yes |

17 agents, 17 capability entries. Full 1:1 correspondence with matching relative paths.

---

## 6. No Duplicate MCP Tool — PASS

**File**: `interverse/interlock/internal/tools/tools.go` (lines 606-626)

Only `list_agents` exists — no `discover_agents` tool registered:

```go
func listAgents(c *client.Client) server.ServerTool {
    return server.ServerTool{
        Tool: mcp.NewTool("list_agents",
            mcp.WithDescription("List agents registered with intermute. Optionally filter by capability tag (e.g. 'review:architecture'). Comma-separated capabilities use OR matching."),
            mcp.WithString("capability",
                mcp.Description("Capability tag to filter by (e.g. 'review:architecture'). Comma-separated for OR matching. Omit to list all agents."),
            ),
        ),
```

The existing `list_agents` tool was extended with an optional `capability` parameter. A grep for `discover_agents` returns zero matches. This is the correct approach — one tool, backward compatible.

The handler also correctly applies the same trailing-comma guard:

```go
capability, _ := args["capability"].(string)
if capability != "" {
    for _, c := range strings.Split(capability, ",") {
        if c = strings.TrimSpace(c); c != "" {
            caps = append(caps, c)
        }
    }
    agents, err = c.DiscoverAgents(ctx, caps)
```

---

## 7. Test Coverage — PASS

**File**: `core/intermute/internal/http/handlers_agents_test.go`

`TestListAgentsCapabilityFilter` covers all required scenarios:

| Required Test Case | Test Name | Query | Expected Count | Present |
|---|---|---|---|---|
| Single capability match | `single match` | `?capability=review:architecture` | 2 | Yes |
| Multi-capability OR | `multi OR match` | `?capability=review:architecture,review:security` | 3 | Yes |
| No match | `no match` | `?capability=research:docs` | 0 | Yes |
| No filter (returns all) | `no filter returns all` | `?project=proj-a` (no capability param) | 4 | Yes |
| Trailing comma | `trailing comma ignored` | `?capability=review:architecture,` | 2 | Yes |
| Empty-caps agent exclusion | Implicit in counts | `agent-nocaps` (empty caps) registered but excluded from filtered results | Verified | Yes |

The empty-caps agent exclusion is validated implicitly: 4 agents are registered (including `agent-nocaps` with `[]` capabilities), but filtered queries return correct counts excluding it (single=2, multi OR=3, no match=0). The "no filter returns all" case correctly returns 4, confirming the empty-caps agent IS included when no capability filter is applied.

Additionally, `TestCapabilityDiscoveryEndToEnd` (line 161) provides an integration-level test with real agent names and capabilities matching the interflux plugin structure.

---

## Summary

| # | Item | Verdict |
|---|---|---|
| 1 | SQL NULL guard on json_each | PASS |
| 2 | ListAgents signature preserved + DiscoverAgents added | PASS |
| 3 | Handler trailing-comma guard | PASS |
| 4 | Registration reads per-agent caps file (no CLAUDE_PLUGIN_ROOT) | PASS |
| 5 | agentCapabilities keys match agents array (17/17) | PASS |
| 6 | No duplicate discover_agents tool | PASS |
| 7 | Test coverage for all required scenarios | PASS |

All 7 quality gate items verified. The Agent Capability Discovery implementation is correctly built.
