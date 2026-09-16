# Naukri Job-Match Agent

Takes a resume (PDF/DOCX) + intended job role, finds the top N unique job
postings on naukri.com, ranks them against the resume, and writes a CSV.

## Why Tavily instead of scraping naukri.com

Naukri's `robots.txt` explicitly disallows AI-agent user agents
(`Claude-User`, `Claude-SearchBot`, `GPTBot`, etc.) across the whole site.
Rather than build around that opt-out, this agent searches via the
[Tavily](https://tavily.com) web-search API restricted to `naukri.com`, and
only ever reads what a third-party search index has already crawled.
Coverage/freshness will lag a live Naukri search — if that's a blocker,
consider the human-in-the-loop variant (agent builds the search query, a
person opens naukri.com and pastes back the results for ranking).

## Setup

```bash
pip install -r requirements.txt
cp .env.example .env
```

Then edit `.env` and fill in real values for `GEMINI_API_KEY` and
`TAVILY_API_KEY`:

- Gemini key: https://aistudio.google.com/apikey
- Tavily key: https://tavily.com

## Usage

```bash
python agent.py --resume path/to/resume.pdf --role "Senior Data Scientist" --location Bangalore
```

Options:
- `--max-results` (default 25) — how many unique jobs to return
- `--out` — output CSV path (default `naukri_top_jobs_<timestamp>.csv`)

## How it works

1. `resume_parser.py` extracts text from the PDF/DOCX.
2. `agent.py` runs a Gemini-backed agent (OpenAI Agents SDK, pointed at
   Gemini's OpenAI-compatible endpoint) that generates several search
   queries and calls the `search_naukri_jobs` tool.
3. `tools.py` queries Tavily, keeps only actual `naukri.com/job-listings-*`
   URLs, and de-duplicates by the numeric job ID in the URL (deterministic,
   not left to the LLM).
4. The agent reviews the full de-duplicated pool, scores each listing
   against the resume, and returns a structured, ranked top-N.
5. `agent.py` sorts by score, writes the CSV, and prints a console summary.
