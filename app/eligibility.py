import re
from typing import Literal

EligibilityResult = Literal["eligible", "probably_eligible", "eligibility_unknown", "ineligible"]

def check_eligibility(job_desc: str, user_config: dict) -> EligibilityResult:
    """
    Run fast, deterministic rule-based checks before passing a job to the LLM.
    Returns the eligibility status.
    """
    if not job_desc:
        return "eligibility_unknown"
        
    desc_lower = job_desc.lower()
    
    requires_sponsorship = user_config.get("requires_sponsorship") or user_config.get("visa_sponsorship")
    remote_only = user_config.get("remote_only")
    target_countries = [c.lower() for c in user_config.get("target_countries", [])]
    
    # 1. Visa & Sponsorship Checks
    if requires_sponsorship:
        ineligible_patterns = [
            r"no (visa )?sponsorship",
            r"cannot (provide|offer) sponsorship",
            r"will not sponsor",
            r"must be (a )?(us|u\.s\.) citizen",
            r"us citizen(ship)? (is )?required",
            r"green card (holder )?required",
            r"authorized to work in the (us|u\.s\.) without sponsorship",
            r"w2 only",
            r"no c2c",
            r"security clearance"
        ]
        for pattern in ineligible_patterns:
            if re.search(pattern, desc_lower):
                return "ineligible"
                
    # 2. Remote Checks
    if remote_only:
        # If they want remote but job says "must reside in", it's tricky. 
        # But let's check for explicit non-remote markers if they scraped a "remote" search but it's fake.
        if "hybrid" in desc_lower and "remote" not in desc_lower:
            return "ineligible"
        if "on-site" in desc_lower or "onsite" in desc_lower:
            # Lots of remote jobs say "onsite occasionally". Be careful with this.
            pass
            
    # 3. Target Country Checks
    if "united states" in target_countries or "us" in target_countries:
        if requires_sponsorship:
            if "sponsorship available" in desc_lower or "will sponsor" in desc_lower:
                return "eligible"
            return "eligibility_unknown"
            
    return "probably_eligible"
