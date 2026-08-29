"""Resume processing, offline question generation, and optional AI helpers.

The local path is the product baseline. External providers are deliberately
optional: a missing key, timeout, invalid JSON, or quota error never prevents a
user from practising an interview.
"""

from __future__ import annotations

import json
import secrets
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
    language: str = "en",
) -> list[dict[str, Any]]:
    """Generate grounded questions from resume evidence, entirely offline."""

    difficulty = difficulty if difficulty in {"easy", "medium", "hard"} else "medium"
    interview_type = interview_type if interview_type in {"general", "technical", "behavioral"} else "general"
    language = language if language in {"en", "hi", "bilingual"} else "en"
    try:
        target_count = max(1, min(int(count), 40))
    except (TypeError, ValueError):
        target_count = 15
    questions: list[dict[str, Any]] = []

    def localized(english: str, hindi: str) -> str:
        if language == "hi":
            return hindi
        if language == "bilingual":
            return f"{english}\n{hindi}"
        return english

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
                localized(
                    f"Walk me through {name}. What problem did it solve and what was your contribution?",
                    f"{name} प्रोजेक्ट के बारे में बताइए। इसने कौन-सी समस्या हल की और आपका योगदान क्या था?",
                ),
                "Project",
                "project",
                description,
                ["problem", "contribution", "implementation", *technologies],
            )
            if difficulty != "easy":
                add(
                    localized(
                        f"What technical decision did you make in {name}, and what would you improve now?",
                        f"{name} में आपने कौन-सा तकनीकी निर्णय लिया था और आज आप इसमें क्या सुधार करेंगे?",
                    ),
                    "Project Technical",
                    "project",
                    description,
                    ["decision", "trade-off", "improvement", *technologies],
                )

        for skill in skills[:3]:
            add(
                localized(
                    f"You listed {skill} on your resume. Explain how you have used it and give one concrete example.",
                    f"आपने रिज्यूमे में {skill} लिखा है। आपने इसका उपयोग कैसे किया? एक वास्तविक उदाहरण दीजिए।",
                ),
                "Skill",
                "skill",
                skill,
                [skill, "example", "implementation"],
            )

    if interview_type in {"general", "behavioral"}:
        for item in experience[:1]:
            add(
                localized(
                    f"Tell me about the experience described here: {item[:160]}. What did you learn?",
                    f"यहाँ दिए गए अनुभव के बारे में बताइए: {item[:160]} आपने इससे क्या सीखा?",
                ),
                "Experience",
                "experience",
                item,
                ["responsibility", "result", "learning"],
            )
        for item in education[:1]:
            add(
                localized(
                    f"How has your education or coursework prepared you for a {role} position?",
                    f"आपकी शिक्षा या coursework ने आपको {role} भूमिका के लिए कैसे तैयार किया?",
                ),
                "Education",
                "education",
                item,
                ["coursework", "foundation", role],
            )
        add(
            localized(
                f"Why are you interested in working as a {role}, and which resume experience supports that choice?",
                f"आप {role} के रूप में काम करने में रुचि क्यों रखते हैं और रिज्यूमे का कौन-सा अनुभव इसका समर्थन करता है?",
            ),
            "Motivation",
            "profile",
            ", ".join(_profile_evidence(profile)[:3]) or role,
            [role, "motivation", "experience"],
        )

    if not questions:
        add(
            localized(
                f"What makes you a good candidate for a {role} role? Use only the skills and experience in your profile.",
                f"आप {role} भूमिका के लिए अच्छे उम्मीदवार क्यों हैं? अपने प्रोफाइल की skills और experience का उपयोग करें।",
            ),
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
            localized(
                f"Which part of your profile ({profile_evidence[:120]}) best prepares you for this role?",
                f"आपके प्रोफाइल का कौन-सा भाग ({profile_evidence[:120]}) आपको इस भूमिका के लिए सबसे अच्छी तरह तैयार करता है?",
            ),
            "Profile",
            ["profile", role, "preparation"],
        ),
        (
            localized(
                "Describe a challenge you faced while learning or building something listed in your profile.",
                "अपने प्रोफाइल में दी गई किसी skill या project को सीखते या बनाते समय आई चुनौती बताइए।",
            ),
            "Behavioral",
            ["challenge", "action", "result"],
        ),
        (
            localized(
                "What would you improve next in the work or project experience shown on your resume?",
                "रिज्यूमे में दिखाए गए work या project experience में आप अगला सुधार क्या करेंगे?",
            ),
            "Improvement",
            ["improvement", "reason", "plan"],
        ),
        (
            localized(
                "Choose one item from your profile and explain how you would measure a successful outcome.",
                "अपने प्रोफाइल की एक item चुनिए और बताइए कि successful outcome को कैसे measure करेंगे।",
            ),
            "Results",
            ["measurement", "outcome", "result"],
        ),
        (
            localized(
                "How would you explain one project or skill from your resume to a non-technical teammate?",
                "अपने रिज्यूमे के किसी project या skill को non-technical teammate को कैसे समझाएंगे?",
            ),
            "Communication",
            ["explanation", "audience", "clarity"],
        ),
    ]
    for text, category, topics in generic:
        if len(questions) >= target_count:
            break
        add(text, category, "profile", profile_evidence, topics)

    # Expand sparse resumes into a realistic long-form interview. Every item
    # still points to an exact resume/profile evidence phrase; only the angle
    # of the question changes.
    evidence_items = _unique(_profile_evidence(profile)) or [role]
    variant_templates = [
        (
            "Explain the most important idea behind {evidence} and how you would teach it to a teammate.",
            "{evidence} के पीछे का सबसे महत्वपूर्ण idea समझाइए और इसे teammate को कैसे सिखाएंगे?",
            "Concept clarity",
            ["explain", "concept", "teammate"],
        ),
        (
            "What challenge could appear while working with {evidence}, and how would you investigate it?",
            "{evidence} पर काम करते समय कौन-सी challenge आ सकती है और आप उसकी जांच कैसे करेंगे?",
            "Problem solving",
            ["challenge", "investigate", "solution"],
        ),
        (
            "How would you measure whether your work on {evidence} was successful?",
            "{evidence} पर आपके काम के successful होने को आप कैसे measure करेंगे?",
            "Results",
            ["measure", "success", "result"],
        ),
        (
            "What trade-off would you consider before changing the work connected to {evidence}?",
            "{evidence} से जुड़े काम में बदलाव करने से पहले आप किस trade-off पर विचार करेंगे?",
            "Decision making",
            ["trade-off", "decision", "impact"],
        ),
        (
            "If you had one more week to improve {evidence}, what would you change first and why?",
            "अगर {evidence} को बेहतर बनाने के लिए एक और सप्ताह मिले, तो आप सबसे पहले क्या बदलेंगे और क्यों?",
            "Improvement",
            ["improve", "priority", "reason"],
        ),
        (
            "Describe one realistic edge case or failure scenario related to {evidence}.",
            "{evidence} से जुड़ा एक realistic edge case या failure scenario बताइए।",
            "Technical depth",
            ["edge case", "failure", "testing"],
        ),
        (
            "What did you personally learn from the work represented by {evidence}?",
            "{evidence} से दिखने वाले काम से आपने personally क्या सीखा?",
            "Learning",
            ["learning", "reflection", "growth"],
        ),
        (
            "How would you validate the quality of the result connected to {evidence}?",
            "{evidence} से जुड़े result की quality को आप कैसे validate करेंगे?",
            "Quality",
            ["validate", "quality", "test"],
        ),
    ]
    # Additional interview angles keep the offline path useful even when a
    # resume contains only one short item. They are deliberately different
    # prompts, so a 40-question hard interview still feels like a real panel.
    variant_templates.extend([
        (
            "What assumption did you make while working with {evidence}, and how did you verify it?",
            "{evidence} पर काम करते समय आपने कौन-सी assumption बनाई और उसे कैसे verify किया?",
            "Reasoning",
            ["assumption", "verify", "reasoning"],
        ),
        (
            "How would you prioritize work related to {evidence} when the deadline is shortened?",
            "अगर {evidence} की deadline कम हो जाए तो आप काम को कैसे prioritize करेंगे?",
            "Prioritization",
            ["priority", "deadline", "scope"],
        ),
        (
            "Which metric or signal would you monitor for {evidence} after release?",
            "{evidence} को release करने के बाद आप कौन-सा metric या signal monitor करेंगे?",
            "Monitoring",
            ["metric", "monitoring", "release"],
        ),
        (
            "How would you test a change that affects {evidence} without breaking existing behavior?",
            "{evidence} को प्रभावित करने वाले change को existing behavior तोड़े बिना कैसे test करेंगे?",
            "Testing",
            ["test", "regression", "safety"],
        ),
        (
            "What would you document for another developer who has to maintain {evidence}?",
            "जो developer {evidence} को maintain करेगा उसके लिए आप क्या document करेंगे?",
            "Documentation",
            ["documentation", "maintenance", "handoff"],
        ),
        (
            "Tell me about a time you had to explain a decision related to {evidence} and defend it.",
            "{evidence} से जुड़े decision को समझाकर defend करने का कोई अनुभव बताइए।",
            "Communication",
            ["communication", "decision", "defend"],
        ),
        (
            "If {evidence} suddenly failed in production, what would you do in the first thirty minutes?",
            "अगर production में {evidence} अचानक fail हो जाए तो पहले तीस मिनट में आप क्या करेंगे?",
            "Incident response",
            ["incident", "debug", "recovery"],
        ),
        (
            "What security or privacy risk would you check around {evidence}?",
            "{evidence} से जुड़ा कौन-सा security या privacy risk आप check करेंगे?",
            "Security",
            ["security", "privacy", "risk"],
        ),
        (
            "How would you make the work behind {evidence} more accessible to its users?",
            "{evidence} के पीछे के काम को users के लिए अधिक accessible कैसे बनाएंगे?",
            "User focus",
            ["users", "accessibility", "usability"],
        ),
        (
            "What part of {evidence} would you automate first, and what would you keep manual?",
            "{evidence} में आप सबसे पहले क्या automate करेंगे और क्या manual रखेंगे?",
            "Automation",
            ["automation", "manual", "trade-off"],
        ),
        (
            "How would you estimate the effort for a new requirement involving {evidence}?",
            "{evidence} से जुड़ी नई requirement का effort आप कैसे estimate करेंगे?",
            "Planning",
            ["estimate", "requirement", "planning"],
        ),
        (
            "What would you do if a teammate strongly disagreed with your approach to {evidence}?",
            "अगर teammate {evidence} के आपके approach से strongly disagree करे तो आप क्या करेंगे?",
            "Collaboration",
            ["collaboration", "disagreement", "resolution"],
        ),
        (
            "Which part of {evidence} is hardest to scale, and how would you redesign it?",
            "{evidence} के किस हिस्से को scale करना सबसे कठिन है और आप उसे कैसे redesign करेंगे?",
            "Scalability",
            ["scale", "bottleneck", "redesign"],
        ),
        (
            "How would you compare two possible implementations for {evidence}?",
            "{evidence} की दो possible implementations की तुलना आप कैसे करेंगे?",
            "Architecture",
            ["compare", "architecture", "criteria"],
        ),
        (
            "What feedback did you receive about work related to {evidence}, and what changed afterward?",
            "{evidence} से जुड़े काम पर आपको कौन-सा feedback मिला और उसके बाद क्या बदला?",
            "Feedback",
            ["feedback", "change", "growth"],
        ),
        (
            "How would you reproduce a bug reported against {evidence}?",
            "{evidence} से जुड़े reported bug को आप reproduce कैसे करेंगे?",
            "Debugging",
            ["bug", "reproduce", "debug"],
        ),
        (
            "What data would you collect before making a major change to {evidence}?",
            "{evidence} में बड़ा change करने से पहले आप कौन-सा data collect करेंगे?",
            "Evidence-based decisions",
            ["data", "decision", "impact"],
        ),
        (
            "How would you handle an ambiguous requirement connected to {evidence}?",
            "{evidence} से जुड़ी ambiguous requirement को आप कैसे handle करेंगे?",
            "Ambiguity",
            ["clarify", "requirement", "stakeholder"],
        ),
        (
            "What would a good code review for changes to {evidence} look like?",
            "{evidence} में changes का अच्छा code review कैसा होगा?",
            "Code review",
            ["review", "quality", "maintainability"],
        ),
        (
            "How would you roll back a risky change involving {evidence}?",
            "{evidence} से जुड़े risky change को आप rollback कैसे करेंगे?",
            "Reliability",
            ["rollback", "risk", "reliability"],
        ),
        (
            "What is one limitation of the way {evidence} is currently represented on your resume?",
            "रिज्यूमे में {evidence} को जिस तरह लिखा है उसकी एक limitation क्या है?",
            "Self-awareness",
            ["limitation", "honesty", "reflection"],
        ),
        (
            "If you joined tomorrow, what would you want to learn first about {evidence}?",
            "अगर आप कल join करें तो {evidence} के बारे में सबसे पहले क्या सीखना चाहेंगे?",
            "Learning plan",
            ["learning", "onboarding", "plan"],
        ),
        (
            "How would you present the result of {evidence} to a hiring manager in one minute?",
            "{evidence} के result को hiring manager के सामने एक मिनट में कैसे present करेंगे?",
            "Executive communication",
            ["summary", "impact", "communication"],
        ),
        (
            "What alternative would you choose if the resources for {evidence} were cut in half?",
            "अगर {evidence} के resources आधे हो जाएं तो आप कौन-सा alternative चुनेंगे?",
            "Constraints",
            ["constraints", "alternative", "prioritization"],
        ),
        (
            "How would you transfer your learning from {evidence} to a new project?",
            "{evidence} से मिली learning को नए project में कैसे apply करेंगे?",
            "Transferable skills",
            ["learning", "transfer", "application"],
        ),
        (
            "What result from {evidence} would you be most comfortable defending with numbers?",
            "{evidence} के किस result को आप numbers के साथ सबसे confidently defend करेंगे?",
            "Impact",
            ["numbers", "impact", "evidence"],
        ),
        (
            "How would you decide that the work connected to {evidence} is ready to ship?",
            "आप कैसे तय करेंगे कि {evidence} से जुड़ा काम ship करने के लिए ready है?",
            "Delivery",
            ["ready", "acceptance", "delivery"],
        ),
        (
            "What follow-up question would you ask a stakeholder before changing {evidence}?",
            "{evidence} बदलने से पहले stakeholder से कौन-सा follow-up question पूछेंगे?",
            "Stakeholder management",
            ["stakeholder", "clarify", "question"],
        ),
        (
            "What is the next meaningful milestone you would set for {evidence}?",
            "{evidence} के लिए आप अगला meaningful milestone क्या set करेंगे?",
            "Goals",
            ["milestone", "goal", "planning"],
        ),
    ])
    # Add a fresh interviewer follow-up to each prompt. The shuffled suffixes
    # mean even the 40-question offline format changes wording on every run,
    # instead of merely changing question order.
    follow_up_suffixes = [
        (" Give a specific example and the result.", " एक specific example और result दीजिए।"),
        (" Explain the reasoning, not just the tool name.", " सिर्फ tool का नाम नहीं, reasoning भी समझाइए।"),
        (" Include one trade-off you would discuss.", " एक trade-off भी बताइए जिस पर चर्चा करेंगे।"),
        (" Mention how you would validate the outcome.", " outcome को validate कैसे करेंगे, बताइए।"),
        (" Close with the improvement you would make next.", " अंत में अगला improvement बताइए।"),
        (" Keep the response clear enough for a two-minute answer.", " उत्तर को two-minute explanation जितना clear रखिए।"),
        (" Say what you personally owned.", " बताइए कि आपका personal ownership क्या था।"),
        (" Describe the first step you would take.", " पहला step क्या लेंगे, बताइए।"),
        (" Compare it with one practical alternative.", " एक practical alternative से इसकी तुलना कीजिए।"),
        (" Explain it so a teammate can act on it.", " इसे ऐसे समझाइए कि teammate उस पर action ले सके।"),
        (" Mention the risk you would watch most closely.", " जिस risk को closely watch करेंगे, उसे बताइए।"),
        (" State what evidence would prove success.", " कौन-सा evidence success prove करेगा, बताइए।"),
        (" Describe how you would recover if it failed.", " fail होने पर recover कैसे करेंगे, बताइए।"),
        (" Highlight the constraint you would clarify first.", " पहले कौन-सा constraint clarify करेंगे, बताइए।"),
        (" Include the assumption you would verify.", " कौन-सी assumption verify करेंगे, बताइए।"),
        (" Explain how you would prioritize it under a deadline.", " deadline में इसे prioritize कैसे करेंगे, बताइए।"),
        (" Mention one edge case you would test.", " एक edge case बताइए जिसे test करेंगे।"),
        (" Describe the feedback you would seek.", " किस feedback की जरूरत होगी, बताइए।"),
        (" End with your next learning step.", " अंत में अपना next learning step बताइए।"),
        (" Use a measurable outcome wherever the resume supports one.", " जहाँ resume support करे वहाँ measurable outcome दीजिए।"),
    ]
    secrets.SystemRandom().shuffle(follow_up_suffixes)
    for evidence in evidence_items[:8]:
        short_evidence = evidence[:150]
        for template_index, (english, hindi, category, topics) in enumerate(variant_templates):
            suffix_en, suffix_hi = follow_up_suffixes[template_index % len(follow_up_suffixes)]
            add(
                localized(
                    english.format(evidence=short_evidence) + suffix_en,
                    hindi.format(evidence=short_evidence) + suffix_hi,
                ),
                category,
                "resume-evidence",
                evidence,
                [*topics, short_evidence],
            )

    # Use a cryptographically random order so repeated starts with the same
    # resume do not produce the same fixed sequence.
    secrets.SystemRandom().shuffle(questions)
    result: list[dict[str, Any]] = []
    for question in questions:
        if len(result) >= target_count:
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
        # Keep the API key out of the request URL, where reverse proxies and
        # access logs can accidentally record it.
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"responseMimeType": "application/json"},
        }
        request = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json", "x-goog-api-key": key},
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


def _valid_ai_questions(value: Any, raw_text: str, count: int, language: str = "en") -> list[dict[str, Any]]:
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
        # Gemini can occasionally ignore the requested language. Reject that
        # response so the deterministic Hindi/bilingual fallback is used.
        has_devanagari = bool(re.search(r"[\u0900-\u097F]", question))
        if language == "hi" and not has_devanagari:
            continue
        if language == "bilingual" and ("\n" not in question or not has_devanagari):
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
    language: str = "en",
) -> tuple[list[dict[str, Any]], str]:
    language = language if language in {"en", "hi", "bilingual"} else "en"
    count = max(1, min(int(count), 40))
    fallback = local_questions(profile, role, difficulty, interview_type, count, language)
    if not getattr(settings, "AI_ENABLED", False) or getattr(settings, "AI_PROVIDER", "local") == "local":
        return fallback, "local"

    prompt = f"""
Create a fresh set of exactly {count} {difficulty} {interview_type} interview questions for the role {role}.
Use only the verified resume text below. Never invent a skill, project, employer,
technology, qualification, or experience. Every question must cite an exact
source_evidence phrase copied from the resume. Return JSON with a questions array;
each item must contain question, category, source, source_evidence, expected_topics.
LANGUAGE: {language}. For hi, write the question in natural Hindi using Devanagari
while keeping technical terms in English. For bilingual, put the English question
first and the Hindi translation on the next line. For en, write only English.
Interview order should feel real: warm-up, resume verification, project/skill
deep-dive, problem solving, behavioral follow-ups, and a closing question. Every
question must use a different angle; do not repeat a previous question or merely
change one word. This run variation token is {secrets.token_hex(6)}.

RESUME TEXT:
{raw_text[:20000]}
""".strip()
    try:
        questions = _valid_ai_questions(_provider_json(prompt), raw_text, count, language)
        if questions:
            # A free model may return fewer items than requested. Fill the rest
            # with fresh, resume-grounded local questions instead of silently
            # shrinking the interview.
            combined: list[dict[str, Any]] = []
            seen: set[str] = set()
            for item in [*questions, *fallback]:
                key = item["question"].casefold()
                if key not in seen:
                    seen.add(key)
                    combined.append(item)
                if len(combined) >= count:
                    break
            if len(combined) >= count:
                return combined, "ai"
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


def _local_professional_answer(question: dict[str, Any], role: str) -> dict[str, str]:
    """Create a truthful, interview-ready answer without an external API."""

    evidence = str(question.get("source_evidence", "")).strip() or role or "my resume"
    evidence = evidence[:180]
    category = str(question.get("category", question.get("type", "General"))).strip()
    topics = [str(item).strip() for item in question.get("expected_topics", []) if str(item).strip()]
    topic_text = ", ".join(_unique(topics)[:4]) or "context, contribution, result, and learning"
    focus = re.sub(r"\s+", " ", str(question.get("question", "")).splitlines()[0]).strip()[:140]
    focus = focus or f"the {category.casefold() or 'interview'} discussion"
    fresh_en, fresh_hi = secrets.choice(
        [
            ("I would keep the explanation evidence-led and concise.", "मैं explanation को evidence-led और concise रखूंगा।"),
            ("I would lead with the decision and then support it with the example.", "मैं पहले decision बताऊंगा और फिर उसे example से support करूंगा।"),
            ("I would make the outcome clear before adding implementation detail.", "मैं implementation detail से पहले outcome को clear करूंगा।"),
            ("I would be precise about what I personally did and what I learned.", "मैं अपने personal work और learning को precisely बताऊंगा।"),
        ]
    )

    if "behavior" in category.casefold() or "experience" in category.casefold():
        english = (
            f"I would answer this with a STAR example from {evidence}. I would briefly explain the situation and the goal, "
            f"then separate my personal responsibility from the team's work. My actions would cover {topic_text}; I would explain "
            "the decision I made, how I handled the constraint, and how I collaborated. I would finish with the verified result, "
            f"what I learned, and what I would do better next time. The specific point I would address here is: {focus}. {fresh_en} "
            "I would use the exact metric from my project rather than guessing."
        )
        hindi = (
            f"मैं इस प्रश्न का उत्तर {evidence} से जुड़े STAR example से दूंगा। पहले situation और goal बताऊंगा, फिर team के काम से "
            f"अपना personal contribution अलग करूंगा। मेरा action {topic_text} पर focus करेगा; मैं अपने decision, constraint और collaboration "
            f"को स्पष्ट करूंगा। इस प्रश्न का specific focus “{focus}” रहेगा। {fresh_hi} अंत में verified result, मिली learning और अगली बार का "
            "improvement बताऊंगा। Resume में उपलब्ध न होने वाला कोई metric मैं guess नहीं करूंगा।"
        )
    elif "project" in category.casefold() or "technical" in category.casefold() or "skill" in category.casefold():
        english = (
            f"I would ground my answer in the resume evidence {evidence}. I would start with the problem and the success criteria, "
            f"then explain how I applied the relevant ideas—{topic_text}—and what part I personally owned. I would mention the main "
            f"trade-off, the tests or checks used to validate the work, and the result that is actually supported by my resume. The key "
            f"point for this question is {focus}. {fresh_en} I would close with one lesson and a concrete improvement I would make in "
            "the next iteration."
        )
        hindi = (
            f"मैं अपने उत्तर को रिज्यूमे के evidence {evidence} से जोड़ूंगा। पहले problem और success criteria बताऊंगा, फिर समझाऊंगा कि "
            f"मैंने {topic_text} जैसे relevant ideas को कैसे apply किया और मेरा personal ownership क्या था। Main trade-off, work को validate "
            f"करने के tests/checks और resume से supported result बताऊंगा। इस प्रश्न का key point “{focus}” है। {fresh_hi} अंत में एक learning "
            "और next iteration का concrete improvement साझा करूंगा।"
        )
    else:
        english = (
            f"A strong answer should connect this question to {evidence}. I would give the context first, explain my responsibility and "
            f"the reasoning behind my approach, and cover {topic_text}. I would support the explanation with one specific example, state "
            f"the verified outcome, and acknowledge any detail that is not recorded on my resume. The part I would answer most directly is "
            f"{focus}. {fresh_en} I would finish with the lesson and the next step I would take in a real workplace."
        )
        hindi = (
            f"एक strong answer इस प्रश्न को {evidence} से जोड़ेगा। मैं पहले context, अपनी responsibility और approach के पीछे का reasoning "
            f"बताऊंगा और {topic_text} को cover करूंगा। एक specific example और verified outcome दूंगा; जो detail resume में नहीं है उसे साफ़ "
            f"बताऊंगा, invent नहीं करूंगा। इस प्रश्न में मैं “{focus}” को directly address करूंगा। {fresh_hi} अंत में मिली learning और real "
            "workplace में लिया जाने वाला next step बताऊंगा।"
        )
    return {"answer_en": english, "answer_hi": hindi}


def _valid_professional_answers(value: Any, questions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Validate a provider answer key and align it to the session order."""

    if isinstance(value, dict):
        value = value.get("answers", [])
    if not isinstance(value, list):
        return []
    by_order = {}
    for index, question in enumerate(questions, start=1):
        try:
            order = int(question.get("order", index))
        except (TypeError, ValueError):
            order = index
        by_order[order] = question

    valid: dict[int, dict[str, Any]] = {}
    seen_answers: set[str] = set()
    for item in value:
        if not isinstance(item, dict):
            continue
        try:
            order = int(item.get("order"))
        except (TypeError, ValueError):
            continue
        question = by_order.get(order)
        if question is None:
            continue
        english = str(item.get("answer_en", item.get("english", item.get("answer_english", "")))).strip()
        hindi = str(item.get("answer_hi", item.get("hindi", item.get("answer_hindi", "")))).strip()
        if len(english) < 40 or len(hindi) < 30 or not re.search(r"[\u0900-\u097F]", hindi):
            continue
        answer_key = english.casefold()
        if answer_key in seen_answers:
            continue
        seen_answers.add(answer_key)
        valid[order] = {
            "order": order,
            "question": str(question.get("question", ""))[:2000],
            "category": str(question.get("category", question.get("type", "General")))[:80],
            "source_evidence": str(question.get("source_evidence", ""))[:255],
            "answer_en": english[:5000],
            "answer_hi": hindi[:5000],
            "generated_by": "ai",
        }
    return [valid[order] for order in sorted(valid) if order in valid]


def generate_professional_answers(
    questions: list[dict[str, Any]],
    profile: dict[str, Any],
    raw_text: str,
    role: str,
    difficulty: str = "medium",
) -> tuple[list[dict[str, Any]], str]:
    """Generate a bilingual answer key for every question in one interview."""

    local_answers: list[dict[str, Any]] = []
    for index, question in enumerate(questions, start=1):
        item = dict(question)
        item["order"] = question.get("order", index)
        local = _local_professional_answer(item, role)
        local_answers.append(
            {
                "order": int(item["order"]),
                "question": str(item.get("question", ""))[:2000],
                "category": str(item.get("category", item.get("type", "General")))[:80],
                "source_evidence": str(item.get("source_evidence", ""))[:255],
                **local,
                "generated_by": "local",
            }
        )

    if not questions or not getattr(settings, "AI_ENABLED", False) or getattr(settings, "AI_PROVIDER", "local") == "local":
        return local_answers, "local"

    question_payload = [
        {
            "order": int(item.get("order", index)),
            "question": str(item.get("question", ""))[:1200],
            "category": str(item.get("category", item.get("type", "General")))[:80],
            "source_evidence": str(item.get("source_evidence", ""))[:255],
        }
        for index, item in enumerate(questions, start=1)
    ]
    prompt = f"""
Create one professional model answer for EVERY interview question below for a {role} candidate.
Return JSON with an answers array. Each item must contain order, answer_en, and answer_hi.
answer_en must be a natural 80-150 word English sample answer. answer_hi must be a natural
Hindi translation in Devanagari, keeping technical terms in English. Use first person only
for facts explicitly supported by the resume. Never invent a tool, employer, qualification,
responsibility, metric, or result. If a contribution or number is missing, explain what the
candidate should verify or say instead of guessing. Each answer must directly address its
question, use its source_evidence, and have a different structure from the other answers.
These are model answers for practice, not hiring decisions. Variation token: {secrets.token_hex(8)}

QUESTIONS JSON:
{json.dumps(question_payload, ensure_ascii=False)}

PROFILE JSON:
{json.dumps(profile, ensure_ascii=False)[:9000]}

RESUME TEXT:
{raw_text[:16000]}
""".strip()
    try:
        ai_answers = _valid_professional_answers(_provider_json(prompt), question_payload)
        ai_by_order = {int(item["order"]): item for item in ai_answers}
        combined: list[dict[str, Any]] = []
        for local in local_answers:
            replacement = ai_by_order.get(int(local["order"]))
            combined.append(replacement or local)
        if ai_answers:
            return combined, "ai+local" if len(ai_answers) < len(questions) else "ai"
    except Exception:
        pass
    return local_answers, "local-fallback"
