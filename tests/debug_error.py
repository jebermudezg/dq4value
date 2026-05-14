import pandas as pd
import traceback
import sys
sys.path.insert(0, '.')

from engine.parsers import parse_file
from engine.scorer import DQScorer

df, cols = parse_file('tests/dataset_1000.csv')
print(f"DataFrame shape: {df.shape}")
print(f"Index único: {df.index.is_unique}")
df = df.reset_index(drop=True)
print(f"Index único después de reset: {df.index.is_unique}")

scorer = DQScorer(df, 'cliente_id')
scorer.configure('email', {'completitud': {}, 'validez': {'regex_pattern': '^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\\.[a-zA-Z0-9-.]+$'}})
scorer.configure('edad', {'completitud': {}, 'exactitud': {'min_value': 0, 'max_value': 120}})

try:
    results = scorer.run_analysis()
    print("Análisis exitoso")
    print(f"Score general: {results['score_general']}")
except Exception as e:
    print(f"ERROR: {e}")
    traceback.print_exc()
