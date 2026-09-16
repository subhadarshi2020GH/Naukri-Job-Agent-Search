"""Search tool: finds Naukri job-listing pages via the Tavily web-search API.

We deliberately do NOT crawl or scrape naukri.com directly. Naukri's
robots.txt disallows AI-agent user agents (Claude-User, Claude-SearchBot,
GPTBot, etc.) site-wide. Tavily is a third-party search index; querying it
respects that opt-out while still surfacing indexed Naukri job postings.
"""

import os
import re

import requests
from agents import function_tool

TAVILY_URL = "https://api.tavily.com/search"
JOB_URL_PATTERN = re.compile(r"naukri\.com/job-listings-", re.IGNORECASE)
JOB_ID_PATTERN = re.compile(r"-(\d+)/?$")


def _job_id_from_url(url: str) -> str:
    clean = url.split("?", 1)[0].split("#", 1)[0].rstrip("/")
    match = JOB_ID_PATTERN.search(clean)
    return match.group(1) if match else clean


class JobPool:
    """Accumulates unique Naukri job-listing results across multiple searches."""

    def __init__(self):
        self._jobs: dict[str, dict] = {}
        self.queries_used: list[str] = []

    def add_from_tavily(self, results: list[dict]) -> list[dict]:
        added = []
        for r in results:
            url = r.get("url", "")
            if not JOB_URL_PATTERN.search(url):
                continue
            job_id = _job_id_from_url(url)
            if job_id in self._jobs:
                continue
            entry = {"title": r.get("title", ""), "url": url, "snippet": r.get("content", "")}
            self._jobs[job_id] = entry
            added.append(entry)
        return added

    def all_jobs(self) -> list[dict]:
        return list(self._jobs.values())

    def count(self) -> int:
        return len(self._jobs)


def make_tools(pool: JobPool):
    api_key = os.environ["TAVILY_API_KEY"]

    @function_tool
    def search_naukri_jobs(query: str) -> str:
        """Search for job postings on naukri.com matching the given query.

        Call this multiple times with different phrasings (role synonyms,
        seniority levels, key skills, locations) to widen coverage. Results
        are automatically de-duplicated across calls.

        Args:
            query: Search keywords, e.g. "Senior Data Scientist Bangalore Python"
        """
        pool.queries_used.append(query)
        resp = requests.post(
            TAVILY_URL,
            json={
                "api_key": api_key,
                "query": f"{query} site:naukri.com",
                "include_domains": ["naukri.com"],
                "max_results": 15,
                "search_depth": "advanced",
            },
            timeout=30,
        )
        if resp.status_code != 200:
            return f"Tavily API error: {resp.status_code} {resp.text[:200]}"

        results = resp.json().get("results", [])
        added = pool.add_from_tavily(results)
        if not added:
            return f"No new unique job listings found for '{query}'. Pool size so far: {pool.count()}."

        lines = [f"Added {len(added)} new unique job listing(s) for '{query}':"]
        for job in added:
            lines.append(f"- {job['title']} | {job['url']}")
        lines.append(f"Total unique jobs collected so far: {pool.count()}.")
        return "\n".join(lines)

    @function_tool
    def list_collected_jobs() -> str:
        """Return every unique job listing collected so far, with full snippets.

        Call this once you've run enough searches, right before producing
        your final ranked list, so you have the complete candidate pool in
        view.
        """
        jobs = pool.all_jobs()
        if not jobs:
            return "No jobs collected yet. Run search_naukri_jobs first."
        lines = [f"{len(jobs)} unique job listing(s) collected:"]
        for i, job in enumerate(jobs, 1):
            lines.append(f"{i}. {job['title']}\n   URL: {job['url']}\n   Snippet: {job['snippet'][:400]}")
        return "\n".join(lines)

    return [search_naukri_jobs, list_collected_jobs]
