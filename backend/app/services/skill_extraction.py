"""Best-effort extraction of skills and an experience range from a job's own
free-text description, used ONLY as a fallback when a source doesn't supply
structured metadata (this is common with real-world aggregated postings —
see the JSearch adapter's docstring).

This is NOT invented data — a skill is only ever reported if its exact name
literally appears in the posting's own text, and an experience range is only
ever reported when the text contains an explicit "X years" style phrase. If
neither is found, both simply come back empty/None rather than guessing, so
the matching engine's existing "nothing to compare against" neutral handling
(see matching_service._score_skills / _score_experience) takes over instead
of silently fabricating a number.

Why this matters: without it, a job with no structured skills/experience
data scores every candidate near an uninformative ~45-55 "neutral" baseline
on two of the highest-weighted components (skills 25%, experience 20%)
regardless of actual fit — which is indistinguishable from a genuine match
and directly undermines "only show jobs that are actually suitable for this
candidate." Real extracted signal, even approximate, is far better than a
neutral default standing in for 45% of the score.
"""

from __future__ import annotations

import re

# Flat vocabulary for keyword matching against job description text. Casing
# here is the CANONICAL display form returned when matched; matching itself
# is case-insensitive except where noted (short/ambiguous tokens).
_SKILL_VOCABULARY: list[str] = [
    # Languages
    "Python", "Java", "JavaScript", "TypeScript", "C++", "C#", "Golang", "Rust",
    "Ruby", "PHP", "Swift", "Kotlin", "Scala", "MATLAB", "Perl", "Objective-C", "Dart",
    # Frameworks / libraries
    "Django", "Flask", "FastAPI", "Spring Boot", "Spring", "React", "Angular",
    "Vue.js", "Next.js", "Node.js", "Express.js", ".NET", "ASP.NET",
    "Ruby on Rails", "Laravel", "jQuery", "Redux", "GraphQL", "REST API", "gRPC",
    # Databases
    "PostgreSQL", "MySQL", "MongoDB", "Redis", "SQLite", "Oracle", "SQL Server",
    "Cassandra", "DynamoDB", "Elasticsearch", "MariaDB", "Firebase", "Snowflake", "BigQuery",
    # Cloud / infra
    "AWS", "Azure", "GCP", "Google Cloud", "EC2", "S3", "Lambda", "Kubernetes",
    "Docker", "Terraform", "CloudFormation", "Heroku", "DigitalOcean",
    # DevOps / tools
    "Git", "GitHub", "GitLab", "Jenkins", "CI/CD", "Ansible", "Nginx", "Apache",
    "Linux", "Bash", "Prometheus", "Grafana", "Kafka", "RabbitMQ",
    # AI / ML / data
    "Machine Learning", "Deep Learning", "TensorFlow", "PyTorch", "Scikit-learn",
    "Pandas", "NumPy", "Data Science", "NLP", "Computer Vision", "LLM", "RAG",
    "LangChain", "OpenAI", "Hugging Face", "Spark", "Hadoop", "ETL", "Airflow",
    "Tableau", "Power BI",
    # Mobile
    "Android", "iOS", "React Native", "Flutter", "SwiftUI",
    # Testing
    "Selenium", "JUnit", "PyTest", "Jest", "Cypress", "Postman",
    # Practices / misc
    "Agile", "Scrum", "Jira", "Microservices", "OOP", "System Design", "SQL",
    "NoSQL", "HTML", "CSS", "Sass", "Webpack",
]

# Ambiguous short tokens that collide with common English words when matched
# case-insensitively (e.g. "go", "r" as ordinary words) — require exact case.
_CASE_SENSITIVE = {"Golang", "R", "C", "Go"}

_SKILL_PATTERNS: list[tuple[str, re.Pattern]] = [
    (
        skill,
        re.compile(
            rf"(?<![A-Za-z0-9]){re.escape(skill)}(?![A-Za-z0-9])",
            0 if skill in _CASE_SENSITIVE else re.IGNORECASE,
        ),
    )
    for skill in _SKILL_VOCABULARY
]

MAX_EXTRACTED_SKILLS = 20


def extract_skills_from_text(text: str) -> list[str]:
    if not text:
        return []
    found: list[str] = []
    for skill, pattern in _SKILL_PATTERNS:
        if pattern.search(text):
            found.append(skill)
        if len(found) >= MAX_EXTRACTED_SKILLS:
            break
    return found


# "3-5 years", "3 to 5 years", "5+ years", "minimum 5 years", "at least 3 years"
_RANGE_RE = re.compile(r"(\d{1,2})\s*(?:-|to|–)\s*(\d{1,2})\+?\s*years?", re.IGNORECASE)
_PLUS_RE = re.compile(r"(\d{1,2})\s*\+\s*years?", re.IGNORECASE)
_MIN_PHRASE_RE = re.compile(
    r"(?:minimum|min\.?|at least|over)\s*(?:of\s*)?(\d{1,2})\s*years?", re.IGNORECASE
)


def extract_experience_range_from_text(text: str) -> tuple[int, int] | None:
    if not text:
        return None
    m = _RANGE_RE.search(text)
    if m:
        lo, hi = int(m.group(1)), int(m.group(2))
        if lo <= hi and hi <= 40:
            return lo, hi
    m = _PLUS_RE.search(text) or _MIN_PHRASE_RE.search(text)
    if m:
        lo = int(m.group(1))
        if lo <= 40:
            return lo, lo + 5  # open-ended "5+ years" -> a reasonable upper bound, not a hard cap
    return None
