"""
Latency Prediction Model for Remix Debugger

This script builds a regression model to predict Remix debugging latency
based on contract characteristics (State Slots, ByteOp, Annotation Targets)
without having to manually test all 30 contracts.
"""

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from sklearn.linear_model import LinearRegression
from sklearn.preprocessing import PolynomialFeatures
from sklearn.model_selection import cross_val_score
from sklearn.metrics import r2_score, mean_squared_error, mean_absolute_error
import json


def load_benchmark_results(results_file='remix_benchmark_results.csv'):
    """Load benchmark results from CSV"""
    df = pd.read_csv(results_file)
    return df


def load_dataset():
    """Load evaluation dataset"""
    df = pd.read_excel('dataset/evaluation_Dataset.xlsx', header=0)
    df.columns = ['Index', 'Size_KB', 'Sol_File_Name', 'Contract_Name', 'Function_Name',
                  'Original_Function_Line', 'Annotation_Targets', 'State_Slots', 'ByteOp',
                  'Target_Variables']

    # Remove header row if exists
    if df.iloc[0]['Size_KB'] == '용량':
        df = df.iloc[1:].reset_index(drop=True)

    # Convert numeric columns
    df['Annotation_Targets'] = pd.to_numeric(df['Annotation_Targets'], errors='coerce').fillna(0)
    df['State_Slots'] = pd.to_numeric(df['State_Slots'], errors='coerce').fillna(0)
    df['ByteOp'] = pd.to_numeric(df['ByteOp'], errors='coerce')  # Keep NaN for now

    return df


class LatencyModel:
    """Regression model for predicting Remix debugging latency"""

    def __init__(self, model_type='linear'):
        """
        Initialize model

        Args:
            model_type: 'linear' or 'polynomial'
        """
        self.model_type = model_type
        self.model = None
        self.poly_features = None

        if model_type == 'polynomial':
            self.poly_features = PolynomialFeatures(degree=2, include_bias=False)
            self.model = LinearRegression()
        else:
            self.model = LinearRegression()

    def train(self, X, y):
        """
        Train the model

        Args:
            X: Feature matrix (n_samples, n_features)
            y: Target vector (n_samples,)
        """
        if self.model_type == 'polynomial':
            X_poly = self.poly_features.fit_transform(X)
            self.model.fit(X_poly, y)
        else:
            self.model.fit(X, y)

        # Print coefficients
        print(f"\n{'='*60}")
        print(f"Model: {self.model_type.upper()}")
        print(f"{'='*60}")

        if self.model_type == 'linear':
            print(f"Intercept: {self.model.intercept_:.2f}")
            print(f"Coefficients:")
            print(f"  State Slots:        {self.model.coef_[0]:+.4f}ms per slot")
            print(f"  ByteOp Count:       {self.model.coef_[1]:+.4f}ms per op")
            print(f"  Annotation Targets: {self.model.coef_[2]:+.4f}ms per target")
        else:
            print(f"Intercept: {self.model.intercept_:.2f}")
            print(f"Coefficients: {self.model.coef_}")

        print(f"{'='*60}\n")

    def predict(self, X):
        """
        Predict latency

        Args:
            X: Feature matrix

        Returns:
            Predicted latency values
        """
        if self.model_type == 'polynomial':
            X_poly = self.poly_features.transform(X)
            return self.model.predict(X_poly)
        else:
            return self.model.predict(X)

    def evaluate(self, X, y):
        """
        Evaluate model performance

        Args:
            X: Feature matrix
            y: True values

        Returns:
            Dict of metrics
        """
        y_pred = self.predict(X)

        metrics = {
            'r2_score': r2_score(y, y_pred),
            'rmse': np.sqrt(mean_squared_error(y, y_pred)),
            'mae': mean_absolute_error(y, y_pred),
            'mape': np.mean(np.abs((y - y_pred) / y)) * 100  # Mean Absolute Percentage Error
        }

        return metrics, y_pred

    def cross_validate(self, X, y, cv=5):
        """
        Perform cross-validation

        Args:
            X: Feature matrix
            y: Target vector
            cv: Number of folds

        Returns:
            Cross-validation scores
        """
        if self.model_type == 'polynomial':
            X_poly = self.poly_features.transform(X)
            scores = cross_val_score(self.model, X_poly, y, cv=cv, scoring='r2')
        else:
            scores = cross_val_score(self.model, X, y, cv=cv, scoring='r2')

        return scores


def build_model_from_results(results_df, target_metric='pure_debug_time_ms'):
    """
    Build latency prediction model from benchmark results

    Args:
        results_df: DataFrame with benchmark results
        target_metric: Which latency metric to predict
                      ('pure_debug_time_ms', 'total_time_ms', etc.)

    Returns:
        Trained model and evaluation metrics
    """
    # Average multiple runs for each contract
    agg_results = results_df.groupby('contract_name').agg({
        target_metric: 'mean',
        'byteop_count': 'mean',
        'expected_state_slots': 'first',
        'annotation_targets': 'first'
    }).reset_index()

    # Prepare features
    X = agg_results[['expected_state_slots', 'byteop_count', 'annotation_targets']].values
    y = agg_results[target_metric].values

    print(f"\n{'='*60}")
    print(f"Building Model for: {target_metric}")
    print(f"Training samples: {len(X)}")
    print(f"{'='*60}\n")

    # Try both linear and polynomial models
    models = {}
    results = {}

    for model_type in ['linear', 'polynomial']:
        model = LatencyModel(model_type=model_type)
        model.train(X, y)

        metrics, y_pred = model.evaluate(X, y)
        results[model_type] = {
            'model': model,
            'metrics': metrics,
            'predictions': y_pred
        }

        print(f"\n{model_type.upper()} Model Performance:")
        print(f"  R² Score: {metrics['r2_score']:.4f}")
        print(f"  RMSE: {metrics['rmse']:.2f}ms")
        print(f"  MAE: {metrics['mae']:.2f}ms")
        print(f"  MAPE: {metrics['mape']:.2f}%")

    # Select best model (based on R²)
    best_model_type = 'linear' if results['linear']['metrics']['r2_score'] >= results['polynomial']['metrics']['r2_score'] else 'polynomial'
    best_model = results[best_model_type]['model']

    print(f"\n{'='*60}")
    print(f"✓ Best Model: {best_model_type.upper()}")
    print(f"{'='*60}\n")

    return best_model, results, agg_results


def predict_all_contracts(model, dataset_df, byteop_measured=False):
    """
    Predict latency for all contracts in dataset

    Args:
        model: Trained LatencyModel
        dataset_df: Dataset with contract info
        byteop_measured: Whether ByteOp has been measured (if not, will estimate)

    Returns:
        DataFrame with predictions
    """
    predictions = []

    for idx, row in dataset_df.iterrows():
        contract_name = row['Contract_Name']
        state_slots = row['State_Slots']
        annotation_targets = row['Annotation_Targets']
        byteop = row['ByteOp']

        # If ByteOp not measured, estimate based on function line count
        if pd.isna(byteop):
            if byteop_measured:
                print(f"Warning: ByteOp not measured for {contract_name}, skipping")
                continue
            else:
                # Rough estimate: ~3-5 opcodes per line of Solidity
                line_range = row['Original_Function_Line']
                if isinstance(line_range, str) and '-' in line_range:
                    start, end = line_range.split('-')
                    lines = int(end) - int(start) + 1
                    byteop = lines * 4  # Rough estimate
                else:
                    byteop = 50  # Default estimate

        # Prepare features
        X = np.array([[state_slots, byteop, annotation_targets]])

        # Predict
        predicted_latency = model.predict(X)[0]

        predictions.append({
            'contract_name': contract_name,
            'function_name': row['Function_Name'],
            'state_slots': state_slots,
            'byteop': byteop,
            'annotation_targets': annotation_targets,
            'predicted_latency_ms': predicted_latency
        })

    pred_df = pd.DataFrame(predictions)
    return pred_df


def visualize_model_performance(agg_results, model, target_metric='pure_debug_time_ms'):
    """
    Visualize model predictions vs actual values

    Args:
        agg_results: Aggregated benchmark results
        model: Trained model
        target_metric: Target metric name
    """
    X = agg_results[['expected_state_slots', 'byteop_count', 'annotation_targets']].values
    y_true = agg_results[target_metric].values
    y_pred = model.predict(X)

    # Create figure with subplots
    fig, axes = plt.subplots(2, 2, figsize=(14, 10))

    # 1. Predicted vs Actual
    axes[0, 0].scatter(y_true, y_pred, alpha=0.6, s=100)
    axes[0, 0].plot([y_true.min(), y_true.max()], [y_true.min(), y_true.max()], 'r--', lw=2)
    axes[0, 0].set_xlabel('Actual Latency (ms)', fontsize=12)
    axes[0, 0].set_ylabel('Predicted Latency (ms)', fontsize=12)
    axes[0, 0].set_title('Predicted vs Actual Latency', fontsize=14, fontweight='bold')
    axes[0, 0].grid(True, alpha=0.3)

    # 2. Residuals
    residuals = y_true - y_pred
    axes[0, 1].scatter(y_pred, residuals, alpha=0.6, s=100)
    axes[0, 1].axhline(y=0, color='r', linestyle='--', lw=2)
    axes[0, 1].set_xlabel('Predicted Latency (ms)', fontsize=12)
    axes[0, 1].set_ylabel('Residuals (ms)', fontsize=12)
    axes[0, 1].set_title('Residual Plot', fontsize=14, fontweight='bold')
    axes[0, 1].grid(True, alpha=0.3)

    # 3. Feature importance (for linear model)
    if model.model_type == 'linear':
        features = ['State Slots', 'ByteOp', 'Annotation Targets']
        importance = np.abs(model.model.coef_)
        axes[1, 0].barh(features, importance, color=['#1f77b4', '#ff7f0e', '#2ca02c'])
        axes[1, 0].set_xlabel('Absolute Coefficient Value', fontsize=12)
        axes[1, 0].set_title('Feature Importance', fontsize=14, fontweight='bold')
        axes[1, 0].grid(True, alpha=0.3, axis='x')

    # 4. Error distribution
    axes[1, 1].hist(residuals, bins=15, alpha=0.7, color='skyblue', edgecolor='black')
    axes[1, 1].axvline(x=0, color='r', linestyle='--', lw=2)
    axes[1, 1].set_xlabel('Residual (ms)', fontsize=12)
    axes[1, 1].set_ylabel('Frequency', fontsize=12)
    axes[1, 1].set_title('Residual Distribution', fontsize=14, fontweight='bold')
    axes[1, 1].grid(True, alpha=0.3, axis='y')

    plt.tight_layout()
    plt.savefig('latency_model_performance.png', dpi=300, bbox_inches='tight')
    print(f"\n✓ Visualization saved to: latency_model_performance.png\n")


def save_model(model, filename='remix_latency_model.json'):
    """Save model parameters to JSON"""
    model_data = {
        'model_type': model.model_type,
        'intercept': float(model.model.intercept_),
        'coefficients': model.model.coef_.tolist()
    }

    with open(filename, 'w') as f:
        json.dump(model_data, f, indent=2)

    print(f"✓ Model saved to: {filename}")


def main():
    """Main workflow for building latency prediction model"""

    print(f"\n{'#'*60}")
    print(f"# Remix Debugger Latency Prediction Model")
    print(f"{'#'*60}\n")

    # Step 1: Load benchmark results
    try:
        results_df = load_benchmark_results('remix_benchmark_results.csv')
        print(f"✓ Loaded {len(results_df)} benchmark results")
    except FileNotFoundError:
        print("✗ Error: remix_benchmark_results.csv not found")
        print("  Please run remix_benchmark.py first to collect data")
        return

    # Step 2: Build model
    model, all_results, agg_results = build_model_from_results(
        results_df,
        target_metric='pure_debug_time_ms'
    )

    # Step 3: Visualize
    visualize_model_performance(agg_results, model)

    # Step 4: Save model
    save_model(model)

    # Step 5: Predict for all contracts in dataset
    print(f"\n{'='*60}")
    print(f"Predicting latency for all contracts in dataset...")
    print(f"{'='*60}\n")

    dataset_df = load_dataset()
    predictions = predict_all_contracts(model, dataset_df, byteop_measured=False)

    # Save predictions
    predictions.to_csv('predicted_latencies.csv', index=False)
    print(f"\n✓ Predictions saved to: predicted_latencies.csv")

    # Show summary statistics
    print(f"\n{'='*60}")
    print(f"Prediction Summary Statistics")
    print(f"{'='*60}")
    print(f"Mean predicted latency: {predictions['predicted_latency_ms'].mean():.2f}ms")
    print(f"Median predicted latency: {predictions['predicted_latency_ms'].median():.2f}ms")
    print(f"Min predicted latency: {predictions['predicted_latency_ms'].min():.2f}ms")
    print(f"Max predicted latency: {predictions['predicted_latency_ms'].max():.2f}ms")
    print(f"Std predicted latency: {predictions['predicted_latency_ms'].std():.2f}ms")
    print(f"{'='*60}\n")

    return model, predictions


if __name__ == "__main__":
    model, predictions = main()
