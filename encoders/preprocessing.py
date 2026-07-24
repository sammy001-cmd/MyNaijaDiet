"""
MyNaijaDiet — ML Preprocessing Pipeline
========================================
Input : mynaijadiet_dataset_v2.csv
Output: 
  - mynaijadiet_processed.csv      (encoded, scaled, ML-ready)
  - mynaijadiet_encoded_labels.csv (human-readable encoded view)
  - encoders/                      (saved LabelEncoders + Scaler for inference)

Steps:
  1. Load and inspect
  2. Expand multi-value meal_time into binary columns
  3. Label encode all ordinal categoricals
  4. One-hot encode nominal categoricals (region, taste_profile)
  5. Normalise numeric features (MinMaxScaler)
  6. Engineer derived features (calorie_density, macro_ratio_protein, etc.)
  7. Save encoders for use at inference time
  8. Save final processed CSV
"""

import os
import pickle
import numpy as np
import pandas as pd
from sklearn.preprocessing import LabelEncoder, MinMaxScaler

# ── Paths ──────────────────────────────────────────────────────────────────
BASE_DIR    = '/home/claude'
DATA_PATH   = os.path.join(BASE_DIR, 'mynaijadiet_dataset_v2.csv')
OUT_CSV     = os.path.join(BASE_DIR, 'mynaijadiet_processed.csv')
LABEL_CSV   = os.path.join(BASE_DIR, 'mynaijadiet_encoded_labels.csv')
ENCODER_DIR = os.path.join(BASE_DIR, 'encoders')
os.makedirs(ENCODER_DIR, exist_ok=True)


# ════════════════════════════════════════════════════════════════════════════
# STEP 1 — LOAD
# ════════════════════════════════════════════════════════════════════════════
print("=" * 60)
print("STEP 1 — Loading dataset")
print("=" * 60)

df = pd.read_csv(DATA_PATH)
print(f"Loaded {len(df)} rows × {len(df.columns)} columns")
print(f"Columns: {df.columns.tolist()}")

# Keep food_name aside — it's an identifier, not a feature
food_names = df['food_name'].copy()
df_processed = df.copy()


# ════════════════════════════════════════════════════════════════════════════
# STEP 2 — EXPAND meal_time (multi-value) INTO BINARY COLUMNS
# ════════════════════════════════════════════════════════════════════════════
print("\nSTEP 2 — Expanding meal_time into binary columns")

MEAL_TIMES = ['breakfast', 'lunch', 'dinner', 'snack']

for mt in MEAL_TIMES:
    df_processed[f'meal_time_{mt}'] = df_processed['meal_time'].apply(
        lambda x: 1 if mt in str(x).split(',') else 0
    )

# Drop original meal_time string column
df_processed.drop(columns=['meal_time'], inplace=True)

# Verify
for mt in MEAL_TIMES:
    count = df_processed[f'meal_time_{mt}'].sum()
    print(f"  meal_time_{mt}: {count} meals")


# ════════════════════════════════════════════════════════════════════════════
# STEP 3 — LABEL ENCODE ORDINAL COLUMNS
# Ordinal = columns where order matters
#   prep_time:   short < medium < long
#   price_range: low < medium < high
#   goal_suitability, diet_type, category — treated as ordinal for tree models
# ════════════════════════════════════════════════════════════════════════════
print("\nSTEP 3 — Label encoding ordinal columns")

# Manual ordinal mappings (preserves order meaning)
ORDINAL_MAPS = {
    'prep_time': {
        'short':  0,
        'medium': 1,
        'long':   2,
    },
    'price_range': {
        'low':    0,
        'medium': 1,
        'high':   2,
    },
    'goal_suitability': {
        'weight_loss': 0,
        'maintenance': 1,
        'muscle_gain': 2,
    },
    'diet_type': {
        'low-calorie':  0,
        'vegetarian':   1,
        'balanced':     2,
        'high-protein': 3,
        'energy-rich':  4,
        'indulgent':    5,
    },
    'category': {
        'breakfast': 0,
        'snack':     1,
        'lunch':     2,
        'dinner':    3,
    },
}

label_encoders = {}

for col, mapping in ORDINAL_MAPS.items():
    df_processed[col] = df_processed[col].map(mapping)
    label_encoders[col] = mapping
    print(f"  {col}: {mapping}")

# Save ordinal maps
with open(os.path.join(ENCODER_DIR, 'ordinal_maps.pkl'), 'wb') as f:
    pickle.dump(label_encoders, f)
print("  Saved ordinal_maps.pkl")


# ════════════════════════════════════════════════════════════════════════════
# STEP 4 — ONE-HOT ENCODE NOMINAL COLUMNS
# Nominal = no inherent order
#   region, taste_profile
# We use pandas get_dummies for simplicity; 
# drop_first=False so all models can see all categories
# ════════════════════════════════════════════════════════════════════════════
print("\nSTEP 4 — One-hot encoding nominal columns")

NOMINAL_COLS = ['region', 'taste_profile']

# Save the unique values so we can reconstruct at inference
nominal_categories = {}
for col in NOMINAL_COLS:
    nominal_categories[col] = sorted(df_processed[col].unique().tolist())
    print(f"  {col} ({len(nominal_categories[col])} categories): {nominal_categories[col]}")

with open(os.path.join(ENCODER_DIR, 'nominal_categories.pkl'), 'wb') as f:
    pickle.dump(nominal_categories, f)
print("  Saved nominal_categories.pkl")

df_processed = pd.get_dummies(df_processed, columns=NOMINAL_COLS, prefix=NOMINAL_COLS)

# Convert boolean dummies to int (0/1)
for col in df_processed.columns:
    if df_processed[col].dtype == bool:
        df_processed[col] = df_processed[col].astype(int)

ohe_cols = [c for c in df_processed.columns if c.startswith('region_') or c.startswith('taste_profile_')]
print(f"  Created {len(ohe_cols)} one-hot columns")


# ════════════════════════════════════════════════════════════════════════════
# STEP 5 — FEATURE ENGINEERING
# Derived features that help the model reason about nutrition
# ════════════════════════════════════════════════════════════════════════════
print("\nSTEP 5 — Feature engineering")

# Macro ratios (what % of calories come from each macro)
# Protein = 4 kcal/g, Carb = 4 kcal/g, Fat = 9 kcal/g
df_processed['kcal_from_protein'] = df_processed['protein_g'] * 4
df_processed['kcal_from_carb']    = df_processed['carb_g']    * 4
df_processed['kcal_from_fat']     = df_processed['fat_g']     * 9
df_processed['total_macro_kcal']  = (
    df_processed['kcal_from_protein'] +
    df_processed['kcal_from_carb']    +
    df_processed['kcal_from_fat']
)

# Avoid division by zero
safe_total = df_processed['total_macro_kcal'].replace(0, 1)

df_processed['macro_ratio_protein'] = (df_processed['kcal_from_protein'] / safe_total).round(4)
df_processed['macro_ratio_carb']    = (df_processed['kcal_from_carb']    / safe_total).round(4)
df_processed['macro_ratio_fat']     = (df_processed['kcal_from_fat']     / safe_total).round(4)

# Drop intermediate columns
df_processed.drop(columns=['kcal_from_protein','kcal_from_carb','kcal_from_fat','total_macro_kcal'], inplace=True)

# Calorie density bucket (low / medium / high)
# Based on WHO general guidance: <300 light, 300-600 moderate, >600 heavy
df_processed['calorie_density'] = pd.cut(
    df_processed['calories_kcal'],
    bins=[0, 300, 600, 9999],
    labels=[0, 1, 2]   # 0=light, 1=moderate, 2=heavy
).astype(int)

# Protein density (protein per 100 kcal — useful for muscle gain targeting)
df_processed['protein_per_100kcal'] = (
    (df_processed['protein_g'] / df_processed['calories_kcal']) * 100
).round(2)

print("  Created: macro_ratio_protein, macro_ratio_carb, macro_ratio_fat")
print("  Created: calorie_density (0=light, 1=moderate, 2=heavy)")
print("  Created: protein_per_100kcal")


# ════════════════════════════════════════════════════════════════════════════
# STEP 6 — NORMALISE NUMERIC FEATURES (MinMaxScaler → 0 to 1)
# Applied to: calories_kcal, protein_g, carb_g, fat_g,
#             macro ratios, protein_per_100kcal
# NOT applied to: binary columns, ordinal encoded columns (already 0-5)
# ════════════════════════════════════════════════════════════════════════════
print("\nSTEP 6 — Normalising numeric features")

SCALE_COLS = [
    'calories_kcal',
    'protein_g',
    'carb_g',
    'fat_g',
    'macro_ratio_protein',
    'macro_ratio_carb',
    'macro_ratio_fat',
    'protein_per_100kcal',
]

scaler = MinMaxScaler()
df_processed[SCALE_COLS] = scaler.fit_transform(df_processed[SCALE_COLS])

# Round to 6 decimal places for cleanliness
df_processed[SCALE_COLS] = df_processed[SCALE_COLS].round(6)

# Save scaler for inference
with open(os.path.join(ENCODER_DIR, 'minmax_scaler.pkl'), 'wb') as f:
    pickle.dump(scaler, f)
print(f"  Scaled {len(SCALE_COLS)} numeric columns: {SCALE_COLS}")
print("  Saved minmax_scaler.pkl")


# ════════════════════════════════════════════════════════════════════════════
# STEP 7 — DROP food_name (identifier, not a feature)
#          Keep a mapping file for reverse lookup
# ════════════════════════════════════════════════════════════════════════════
print("\nSTEP 7 — Finalising columns")

# Add meal_id for reverse lookup
df_processed.insert(0, 'meal_id', range(len(df_processed)))
food_names.index = range(len(food_names))

# Save the id → name mapping
id_name_map = pd.DataFrame({
    'meal_id':   df_processed['meal_id'],
    'food_name': food_names,
})
id_name_map.to_csv(os.path.join(BASE_DIR, 'meal_id_map.csv'), index=False)
print("  Saved meal_id_map.csv (for reverse lookup at inference)")

# Drop food_name from processed features
df_processed.drop(columns=['food_name'], inplace=True)

print(f"\n  Final shape: {df_processed.shape}")
print(f"  Final columns ({len(df_processed.columns)}):")
for col in df_processed.columns:
    print(f"    {col}: {df_processed[col].dtype}  | min={df_processed[col].min():.4f}  max={df_processed[col].max():.4f}")


# ════════════════════════════════════════════════════════════════════════════
# STEP 8 — SAVE OUTPUTS
# ════════════════════════════════════════════════════════════════════════════
print("\nSTEP 8 — Saving outputs")

df_processed.to_csv(OUT_CSV, index=False)
print(f"  Saved processed dataset → {OUT_CSV}")

# Also save a human-readable version with original labels alongside
df_readable = df.copy()
df_readable.insert(0, 'meal_id', range(len(df_readable)))
df_readable.to_csv(LABEL_CSV, index=False)
print(f"  Saved labelled dataset  → {LABEL_CSV}")


# ════════════════════════════════════════════════════════════════════════════
# FINAL SUMMARY
# ════════════════════════════════════════════════════════════════════════════
print("\n" + "=" * 60)
print("PREPROCESSING COMPLETE")
print("=" * 60)
print(f"  Input rows:         {len(df)}")
print(f"  Output rows:        {len(df_processed)}")
print(f"  Input features:     {len(df.columns)}")
print(f"  Output features:    {len(df_processed.columns)}")
print(f"\n  Saved files:")
print(f"    {OUT_CSV}")
print(f"    {LABEL_CSV}")
print(f"    encoders/ordinal_maps.pkl")
print(f"    encoders/nominal_categories.pkl")
print(f"    encoders/minmax_scaler.pkl")
print(f"    meal_id_map.csv")

print("\n  Feature groups in final dataset:")
print(f"    Numeric (scaled):  {SCALE_COLS}")
print(f"    Ordinal encoded:   {list(ORDINAL_MAPS.keys())}")
print(f"    Binary (meal_time):{[f'meal_time_{mt}' for mt in MEAL_TIMES]}")
print(f"    Engineered:        calorie_density, protein_per_100kcal, macro_ratio_*")
ohe = [c for c in df_processed.columns if c.startswith('region_') or c.startswith('taste_profile_')]
print(f"    One-hot encoded:   {len(ohe)} columns (region + taste_profile)")