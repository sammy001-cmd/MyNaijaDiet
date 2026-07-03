"""
MyNaijaDiet — ML Model Training Pipeline
==========================================
Models trained:
  1. Random Forest  (scikit-learn)
  2. LightGBM       (gradient boosting)
  3. ANN            (Keras Sequential)
  4. LSTM           (Keras with sequence input)

Target:  goal_suitability (0=weight_loss, 1=maintenance, 2=muscle_gain)
Task:    Multi-class classification → recommend meals that match user's goal

Output:
  models/random_forest.pkl
  models/lightgbm.pkl
  models/ann.keras
  models/lstm.keras
  models/model_results.csv    ← accuracy + report for each model
"""

import os
import pickle
import numpy as np
import pandas as pd
import warnings
warnings.filterwarnings('ignore')

from sklearn.ensemble         import RandomForestClassifier
from sklearn.model_selection  import train_test_split, cross_val_score
from sklearn.metrics          import (classification_report,
                                      accuracy_score,
                                      confusion_matrix)
from sklearn.preprocessing    import LabelEncoder
import lightgbm as lgb

import tensorflow as tf
from tensorflow.keras.models  import Sequential
from tensorflow.keras.layers  import (Dense, Dropout, LSTM,
                                       Reshape, BatchNormalization)
from tensorflow.keras.callbacks import EarlyStopping
from tensorflow.keras.utils   import to_categorical

tf.random.set_seed(42)
np.random.seed(42)

# ── Paths ──────────────────────────────────────────────────────────────────
BASE_DIR   = 'C:/smart_diet_app'
DATA_PATH  = os.path.join(BASE_DIR, 'mynaijadiet_processed.csv')
MODEL_DIR  = os.path.join(BASE_DIR, 'models')
os.makedirs(MODEL_DIR, exist_ok=True)

print("=" * 60)
print("MyNaijaDiet — ML Training Pipeline")
print("=" * 60)


# ════════════════════════════════════════════════════════════════════════════
# STEP 1 — LOAD AND SPLIT
# ════════════════════════════════════════════════════════════════════════════
print("\nSTEP 1 — Loading processed dataset")

df = pd.read_csv(DATA_PATH)
print(f"  Shape: {df.shape}")

# Drop meal_id (identifier, not a feature)
df = df.drop(columns=['meal_id'])

# Target and features
TARGET = 'goal_suitability'
FEATURES = [c for c in df.columns if c != TARGET]

X = df[FEATURES].values.astype(np.float32)
y = df[TARGET].values.astype(int)

print(f"  Features: {len(FEATURES)}")
print(f"  Target classes: {np.unique(y)} → 0=weight_loss, 1=maintenance, 2=muscle_gain")
print(f"  Class distribution: {dict(zip(*np.unique(y, return_counts=True)))}")

# Train/test split — stratified so each class is represented
X_train, X_test, y_train, y_test = train_test_split(
    X, y,
    test_size    = 0.2,
    random_state = 42,
    stratify     = y,
)
print(f"\n  Train: {X_train.shape[0]} samples")
print(f"  Test:  {X_test.shape[0]} samples")

# One-hot labels for neural networks
y_train_cat = to_categorical(y_train, num_classes=3)
y_test_cat  = to_categorical(y_test,  num_classes=3)

results = []   # collect results for summary


# ════════════════════════════════════════════════════════════════════════════
# MODEL 1 — RANDOM FOREST
# ════════════════════════════════════════════════════════════════════════════
print("\n" + "=" * 60)
print("MODEL 1 — Random Forest")
print("=" * 60)

rf = RandomForestClassifier(
    n_estimators     = 300,
    max_depth        = None,
    min_samples_split= 2,
    min_samples_leaf = 1,
    max_features     = 'sqrt',
    class_weight     = 'balanced',
    random_state     = 42,
    n_jobs           = -1,
)

rf.fit(X_train, y_train)
rf_preds   = rf.predict(X_test)
rf_acc     = accuracy_score(y_test, rf_preds)
rf_cv      = cross_val_score(rf, X, y, cv=5, scoring='accuracy').mean()

print(f"\n  Test Accuracy:       {rf_acc:.4f}  ({rf_acc*100:.2f}%)")
print(f"  5-Fold CV Accuracy:  {rf_cv:.4f}  ({rf_cv*100:.2f}%)")
print(f"\n  Classification Report:")
print(classification_report(
    y_test, rf_preds,
    target_names=['weight_loss', 'maintenance', 'muscle_gain']
))

# Feature importance top 10
importances = pd.Series(rf.feature_importances_, index=FEATURES)
print("  Top 10 Important Features:")
for feat, score in importances.nlargest(10).items():
    print(f"    {feat}: {score:.4f}")

# Save
rf_path = os.path.join(MODEL_DIR, 'random_forest.pkl')
with open(rf_path, 'wb') as f:
    pickle.dump(rf, f)
print(f"\n  Saved → {rf_path}")

results.append({
    'model': 'Random Forest',
    'test_accuracy': round(rf_acc, 4),
    'cv_accuracy': round(rf_cv, 4),
})


# ════════════════════════════════════════════════════════════════════════════
# MODEL 2 — LIGHTGBM
# ════════════════════════════════════════════════════════════════════════════
print("\n" + "=" * 60)
print("MODEL 2 — LightGBM")
print("=" * 60)

lgb_model = lgb.LGBMClassifier(
    n_estimators     = 500,
    learning_rate    = 0.05,
    max_depth        = 8,
    num_leaves       = 31,
    min_child_samples= 5,
    subsample        = 0.8,
    colsample_bytree = 0.8,
    class_weight     = 'balanced',
    random_state     = 42,
    verbose          = -1,
)

lgb_model.fit(
    X_train, y_train,
    eval_set              = [(X_test, y_test)],
    callbacks             = [lgb.early_stopping(50, verbose=False),
                              lgb.log_evaluation(period=-1)],
)

lgb_preds = lgb_model.predict(X_test)
lgb_acc   = accuracy_score(y_test, lgb_preds)
lgb_cv    = cross_val_score(lgb_model, X, y, cv=5, scoring='accuracy').mean()

print(f"\n  Test Accuracy:       {lgb_acc:.4f}  ({lgb_acc*100:.2f}%)")
print(f"  5-Fold CV Accuracy:  {lgb_cv:.4f}  ({lgb_cv*100:.2f}%)")
print(f"\n  Classification Report:")
print(classification_report(
    y_test, lgb_preds,
    target_names=['weight_loss', 'maintenance', 'muscle_gain']
))

lgb_path = os.path.join(MODEL_DIR, 'lightgbm.pkl')
with open(lgb_path, 'wb') as f:
    pickle.dump(lgb_model, f)
print(f"\n  Saved → {lgb_path}")

results.append({
    'model': 'LightGBM',
    'test_accuracy': round(lgb_acc, 4),
    'cv_accuracy': round(lgb_cv, 4),
})


# ════════════════════════════════════════════════════════════════════════════
# MODEL 3 — ANN (Artificial Neural Network)
# ════════════════════════════════════════════════════════════════════════════
print("\n" + "=" * 60)
print("MODEL 3 — ANN (Artificial Neural Network)")
print("=" * 60)

n_features = X_train.shape[1]

ann = Sequential([
    Dense(256, activation='relu', input_shape=(n_features,)),
    BatchNormalization(),
    Dropout(0.3),

    Dense(128, activation='relu'),
    BatchNormalization(),
    Dropout(0.3),

    Dense(64, activation='relu'),
    BatchNormalization(),
    Dropout(0.2),

    Dense(32, activation='relu'),
    Dropout(0.1),

    Dense(3, activation='softmax'),   # 3 goal classes
], name='MyNaijaDiet_ANN')

ann.compile(
    optimizer = tf.keras.optimizers.Adam(learning_rate=0.001),
    loss      = 'categorical_crossentropy',
    metrics   = ['accuracy'],
)

ann.summary()

early_stop = EarlyStopping(
    monitor              = 'val_accuracy',
    patience             = 20,
    restore_best_weights = True,
    verbose              = 1,
)

history_ann = ann.fit(
    X_train, y_train_cat,
    validation_data = (X_test, y_test_cat),
    epochs          = 200,
    batch_size      = 32,
    callbacks       = [early_stop],
    verbose         = 1,
)

ann_preds_prob = ann.predict(X_test, verbose=0)
ann_preds      = np.argmax(ann_preds_prob, axis=1)
ann_acc        = accuracy_score(y_test, ann_preds)

print(f"\n  Test Accuracy: {ann_acc:.4f}  ({ann_acc*100:.2f}%)")
print(f"\n  Classification Report:")
print(classification_report(
    y_test, ann_preds,
    target_names=['weight_loss', 'maintenance', 'muscle_gain']
))

ann_path = os.path.join(MODEL_DIR, 'ann.keras')
ann.save(ann_path)
print(f"\n  Saved → {ann_path}")

results.append({
    'model': 'ANN',
    'test_accuracy': round(ann_acc, 4),
    'cv_accuracy': None,   # CV not done for Keras models (expensive)
})


# ════════════════════════════════════════════════════════════════════════════
# MODEL 4 — LSTM
# Note: LSTM expects sequential data (timesteps × features).
# Since our data is tabular (not time-series), we treat each feature
# as a timestep — a common technique for applying LSTM to tabular data.
# Each sample becomes shape (n_features, 1) → (44 timesteps, 1 feature each)
# ════════════════════════════════════════════════════════════════════════════
print("\n" + "=" * 60)
print("MODEL 4 — LSTM")
print("=" * 60)

# Reshape for LSTM: (samples, timesteps, features) = (N, 44, 1)
X_train_lstm = X_train.reshape(X_train.shape[0], X_train.shape[1], 1)
X_test_lstm  = X_test.reshape(X_test.shape[0],  X_test.shape[1],  1)

lstm_model = Sequential([
    LSTM(128, return_sequences=True, input_shape=(n_features, 1)),
    Dropout(0.3),

    LSTM(64, return_sequences=False),
    Dropout(0.3),

    Dense(32, activation='relu'),
    BatchNormalization(),
    Dropout(0.2),

    Dense(3, activation='softmax'),
], name='MyNaijaDiet_LSTM')

lstm_model.compile(
    optimizer = tf.keras.optimizers.Adam(learning_rate=0.001),
    loss      = 'categorical_crossentropy',
    metrics   = ['accuracy'],
)

lstm_model.summary()

early_stop_lstm = EarlyStopping(
    monitor              = 'val_accuracy',
    patience             = 20,
    restore_best_weights = True,
    verbose              = 1,
)

history_lstm = lstm_model.fit(
    X_train_lstm, y_train_cat,
    validation_data = (X_test_lstm, y_test_cat),
    epochs          = 200,
    batch_size      = 32,
    callbacks       = [early_stop_lstm],
    verbose         = 1,
)

lstm_preds_prob = lstm_model.predict(X_test_lstm, verbose=0)
lstm_preds      = np.argmax(lstm_preds_prob, axis=1)
lstm_acc        = accuracy_score(y_test, lstm_preds)

print(f"\n  Test Accuracy: {lstm_acc:.4f}  ({lstm_acc*100:.2f}%)")
print(f"\n  Classification Report:")
print(classification_report(
    y_test, lstm_preds,
    target_names=['weight_loss', 'maintenance', 'muscle_gain']
))

lstm_path = os.path.join(MODEL_DIR, 'lstm.keras')
lstm_model.save(lstm_path)
print(f"\n  Saved → {lstm_path}")

results.append({
    'model': 'LSTM',
    'test_accuracy': round(lstm_acc, 4),
    'cv_accuracy': None,
})


# ════════════════════════════════════════════════════════════════════════════
# ENSEMBLE — Average probabilities from all 4 models
# ════════════════════════════════════════════════════════════════════════════
print("\n" + "=" * 60)
print("ENSEMBLE — Combining all 4 models")
print("=" * 60)

# Get probabilities from each model
rf_probs   = rf.predict_proba(X_test)
lgb_probs  = lgb_model.predict_proba(X_test)
ann_probs  = ann.predict(X_test, verbose=0)
lstm_probs = lstm_model.predict(X_test_lstm, verbose=0)

# Average (equal weighting — adjust weights if one model is better)
ensemble_probs = (rf_probs + lgb_probs + ann_probs + lstm_probs) / 4
ensemble_preds = np.argmax(ensemble_probs, axis=1)
ensemble_acc   = accuracy_score(y_test, ensemble_preds)

print(f"\n  Ensemble Test Accuracy: {ensemble_acc:.4f}  ({ensemble_acc*100:.2f}%)")
print(f"\n  Classification Report:")
print(classification_report(
    y_test, ensemble_preds,
    target_names=['weight_loss', 'maintenance', 'muscle_gain']
))

results.append({
    'model': 'Ensemble (avg)',
    'test_accuracy': round(ensemble_acc, 4),
    'cv_accuracy': None,
})


# ════════════════════════════════════════════════════════════════════════════
# FINAL SUMMARY
# ════════════════════════════════════════════════════════════════════════════
print("\n" + "=" * 60)
print("FINAL RESULTS SUMMARY")
print("=" * 60)

results_df = pd.DataFrame(results)
print(results_df.to_string(index=False))

results_df.to_csv(os.path.join(MODEL_DIR, 'model_results.csv'), index=False)

best = results_df.loc[results_df['test_accuracy'].idxmax()]
print(f"\n  Best model: {best['model']} ({best['test_accuracy']*100:.2f}% accuracy)")

print(f"\n  Saved files:")
print(f"    {rf_path}")
print(f"    {lgb_path}")
print(f"    {ann_path}")
print(f"    {lstm_path}")
print(f"    {os.path.join(MODEL_DIR, 'model_results.csv')}")

# Save feature list for inference (important!)
with open(os.path.join(MODEL_DIR, 'feature_names.pkl'), 'wb') as f:
    pickle.dump(FEATURES, f)
print(f"    {os.path.join(MODEL_DIR, 'feature_names.pkl')}")

print("\n  Training complete.")