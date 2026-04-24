import re

from ajas.logger import log


class HallucinationError(Exception):
    """Raised when the LLM invents data not in the source."""

    pass


_SKILL_STOPWORDS = {
    "and",
    "the",
    "of",
    "with",
    "for",
    "to",
    "in",
    "on",
    "using",
    "experience",
    "knowledge",
    "skills",
    "skill",
    "pipeline",
    "pipelines",
}


def _normalize_text(value: str) -> str:
    normalized = str(value).strip().lower()
    normalized = normalized.replace("&", " and ")
    normalized = normalized.replace("/", " ")
    normalized = normalized.replace("-", " ")
    normalized = re.sub(r"[^a-z0-9\s]", " ", normalized)
    normalized = re.sub(r"\s+", " ", normalized).strip()
    return normalized


def _stem_token(token: str) -> str:
    if token.endswith("ies") and len(token) > 4:
        return token[:-3] + "y"
    for suffix in ("ing", "ers", "er", "ed", "es", "s"):
        if token.endswith(suffix) and len(token) > len(suffix) + 2:
            return token[: -len(suffix)]
    return token


def _tokenize_skill(value: str) -> set[str]:
    normalized = _normalize_text(value)
    if not normalized:
        return set()
    tokens = {
        _stem_token(token)
        for token in normalized.split()
        if token and token not in _SKILL_STOPWORDS
    }
    return {token for token in tokens if token}


def extract_master_constraints(master_cv: dict) -> dict[str, list[str]]:
    skills: list[str] = []
    seen_skills: set[str] = set()

    for skill in master_cv.get("skills", []):
        text = str(skill).strip()
        normalized = _normalize_text(text)
        if text and normalized and normalized not in seen_skills:
            seen_skills.add(normalized)
            skills.append(text)

    for exp in master_cv.get("experience", []):
        for bullet in exp.get("bullets", []):
            for keyword in bullet.get("keywords", []):
                text = str(keyword).strip()
                normalized = _normalize_text(text)
                if text and normalized and normalized not in seen_skills:
                    seen_skills.add(normalized)
                    skills.append(text)

    companies: list[str] = []
    seen_companies: set[str] = set()
    for exp in master_cv.get("experience", []):
        company = str(exp.get("company", "")).strip()
        normalized = _normalize_text(company)
        if company and normalized and normalized not in seen_companies:
            seen_companies.add(normalized)
            companies.append(company)

    return {"skills": skills, "companies": companies}


def _is_skill_allowed(
    skill: str,
    allowed_skill_norms: set[str],
    allowed_skill_tokens: list[set[str]],
) -> bool:
    normalized = _normalize_text(skill)
    if not normalized:
        return False
    if normalized in allowed_skill_norms:
        return True

    skill_tokens = _tokenize_skill(skill)
    if not skill_tokens:
        return False

    for master_tokens in allowed_skill_tokens:
        if not master_tokens:
            continue
        if master_tokens.issubset(skill_tokens) or skill_tokens.issubset(master_tokens):
            return True
    return False


def enforce_master_constraints(tailored_cv: dict, master_cv: dict) -> dict:
    constraints = extract_master_constraints(master_cv)

    allowed_norm_to_skill = {
        _normalize_text(skill): skill
        for skill in constraints["skills"]
        if _normalize_text(skill)
    }
    allowed_skill_norms = set(allowed_norm_to_skill.keys())
    allowed_skill_token_pairs = [
        (_tokenize_skill(skill), skill)
        for skill in constraints["skills"]
        if _tokenize_skill(skill)
    ]

    constrained = dict(tailored_cv)

    cleaned_skills: list[str] = []
    seen_cleaned_skills: set[str] = set()
    for skill in tailored_cv.get("skills", []):
        if not isinstance(skill, str):
            continue

        normalized = _normalize_text(skill)
        canonical_skill: str | None = None

        if normalized in allowed_norm_to_skill:
            canonical_skill = allowed_norm_to_skill[normalized]
        else:
            skill_tokens = _tokenize_skill(skill)
            for master_tokens, master_skill in allowed_skill_token_pairs:
                if master_tokens.issubset(skill_tokens) or skill_tokens.issubset(
                    master_tokens
                ):
                    canonical_skill = master_skill
                    break

        if canonical_skill:
            canonical_norm = _normalize_text(canonical_skill)
            if canonical_norm not in seen_cleaned_skills:
                seen_cleaned_skills.add(canonical_norm)
                cleaned_skills.append(canonical_skill)

    if not cleaned_skills:
        cleaned_skills = constraints["skills"][:5]
    constrained["skills"] = cleaned_skills

    allowed_company_norm_to_name = {
        _normalize_text(name): name
        for name in constraints["companies"]
        if _normalize_text(name)
    }
    cleaned_experience = []
    for exp in tailored_cv.get("experience", []):
        if not isinstance(exp, dict):
            continue
        company = str(exp.get("company", "")).strip()
        normalized_company = _normalize_text(company)
        if normalized_company in allowed_company_norm_to_name:
            updated_exp = dict(exp)
            updated_exp["company"] = allowed_company_norm_to_name[normalized_company]
            cleaned_experience.append(updated_exp)

    constrained["experience"] = cleaned_experience
    return constrained


def validate_no_hallucinations(tailored_cv: dict, master_cv: dict):
    """
    Compare tailored CV against master CV to detect hallucinations.
    Checks skills and companies.
    """
    constraints = extract_master_constraints(master_cv)
    allowed_skill_norms = {
        _normalize_text(skill)
        for skill in constraints["skills"]
        if _normalize_text(skill)
    }
    allowed_skill_tokens = [
        _tokenize_skill(skill)
        for skill in constraints["skills"]
        if _tokenize_skill(skill)
    ]

    invented_skills = {
        _normalize_text(skill) or str(skill).strip().lower()
        for skill in tailored_cv.get("skills", [])
        if isinstance(skill, str)
        and not _is_skill_allowed(skill, allowed_skill_norms, allowed_skill_tokens)
    }
    invented_skills.discard("")
    if invented_skills:
        log.warning(f"Hallucination detected in skills: {invented_skills}")
        raise HallucinationError(f"LLM invented skills: {invented_skills}")

    allowed_company_norms = {
        _normalize_text(name)
        for name in constraints["companies"]
        if _normalize_text(name)
    }
    invented_companies = {
        _normalize_text(exp.get("company", ""))
        for exp in tailored_cv.get("experience", [])
        if isinstance(exp, dict)
        and _normalize_text(exp.get("company", "")) not in allowed_company_norms
    }
    invented_companies.discard("")
    if invented_companies:
        log.warning(f"Hallucination detected in companies: {invented_companies}")
        raise HallucinationError(f"LLM invented companies: {invented_companies}")

    return True
