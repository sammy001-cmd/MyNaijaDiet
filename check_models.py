import pickle
import os

model_dir = 'recommender/ml'

print("Checking model files...")
print("=" * 40)

# Check pkl files
for f in ['random_forest.pkl', 'lightgbm.pkl', 'feature_names.pkl']:
    path = os.path.join(model_dir, f)
    try:
        size = os.path.getsize(path)
        with open(path, 'rb') as file:
            obj = pickle.load(file)
        print(f"OK   {f} — {size:,} bytes")
    except Exception as e:
        print(f"FAIL {f} — {e}")

# Check keras files
try:
    import tensorflow as tf
    for f in ['ann.keras', 'lstm.keras']:
        path = os.path.join(model_dir, f)
        try:
            size = os.path.getsize(path)
            model = tf.keras.models.load_model(path)
            print(f"OK   {f} — {size:,} bytes")
        except Exception as e:
            print(f"FAIL {f} — {e}")
except ImportError:
    print("FAIL tensorflow not installed")

print("=" * 40)
print("Done.")