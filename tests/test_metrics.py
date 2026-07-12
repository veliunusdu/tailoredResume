from app.metrics import MetricsCollector

def test_metrics_collector():
    collector = MetricsCollector("test_user")
    collector.add_raw("weworkremotely", 5)
    collector.add_raw("linkedin", 10)
    collector.add_filtered("weworkremotely", 2)
    collector.add_inserted("weworkremotely", 1)
    
    assert collector.raw_counts["weworkremotely"] == 5
    assert collector.raw_counts["linkedin"] == 10
    assert collector.filtered_counts["weworkremotely"] == 2
    assert collector.inserted_counts["weworkremotely"] == 1
