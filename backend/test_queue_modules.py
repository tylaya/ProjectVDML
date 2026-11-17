import json
import unittest
from datetime import date

from pydantic import ValidationError

from ml.queue_modules import (
    _forecast_demand,
    _run_day,
    _segment_and_triage,
    run_synthetic_week,
)
from schemas import QueueSimulationRequest


class QueueModuleTests(unittest.TestCase):
    def test_spt_reduces_wait_for_short_jobs_but_can_increase_longest_wait(self):
        jobs = [
            {
                "id": f"DEMO-{index}",
                "arrival": 0,
                "attended": True,
                "predicted_duration": duration,
                "actual_duration": duration,
                "category": "Outsider Dekat",
            }
            for index, duration in enumerate((12, 2, 2))
        ]

        fifo, _ = _run_day(jobs, counters=1, policy="fifo")
        spt, _ = _run_day(jobs, counters=1, policy="spt")

        self.assertLess(spt["mean_wait_minutes"], fifo["mean_wait_minutes"])
        self.assertGreater(spt["max_wait_minutes"], 0)

    def test_triage_marks_incomplete_and_boundary_cases_for_review(self):
        jobs = [
            {
                "id": "DEMO-INCOMPLETE",
                "distance_km": 1.0,
                "category": "Outsider Dekat",
                "docs_complete": 0,
                "needs_review": 0,
            },
            {
                "id": "DEMO-BOUNDARY",
                "distance_km": 2.05,
                "category": "Outsider Jauh",
                "docs_complete": 1,
                "needs_review": 0,
            },
            {
                "id": "DEMO-STANDARD",
                "distance_km": 4.0,
                "category": "Outsider Jauh",
                "docs_complete": 1,
                "needs_review": 0,
            },
        ]

        segments, recommendations, _ = _segment_and_triage(
            jobs, threshold_km=2.0, review_zone_km=0.2
        )

        self.assertEqual(segments["Perlu melengkapi checklist"], 1)
        self.assertEqual(segments["Review petugas"], 1)
        self.assertEqual(segments["Layanan standar"], 1)
        self.assertEqual(recommendations["Perlu tinjauan petugas"], 2)

    def test_demand_forecast_is_seeded_and_scales_to_demo_volume(self):
        first = _forecast_demand(seed=42, applicants_per_day=80)
        repeated = _forecast_demand(seed=42, applicants_per_day=80)

        self.assertEqual(first, repeated)
        forecast, metrics = first
        self.assertEqual(len(forecast), 5)
        self.assertGreater(sum(day["expected_applicants"] for day in forecast), 300)
        self.assertGreater(metrics["daily_mae"], 0)

    def test_simulation_window_must_start_on_monday(self):
        request = QueueSimulationRequest(start_date=date(2026, 11, 23))
        self.assertEqual(request.start_date.weekday(), 0)

        with self.assertRaises(ValidationError):
            QueueSimulationRequest(start_date=date(2026, 11, 24))

    def test_api_payload_contains_json_compatible_values_for_all_modules(self):
        result = run_synthetic_week(
            start_date=date(2026, 11, 23),
            service_counters=1,
            applicants_per_day=5,
            seed=15,
        )

        payload = json.loads(json.dumps(result, allow_nan=False))
        self.assertEqual(set(payload["modules"]), {f"M{index}" for index in range(1, 9)})


if __name__ == "__main__":
    unittest.main()
