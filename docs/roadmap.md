# Roadmap

Planned work that is not built yet, with the decisions each item needs. Done work is in the git history and the
README.

## 1. Plain-language questions on graph.dmom.ai

**Goal:** visitors to the showcase, potential partners and customers, can ask questions about the products in plain
language, such as *"Can Warehouse Advanced and Construction Management be installed in the same environment?"* or
*"What does the Serbian Localization cover for VAT?"*, and get an answer from the graph.

**Why it needs a server:** GitHub Pages only serves files. Answering a question needs code that runs for each
request, so a small service has to run somewhere else, reachable under its own subdomain (proposed:
`mcp.dmom.ai`).

### Options

| | What the visitor does | What runs | Cost |
|---|---|---|---|
| **A. Public MCP endpoint** | Adds `https://mcp.dmom.ai` as a connector in Claude (or another MCP client) and asks in their own chat | `bckg mcp --http` on the published showcase graph, behind HTTPS | Hosting only (about €0–5 per month); the visitor's own AI subscription pays for the answers |
| **B. "Ask" box on the page** | Types a question on graph.dmom.ai and reads the answer there | The same service, plus an endpoint that sends the question to the Claude API with the question catalog as tools; the model chooses the questions and writes the answer | Hosting plus the Claude API per question (with a small model, roughly €0.005–0.02 each) |
| **C. Guided search, no AI** | Picks a question and fills in a field (feature code, object name) | JavaScript in the page reads `graph.json`; stays on GitHub Pages | Free, but not free text |

**Recommended order:** A, then B. A is cheap, has no API bill and almost no abuse risk (public data, read-only
tools), and it shows the MCP server to the audience most likely to use it. B reaches every visitor and reuses A's
service, but spends money per question, so its limits must be in place before it goes live.

### Work

**A — public MCP endpoint**
- Container image that runs `bckg mcp --http --host 0.0.0.0` on the showcase graph.
- The Showcase workflow builds the graph and deploys the image (or uploads the graph to it).
- Read-only by construction: only the question tools, `overview`, `find_objects` and `object_details`. No
  `write_report` and no `cypher` tool on the public endpoint.
- Rate limiting per client IP, request size limits, and logging without personal data.
- HTTPS on `mcp.dmom.ai`: a CNAME record at GoDaddy and the cloud provider's managed certificate.
- An "Ask about these apps in Claude" section on the page: the URL and one line of setup.

**B — Ask box**
- `POST /ask`: the question goes to the Claude API with the catalog as tools, and the answer comes back with the
  questions it was based on.
- A monthly spending cap at the API provider, plus a per-IP and a global daily limit in the service.
- A bot check (for example Cloudflare Turnstile) before a question is accepted.
- A small form on graph.dmom.ai, still a static page, that calls the endpoint; a clear message when the limit is
  reached.
- The API key lives only in the service's secret store, never in the page or the repository.

### Decisions needed (the owner's)

1. **Hosting:** Azure Container Apps (scales to zero, region West Europe) is the default proposal; Fly.io or
   Railway are simpler alternatives. It needs an account in the owner's name.
2. **For B:** an Anthropic API key and a monthly limit (for example €20).
3. **Subdomain:** `mcp.dmom.ai`, or another name.

## 2. Later ideas

- **GitHub Action for partners:** fail a pull request when the apps listed in `products.yaml` collide on object IDs
  or table fields. It runs without Neo4j, from the question catalog.
- **TypeScript consumers:** read which modules of non-AL repositories call which contract operations, instead of the
  current text search.
- **Hosted graphs for other partners' private code:** sign-in, a read-only GitHub App, one graph per workspace, data
  kept in the EU, and deletion on request. Only if partners ask for it.
