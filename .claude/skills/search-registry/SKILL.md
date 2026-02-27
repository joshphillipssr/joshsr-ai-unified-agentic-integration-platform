---
name: search-registry
description: Search the MCP Gateway Registry using semantic search. Takes a natural language query, calls the /api/search/semantic endpoint, and returns formatted results directly in the conversation.
license: Apache-2.0
metadata:
  author: mcp-gateway-registry
  version: "1.2"
---

# Search Registry Skill

Search the MCP Gateway Registry for MCP servers, tools, A2A agents, skills, and virtual servers using natural language semantic search.

## Prerequisites

You need two things to use this skill:

1. **Registry Endpoint URL** - The base URL of your MCP Gateway Registry (e.g., `https://registry.us-east-1.acme.com`)
2. **JWT Token** - A valid JWT token for authentication

### Getting a JWT Token

The easiest way to get a token is from the **"Get JWT Token"** button in the top-left of the Registry UI. The token is saved to a `.token` file.

The `.token` file supports two formats:

**Format 1: Raw JWT token (just the token string)**
```
eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3Mi...
```

**Format 2: Nested JSON (as downloaded from the Registry UI)**
```json
{
  "success": true,
  "tokens": {
    "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3Mi..."
  },
  "token_data": {
    "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3Mi..."
  }
}
```

Both formats are valid. The skill will auto-detect the format and extract the token.

## Input

The skill accepts up to 3 parameters in this order: `REGISTRY_URL TOKEN_FILE QUERY`

```
/search-registry REGISTRY_URL TOKEN_FILE QUERY
```

- **REGISTRY_URL** - The base URL of the registry (no trailing slash)
- **TOKEN_FILE** - Path to the `.token` file
- **QUERY** - The natural language search query (everything after the first two parameters)

All three parameters are optional. If any are missing, ask the user for the missing values.

### Examples

All parameters provided:
```
/search-registry https://registry.us-east-1.acme.com .token tools for file management
```

No parameters (will prompt for all three):
```
/search-registry
```

### Parsing Rules

Parse the arguments string as follows:
1. If the first argument starts with `http://` or `https://`, treat it as REGISTRY_URL
2. If the next argument looks like a file path (contains `.` or `/`), treat it as TOKEN_FILE
3. Everything remaining is the QUERY

If the first argument does NOT start with `http://` or `https://`, assume all parameters are missing and treat the entire argument string as nothing (prompt for all three).

## Permission Handling

**IMPORTANT**: Do NOT ask for user permission on any Bash tool calls until the search results are displayed. All steps between gathering configuration and presenting results should run without pausing for permission. This includes:
- The Python code that extracts the JWT token from the token file
- The `head -c 3` validation command
- The `curl` API call to the search endpoint
- The result parsing and cleanup commands

The only user interaction should be the AskUserQuestion prompts in Step 1 (for missing parameters). After that, everything should execute without permission prompts.

## Workflow

### Step 1: Gather Configuration

Parse the skill arguments to extract REGISTRY_URL, TOKEN_FILE, and QUERY. For any parameter that was NOT provided in the arguments, ask the user using AskUserQuestion:

1. **Registry Endpoint** (if not provided):
   - Offer exactly two options using AskUserQuestion: "http://localhost" and "Custom URL".
   - For the "Custom URL" option, use the `description` field to say "Enter your registry URL in the text box below".
   - Do NOT rely on the automatic "Other" option. These two options are the only ones needed.
   - The endpoint should NOT have a trailing slash.

2. **Token File Path** (if not provided):
   - Default suggestion: `.token` (in the current repo root)
   - Also check common locations: `.token`, `api/.token`
   - Tell the user: Both raw JWT and nested JSON formats are supported. You can get the token from the "Get JWT Token" button on the top-left of the Registry UI.

3. **Search Query** (if not provided):
   - Simply ask the user: "What would you like to search for?" as a free-text question.
   - Do NOT offer predefined category options like "MCP servers", "tools", "agents", etc.
   - The query is always free-text -- the user types whatever they want to find.
   - Remember: we always search ALL entity types, so do not present entity-type choices.

### Step 2: Extract the Token to a Temp File

Read the token file and extract the JWT token into a temporary file. This is critical because JWT tokens are very long strings that can be silently truncated or dropped when embedded directly in shell variables or curl command lines.

**IMPORTANT**: Always extract the token to a temp file first, then read it from the file when constructing the curl command. Never try to inline a JWT token directly in a curl `-H` header via shell variable interpolation.

Use this approach:

```bash
python3 -c "
import json
content = open('TOKEN_FILE_PATH').read().strip()
try:
    data = json.loads(content)
    token = data.get('tokens', {}).get('access_token') or data.get('token_data', {}).get('access_token') or data.get('access_token')
    if token:
        print(token, end='')
    else:
        print(content, end='')
except json.JSONDecodeError:
    print(content, end='')
" > /tmp/_registry_jwt_token.txt
```

Validate the extracted token:
```bash
# Verify the token file is not empty and starts with eyJ
head -c 3 /tmp/_registry_jwt_token.txt
```

If the token file is empty or does not start with `eyJ`, tell the user and ask for a valid token.

### Step 3: Call the Semantic Search API

Always search across ALL entity types (servers, tools, agents, skills, virtual servers). Do NOT ask the user which entity types to filter by -- just search everything and let the results speak for themselves. Do NOT pass `entity_types` in the request body so the API returns all categories.

Make the API call using curl, reading the token from the temp file:

```bash
curl -s -X POST "REGISTRY_ENDPOINT/api/search/semantic" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $(cat /tmp/_registry_jwt_token.txt)" \
  -d '{"query": "USER_QUERY", "max_results": 10}'
```

Save the raw JSON response to a temporary file for processing:

```bash
curl -s -X POST "REGISTRY_ENDPOINT/api/search/semantic" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $(cat /tmp/_registry_jwt_token.txt)" \
  -d '{"query": "USER_QUERY", "max_results": 10}' > /tmp/_registry_search_results.json
```

### Step 4: Present Results Directly to the User

Do NOT save results to a markdown file. Instead, read the JSON response and present the results directly in the conversation as formatted text.

Display the results in this format:

```
### Registry Search Results

**Query:** {query}
**Registry:** {endpoint}
**Search Mode:** {search_mode from response}

**Found:** {total_servers} servers, {total_tools} tools, {total_agents} agents, {total_skills} skills, {total_virtual_servers} virtual servers

---

#### MCP Servers

(Only include this section if total_servers > 0)

| Name | Path | Score | Tools | Enabled | Endpoint | Description |
|------|------|-------|-------|---------|----------|-------------|
| {server_name} | {path} | {relevance_score} | {num_tools} | {is_enabled} | {endpoint_url} | {description (truncated to 80 chars)} |

**Matching Tools per Server:**

For each server that has matching_tools, list them:

**{server_name}** ({path})
| Tool | Description |
|------|-------------|
| {tool_name} | {first line of description, truncated to 80 chars} |

---

#### Tools

(Only include this section if total_tools > 0)

| Tool Name | Server | Path | Score | Endpoint | Description |
|-----------|--------|------|-------|----------|-------------|
| {tool_name} | {server_name} | {server_path} | {relevance_score} | {endpoint_url} | {description (truncated to 80 chars)} |

---

#### A2A Agents

(Only include this section if total_agents > 0)

| Name | Path | Score | URL | Skills | Description |
|------|------|-------|-----|--------|-------------|
| {agent_card.name} | {path} | {relevance_score} | {agent_card.url} | {len(agent_card.skills)} | {agent_card.description (truncated to 80 chars)} |

For each agent, also list its skills:

**{agent_card.name}** ({path})
| Skill | Description | Tags |
|-------|-------------|------|
| {skill.name} | {skill.description} | {skill.tags joined} |

---

#### Skills

(Only include this section if total_skills > 0)

| Skill Name | Path | Score | Version | Author | Enabled | Health | Description |
|------------|------|-------|---------|--------|---------|--------|-------------|
| {skill_name} | {path} | {relevance_score} | {version} | {author} | {is_enabled} | {health_status} | {description (truncated to 80 chars)} |

---

#### Virtual Servers

(Only include this section if total_virtual_servers > 0)

| Name | Path | Score | Tools | Backends | Enabled | Endpoint | Description |
|------|------|-------|-------|----------|---------|----------|-------------|
| {server_name} | {path} | {relevance_score} | {num_tools} | {backend_count} | {is_enabled} | {endpoint_url} | {description (truncated to 80 chars)} |
```

After displaying the tables, highlight the top 3-5 most relevant results across all categories with a brief plain-text summary.

### Error Handling

- If the API returns a 401/403: Tell the user their token may be expired. Suggest getting a new one from the "Get JWT Token" button in the Registry UI.
- If the API returns a 404: Suggest verifying the registry endpoint URL.
- If the API returns no results: Tell the user and suggest broadening their query or trying different keywords.
- If the token file cannot be read: Tell the user and ask for the correct path.
- If the token file is in an unexpected format: Tell the user and show what was found.

### Cleanup

After presenting results, clean up the temporary files:

```bash
rm -f /tmp/_registry_jwt_token.txt /tmp/_registry_search_results.json
```

## Example Usage

### Example 1: All parameters provided

```
User: /search-registry https://registry.us-east-1.acme.com .token tools for weather data
```

1. Parse: REGISTRY_URL=`https://registry.us-east-1.acme.com`, TOKEN_FILE=`.token`, QUERY=`tools for weather data`
2. Extract token from `.token` to `/tmp/_registry_jwt_token.txt`
3. POST to `/api/search/semantic` with query "tools for weather data", reading token from temp file
4. Display results directly in the conversation

### Example 2: No parameters

```
User: /search-registry
```

1. Ask user for registry endpoint (two options: "http://localhost" or enter URL), token file path, and search query
2. Extract token to temp file
3. POST to `/api/search/semantic`
4. Display results directly:
   ```
   ### Registry Search Results

   **Query:** tools for weather data
   **Registry:** https://registry.us-east-1.acme.com
   **Search Mode:** hybrid

   **Found:** 2 servers, 5 tools, 0 agents, 0 skills, 1 virtual server

   ---

   #### MCP Servers

   | Name | Path | Score | Tools | Enabled | Endpoint | Description |
   |------|------|-------|-------|---------|----------|-------------|
   | weather-api | /weather-api | 0.85 | 3 | Yes | https://registry.example.com/weather-api/mcp | Weather data MCP server |

   ...

   **Top results:**
   - [Tool] get_weather (server: /weather-api, score: 0.92) - Get current weather for a location
   - [Tool] forecast (server: /weather-api, score: 0.87) - Get weather forecast
   - [Server] weather-api (path: /weather-api, score: 0.85) - Weather data MCP server
   ```
