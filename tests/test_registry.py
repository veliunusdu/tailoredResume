from app.registry import SourceRegistry

def test_registry_get_source():
    src = SourceRegistry.get_source("weworkremotely")
    assert src is not None
    assert src["name"] == "We Work Remotely"

def test_registry_get_route():
    assert SourceRegistry.get_route("weworkremotely", has_stable_access=True) == "direct"
    assert SourceRegistry.get_route("wellfound", has_stable_access=False) == "google_fallback"
    assert SourceRegistry.get_route("unknown_site") == "jobspy"
