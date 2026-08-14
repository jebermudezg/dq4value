"""
Genera datasets escalados de razones sociales peruanas con duplicados sembrados.
Salida: tests/escala_5k.csv, tests/escala_20k.csv, tests/escala_50k.csv

Columnas: empresa_id, razon_social, entidad_real_id
Garantías:
  - Los no-duplicados son genuinamente distintos (verificado por muestreo de pares)
  - Los duplicados sembrados usan 5 tipos: abreviatura, sin tildes→typo, sufijo,
    palabra extra, y combinación
  - entidad_real_id agrupa originales + variantes

Ejecutar: python3 tests/generar_escala.py
"""
import itertools
import random
import sys
from pathlib import Path

import pandas as pd

# Reproducibilidad
random.seed(42)

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from engine.dimensions.similitud import _normalizar, _calcular_similitud

# ── Vocabulario ────────────────────────────────────────────────────────────────
# 28 actividades — sin pares con raíz compartida larga (ej. import/export evitado)
ACTIVIDADES = [
    'Importaciones', 'Distribuciones', 'Fabricaciones', 'Construcciones',
    'Representaciones', 'Inversiones', 'Servicios', 'Logistica',
    'Transportes', 'Tecnologias', 'Proyectos', 'Instalaciones',
    'Consultores', 'Desarrollos', 'Manufacturas', 'Abastecimientos',
    'Gestion', 'Ingenieria', 'Suministros', 'Comercializadora',
    'Procesamiento', 'Soluciones', 'Capacitaciones', 'Acabados',
    'Operaciones', 'Sistemas', 'Productos', 'Investigaciones',
]

# 55 palabras geográficas / descriptores primarios
GEOGRAFICOS = [
    'Lima', 'Callao', 'Arequipa', 'Trujillo', 'Cusco', 'Piura',
    'Chiclayo', 'Tacna', 'Puno', 'Huancayo', 'Ayacucho', 'Cajamarca',
    'Chimbote', 'Iquitos', 'Pucallpa', 'Moquegua', 'Tumbes', 'Huaraz',
    'Tarapoto', 'Huanuco', 'Abancay', 'Sullana', 'Nazca', 'Chincha',
    'Andino', 'Pacifico', 'Norte', 'Sur', 'Central', 'Nacional',
    'Global', 'Internacional', 'Continental', 'Universal', 'Amazonica',
    'Costera', 'Tropical', 'Peruana', 'Americana', 'Surena',
    'Norteña', 'Fluvial', 'Marina', 'Sierra', 'Selva',
    'Altiplano', 'Valle', 'Delta', 'Costena', 'Interior',
    'Pacifico', 'Andina', 'Oriental', 'Occidental', 'Meridional',
    'Septentrional',
]

# 55 apellidos / descriptores secundarios — fonética variada
DESCRIPTORES = [
    'Quispe', 'Mamani', 'Condori', 'Flores', 'Garcia', 'Lopez',
    'Rodriguez', 'Hernandez', 'Torres', 'Vargas', 'Ramos', 'Cruz',
    'Chavez', 'Mendoza', 'Huanca', 'Ccopa', 'Limachi', 'Apaza',
    'Churata', 'Ticona', 'Yana', 'Tarqui', 'Cutipa', 'Velasquez',
    'Sanchez', 'Martinez', 'Gutierrez', 'Rojas', 'Morales', 'Castillo',
    'Reyes', 'Paredes', 'Vega', 'Salinas', 'Ramirez', 'Castro',
    'Ortega', 'Medina', 'Nunez', 'Pena', 'Aliaga', 'Caceres',
    'Palomino', 'Delgado', 'Fuentes', 'Carpio', 'Benavides', 'Pizarro',
    'Alvarado', 'Bustamante', 'Cornejo', 'Espinoza', 'Gomez', 'Herrera',
    'Jimenez',
]

# Sufijos — se alternan aleatoriamente en los originales
SUFIJOS = ['S.A.C.', 'S.A.', 'E.I.R.L.', 'S.R.L.', 'S.C.R.L.']

# Sufijos compactos (para variantes tipo "sufijo compacto")
SUFIJOS_COMPACT = ['SAC', 'SA', 'EIRL', 'SRL', 'SCRL']

# Palabras extra para variantes tipo "palabra adicional"
EXTRA_WORDS = ['del Peru', 'y Asociados', 'International', 'Group', 'Corp']


def _nombre_base(act, geo, desc, suf):
    return f'{act} {geo} {desc} {suf}'


def _generar_variante(nombre_base, act, geo, desc, suf, tipo):
    """
    Genera una variante del nombre base sin que colapse a exactamente igual
    después de normalización (excepto tipos 'sin tildes' / 'mayusculas' que
    sí colapsan — en ese caso usamos un typo para preservar el interés de prueba).

    Tipos:
      1  abreviatura   — trunca una palabra de contenido (geo o descriptor)
      2  typo          — un carácter cambiado en el descriptor
      3  sufijo        — elimina el sufijo (o lo pone compacto)
      4  extra         — agrega una palabra al final (antes del sufijo)
      5  combinacion   — typo + sin sufijo
    """
    suf_idx = SUFIJOS.index(suf) if suf in SUFIJOS else 0
    suf_compact = SUFIJOS_COMPACT[suf_idx]

    if tipo == 1:          # abreviatura de palabra geográfica
        geo_abrev = geo[:max(3, len(geo) - 2)]   # ej. Lima→Lim, Arequipa→Areq
        return f'{act} {geo_abrev} {desc} {suf}'

    elif tipo == 2:        # typo en el descriptor (un carácter cambiado)
        chars = list(desc)
        pos = max(1, len(chars) // 2)  # posición central
        old_c = chars[pos]
        # cambiar por una letra próxima en el teclado
        typo_map = {'a': 'e', 'e': 'a', 'i': 'y', 'o': 'u', 'u': 'o',
                    'r': 'l', 'l': 'r', 'n': 'm', 'm': 'n',
                    's': 'z', 'z': 's', 'c': 'k', 'k': 'c',
                    'p': 'b', 'b': 'p', 'g': 'j', 'j': 'g',
                    'v': 'f', 'f': 'v', 'd': 't', 't': 'd',
                    'h': 'x', 'x': 'h'}
        new_c = typo_map.get(old_c.lower(), 'x')
        chars[pos] = new_c
        desc_typo = ''.join(chars)
        return f'{act} {geo} {desc_typo} {suf}'

    elif tipo == 3:        # sufijo compacto o sin sufijo
        if random.random() < 0.5:
            return f'{act} {geo} {desc} {suf_compact}'
        else:
            return f'{act} {geo} {desc}'   # sin sufijo

    elif tipo == 4:        # palabra extra antes del sufijo
        extra = random.choice(EXTRA_WORDS)
        return f'{act} {geo} {desc} {extra} {suf}'

    elif tipo == 5:        # combinacion: typo + sin sufijo
        chars = list(desc)
        pos = min(2, len(chars) - 1)
        old_c = chars[pos]
        typo_map = {'a': 'e', 'e': 'a', 'i': 'y', 'o': 'u', 'u': 'o',
                    'r': 'l', 'l': 'r', 'n': 'm', 'm': 'n',
                    's': 'z', 'z': 's', 'c': 'k', 'k': 'c',
                    'p': 'b', 'b': 'p', 'g': 'j', 'j': 'g'}
        new_c = typo_map.get(old_c.lower(), 'x')
        chars[pos] = new_c
        desc_typo = ''.join(chars)
        return f'{act} {geo} {desc_typo}'   # sin sufijo y con typo

    return nombre_base   # fallback


def _spot_check_similarity(nombres_unicos, n_sample=8000, umbral=85):
    """
    Muestrea n_sample pares de la lista de nombres únicos y verifica que
    ningún par no-duplicado supere el umbral de qgrams.
    Devuelve (pares_revisados, max_sim, n_sobre_umbral, ejemplos).
    """
    print(f'  Verificando similitud: muestreo de {n_sample} pares aleatorios...')
    sample = random.sample(list(range(len(nombres_unicos))), min(200, len(nombres_unicos)))
    pares_muestra = list(itertools.combinations(sample, 2))
    if len(pares_muestra) > n_sample:
        pares_muestra = random.sample(pares_muestra, n_sample)

    max_sim = 0.0
    sobre_umbral = []
    norms = [_normalizar(n) for n in nombres_unicos]

    for a, b in pares_muestra:
        sim = _calcular_similitud(norms[a], norms[b], 'qgrams')
        if sim > max_sim:
            max_sim = sim
        if sim > umbral:
            sobre_umbral.append((sim, nombres_unicos[a], nombres_unicos[b]))

    return len(pares_muestra), max_sim, len(sobre_umbral), sobre_umbral[:3]


def generar_dataset(n_filas, n_grupos, nombre_archivo):
    """
    Genera un CSV con n_filas filas, de las cuales n_grupos × avg_variantes
    son duplicados sembrados.
    """
    print(f'\n{"="*70}')
    print(f'  Generando {nombre_archivo}  ({n_filas} filas, {n_grupos} grupos)')
    print(f'{"="*70}')

    # ── Paso 1: generar pool de nombres base únicos ────────────────────────
    combos = list(itertools.product(ACTIVIDADES, GEOGRAFICOS, DESCRIPTORES))
    random.shuffle(combos)

    filas_para_grupos = n_grupos * 2   # reserva espacio para variantes
    n_no_dup_base = n_filas - filas_para_grupos
    total_base_needed = n_no_dup_base + n_grupos   # originales + no-dups
    if total_base_needed > len(combos):
        print(f'  ⚠️  No hay suficientes combinaciones ({len(combos)}). '
              f'Reducir n_filas o vocabulario.')
        sys.exit(1)

    combos_seleccionados = combos[:total_base_needed]
    sufijos_asignados    = [SUFIJOS[i % len(SUFIJOS)] for i in range(total_base_needed)]

    base_nombres = [
        _nombre_base(a, g, d, s)
        for (a, g, d), s in zip(combos_seleccionados, sufijos_asignados)
    ]

    # Separar: primeros n_grupos serán los originales de grupos de dups
    originales_combos = combos_seleccionados[:n_grupos]
    originales_sufs   = sufijos_asignados[:n_grupos]
    originales_names  = base_nombres[:n_grupos]
    no_dup_names      = base_nombres[n_grupos:]

    # ── Paso 2: spot-check de similitud en no-duplicados ──────────────────
    n_sample_pairs, max_sim, n_sobre, ejemplos = _spot_check_similarity(
        no_dup_names, n_sample=8000, umbral=85
    )
    print(f'  Spot-check ({n_sample_pairs} pares): max similitud = {max_sim:.1f}%'
          f'  |  pares ≥ 85%: {n_sobre}')
    if n_sobre > 0:
        print('  ⚠️  Ejemplos sobre umbral:')
        for sim, a, b in ejemplos:
            print(f'     {sim:.1f}%  "{a}" / "{b}"')

    # ── Paso 3: generar variantes para cada grupo ─────────────────────────
    tipos_disponibles = [1, 2, 3, 4, 5]
    registros = []
    emp_id    = 1
    ent_id    = 1   # entidad_real_id empieza en 1
    pares_verdaderos = set()

    for idx in range(n_grupos):
        act, geo, desc = originales_combos[idx]
        suf = originales_sufs[idx]
        nombre_orig = originales_names[idx]

        # Determinar cuántas variantes: 1 o 2 (con distribución 70%/30%)
        n_var = 1 if random.random() < 0.70 else 2

        # Elegir tipos de variante sin repetir
        tipos_elegidos = random.sample(tipos_disponibles, n_var)
        variantes = []
        for tipo in tipos_elegidos:
            v = _generar_variante(nombre_orig, act, geo, desc, suf, tipo)
            # Si la variante colapsa a idéntica (por normalization), usar tipo 2
            if _normalizar(v) == _normalizar(nombre_orig):
                v = _generar_variante(nombre_orig, act, geo, desc, suf, 2)
            variantes.append(v)

        # Registrar original
        registros.append({'empresa_id': emp_id, 'razon_social': nombre_orig,
                          'entidad_real_id': ent_id})
        ids_grupo = [emp_id]
        emp_id += 1

        # Registrar variantes
        for v in variantes:
            registros.append({'empresa_id': emp_id, 'razon_social': v,
                              'entidad_real_id': ent_id})
            ids_grupo.append(emp_id)
            emp_id += 1

        # Verdad: combinaciones de IDs dentro del grupo
        for a, b in itertools.combinations(sorted(ids_grupo), 2):
            pares_verdaderos.add((a, b))

        ent_id += 1

    # ── Paso 4: agregar filas no-duplicadas ───────────────────────────────
    n_ya_generados = sum(1 + (1 if random.random() < 0.70 else 2)
                         for _ in range(n_grupos))
    # Ajuste: rellenar hasta n_filas con no-dups
    n_dups_reales = len(registros)
    n_no_dups_needed = max(0, n_filas - n_dups_reales)

    no_dup_muestra = no_dup_names[:n_no_dups_needed]
    for nombre in no_dup_muestra:
        registros.append({'empresa_id': emp_id, 'razon_social': nombre,
                          'entidad_real_id': ent_id})
        emp_id  += 1
        ent_id  += 1

    # ── Paso 5: mezclar y guardar ──────────────────────────────────────────
    random.shuffle(registros)
    # Re-numerar empresa_id tras el shuffle
    for i, r in enumerate(registros, 1):
        r['empresa_id'] = i

    df = pd.DataFrame(registros)
    out_path = Path(__file__).parent / nombre_archivo
    df.to_csv(out_path, index=False)

    n_filas_real      = len(df)
    n_unicos_norm     = df['razon_social'].apply(_normalizar).nunique()
    n_pares_verdad    = len(pares_verdaderos)
    n_grupos_real     = df['entidad_real_id'].value_counts()
    n_grupos_2plus    = (n_grupos_real >= 2).sum()

    print(f'  Filas totales:         {n_filas_real}')
    print(f'  Valores únicos (norm): {n_unicos_norm}')
    print(f'  Grupos de dups:        {n_grupos_2plus}  (objetivo: {n_grupos})')
    print(f'  Pares verdaderos:      {n_pares_verdad}')
    print(f'  Guardado en:           {out_path}')

    return n_pares_verdad


# ── Main ───────────────────────────────────────────────────────────────────────
if __name__ == '__main__':
    resultados = {}

    configs = [
        (5_000,  150, 'escala_5k.csv'),
        (20_000, 600, 'escala_20k.csv'),
        (50_000, 1500, 'escala_50k.csv'),
    ]

    for n_filas, n_grupos, archivo in configs:
        n_pares = generar_dataset(n_filas, n_grupos, archivo)
        resultados[archivo] = n_pares

    print('\n\n' + '='*70)
    print('  RESUMEN GENERACIÓN')
    print('='*70)
    for archivo, n_pares in resultados.items():
        print(f'  {archivo:<22}  pares verdaderos: {n_pares}')
    print('\nListo. Ejecutar tests/medir_escala.py para la medición.')
