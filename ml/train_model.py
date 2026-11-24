import json
from pathlib import Path

import pandas as pd
from joblib import dump
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, confusion_matrix, f1_score, precision_score, recall_score
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

from generate_dataset import OUTPUT, generate_dataset, save_dataset


ROOT = Path(__file__).resolve().parent
ARTIFACTS = ROOT / "artifacts"
MODEL_PATH = ARTIFACTS / "housing_model.joblib"
METRICS_PATH = ARTIFACTS / "model_metrics.json"
NUMERIC_FEATURES = ["jarak_km", "waktu_tempuh_menit"]
CATEGORICAL_FEATURES = ["kelurahan", "akses_jalan"]
FEATURES = NUMERIC_FEATURES + CATEGORICAL_FEATURES
LABELS = ["Outsider Dekat", "Outsider Jauh"]
VILLAGE_DEAN_OUTPUT = ROOT / "villagedean_dataset.csv"


def evaluate_model(model, x_train, x_test, y_train, y_test, numeric_features, categorical_features):
    pipeline = Pipeline(
        [
            (
                "preprocessor",
                ColumnTransformer(
                    [
                        ("numeric", StandardScaler(), numeric_features),
                        *(
                            [("categorical", OneHotEncoder(handle_unknown="ignore"), categorical_features)]
                            if categorical_features else []
                        ),
                    ]
                ),
            ),
            ("classifier", model),
        ]
    )
    pipeline.fit(x_train, y_train)
    predictions = pipeline.predict(x_test)
    metrics = {
        "accuracy": float(accuracy_score(y_test, predictions)),
        "precision": float(precision_score(y_test, predictions, average="macro", zero_division=0)),
        "recall": float(recall_score(y_test, predictions, average="macro", zero_division=0)),
        "f1_score": float(f1_score(y_test, predictions, average="macro", zero_division=0)),
        "confusion_matrix": confusion_matrix(y_test, predictions, labels=LABELS).tolist(),
        "labels": LABELS,
    }
    return pipeline, metrics


def train():
    if VILLAGE_DEAN_OUTPUT.exists():
        village_data = pd.read_csv(VILLAGE_DEAN_OUTPUT)
        missing = {"kategori_outsider", "jarak_km"} - set(village_data.columns)
        if missing:
            raise ValueError(
                f"Kolom dataset Village Dean tidak lengkap: {', '.join(sorted(missing))}"
            )
        dataset = village_data[["jarak_km"]].copy()
        dataset["kategori"] = dataset["jarak_km"].apply(
            lambda distance: "Outsider Jauh" if float(distance) > 2.0 else "Outsider Dekat"
        )
        active_features = ["jarak_km"]
        numeric_features = ["jarak_km"]
        categorical_features = []
    else:
        if not OUTPUT.exists():
            save_dataset(generate_dataset())
        dataset = pd.read_csv(OUTPUT)
        missing = set(FEATURES + ["kategori"]) - set(dataset.columns)
        if missing:
            raise ValueError(f"Kolom dataset tidak lengkap: {', '.join(sorted(missing))}")
        active_features = FEATURES
        numeric_features = NUMERIC_FEATURES
        categorical_features = CATEGORICAL_FEATURES

    if len(dataset) < 20:
        raise ValueError("Dataset pelatihan minimal harus berisi 20 baris.")
    class_counts = dataset["kategori"].value_counts()
    if set(class_counts.index) != set(LABELS) or any(count < 2 for count in class_counts):
        raise ValueError("Dataset harus memiliki minimal 2 baris untuk setiap kategori.")
    x_train, x_test, y_train, y_test = train_test_split(
        dataset[active_features],
        dataset["kategori"],
        test_size=0.25,
        random_state=42,
        stratify=dataset["kategori"],
    )
    models = {
        "RandomForestClassifier": RandomForestClassifier(
            n_estimators=180, max_depth=8, min_samples_leaf=2, class_weight="balanced", random_state=42
        ),
        "LogisticRegression": LogisticRegression(max_iter=1500, class_weight="balanced", random_state=42),
    }
    evaluated = {}
    pipelines = {}
    for name, estimator in models.items():
        pipelines[name], evaluated[name] = evaluate_model(
            estimator,
            x_train,
            x_test,
            y_train,
            y_test,
            numeric_features,
            categorical_features,
        )
        print(f"{name}: accuracy={evaluated[name]['accuracy']:.3f}, F1={evaluated[name]['f1_score']:.3f}")

    best_name = max(evaluated, key=lambda name: evaluated[name]["f1_score"])
    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    dump(pipelines[best_name], MODEL_PATH)
    summary = {
        "model_name": best_name,
        "features": active_features,
        "target": "kategori",
        "dataset_rows": int(len(dataset)),
        "train_rows": int(len(x_train)),
        "test_rows": int(len(x_test)),
        "selection_metric": "f1_score_macro",
        "metrics": evaluated[best_name],
        "comparison": evaluated,
    }
    METRICS_PATH.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Model terbaik: {best_name}")
    print(f"Model disimpan di {MODEL_PATH}")
    print(f"Metrik disimpan di {METRICS_PATH}")


if __name__ == "__main__":
    train()
