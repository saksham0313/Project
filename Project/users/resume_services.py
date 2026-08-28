"""Resume processing, offline question generation, and optional AI helpers.

The local path is the product baseline. External providers are deliberately
optional: a missing key, timeout, invalid JSON, or quota error never prevents a
user from practising an interview.
"""

from __future__ import annotations

import json
import re
from collections import OrderedDict
from typing import Any

from django.conf import settings


class ResumeProcessingError(Exception):
    """Raised when a resume cannot be safely converted to text."""


SKILL_CATALOG = (
    "Python", "Java", "JavaScript", "TypeScript", "C", "C++", "C#",
    "Django", "Flask", "FastAPI", "React", "Angular", "Node.js",
    "HTML", "CSS", "Bootstrap", "REST API", "GraphQL", "SQL", "MySQL",
    "SQLite", "PostgreSQL", "MongoDB", "Git", "GitHub", "Docker",
    "AWS", "Azure", "Linux", "Machine Learning", "Deep Learning",
    "TensorFlow", "PyTorch", "Pandas", "NumPy", "Power BI", "Excel",
    "Figma", "Firebase", "Web Speech API", "OpenAI", "Gemini",
)

SECTION_ALIASES = OrderedDict(
    [
        ("skills", ("skills", "technical skills", "skill set", "technologies")),
        ("education", ("education", "academic", "qualification")),
        ("experience", ("experience", "employment", "work history", "internship")),
        ("projects", ("projects", "project work", "personal projects")),
        ("certifications", ("certifications", "certificates", "courses")),
    ]
)


def extract_resume_text(file_field) -> str:
    """Extract text from a PDF FileField using the local pypdf package."""

    try:
        from pypdf import PdfReader
    except ImportError as exc:  # pragma: no cover - dependency is in requirements
        raise ResumeProcessingError("pypdf is not installed") from exc

    try:
        with file_field.open("rb") as handle:
            reader = PdfReader(handle)
            pages = [(page.extract_text() or "").strip() for page in reader.pages]
    except Exception as exc:
        raise ResumeProcessingError(f"Could not read the PDF: {exc}") from exc

    text = "\n".join(page for page in pages if page).strip()
    if not text:
        raise ResumeProcessingError(
            "No selectable text was found. Upload a text-based PDF or type your profile manually."
        )
    return text[:100_000]


def _clean_line(value: str) -> str:
    value = re.sub(r"^[\s•●▪‣*-]+", "", value)
    return re.sub(r"\s+", " ", value).strip(" -–—:")


def _section_lines(text: str) -> dict[str, list[str]]:
    lines = [_clean_line(line) for line in text.splitlines()]
    sections: dict[str, list[str]] = {name: [] for name in SECTION_ALIASES}
    current: str | None = None
    for line in lines:
        if not line:
            continue
        lower = re.sub(r"[^a-z ]", "", line.lower()).strip()
        found = next(
            (name for name, aliases in SECTION_ALIASES.items()
             if lower in aliases or any(lower.startswith(alias + " ") for alias in aliases)),
            None,
        )
        if found:
            current = found
            continue
        if current:
            sections[current].append(line)
    return sections


def _unique(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        value = value.strip()
        key = value.casefold()
        if value and key not in seen:
            seen.add(key)
            result.append(value)
    return result


def _contains_skill(text: str, skill: str) -> bool:
    """Match a skill as a token, avoiding C matching Computer or JavaScript."""

    return bool(re.search(rf"(?<![A-Za-z0-9]){re.escape(skill)}(?![A-Za-z0-9])", text, re.IGNORECASE))


def build_local_profile(text: str, student=None) -> dict[str, Any]:
    """Create a conservative, deterministic profile without any API call."""

    text = text or ""
    lower = text.casefold()
    skills = [skill for skill in SKILL_CATALOG if _contains_skill(text, skill)]
    if student is not None and getattr(student, "skills", ""):
        skills.extend(re.split(r"[,;/|\n]", student.skills))
    skills = _unique(skills)

    sections = _section_lines(text)
    education = _unique(sections["education"][:8])
    experience = _unique(sections["experience"][:8])
    raw_projects = _unique(sections["projects"][:8])
    certifications = _unique(sections["certifications"][:8])

    # Resumes often omit headings. Keep only lines that explicitly provide
    # project evidence rather than inventing a project name.
    if not raw_projects:
        raw_projects = _unique(
            [
                _clean_line(line)
                for line in text.splitlines()
                if "project" in line.casefold()
            ][:8]
        )

    projects = []
    for line in raw_projects:
        technologies = [skill for skill in skills if _contains_skill(line, skill)]
        projects.append(
            {
                "name": line[:100],
                "description": line[:300],
                "technologies": technologies,
            }
        )

    return {
        "skills": skills,
        "education": education,
        "experience": experience,
        "projects": projects,
        "certifications": certifications,
        "source": "local",
    }


def _profile_evidence(profile: dict[str, Any]) -> list[str]:
    evidence: list[str] = list(profile.get("skills", []) or [])
    for key in ("education", "experience", "certifications"):
        evidence.extend(profile.get(key, []) or [])
    for project in profile.get("projects", []) or []:
        if isinstance(project, dict):
            evidence.append(str(project.get("name", "")))
            evidence.append(str(project.get("description", "")))
    return [item.strip() for item in evidence if str(item).strip()]


def local_questions(
    profile: dict[str, Any],
    role: str,
    difficulty: str = "medium",
    interview_type: str = "general",
    count: int = 5,
) -> list[dict[str, Any]]:
    """Generate grounded questions from resume evidence, entirely offline."""

    difficulty = difficulty if difficulty in {"easy", "medium", "hard"} else "medium"
    interview_type = interview_type if interview_type in {"general", "technical", "behavioral"} else "general"
    questions: list[dict[str, Any]] = []

    def add(text: str, category: str, source: str, evidence: str, topics: list[str]):
        questions.append(
            {
                "question": text,
                "type": category,
                "category": category,
                "source": source,
                "source_evidence": evidence[:255],
                "expected_topics": _unique(topics),
            }
        )

    projects = profile.get("projects", []) or []
    skills = profile.get("skills", []) or []
    education = profile.get("education", []) or []
    experience = profile.get("experience", []) or []

    if interview_type in {"general", "technical"}:
        for project in projects[:2]:
            if isinstance(project, dict):
                name = project.get("name") or "the project listed on your resume"
                description = project.get("description") or name
                technologies = project.get("technologies", []) or []
            else:
                name, description, technologies = str(project), str(project), []
            add(
                f"Walk me through {name}. What problem did it solve and what was your contribution?",
                "Project",
                "project",
                description,
                ["problem", "contribution", "implementation", *technologies],
            )
            if difficulty != "easy":
                add(
                    f"What technical decision did you make in {name}, and what would you improve now?",
                    "Project Technical",
                    "project",
                    description,
                    ["decision", "trade-off", "improvement", *technologies],
                )

        for skill in skills[:3]:
            add(
                f"You listed {skill} on your resume. Explain how you have used it and give one concrete example.",
                "Skill",
                "skill",
                skill,
                [skill, "example", "implementation"],
            )

    if interview_type in {"general", "behavioral"}:
        for item in experience[:1]:
            add(
                f"Tell me about the experience described here: {item[:160]}. What did you learn?",
                "Experience",
                "experience",
                item,
                ["responsibility", "result", "learning"],
            )
        for item in education[:1]:
            add(
                f"How has your education or coursework prepared you for a {role} position?",
                "Education",
                "education",
                item,
                ["coursework", "foundation", role],
            )
        add(
            f"Why are you interested in working as a {role}, and which resume experience supports that choice?",
            "Motivation",
            "profile",
            ", ".join(_profile_evidence(profile)[:3]) or role,
            [role, "motivation", "experience"],
        )

    if not questions:
        add(
            f"What makes you a good candidate for a {role} role? Use only the skills and experience in your profile.",
            "General",
            "fallback",
            role,
            [role, "skills", "experience"],
        )

    # Small or sparse resumes still get a complete practice set. These prompts
    # refer to the user's profile without inventing a technology or employer.
    profile_evidence = ", ".join(_profile_evidence(profile)[:3]) or role
    generic = [
        (
            f"Which part of your profile ({profile_evidence[:120]}) best prepares you for this role?",
            "Profile",
            ["profile", role, "preparation"],
        ),
        (
            "Describe a challenge you faced while learning or building something listed in your profile.",
            "Behavioral",
            ["challenge", "action", "result"],
        ),
        (
            "What would you improve next in the work or project experience shown on your resume?",
            "Improvement",
            ["improvement", "reason", "plan"],
        ),
        (
            "Choose one item from your profile and explain how you would measure a successful outcome.",
            "Results",
            ["measurement", "outcome", "result"],
        ),
        (
            "How would you explain one project or skill from your resume to a non-technical teammate?",
            "Communication",
            ["explanation", "audience", "clarity"],
        ),
    ]
    for text, category, topics in generic:
        if len(questions) >= max(1, min(int(count), 15)):
            break
        add(text, category, "profile", profile_evidence, topics)

    # Keep a small interview predictable while still varying the evidence.
    result: list[dict[str, Any]] = []
    for question in questions:
        if len(result) >= max(1, min(int(count), 15)):
            break
        if not any(existing["question"] == question["question"] for existing in result):
            result.append(question)
    return result


def _extract_json(value: Any) -> Any:
    if isinstance(value, (dict, list)):
        return value
    if not isinstance(value, str):
        raise ValueError("Provider did not return JSON text")
    value = value.strip()
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        match = re.search(r"(\{.*\}|\[.*\])", value, flags=re.DOTALL)
        if not match:
            raise ValueError("Provider returned invalid JSON")
        return json.loads(match.group(1))


def _provider_json(prompt: str) -> Any:
    """Call one optional provider using only the Python standard library."""

    import urllib.error
    import urllib.request

    provider = getattr(settings, "AI_PROVIDER", "local").lower()
    timeout = getattr(settings, "AI_TIMEOUT_SECONDS", 20)
    if provider == "gemini":
        key = getattr(settings, "GEMINI_API_KEY", "")
        model = getattr(settings, "GEMINI_MODEL", "gemini-2.5-flash")
        if not key:
            raise ValueError("GEMINI_API_KEY is not configured")
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={key}"
        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"responseMimeType": "application/json"},
        }
        request = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=timeout) as response:
            body = json.loads(response.read().decode("utf-8"))
        text = body["candidates"][0]["content"]["parts"][0]["text"]
        return _extract_json(text)

    if provider in {"openai", "openrouter"}:
        key = getattr(settings, "OPENAI_API_KEY", "")
        if not key:
            raise ValueError("OPENAI_API_KEY is not configured")
        base_url = getattr(settings, "OPENAI_BASE_URL", "https://api.openai.com/v1").rstrip("/")
        model = getattr(settings, "OPENAI_MODEL", "gpt-4o-mini")
        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": "Return valid JSON only."},
                {"role": "user", "content": prompt},
            ],
            "response_format": {"type": "json_object"},
        }
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {key}",
        }
        if provider == "openrouter":
            referer = getattr(settings, "OPENROUTER_HTTP_REFERER", "")
            title = getattr(settings, "OPENROUTER_TITLE", "CareerAI Resume Interview")
            if referer:
                headers["HTTP-Referer"] = referer
            if title:
                headers["X-Title"] = title
        request = urllib.request.Request(
            f"{base_url}/chat/completions",
            data=json.dumps(payload).encode("utf-8"),
            headers=headers,
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=timeout) as response:
            body = json.loads(response.read().decode("utf-8"))
        text = body["choices"][0]["message"]["content"]
        return _extract_json(text)

    raise ValueError(f"Unsupported provider: {provider}")


def _valid_ai_questions(value: Any, raw_text: str, count: int) -> list[dict[str, Any]]:
    if isinstance(value, dict):
        value = value.get("questions", [])
    if not isinstance(value, list):
        return []
    grounded: list[dict[str, Any]] = []
    resume_lower = raw_text.casefold()
    for item in value:
        if not isinstance(item, dict):
            continue
        question = str(item.get("question", "")).strip()
        evidence = str(item.get("source_evidence", item.get("evidence", ""))).strip()
        if len(question) < 12 or not evidence or evidence.casefold() not in resume_lower:
            continue
        grounded.append(
            {
                "question": question[:1000],
                "type": str(item.get("category", item.get("type", "General")))[:50],
                "category": str(item.get("category", item.get("type", "General")))[:50],
                "source": str(item.get("source", "ai"))[:30],
                "source_evidence": evidence[:255],
                "expected_topics": [str(x)[:80] for x in item.get("expected_topics", []) if str(x).strip()][:12],
            }
        )
        if len(grounded) >= count:
            break
    return grounded


def generate_questions(
    profile: dict[str, Any],
    raw_text: str,
    role: str,
    difficulty: str,
    interview_type: str,
    count: int,
) -> tuple[list[dict[str, Any]], str]:
    fallback = local_questions(profile, role, difficulty, interview_type, count)
    if not getattr(settings, "AI_ENABLED", False) or getattr(settings, "AI_PROVIDER", "local") == "local":
        return fallback, "local"

    prompt = f"""
Create {count} {difficulty} {interview_type} interview questions for the role {role}.
Use only the verified resume text below. Never invent a skill, project, employer,
technology, qualification, or experience. Every question must cite an exact
source_evidence phrase copied from the resume. Return JSON with a questions array;
each item must contain question, category, source, source_evidence, expected_topics.

RESUME TEXT:
{raw_text[:20000]}
""".strip()
    try:
        questions = _valid_ai_questions(_provider_json(prompt), raw_text, count)
        if len(questions) >= max(1, min(count, 3)):
            return questions, "ai"
    except Exception:
        pass
    return fallback, "local-fallback"


def local_evaluate_answer(question: dict[str, Any], answer: str) -> dict[str, Any]:
    answer = (answer or "").strip()
    words = re.findall(r"[A-Za-z0-9+#.-]+", answer.casefold())
    word_count = len(words)
    filler_count = len(re.findall(r"\b(?:um|uh|like|basically|actually|you know|so)\b", answer.casefold()))
    topics = [str(item).casefold() for item in question.get("expected_topics", []) if str(item).strip()]
    matched_topics = [topic for topic in topics if topic in answer.casefold()]
    topic_score = min(100.0, (len(matched_topics) / max(1, len(topics))) * 100)
    length_score = min(100.0, word_count * 1.6)
    communication = max(0.0, min(100.0, 35 + min(word_count, 80) * 0.65 - filler_count * 4))
    technical = round((topic_score * 0.7) + (length_score * 0.3), 2)
    relevance = round(topic_score, 2)
    overall = round((technical * 0.5) + (relevance * 0.25) + (communication * 0.25), 2)

    feedback = []
    if not answer:
        feedback.append("Answer was empty; provide a specific example.")
    elif word_count < 25:
        feedback.append("Add more detail using the situation, action, and result.")
    if filler_count:
        feedback.append(f"Reduce filler words ({filler_count} detected).")
    if topics and not matched_topics:
        feedback.append("Connect the answer more directly to the resume evidence and expected technical points.")
    if not feedback:
        feedback.append("Good structure. Add measurable results where possible.")

    return {
        "technical_score": technical,
        "relevance_score": relevance,
        "communication_score": round(communication, 2),
        "overall_score": overall,
        "filler_count": filler_count,
        "feedback": feedback,
    }


def evaluate_answer(question: dict[str, Any], answer: str) -> tuple[dict[str, Any], str]:
    fallback = local_evaluate_answer(question, answer)
    if not getattr(settings, "AI_ENABLED", False) or getattr(settings, "AI_PROVIDER", "local") == "local":
        return fallback, "local"
    prompt = f"""
Evaluate the candidate answer only against this interview question and expected topics.
Do not infer emotion or make hiring decisions. Return JSON with numeric fields
technical_score, relevance_score, communication_score, overall_score (0-100),
filler_count, and a feedback array of at most three actionable strings.

QUESTION: {question.get('question', '')}
EXPECTED TOPICS: {question.get('expected_topics', [])}
ANSWER: {answer[:12000]}
""".strip()
    try:
        value = _provider_json(prompt)
        if isinstance(value, dict):
            result = dict(fallback)
            for key in ("technical_score", "relevance_score", "communication_score", "overall_score"):
                if isinstance(value.get(key), (int, float)):
                    result[key] = max(0.0, min(100.0, float(value[key])))
            if isinstance(value.get("filler_count"), int):
                result["filler_count"] = max(0, value["filler_count"])
            if isinstance(value.get("feedback"), list):
                result["feedback"] = [str(item)[:300] for item in value["feedback"][:3]]
            return result, "ai"
    except Exception:
        pass
    return fallback, "local-fallback"


def feedback_from_answers(answers: list[dict[str, Any]]) -> dict[str, Any]:
    if not answers:
        return {
            "strengths": [],
            "weaknesses": ["No answers were submitted."],
            "recommendations": ["Complete the interview and answer with specific resume examples."],
        }
    strengths: list[str] = []
    weaknesses: list[str] = []
    for answer in answers:
        score = float(answer.get("overall_score", 0))
        if score >= 70:
            strengths.append("Clear and relevant response")
        if score < 55:
            weaknesses.append("Answer depth or technical relevance")
        if int(answer.get("filler_count", 0)) > 2:
            weaknesses.append("Filler-word control")
    strengths = _unique(strengths)
    weaknesses = _unique(weaknesses)
    recommendations = []
    if "Answer depth or technical relevance" in weaknesses:
        recommendations.append("Use a specific project example and explain your contribution and result.")
    if "Filler-word control" in weaknesses:
        recommendations.append("Pause briefly instead of using filler words while thinking.")
    if not recommendations:
        recommendations.append("Keep practising concise answers with measurable outcomes.")
    return {"strengths": strengths, "weaknesses": weaknesses, "recommendations": recommendations}


def _text_list(value: Any, limit: int = 6, item_limit: int = 240) -> list[str]:
    """Keep provider-generated guidance predictable and safe for templates."""

    if not isinstance(value, list):
        return []
    result: list[str] = []
    for item in value:
        item = re.sub(r"\s+", " ", str(item)).strip()
        if item and item.casefold() not in {entry.casefold() for entry in result}:
            result.append(item[:item_limit])
        if len(result) >= limit:
            break
    return result


def local_career_guidance(
    profile: dict[str, Any],
    interview_feedback: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Generate useful career guidance without an external API."""

    skills = [str(item) for item in profile.get("skills", []) if str(item).strip()]
    lower_skills = {item.casefold() for item in skills}
    roles: list[str] = []
    if {"react", "javascript", "typescript", "html", "css"} & lower_skills:
        roles.append("Frontend / Web Developer")
    if {"django", "flask", "fastapi", "python", "java", "sql"} & lower_skills:
        roles.append("Backend Developer")
    if {"machine learning", "deep learning", "tensorflow", "pytorch", "pandas"} & lower_skills:
        roles.append("AI / ML Engineer")
    if {"sql", "power bi", "excel", "data analysis"} & lower_skills:
        roles.append("Data Analyst")
    if not roles:
        roles = ["Software Developer", "Junior Web Developer"]

    gaps: list[str] = []
    if not ({"git", "github"} & lower_skills):
        gaps.append("Git and GitHub workflow")
    if not ({"docker", "aws", "azure"} & lower_skills):
        gaps.append("Deployment fundamentals")
    if not ({"testing", "pytest", "selenium"} & lower_skills):
        gaps.append("Automated testing")
    if not profile.get("projects"):
        gaps.append("One measurable portfolio project")

    strengths = skills[:4] or ["Willingness to learn", "Resume evidence ready for practice"]
    projects = []
    if "python" in lower_skills or "django" in lower_skills:
        projects.append("Build a resume-grounded Django app with authentication, tests, and deployment notes.")
    if "react" in lower_skills or "javascript" in lower_skills:
        projects.append("Create a responsive dashboard that consumes a small REST API and handles loading states.")
    if "sql" in lower_skills or "pandas" in lower_skills:
        projects.append("Publish a small data story with a cleaned dataset, SQL queries, and three decision-focused charts.")
    if not projects:
        projects.append("Build one small end-to-end project and document the problem, decisions, and measurable result.")

    recommendations = [
        "Rewrite each project bullet as action + technology + measurable result.",
        "Practise one two-minute answer for every major skill listed on the resume.",
        "Add a README, screenshots, and a short demo link to your strongest project.",
    ]
    if interview_feedback:
        recommendations.extend(_text_list(interview_feedback.get("recommendations"), limit=2))

    return {
        "target_roles": _unique(roles)[:5],
        "strengths": _unique(strengths)[:6],
        "skill_gaps": _unique(gaps)[:6],
        "project_ideas": _unique(projects)[:5],
        "thirty_day_plan": [
            "Week 1 · Pick one target role and map your resume evidence to its core requirements.",
            "Week 2 · Strengthen one gap with a small hands-on task and commit the work to GitHub.",
            "Week 3 · Rehearse five resume-grounded questions and tighten every answer with a result.",
            "Week 4 · Ship or polish one portfolio project, then run another practice interview.",
        ],
        "next_steps": _unique(recommendations)[:6],
    }


def _valid_career_guidance(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {}
    result = {
        "target_roles": _text_list(value.get("target_roles")),
        "strengths": _text_list(value.get("strengths")),
        "skill_gaps": _text_list(value.get("skill_gaps")),
        "project_ideas": _text_list(value.get("project_ideas")),
        "thirty_day_plan": _text_list(value.get("thirty_day_plan"), limit=8),
        "next_steps": _text_list(value.get("next_steps")),
    }
    if not result["target_roles"] or not result["next_steps"]:
        return {}
    return result


def generate_career_guidance(
    profile: dict[str, Any],
    raw_text: str,
    interview_feedback: dict[str, Any] | None = None,
) -> tuple[dict[str, Any], str]:
    """Create resume-grounded career suggestions with Gemini or local fallback."""

    fallback = local_career_guidance(profile, interview_feedback)
    if not getattr(settings, "AI_ENABLED", False) or getattr(settings, "AI_PROVIDER", "local") == "local":
        return fallback, "local"

    prompt = f"""
Create practical career guidance using only the verified resume evidence below.
Do not invent employers, credentials, technologies, achievements, or job history.
Return JSON with exactly these array keys: target_roles, strengths, skill_gaps,
project_ideas, thirty_day_plan, next_steps. Keep every item concise and specific.
Use the interview feedback only as a practice signal, never as a hiring decision.

PROFILE JSON:
{json.dumps(profile, ensure_ascii=False)[:12000]}

RESUME EVIDENCE:
{raw_text[:16000]}

INTERVIEW FEEDBACK:
{json.dumps(interview_feedback or {}, ensure_ascii=False)[:5000]}
""".strip()
    try:
        guidance = _valid_career_guidance(_provider_json(prompt))
        if guidance:
            return guidance, "ai"
    except Exception:
        pass
    return fallback, "local-fallback"


def generate_interview_feedback(answers: list[dict[str, Any]]) -> tuple[dict[str, Any], str]:
    """Summarise saved interview answers with Gemini when it is available."""

    fallback = feedback_from_answers(answers)
    if not getattr(settings, "AI_ENABLED", False) or getattr(settings, "AI_PROVIDER", "local") == "local":
        return fallback, "local"

    prompt = f"""
Review these interview answers as a practice coach. Use only the questions,
answers, scores, and saved feedback provided. Do not make a hiring decision,
infer personality, or invent facts. Return JSON with exactly three array keys:
strengths, weaknesses, recommendations. Give at most four short, actionable
items in each array.

ANSWERS JSON:
{json.dumps(answers, ensure_ascii=False)[:18000]}
""".strip()
    try:
        value = _provider_json(prompt)
        if isinstance(value, dict):
            result = {
                "strengths": _text_list(value.get("strengths"), limit=4),
                "weaknesses": _text_list(value.get("weaknesses"), limit=4),
                "recommendations": _text_list(value.get("recommendations"), limit=4),
            }
            if result["recommendations"] and (result["strengths"] or result["weaknesses"]):
                return result, "ai"
    except Exception:
        pass
    return fallback, "local-fallback"
