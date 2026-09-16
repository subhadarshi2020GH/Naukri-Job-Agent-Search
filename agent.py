"""Resume -> Naukri job-match agent.

Given a resume (PDF/DOCX) and an intended job role, this agent:
  1. Reads the resume.
  2. Uses an LLM (Gemini, via the OpenAI Agents SDK) to generate several
     Naukri-oriented search queries and run them through Tavily web search
     (restricted to naukri.com), instead of scraping naukri.com directly.
  3. De-duplicates results by job listing URL/ID (deterministic, in code).
  4. Has the LLM score each unique listing against the resume and pick the
     top N (default 25).
  5. Writes a CSV and prints a console summary.

Usage:
    python agent.py --resume path/to/resume.pdf --role "Senior Data Scientist" --location Bangalore
"""

import argparse
import asyncio
import csv
import os
from datetime import datetime
from pathlib import Path

from agents import Agent, OpenAIChatCompletionsModel, Runner, set_tracing_disabled
from dotenv import load_dotenv
from openai import AsyncOpenAI

from models import JobSearchOutput
from resume_parser import extract_resume_text
from tools import JobPool, make_tools

load_dotenv(Path(__file__).resolve().parent / ".env")
set_tracing_disabled(True)

GEMINI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/openai/"
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")

INSTRUCTIONS = """\
You are a job-search assistant. You are given a candidate's resume text and \
their intended job role (and optionally a preferred location).

Your job:
1. From the resume, identify the candidate's core skills, seniority/years of \
   experience, and job titles they're qualified for.
2. Call the search_naukri_jobs tool 4-8 times with varied, specific queries: \
   mix the intended role, close synonyms, seniority levels, and top skills \
   (and the preferred location, if given). Prefer specific queries over broad \
   ones - specific queries surface more unique, relevant postings.
3. Once you've searched enough, call list_collected_jobs to review every \
   unique listing found.
4. Score each listing 0-100 on fit against the resume and intended role, \
   using its title/snippet. For each, extract company, location, experience \
   range, and key skills as best you can from the title/snippet - use \
   "Not specified" / "Unknown" if a field truly isn't stated, don't guess.
5. Return the top matches, ranked by match_score descending, most relevant \
   first, capped at the number requested. Never invent a job that wasn't \
   returned by a tool call.
"""


async def run_agent(resume_text: str, role: str, location: str | None, max_results: int) -> JobSearchOutput:
    gemini_client = AsyncOpenAI(api_key=os.environ["GEMINI_API_KEY"], base_url=GEMINI_BASE_URL)
    pool = JobPool()

    agent = Agent(
        name="Naukri Job Matcher",
        instructions=INSTRUCTIONS,
        model=OpenAIChatCompletionsModel(model=GEMINI_MODEL, openai_client=gemini_client),
        tools=make_tools(pool),
        output_type=JobSearchOutput,
    )

    prompt = (
        f"Candidate resume:\n{resume_text[:10000]}\n\n"
        f"Intended job role: {role}\n"
        f"Preferred location: {location or 'Any'}\n\n"
        f"Find the top {max_results} unique, best-matching job postings on naukri.com for this candidate."
    )

    result = await Runner.run(agent, prompt, max_turns=20)
    output: JobSearchOutput = result.final_output
    output.jobs = sorted(output.jobs, key=lambda j: j.match_score, reverse=True)[:max_results]
    return output


def write_csv(output: JobSearchOutput, out_path: Path) -> None:
    with out_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["rank", "title", "company", "location", "experience", "match_score", "match_reason", "key_skills", "url"])
        for i, job in enumerate(output.jobs, 1):
            writer.writerow([i, job.title, job.company, job.location, job.experience, job.match_score, job.match_reason, "; ".join(job.key_skills), job.url])


def print_summary(output: JobSearchOutput, csv_path: Path) -> None:
    print(f"\nCandidate summary: {output.candidate_summary}")
    print(f"Search queries used ({len(output.search_queries_used)}): {', '.join(output.search_queries_used)}")
    print(f"\nTop {len(output.jobs)} unique job matches:\n")
    for i, job in enumerate(output.jobs, 1):
        print(f"{i:2}. [{job.match_score:3}] {job.title} - {job.company} - {job.location} ({job.experience})")
        print(f"     {job.url}")
    print(f"\nSaved full results to {csv_path}")


def main():
    parser = argparse.ArgumentParser(description="Match a resume to top Naukri job postings.")
    parser.add_argument("--resume", required=True, help="Path to resume file (.pdf or .docx)")
    parser.add_argument("--role", required=True, help="Intended job role, e.g. 'Senior Data Scientist'")
    parser.add_argument("--location", default=None, help="Preferred job location (optional)")
    parser.add_argument("--max-results", type=int, default=25, help="Number of unique jobs to return (default 25)")
    parser.add_argument("--out", default=None, help="Output CSV path (default: naukri_top_jobs_<timestamp>.csv)")
    args = parser.parse_args()

    resume_text = extract_resume_text(args.resume)
    if not resume_text.strip():
        raise SystemExit("Could not extract any text from the resume file.")

    output = asyncio.run(run_agent(resume_text, args.role, args.location, args.max_results))

    out_path = Path(args.out) if args.out else Path(f"naukri_top_jobs_{datetime.now():%Y%m%d_%H%M%S}.csv")
    write_csv(output, out_path)
    print_summary(output, out_path)


if __name__ == "__main__":
    main()
