"""
Query Builder: Turns extracted CV data into search queries.
Uses synonyms and skill-based expansion.
"""

from typing import Any, Dict, List

from ajas.logger import log


def build_queries_from_master(master_data: Dict[str, Any]) -> List[str]:
    """
    Builds a list of search queries from Master CV data (skills + target_roles).
    """
    queries = []

    # 1. Target Roles from Preferences
    prefs = master_data.get("preferences", {})
    target_roles = prefs.get("target_roles", [])

    # 2. Key Skills
    skills = master_data.get("skills", [])
    top_skills = skills[:5] if skills else []

    # 3. Combine Roles + Skills (Basic expansions)
    # Simple strategy: Each role, plus each role + a key skill
    for role in target_roles:
        queries.append(role)
        # Expansion e.g. "Software Engineer Python"
        for skill in top_skills[:3]:
            # Keep it simple: "Role Skill"
            queries.append(f"{role} {skill}")

    # Add just top skills as queries too
    for skill in top_skills[:3]:
        queries.append(skill)
        queries.append(f"{skill} Developer")
    # De-duplicate
    final_queries = sorted(list(set(queries)))

    log.info(f"Built {len(final_queries)} queries from Master CV: {final_queries}")
    return final_queries
