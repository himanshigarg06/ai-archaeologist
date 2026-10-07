# AI Archaeologist 🏛️

A software archaeology platform that analyzes abandoned or aging GitHub repositories to reconstruct their history, evolution, and reasons for decline.

**Current Phase: Phase 1 — Repository Mining & Data Collection Backend**

---

## What This Does (Phase 1)

Given a GitHub repository URL, this backend will:

1. Validate the URL
2. Fetch repository metadata
3. Fetch complete commit history
4. Fetch all contributors
5. Fetch all issues (open and closed)
6. Fetch all pull requests (open, closed, merged)
7. Fetch the repository file/directory structure
8. Store everything in a local SQLite database
9. Return a clean JSON response

Later phases will add intelligence layers (analysis, NLP, visualization) on top of this data.

---

## Project Structure

```
ai-archaeologist/
│
├── backend/
│   ├── app.py                  ← Flask app entry point
│   ├── config.py               ← Configuration and environment variables
│   │
│   ├── routes/
│   │   └── repository_routes.py  ← HTTP endpoints (POST/GET)
│   │
│   ├── services/
│   │   ├── github_service.py     ← All GitHub API communication
│   │   ├── repository_service.py ← Orchestrates repository analysis
│   │   ├── commit_service.py     ← Commit data collection
│   │   ├── contributor_service.py← Contributor data collection
│   │   ├── issue_service.py      ← Issue data collection
│   │   ├── pull_request_service.py ← PR data collection
│   │   └── file_service.py       ← File structure collection
│   │
│   ├── models/
│   │   ├── repository.py         ← Repository database model
│   │   ├── commit.py             ← Commit database model
│   │   ├── contributor.py        ← Contributor database model
│   │   ├── issue.py              ← Issue database model
│   │   ├── pull_request.py       ← PullRequest database model
│   │   └── repository_file.py    ← RepositoryFile database model
│   │
│   └── utils/
│       ├── github_helpers.py     ← Pagination, response parsing helpers
│       └── validators.py         ← GitHub URL validation
│
├── data/
│   ├── raw/                    ← Raw JSON responses from GitHub API
│   └── processed/              ← (Reserved for future phases)
│
├── tests/
│   ├── test_validators.py      ← Tests for URL validation
│   └── test_github_service.py  ← Tests for GitHub service
│
├── .env                        ← Your secrets (NOT committed to GitHub)
├── .env.example                ← Template showing what goes in .env
├── .gitignore                  ← Tells Git what to ignore
├── requirements.txt            ← Python package dependencies
└── README.md                   ← This file
```

---

## Setup Instructions

### Step 1 — Prerequisites

Make sure you have the following installed:

- **Python 3.10 or higher** — check with `python3 --version`
- **pip** — Python package manager (comes with Python)
- **Git** — for version control

### Step 2 — Create a GitHub Personal Access Token

The GitHub API allows only 60 requests per hour without authentication.  
With a token, you get **5,000 requests per hour** — essential for analyzing repositories.

**How to create your token:**

1. Log in to GitHub and go to: https://github.com/settings/tokens
2. Click **"Generate new token"** → **"Generate new token (classic)"**
3. Give it a descriptive name like `ai-archaeologist`
4. Set expiration to 90 days (or as preferred)
5. Under **"Select scopes"**, tick only **`public_repo`**
   - This gives read-only access to public repositories
   - We don't need write access to anything
6. Scroll down and click **"Generate token"**
7. **Copy the token immediately** — GitHub will never show it again

> ⚠️ **Security rule**: Never paste your token directly into Python code or commit it to GitHub. It goes only in `.env`.

### Step 3 — Clone or Enter the Project Directory

```bash
cd "path/to/ai-archaeologist"
```

### Step 4 — Create a Python Virtual Environment

A virtual environment keeps this project's packages isolated from your system Python.

```bash
# Create the virtual environment
python3 -m venv venv

# Activate it (macOS/Linux)
source venv/bin/activate

# Activate it (Windows)
venv\Scripts\activate
```

You should see `(venv)` at the start of your terminal prompt.

### Step 5 — Install Dependencies

```bash
pip install -r requirements.txt
```

### Step 6 — Configure Environment Variables

```bash
# Copy the example file
cp .env.example .env
```

Open `.env` and replace `your_github_token_here` with your actual token:

```
GITHUB_TOKEN=ghp_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
```

**Never commit the `.env` file.** It is already listed in `.gitignore`.

### Step 7 — Run the Backend

```bash
python backend/app.py
```

The server will start at `http://localhost:5000`.

---

## API Usage

### Analyze a Repository

```
POST /api/repositories/analyze
Content-Type: application/json

{
    "url": "https://github.com/owner/repository"
}
```

**Example using curl:**

```bash
curl -X POST http://localhost:5000/api/repositories/analyze \
  -H "Content-Type: application/json" \
  -d '{"url": "https://github.com/kennethreitz/requests"}'
```

**Success response:**

```json
{
    "success": true,
    "message": "Repository analyzed successfully",
    "repository": {
        "owner": "kennethreitz",
        "name": "requests"
    }
}
```

**Error response:**

```json
{
    "success": false,
    "error": "Repository not found",
    "details": "The requested GitHub repository does not exist or is not accessible."
}
```

### Retrieve Stored Data

```
GET /api/repositories/<owner>/<repo>
GET /api/repositories/<owner>/<repo>/commits
GET /api/repositories/<owner>/<repo>/contributors
GET /api/repositories/<owner>/<repo>/issues
GET /api/repositories/<owner>/<repo>/pull-requests
GET /api/repositories/<owner>/<repo>/files
```

---

## Pagination Note

The GitHub API returns data in pages (usually 100 items per page).

This backend automatically collects all pages, not just the first.

**Safety limits** are configured in `config.py`:
- Maximum pages per request: `MAX_PAGES_PER_REQUEST` (default: 50)
- This means up to 5,000 commits, 5,000 issues, etc.

For very large repositories (Linux kernel, VS Code, etc.), you may want to reduce this limit to avoid long wait times and API rate limit consumption.

---

## GitHub API Rate Limits

| Scenario | Requests per hour |
|----------|-------------------|
| No token (unauthenticated) | 60 |
| With token (authenticated) | 5,000 |

If you hit the rate limit, the API will return:

```json
{
    "success": false,
    "error": "GitHub API rate limit reached",
    "details": "You have exceeded the GitHub API rate limit. Please wait before trying again."
}
```

---

## Running Tests

```bash
pytest tests/ -v
```

---

## Important Notes for Students

- **One responsibility per file**: Each service file handles exactly one concern.
- **Routes are thin**: Routes call services — they don't contain business logic.
- **Services call github_service**: No service talks directly to GitHub except `github_service.py`.
- **Models define structure**: Models describe database tables — they don't contain query logic.
- **Validators first**: User input is validated before any API calls are made.
- **No secrets in code**: Everything sensitive lives in `.env` only.

---

## Phase Roadmap

| Phase | Status | Description |
|-------|--------|-------------|
| Phase 1 | 🟡 In Progress | Repository mining & data collection backend |
| Phase 2 | ⬜ Planned | Timeline analysis & archaeology intelligence |
| Phase 3 | ⬜ Planned | AI/NLP layer — ask questions about repositories |
| Phase 4 | ⬜ Planned | Frontend visualization |

---

## License

MIT License — see LICENSE file for details.
