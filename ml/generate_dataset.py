import csv
import random
from pathlib import Path


ROOT = Path(__file__).resolve().parent
OUTPUT = ROOT / "housing_dataset.csv"
KELURAHAN = [
    "Airmadidi Bawah",
    "Airmadidi Atas",
    "Sarongsong",
    "Sukur",
    "Rap-Rap",
    "Suwaan",
]
AKSES_JALAN = ["Jalan Utama", "Lorong", "Perbukitan"]


def generate_dataset(rows: int = 400, seed: int = 42) -> list[dict]:
    if rows < 20:
        raise ValueError("Dataset minimal harus berisi 20 baris.")
    rng = random.Random(seed)
    weights = [0.25, 0.2, 0.16, 0.15, 0.12, 0.12]
    center_distance = {
        "Airmadidi Bawah": 1.4,
        "Airmadidi Atas": 2.0,
        "Sarongsong": 2.5,
        "Sukur": 3.4,
        "Rap-Rap": 4.3,
        "Suwaan": 4.8,
    }
    dataset = []
    for _ in range(rows):
        place = rng.choices(KELURAHAN, weights=weights, k=1)[0]
        road = rng.choices(AKSES_JALAN, weights=[0.52, 0.34, 0.14], k=1)[0]
        distance = min(
            9.5,
            max(
                0.2,
                center_distance[place]
                + rng.gauss(0, 0.85)
                + (0.35 if road == "Perbukitan" else 0),
            ),
        )
        travel = min(
            65,
            max(
                2,
                distance * rng.uniform(3.0, 5.2)
                + (3.5 if road == "Lorong" else 0)
                + (8 if road == "Perbukitan" else 0)
                + rng.gauss(0, 3),
            ),
        )
        score = (
            (distance - 2.05) * 1.2
            + (travel - distance * 4.0) * 0.045
            + (0.15 if road == "Perbukitan" else 0)
            + rng.gauss(0, 0.55)
        )
        dataset.append(
            {
                "jarak_km": round(distance, 2),
                "waktu_tempuh_menit": round(travel),
                "kelurahan": place,
                "akses_jalan": road,
                "kategori": "Outsider Jauh" if score >= 0 else "Outsider Dekat",
            }
        )
    return dataset


def save_dataset(dataset: list[dict], output: Path = OUTPUT):
    with output.open("w", newline="", encoding="utf-8") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=dataset[0].keys())
        writer.writeheader()
        writer.writerows(dataset)


if __name__ == "__main__":
    dataset = generate_dataset()
    save_dataset(dataset)
    label_counts = {}
    for row in dataset:
        label_counts[row["kategori"]] = label_counts.get(row["kategori"], 0) + 1
    print(f"Dataset sintetis {len(dataset)} baris disimpan di {OUTPUT}")
    print(label_counts)
