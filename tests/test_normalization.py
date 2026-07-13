from app.filters import _normalize

def test_normalize_weworkremotely():
    job = {
        "source_type": "other",
        "title": "Backend Dev",
        "company": "TestCorp",
        "url": "http://example.com/job",
        "site": "We Work Remotely",
        "salary": "$100k",
    }
    norm = _normalize(job)
    assert norm["url"] == "http://example.com/job"
    assert norm["salary"] == "$100k"
    assert norm["site"] == "We Work Remotely"

def test_normalize_jobspy():
    job = {
        "source_type": "jobspy",
        "title": "Frontend Dev",
        "company": "JobSpyCorp",
        "job_url": "http://example.com/jobspy",
        "salary_source": "$120k",
        "site": "indeed"
    }
    norm = _normalize(job)
    assert norm["url"] == "http://example.com/jobspy"
    assert norm["salary"] == "$120k"
    assert norm["site"] == "Indeed"
