# from django.apps import AppConfig


# class RecommenderConfig(AppConfig):
#     name = "recommender"


import os
from django.apps import AppConfig


class RecommenderConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'recommender'

    def ready(self):
        """
        Load all ML models into memory once when Django starts.
        This prevents the 30-second delay on first request.
        Models are stored as module-level variables in ml_engine.py
        so they stay alive for the entire server lifetime.
        """
        # Skip during management commands like makemigrations, migrate etc.
        import sys
        if 'migrate' in sys.argv or 'makemigrations' in sys.argv:
            return

        try:
            # Suppress TensorFlow noise
            os.environ['TF_CPP_MIN_LOG_LEVEL']   = '3'
            os.environ['TF_ENABLE_ONEDNN_OPTS']  = '0'

            import logging
            logging.getLogger('tensorflow').setLevel(logging.ERROR)

            print('[MyNaijaDiet] Loading ML models...')
            import recommender.ml_engine  # noqa — triggers module load
            print('[MyNaijaDiet] ML models loaded successfully.')

        except Exception as e:
            print(f'[MyNaijaDiet] Warning: ML models could not be loaded — {e}')
            print('[MyNaijaDiet] App will run without ML. Falling back to DB queries.')