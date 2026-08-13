import os
import pickle
import pandas as pd

from sklearn.tree import DecisionTreeClassifier
from sklearn.ensemble import RandomForestRegressor
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score, mean_absolute_error


BASE_DIR = os.path.dirname(__file__)

DATA_PATH = os.path.join(BASE_DIR, "fault_training_data.csv")
MODEL_PATH = os.path.join(BASE_DIR, "drivesense_ml_model.pkl")


def train_models():

    data = pd.read_csv(DATA_PATH)

    features = data[
        [
            "fault_count",
            "coolant_temp",
            "engine_load",
            "rpm",
            "severity_score"
        ]
    ]

    urgency_target = data["urgency"]
    health_target = data["health_score"]

    x_train, x_test, y_train, y_test = train_test_split(
        features,
        urgency_target,
        test_size=0.25,
        random_state=42
    )

    urgency_model = DecisionTreeClassifier(
        max_depth=4,
        random_state=42
    )

    urgency_model.fit(x_train, y_train)

    urgency_predictions = urgency_model.predict(x_test)

    urgency_accuracy = accuracy_score(
        y_test,
        urgency_predictions
    )

    hx_train, hx_test, hy_train, hy_test = train_test_split(
        features,
        health_target,
        test_size=0.25,
        random_state=42
    )

    health_model = RandomForestRegressor(
        n_estimators=80,
        random_state=42
    )

    health_model.fit(hx_train, hy_train)

    health_predictions = health_model.predict(hx_test)

    health_error = mean_absolute_error(
        hy_test,
        health_predictions
    )

    bundle = {
        "urgency_model": urgency_model,
        "health_model": health_model,
        "features": [
            "fault_count",
            "coolant_temp",
            "engine_load",
            "rpm",
            "severity_score"
        ],
        "urgency_accuracy": round(float(urgency_accuracy), 3),
        "health_mae": round(float(health_error), 2)
    }

    with open(MODEL_PATH, "wb") as f:
        pickle.dump(bundle, f)

    print("✅ DriveSense ML model trained")
    print("Urgency accuracy:", bundle["urgency_accuracy"])
    print("Health MAE:", bundle["health_mae"])
    print("Saved to:", MODEL_PATH)


if __name__ == "__main__":
    train_models()