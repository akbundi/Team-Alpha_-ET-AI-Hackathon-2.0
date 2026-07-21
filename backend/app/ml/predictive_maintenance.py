import os
import json
import logging
from typing import Dict, Any, List
import pandas as pd
import numpy as np

# Configure logging
logger = logging.getLogger(__name__)

# Fallback imports
XGB_AVAILABLE = False
SHAP_AVAILABLE = False
SKLEARN_AVAILABLE = False

try:
    import xgboost as xgb
    XGB_AVAILABLE = True
except ImportError:
    logger.warning("xgboost is not installed or failed to import. Falling back to scikit-learn.")

try:
    import shap
    SHAP_AVAILABLE = True
except Exception as e:
    logger.warning(f"shap failed to import ({str(e)}). Using custom feature attribution fallback.")

try:
    from sklearn.ensemble import RandomForestClassifier
    from sklearn.model_selection import train_test_split
    SKLEARN_AVAILABLE = True
except ImportError:
    logger.warning("scikit-learn is not installed. ML model may fail to run if not installed.")

# Constants
MODEL_PATH_XGB = os.path.join(os.path.dirname(__file__), "predictive_model.json")
MODEL_PATH_RF = os.path.join(os.path.dirname(__file__), "predictive_model.joblib")
FEATURE_NAMES = [
    "temperature",
    "vibration",
    "pressure",
    "operating_hours",
    "maintenance_history_index",
    "failure_records_count"
]

class PredictiveMaintenanceModel:
    def __init__(self):
        self.model = None
        self.explainer = None
        self.is_xgboost = False
        
        # Load or train
        self.load_or_train_model()

    def generate_synthetic_data(self, size: int = 1500) -> pd.DataFrame:
        """
        Generates synthetic telemetry data for industrial equipment.
        """
        np.random.seed(42)
        
        # Features
        temperature = np.random.uniform(50.0, 110.0, size)  # normal is 60-90
        vibration = np.random.uniform(0.5, 10.0, size)      # normal is 1.0-5.0
        pressure = np.random.uniform(15.0, 75.0, size)       # normal is 30-50
        operating_hours = np.random.uniform(100.0, 8000.0, size)
        maintenance_history_index = np.random.uniform(0.0, 1.0, size)  # 0: just maintained, 1: neglected
        failure_records_count = np.random.randint(0, 6, size)
        
        df = pd.DataFrame({
            "temperature": temperature,
            "vibration": vibration,
            "pressure": pressure,
            "operating_hours": operating_hours,
            "maintenance_history_index": maintenance_history_index,
            "failure_records_count": failure_records_count
        })
        
        # Define probability of failure base equation
        # Linear combos & non-linear limits
        logit = (
            0.05 * (df["temperature"] - 80) + 
            0.40 * (df["vibration"] - 4.0) +
            0.03 * np.abs(df["pressure"] - 40) +
            0.0003 * (df["operating_hours"] - 3000) +
            1.20 * (df["maintenance_history_index"] - 0.3) +
            0.50 * df["failure_records_count"] - 
            2.5  # Bias / intercept
        )
        
        # Extreme limits where failure is highly likely
        logit += np.where(df["temperature"] > 98.0, 3.5, 0.0)
        logit += np.where(df["vibration"] > 8.0, 4.0, 0.0)
        logit += np.where((df["pressure"] > 65.0) | (df["pressure"] < 20.0), 3.0, 0.0)
        logit += np.where(df["operating_hours"] > 6000.0, 2.0, 0.0)
        
        # Sigmoid to get probability
        prob = 1 / (1 + np.exp(-logit))
        
        # Binary target
        df["failure"] = np.random.binomial(1, prob)
        return df

    def load_or_train_model(self):
        """
        Loads the saved model or trains a new one if not found.
        """
        df = self.generate_synthetic_data()
        X = df[FEATURE_NAMES]
        y = df["failure"]
        
        if XGB_AVAILABLE:
            try:
                self.model = xgb.XGBClassifier(
                    n_estimators=100,
                    max_depth=5,
                    learning_rate=0.1,
                    random_state=42,
                    eval_metric="logloss"
                )
                self.model.fit(X, y)
                self.is_xgboost = True
                logger.info("XGBoost Predictive Maintenance model trained successfully.")
                
                if SHAP_AVAILABLE:
                    try:
                        self.explainer = shap.TreeExplainer(self.model)
                        logger.info("SHAP TreeExplainer initialized for XGBoost.")
                    except Exception as e:
                        logger.warning(f"Failed to initialize SHAP TreeExplainer: {e}")
                return
            except Exception as e:
                logger.error(f"Failed to initialize or train XGBoost model: {e}. Falling back.")
        
        # Fallback to Random Forest (scikit-learn)
        if SKLEARN_AVAILABLE:
            try:
                self.model = RandomForestClassifier(n_estimators=100, max_depth=6, random_state=42)
                self.model.fit(X, y)
                self.is_xgboost = False
                logger.info("Random Forest Predictive Maintenance model trained successfully (fallback).")
                
                if SHAP_AVAILABLE:
                    try:
                        self.explainer = shap.TreeExplainer(self.model)
                        logger.info("SHAP TreeExplainer initialized for Random Forest.")
                    except Exception as e:
                        logger.warning(f"Failed to initialize SHAP TreeExplainer for Random Forest: {e}")
                return
            except Exception as e:
                logger.error(f"Failed to train Random Forest model: {e}")
                
        # Base class fallback if no models work (simplified mock classifier)
        logger.error("No ML libraries found. Using deterministic mock predictor.")
        self.model = "MOCK"

    def predict(self, data: Dict[str, float]) -> Dict[str, Any]:
        """
        Predicts failure probability and returns SHAP values or feature contributions.
        """
        # Validate inputs
        input_data = {}
        for feat in FEATURE_NAMES:
            input_data[feat] = float(data.get(feat, 0.0))
            
        input_df = pd.DataFrame([input_data])
        
        # Calculate failure probability
        if self.model == "MOCK":
            prob = self._mock_predict(input_data)
        else:
            prob = float(self.model.predict_proba(input_df)[0][1])
            
        # Get SHAP values / feature contributions
        contributions = []
        
        if SHAP_AVAILABLE and self.explainer is not None and self.model != "MOCK":
            try:
                if self.is_xgboost:
                    shap_vals = self.explainer.shap_values(input_df)
                else:
                    # Sklearn Random Forest returns list for multiclass [class0_shap, class1_shap]
                    shap_vals = self.explainer.shap_values(input_df)
                    if isinstance(shap_vals, list):
                        shap_vals = shap_vals[1] # class 1 (failure)
                
                # shap_vals is of shape (1, 6)
                row_vals = shap_vals[0] if len(shap_vals.shape) > 1 else shap_vals
                
                for idx, feat in enumerate(FEATURE_NAMES):
                    contributions.append({
                        "feature": feat,
                        "value": input_data[feat],
                        "shap_value": float(row_vals[idx])
                    })
            except Exception as e:
                logger.warning(f"SHAP explanation failed: {e}. Falling back to custom contributions.")
                contributions = self._calculate_fallback_contributions(input_data, prob)
        else:
            contributions = self._calculate_fallback_contributions(input_data, prob)
            
        # Sort contributions by absolute impact
        contributions = sorted(contributions, key=lambda x: abs(x["shap_value"]), reverse=True)
        
        # Recommendations
        recommendations = []
        if input_data["temperature"] > 95.0:
            recommendations.append("High temperature detected. Inspect cooling system and bearing lubrication.")
        if input_data["vibration"] > 7.0:
            recommendations.append("Severe vibration levels. Check rotor alignment, structural mounts, and check for cavitation.")
        if input_data["pressure"] > 60.0 or input_data["pressure"] < 25.0:
            recommendations.append("Abnormal operating pressure. Inspect seals, intake/outlet valves, and pressure regulators.")
        if input_data["operating_hours"] > 5000:
            recommendations.append("Equipment exceeded scheduled maintenance hours. Plan scheduled overhaul.")
        if input_data["maintenance_history_index"] > 0.7:
            recommendations.append("Neglected maintenance history. Perform comprehensive inspection and greasing immediately.")
            
        if prob < 0.2:
            status = "HEALTHY"
            recommendations = ["Equipment operating within normal parameters. Continue standard monitoring."]
        elif prob < 0.5:
            status = "WARN"
            if not recommendations:
                recommendations = ["Monitor operating parameters closely. Plan maintenance in next scheduled window."]
        else:
            status = "CRITICAL"
            if not recommendations:
                recommendations = ["Urgent maintenance required. High probability of imminent failure."]
                
        return {
            "failure_probability": prob,
            "status": status,
            "contributions": contributions,
            "recommendations": recommendations
        }
        
    def _mock_predict(self, data: Dict[str, float]) -> float:
        # Simple math to return a plausible probability
        score = 0.0
        if data["temperature"] > 90: score += 0.3
        if data["vibration"] > 6: score += 0.4
        if data["pressure"] > 55 or data["pressure"] < 25: score += 0.2
        if data["operating_hours"] > 5000: score += 0.15
        if data["maintenance_history_index"] > 0.6: score += 0.15
        score += data["failure_records_count"] * 0.05
        return min(max(score, 0.02), 0.98)

    def _calculate_fallback_contributions(self, data: Dict[str, float], prob: float) -> List[Dict[str, Any]]:
        """
        Calculates feature contributions manually if SHAP is not available.
        Uses deviations from typical 'healthy' values.
        """
        baselines = {
            "temperature": 75.0,  # middle of normal
            "vibration": 2.5,
            "pressure": 40.0,
            "operating_hours": 2000.0,
            "maintenance_history_index": 0.2,
            "failure_records_count": 0.0
        }
        
        weights = {
            "temperature": 0.008,
            "vibration": 0.08,
            "pressure": 0.005,
            "operating_hours": 0.00005,
            "maintenance_history_index": 0.3,
            "failure_records_count": 0.05
        }
        
        contributions = []
        for feat in FEATURE_NAMES:
            val = data[feat]
            base = baselines[feat]
            w = weights[feat]
            
            if feat == "pressure":
                diff = abs(val - base)
            else:
                diff = val - base
                
            shap_val = diff * w
            contributions.append({
                "feature": feat,
                "value": val,
                "shap_value": float(shap_val)
            })
            
        return contributions

# Singleton instance
pm_model = PredictiveMaintenanceModel()
