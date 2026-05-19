# tests/validar_brecha_afin.py
import sys
sys.path.insert(0, '.')
from engine.dimensions.similitud import _brecha_afin, _calcular_similitud, _normalizar

casos_abreviatura = [
    ("juan alberto garcia lopez", "juan a garcia lopez"),
    ("maria fernanda torres", "m f torres"),
    ("telefonica del peru saa", "tel peru"),
    ("avenida siempre viva 123", "av siempre viva 123"),
    ("juan carlos perez gomez", "juan c perez g"),
]
algoritmos = ['brecha_afin', 'jaro_winkler', 'levenshtein', 'monge_elkan', 'qgrams']

print("\n=== VALIDACIÓN BRECHA AFÍN vs OTROS ALGORITMOS ===")
print("Casos de abreviaturas — mayor score = mejor detección\n")
print(f"{'Caso':<40}", end="")
for alg in algoritmos:
    print(f"{alg[:12]:>13}", end="")
print()
print("-" * 105)
for a, b in casos_abreviatura:
    a_n = _normalizar(a)
    b_n = _normalizar(b)
    print(f"{a[:20]+' vs '+b[:15]:<40}", end="")
    for alg in algoritmos:
        score = _calcular_similitud(a_n, b_n, alg)
        print(f"{score:>12.1f}%", end="")
    print()

print("\nEjecutar con: python3 tests/validar_brecha_afin.py")
