from pydantic import BaseModel, Field


class JobListing(BaseModel):
    title: str = Field(description="Job title as posted")
    company: str = Field(description="Hiring company name, or 'Unknown' if not stated")
    location: str = Field(description="Job location(s), or 'Not specified'")
    experience: str = Field(description="Experience range mentioned, or 'Not specified'")
    key_skills: list[str] = Field(default_factory=list, description="Key skills/keywords mentioned for this role")
    match_score: int = Field(ge=0, le=100, description="How well this job matches the candidate's resume and intended role")
    match_reason: str = Field(description="One-sentence reason for the match score, referencing the candidate's resume")
    url: str = Field(description="Naukri job listing URL")


class JobSearchOutput(BaseModel):
    candidate_summary: str = Field(description="1-2 sentence summary of the candidate's profile used for matching")
    search_queries_used: list[str] = Field(description="The search queries the agent issued")
    jobs: list[JobListing] = Field(description="Top unique job matches, ranked by match_score descending")
