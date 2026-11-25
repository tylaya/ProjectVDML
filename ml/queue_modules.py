"""Synthetic, offline demonstrations for the queue-planning ML modules."""

from __future__ import annotations

import math
import random
from collections import defaultdict
from datetime import date, timedelta
from functools import lru_cache
from statistics import median
from typing import Any

import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest, RandomForestRegressor
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import mean_absolute_error, precision_score, recall_score
from sklearn.model_selection import train_test_split
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler


OPEN_MINUTES = 8 * 60
CLOSE_MINUTES = 17 * 60
SERVICE_MINUTES_PER_DAY = CLOSE_MINUTES - OPEN_MINUTES
SERVICE_DAYS = 5
WEEKDAYS = ("Senin", "Selasa", "Rabu", "Kamis", "Jumat")
DOCUMENT_NAMES = ("Surat keterangan domisili (contoh)", "Dokumen pendukung (contoh)")
SERVICE_FEATURES = (
    "is_renewal",
    "distance_km",
    "documents_complete",
    "supporting_review",
)
NO_SHOW_FEATURES = (
    "days_ahead",
    "hour",
    "previous_no_show",
    "is_renewal",
)


def _service_sample(rng: random.Random) -> dict[str, Any]:
    is_renewal = rng.randint(0, 1)
    distance_km = rng.uniform(0.3, 10.0)
    documents_complete = rng.randint(0, 1)
    supporting_review = rng.randint(0, 1)
    duration = _service_duration(
        is_renewal, distance_km, documents_complete, supporting_review, rng
    )
    return {
        "is_renewal": is_renewal,
        "distance_km": distance_km,
        "documents_complete": documents_complete,
        "supporting_review": supporting_review,
        "duration_minutes": max(3.0, duration),
    }


def _service_duration(
    is_renewal: int,
    distance_km: float,
    documents_complete: int,
    supporting_review: int,
    rng: random.Random,
) -> float:
    return max(
        3.0,
        6.0
        + 2.2 * is_renewal
        + 1.8 * (1 - documents_complete)
        + 3.0 * supporting_review
        + min(distance_km, 8.0) * 0.35
        + rng.gauss(0, 1.6),
    )


def _no_show_probability(row: dict[str, Any]) -> float:
    score = (
        -3.2
        + 0.19 * row["days_ahead"]
        + 0.65 * row["previous_no_show"]
        + 0.22 * row["is_renewal"]
        + (0.25 if row["hour"] < 9 or row["hour"] >= 16 else 0)
    )
    return 1.0 / (1.0 + math.exp(-score))


def _no_show_sample(rng: random.Random) -> dict[str, int]:
    row = {
        "days_ahead": rng.randint(0, 14),
        "hour": rng.randint(8, 16),
        "previous_no_show": int(rng.random() < 0.08),
        "is_renewal": rng.randint(0, 1),
    }
    return {**row, "no_show": int(rng.random() < _no_show_probability(row))}


@lru_cache(maxsize=16)
def _train_duration_model(seed: int) -> tuple[RandomForestRegressor, dict[str, float]]:
    rng = random.Random(seed + 101)
    samples = [_service_sample(rng) for _ in range(1200)]
    frame = pd.DataFrame(samples)
    features = frame[list(SERVICE_FEATURES)]
    target = frame["duration_minutes"]
    x_train, x_test, y_train, y_test = train_test_split(
        features, target, test_size=0.25, random_state=seed, shuffle=True
    )
    model = RandomForestRegressor(
        n_estimators=60, min_samples_leaf=3, random_state=seed, n_jobs=1
    )
    model.fit(x_train, y_train)
    prediction = model.predict(x_test)
    baseline = np.full(len(y_test), float(y_train.median()))
    return model, {
        "mae_minutes": round(float(mean_absolute_error(y_test, prediction)), 2),
        "baseline_mae_minutes": round(
            float(mean_absolute_error(y_test, baseline)), 2
        ),
    }


@lru_cache(maxsize=16)
def _train_no_show_model(seed: int) -> tuple[Any, dict[str, float]]:
    rng = random.Random(seed + 202)
    samples = [_no_show_sample(rng) for _ in range(1600)]
    frame = pd.DataFrame(samples)
    x_train, x_test, y_train, y_test = train_test_split(
        frame[list(NO_SHOW_FEATURES)],
        frame["no_show"],
        test_size=0.25,
        random_state=seed,
        stratify=frame["no_show"],
    )
    model = make_pipeline(StandardScaler(), LogisticRegression(max_iter=500, random_state=seed))
    model.fit(x_train, y_train)
    predicted = model.predict(x_test)
    probabilities = model.predict_proba(x_test)[:, 1]
    return model, {
        "precision": round(float(precision_score(y_test, predicted, zero_division=0)), 3),
        "recall": round(float(recall_score(y_test, predicted, zero_division=0)), 3),
        "brier_score": round(float(np.mean((probabilities - y_test.to_numpy()) ** 2)), 3),
    }


def _arrival_minute(rng: random.Random) -> int:
    return min(
        SERVICE_MINUTES_PER_DAY - 1,
        max(0, int(rng.triangular(0, SERVICE_MINUTES_PER_DAY - 1, 210))),
    )


def _forecast_demand(
    seed: int, applicants_per_day: int
) -> tuple[list[dict[str, Any]], dict[str, float]]:
    rng = random.Random(seed + 303)
    weekly_counts: dict[int, list[int]] = defaultdict(list)
    weekly_hours: dict[int, list[int]] = defaultdict(list)
    for week_index in range(5):
        for day_index in range(SERVICE_DAYS):
            daily_total = max(
                5, int(rng.gauss(applicants_per_day, max(2, applicants_per_day * 0.2)))
            )
            weekly_counts[day_index].append(daily_total)
            hour_counts = [0] * 9
            for _ in range(daily_total):
                hour_counts[min(8, _arrival_minute(rng) // 60)] += 1
            for hour_index, count in enumerate(hour_counts):
                weekly_hours[day_index * 9 + hour_index].append(count)

    forecast = []
    daily_errors = []
    hourly_errors = []
    for day_index, name in enumerate(WEEKDAYS):
        hourly = [
            round(sum(weekly_hours[day_index * 9 + hour][:4]) / 4, 1)
            for hour in range(9)
        ]
        daily_expected = round(sum(weekly_counts[day_index][:4]) / 4, 1)
        daily_errors.append(
            abs(daily_expected - weekly_counts[day_index][4])
        )
        hourly_errors.extend(
            abs(
                hourly[hour]
                - weekly_hours[day_index * 9 + hour][4]
            )
            for hour in range(9)
        )
        forecast.append(
            {
                "weekday": name,
                "expected_applicants": daily_expected,
                "peak_hour": f"{8 + hourly.index(max(hourly)):02d}:00",
                "hourly_counts": hourly,
            }
        )
    return forecast, {
        "daily_mae": round(sum(daily_errors) / len(daily_errors), 2),
        "hourly_mae": round(sum(hourly_errors) / len(hourly_errors), 2),
    }


def _encode_minute(day_offset: int, minute: int) -> int:
    return day_offset * SERVICE_MINUTES_PER_DAY + minute


def _format_minutes(value: float) -> str:
    day, minute_of_day = divmod(int(value), SERVICE_MINUTES_PER_DAY)
    hour, minute = divmod(OPEN_MINUTES + minute_of_day, 60)
    return f"{WEEKDAYS[min(day, SERVICE_DAYS - 1)]} {hour:02d}:{minute:02d}"


def _q_state(queue: list[dict[str, Any]], now: int) -> tuple[int, int, int]:
    size_bucket = min(3, len(queue) // 3)
    oldest_wait = max((now - job["arrival"] for job in queue), default=0)
    wait_bucket = min(3, oldest_wait // 15)
    hour_bucket = min(2, (now % SERVICE_MINUTES_PER_DAY) // 180)
    return size_bucket, wait_bucket, hour_bucket


def _run_day(
    day_jobs: list[dict[str, Any]],
    counters: int,
    policy: str,
    q_table: dict[tuple[int, int, int], list[float]] | None = None,
    epsilon: float = 0.0,
    rng: random.Random | None = None,
    collect_transitions: bool = False,
) -> tuple[dict[str, Any], list[tuple[Any, int, float, Any]]]:
    rng = rng or random.Random(0)
    jobs = sorted(day_jobs, key=lambda job: job["arrival"])
    no_shows = sum(not job["attended"] for job in jobs)
    queue: list[dict[str, Any]] = []
    server_free = [0] * counters
    results: list[dict[str, Any]] = []
    transitions: list[tuple[Any, int, float, Any]] = []
    cursor = 0
    now = 0
    max_queue = 0

    while cursor < len(jobs) or queue:
        if not queue and cursor < len(jobs):
            now = max(now, jobs[cursor]["arrival"])
        while cursor < len(jobs) and jobs[cursor]["arrival"] <= now:
            if jobs[cursor]["attended"]:
                queue.append(jobs[cursor])
            cursor += 1
        max_queue = max(max_queue, len(queue))

        idle_servers = [index for index, free_at in enumerate(server_free) if free_at <= now]
        while idle_servers and queue:
            state = _q_state(queue, now)
            action = 0
            if policy == "spt":
                action = 1
            elif policy == "rl" and q_table is not None:
                values = q_table.get(state, [0.0, 0.0])
                if rng.random() < epsilon:
                    action = rng.randrange(2)
                else:
                    action = int(values[1] > values[0])

            if action == 1:
                selected = min(queue, key=lambda job: (job["predicted_duration"], job["arrival"]))
            else:
                selected = min(queue, key=lambda job: job["arrival"])
            queue.remove(selected)
            start = now
            wait = start - selected["arrival"]
            duration = selected["actual_duration"]
            server_free[idle_servers.pop(0)] = start + duration
            results.append({**selected, "start": start, "wait": wait, "duration": duration})

            next_state = _q_state(queue, start + duration)
            remaining_wait = sum(start + duration - job["arrival"] for job in queue)
            fairness_penalty = max(
                0, max((start + duration - job["arrival"] for job in queue), default=0) - 30
            )
            reward = -(remaining_wait + 0.25 * fairness_penalty + 0.05 * duration)
            if collect_transitions:
                transitions.append((state, action, reward, next_state))

        if cursor < len(jobs) and (not queue or min(server_free) > now):
            next_arrival = jobs[cursor]["arrival"]
            next_free = min(server_free)
            now = min(next_arrival, next_free) if next_free > now else next_arrival
        elif queue and not any(free_at <= now for free_at in server_free):
            now = min(server_free)
        elif cursor >= len(jobs) and not queue:
            break
        elif not queue and cursor >= len(jobs):
            break

    waits = [row["wait"] for row in results]
    waits_sorted = sorted(waits)
    p90_wait = waits_sorted[min(len(waits_sorted) - 1, int(0.9 * len(waits_sorted)))] if waits_sorted else 0
    category_waits: dict[str, list[int]] = defaultdict(list)
    for row in results:
        category_waits[row["category"]].append(row["wait"])
    category_averages = {
        category: round(sum(values) / len(values), 1)
        for category, values in category_waits.items()
        if values
    }
    summary = {
        "served": len(results),
        "no_shows": no_shows,
        "mean_wait_minutes": round(sum(waits) / len(waits), 1) if waits else 0.0,
        "p90_wait_minutes": int(p90_wait),
        "max_wait_minutes": max(waits, default=0),
        "max_queue": max_queue,
        "overtime_minutes": max(0, max(server_free, default=0) - SERVICE_MINUTES_PER_DAY),
        "category_mean_wait_minutes": category_averages,
        "wait_gap_minutes": round(
            max(category_averages.values()) - min(category_averages.values()), 1
        ) if len(category_averages) > 1 else 0.0,
    }
    return summary, transitions


@lru_cache(maxsize=16)
def _train_q_policy(
    seed: int, counters: int, applicants_per_day: int
) -> dict[tuple[int, int, int], list[float]]:
    table: dict[tuple[int, int, int], list[float]] = defaultdict(lambda: [0.0, 0.0])
    rng = random.Random(seed + 404)
    for episode in range(24):
        jobs = _generate_jobs(
            start_date=date(2025, 1, 6),
            applicants_per_day=applicants_per_day,
            seed=seed + 500 + episode,
            duration_model=None,
            no_show_model=None,
            training_episode=True,
        )
        episode_transitions = []
        for day_index in range(SERVICE_DAYS):
            _, transitions = _run_day(
                [job for job in jobs if job["day_index"] == day_index],
                counters,
                "rl",
                q_table=table,
                epsilon=max(0.08, 0.65 * (1 - episode / 24)),
                rng=rng,
                collect_transitions=True,
            )
            episode_transitions.extend(transitions)
        for state, action, reward, next_state in episode_transitions:
            values = table[state]
            next_values = table[next_state]
            values[action] += 0.18 * (
                reward + 0.75 * max(next_values) - values[action]
            )
    return dict(table)


def _generate_jobs(
    start_date: date,
    applicants_per_day: int,
    seed: int,
    duration_model: RandomForestRegressor | None,
    no_show_model: Any | None,
    training_episode: bool = False,
) -> list[dict[str, Any]]:
    rng = random.Random(seed)
    jobs = []
    for day_index in range(SERVICE_DAYS):
        service_date = start_date + timedelta(days=day_index)
        for applicant_index in range(applicants_per_day):
            is_renewal = rng.randint(0, 1)
            distance = round(min(12, max(0.2, rng.gauss(3.2, 2.1))), 2)
            domisili_present = rng.random() > 0.15
            supporting_present = rng.random() > 0.22
            docs_complete = int(domisili_present and supporting_present)
            needs_review = int(rng.random() < 0.2 or distance > 7)
            arrival_minute = _arrival_minute(rng)
            hour = 8 + arrival_minute // 60
            days_ahead = rng.randint(0, 14)
            previous_no_show = int(rng.random() < 0.08)
            category = "Outsider Jauh" if distance > 2.0 else "Outsider Dekat"
            if duration_model is None or training_episode:
                predicted_duration = (
                    6 + 2.2 * is_renewal + 1.8 * (1 - docs_complete)
                    + 3 * needs_review + min(distance, 8) * 0.35
                )
                actual_duration = _service_duration(
                    is_renewal, distance, docs_complete, needs_review, rng
                )
            else:
                predicted_duration = None
                actual_duration = _service_duration(
                    is_renewal, distance, docs_complete, needs_review, rng
                )
            no_show_features = {
                "days_ahead": days_ahead,
                "hour": hour,
                "previous_no_show": previous_no_show,
                "is_renewal": is_renewal,
            }
            if no_show_model is None or training_episode:
                no_show_probability = _no_show_probability(no_show_features)
                actual_no_show = rng.random() < no_show_probability
            else:
                no_show_probability = None
                actual_no_show = False
            jobs.append(
                {
                    "id": f"DEMO-{day_index + 1:02d}-{applicant_index + 1:03d}",
                    "day_index": day_index,
                    "service_date": service_date.isoformat(),
                    "arrival": arrival_minute,
                    "arrival_week_minute": _encode_minute(day_index, arrival_minute),
                    "arrival_clock": f"{hour:02d}:{(arrival_minute % 60):02d}",
                    "arrival_minute": arrival_minute,
                    "category": category,
                    "distance_km": distance,
                    "request_type": "Perpanjangan" if is_renewal else "Pendaftaran baru",
                    "docs_complete": docs_complete,
                    "domisili_present": domisili_present,
                    "supporting_present": supporting_present,
                    "needs_review": needs_review,
                    "days_ahead": days_ahead,
                    "previous_no_show": previous_no_show,
                    "predicted_duration": predicted_duration,
                    "actual_duration": actual_duration,
                    "no_show_probability": no_show_probability,
                    "attended": not actual_no_show,
                }
            )
    if duration_model is not None and not training_episode:
        predictions = duration_model.predict(
            pd.DataFrame(
                [
                    {
                        "is_renewal": job["request_type"] == "Perpanjangan",
                        "distance_km": job["distance_km"],
                        "documents_complete": job["docs_complete"],
                        "supporting_review": job["needs_review"],
                    }
                    for job in jobs
                ],
                columns=SERVICE_FEATURES,
            )
        )
        for job, prediction in zip(jobs, predictions):
            job["predicted_duration"] = max(3.0, float(prediction))
    if no_show_model is not None and not training_episode:
        probabilities = no_show_model.predict_proba(
            pd.DataFrame(
                [
                    {
                        "days_ahead": job["days_ahead"],
                        "hour": 8 + job["arrival_minute"] // 60,
                        "previous_no_show": job["previous_no_show"],
                        "is_renewal": job["request_type"] == "Perpanjangan",
                    }
                    for job in jobs
                ],
                columns=NO_SHOW_FEATURES,
            )
        )[:, 1]
        for job, probability in zip(jobs, probabilities):
            job["no_show_probability"] = float(probability)
            job["attended"] = rng.random() >= probability
    return jobs


def _segment_and_triage(
    jobs: list[dict[str, Any]], threshold_km: float, review_zone_km: float
) -> tuple[dict[str, int], dict[str, int], list[dict[str, Any]]]:
    segments: dict[str, int] = defaultdict(int)
    recommendations: dict[str, int] = defaultdict(int)
    assessed = []
    for job in jobs:
        rule_category = "Outsider Jauh" if job["distance_km"] > threshold_km else "Outsider Dekat"
        near_boundary = abs(job["distance_km"] - threshold_km) <= review_zone_km
        mismatch = rule_category != job["category"]
        incomplete = not job["docs_complete"]
        needs_review = near_boundary or mismatch or incomplete or bool(job["needs_review"])
        recommendation = "Perlu tinjauan petugas" if needs_review else "Data konsisten — keputusan petugas"
        if incomplete:
            segment = "Perlu melengkapi checklist"
        elif needs_review:
            segment = "Review petugas"
        else:
            segment = "Layanan standar"
        segments[segment] += 1
        recommendations[recommendation] += 1
        assessed.append(
            {
                "id": job["id"],
                "category": job["category"],
                "distance_km": job["distance_km"],
                "documents_complete": bool(job["docs_complete"]),
                "recommendation": recommendation,
                "segment": segment,
            }
        )
    return dict(segments), dict(recommendations), assessed


def _detect_anomalies(jobs: list[dict[str, Any]], seed: int) -> list[dict[str, Any]]:
    features = pd.DataFrame(
        [
            {
                "distance_km": job["distance_km"],
                "predicted_duration": job["predicted_duration"],
                "no_show_probability": job["no_show_probability"],
            }
            for job in jobs
        ]
    )
    detector = IsolationForest(
        contamination=0.04, random_state=seed, n_estimators=80
    )
    labels = detector.fit_predict(features)
    flagged = []
    for job, label in zip(jobs, labels):
        if label == -1:
            reasons = []
            if job["distance_km"] > 7:
                reasons.append("jarak sintetis relatif tinggi")
            if job["predicted_duration"] > 15:
                reasons.append("estimasi layanan sintetis relatif lama")
            if job["no_show_probability"] > 0.25:
                reasons.append("probabilitas no-show sintetis relatif tinggi")
            if not reasons:
                reasons.append("kombinasi fitur sintetis tidak umum")
            flagged.append({"id": job["id"], "reasons": reasons})
    return flagged


def run_synthetic_week(
    start_date: date,
    service_counters: int = 2,
    applicants_per_day: int = 24,
    seed: int = 42,
    distance_threshold_km: float = 2.0,
    review_zone_km: float = 0.2,
) -> dict[str, Any]:
    """Run all eight modules on synthetic records; never reads or writes real applicant data."""
    if start_date.weekday() != 0:
        raise ValueError("Tanggal mulai harus hari Senin.")
    if not 1 <= service_counters <= 10:
        raise ValueError("Jumlah loket demo harus antara 1 dan 10.")
    if not 5 <= applicants_per_day <= 100:
        raise ValueError("Jumlah pendaftar demo per hari harus antara 5 dan 100.")

    duration_model, duration_metrics = _train_duration_model(seed)
    no_show_model, no_show_metrics = _train_no_show_model(seed)
    jobs = _generate_jobs(
        start_date,
        applicants_per_day,
        seed,
        duration_model,
        no_show_model,
    )
    forecast, demand_metrics = _forecast_demand(seed, applicants_per_day)
    q_table = _train_q_policy(seed, service_counters, applicants_per_day)
    policy_results = {}
    for policy, label in (
        ("fifo", "FIFO"),
        ("spt", "SPT — estimasi durasi terpendek"),
        ("rl", "RL — kebijakan hasil latihan simulator"),
    ):
        daily = [
            _run_day(
                [job for job in jobs if job["day_index"] == day_index],
                service_counters,
                policy,
                q_table=q_table,
                rng=random.Random(seed + day_index),
            )[0]
            for day_index in range(SERVICE_DAYS)
        ]
        served = sum(day["served"] for day in daily)
        waits = [
            day["mean_wait_minutes"] * day["served"]
            for day in daily
        ]
        policy_results[policy] = {
            "label": label,
            "served": served,
            "no_shows": sum(day["no_shows"] for day in daily),
            "mean_wait_minutes": round(sum(waits) / served, 1) if served else 0,
            "p90_wait_minutes": max(day["p90_wait_minutes"] for day in daily),
            "max_wait_minutes": max(day["max_wait_minutes"] for day in daily),
            "max_queue": max(day["max_queue"] for day in daily),
            "overtime_minutes": sum(day["overtime_minutes"] for day in daily),
            "wait_gap_minutes": round(
                sum(day["wait_gap_minutes"] for day in daily) / SERVICE_DAYS, 1
            ),
        }

    segments, triage, assessed = _segment_and_triage(
        jobs, distance_threshold_km, review_zone_km
    )
    anomalies = _detect_anomalies(jobs, seed)
    attended = sum(bool(job["attended"]) for job in jobs)
    no_show_predictions = np.array(
        [job["no_show_probability"] for job in jobs], dtype=float
    )

    return {
        "mode": "synthetic_demo",
        "seed": seed,
        "period": {
            "start_date": start_date.isoformat(),
            "end_date": (start_date + timedelta(days=4)).isoformat(),
            "service_days": list(WEEKDAYS),
            "hours": "08:00-17:00",
            "service_counters": service_counters,
            "applicants_per_day": applicants_per_day,
        },
        "notice": (
            "Simulasi offline dengan data sintetis dan parameter sementara. "
            "Tidak membuat slot/tiket, tidak memakai data mahasiswa nyata, dan "
            "tidak mengubah antrean operasional."
        ),
        "modules": {
            "M1": {
                "status": "demo",
                "model": "RandomForestRegressor sintetis",
                "mae_minutes": duration_metrics["mae_minutes"],
                "baseline_mae_minutes": duration_metrics["baseline_mae_minutes"],
                "mean_predicted_duration_minutes": round(
                    sum(job["predicted_duration"] for job in jobs) / len(jobs), 1
                ),
                "sample_count": len(jobs),
            },
            "M2": {
                "status": "demo",
                "method": "Rata-rata per hari/jam dari empat periode sintetis lima hari",
                "daily_mae_validation": demand_metrics["daily_mae"],
                "hourly_mae_validation": demand_metrics["hourly_mae"],
                "forecast": forecast,
                "forecast_total": round(
                    sum(day["expected_applicants"] for day in forecast), 1
                ),
            },
            "M3": {
                "status": "demo",
                "model": "LogisticRegression sintetis",
                **no_show_metrics,
                "predicted_no_show_rate": round(
                    float(sum(no_show_predictions) / len(no_show_predictions)), 3
                ),
                "simulated_no_shows": int(len(jobs) - attended),
                "sample_count": len(jobs),
            },
            "M4": {
                "status": "provisional_rule_demo",
                "recommendations": triage,
                "distance_threshold_km": distance_threshold_km,
                "review_zone_km": review_zone_km,
                "note": (
                    "Aturan jarak hanya contoh sementara. Tidak ada keputusan "
                    "layak/tolak atau arahan asrama otomatis."
                ),
            },
            "M5": {
                "status": "checklist_only",
                "documents": list(DOCUMENT_NAMES),
                "complete_count": sum(bool(job["docs_complete"]) for job in jobs),
                "incomplete_count": sum(not bool(job["docs_complete"]) for job in jobs),
                "document_checklist": {
                    document: {
                        "provided": sum(
                            job["domisili_present" if index == 0 else "supporting_present"]
                            for job in jobs
                        ),
                        "missing": sum(
                            not job["domisili_present" if index == 0 else "supporting_present"]
                            for job in jobs
                        ),
                    }
                    for index, document in enumerate(DOCUMENT_NAMES)
                },
                "note": "Nama dokumen contoh; belum ada unggah atau penyimpanan berkas.",
            },
            "M6": {
                "status": "demo",
                "segments": segments,
                "note": "Kelompok operasional yang dapat dijelaskan; bukan pembatas akses layanan.",
            },
            "M7": {
                "status": "demo",
                "method": "IsolationForest pada fitur sintetis",
                "flagged_count": len(anomalies),
                "sample_count": len(jobs),
                "flags": anomalies[:20],
                "note": "Flag hanya untuk tinjauan; kombinasi jarang bukan bukti kecurangan.",
            },
            "M8": {
                "status": "offline_simulation",
                "episodes": 24,
                "policies": policy_results,
                "note": (
                    "FIFO, SPT, dan Q-learning dibandingkan pada skenario sintetis. "
                    "RL belum mengendalikan layanan nyata dan belum lulus gate validasi fairness."
                ),
            },
        },
        "applicant_samples": assessed[:12],
    }
