"""
tests/generar_datasets_prueba.py
Genera tres datasets con características distintas para la prueba integral v3.

Dataset A — prueba_tipograficos_800.csv  (errores de tipeo en nombres)
Dataset B — prueba_tokens_600.csv        (direcciones con tokens desordenados)
Dataset C — prueba_limpio_500.csv        (caso de control — casi sin problemas)

Cada dataset incluye columna entidad_real_id que indica la entidad "verdadera"
representada por cada fila. Registros con mismo entidad_real_id son duplicados reales.
"""
import sys, random
sys.path.insert(0, '.')

import pandas as pd
import numpy as np
from datetime import date, timedelta

random.seed(7)
np.random.seed(7)

# ──────────────────────────────────────────────────────────────────────────────
# Helpers compartidos
# ──────────────────────────────────────────────────────────────────────────────

def rand_date(start='2015-01-01', end='2024-12-31', fmt='%Y-%m-%d'):
    s = date.fromisoformat(start)
    e = date.fromisoformat(end)
    d = s + timedelta(days=random.randint(0, (e - s).days))
    return d.strftime(fmt)

def rand_phone():
    return f"9{random.randint(10000000, 99999999)}"

def rand_dni():
    return f"{random.randint(10000000, 99999999)}"

def _letra_adyacente(c):
    """Devuelve una letra adyacente en el teclado qwerty (aproximación)."""
    adj = {
        'a':'sq','b':'vn','c':'xv','d':'sf','e':'wr','f':'dg','g':'fh','h':'gj',
        'i':'uo','j':'hk','k':'jl','l':'kñ','m':'n','n':'bm','o':'ip','p':'oñ',
        'q':'wa','r':'et','s':'az','t':'ry','u':'yi','v':'bc','w':'qe','x':'zc',
        'y':'tu','z':'as',
    }
    c_lower = c.lower()
    if c_lower in adj:
        replacement = random.choice(adj[c_lower])
        return replacement.upper() if c.isupper() else replacement
    return c

def typo_transponer(s):
    """Transpone dos letras adyacentes."""
    if len(s) < 4: return s
    chars = list(s)
    i = random.randint(1, len(chars)-3)
    # evitar espacios
    while chars[i] == ' ' or chars[i+1] == ' ':
        i = random.randint(1, len(chars)-3)
    chars[i], chars[i+1] = chars[i+1], chars[i]
    return ''.join(chars)

def typo_faltante(s):
    """Elimina un carácter (no el primero ni espacio)."""
    indices = [i for i in range(1, len(s)-1) if s[i] != ' ']
    if not indices: return s
    i = random.choice(indices)
    return s[:i] + s[i+1:]

def typo_duplicado(s):
    """Duplica una letra."""
    indices = [i for i in range(1, len(s)-1) if s[i].isalpha()]
    if not indices: return s
    i = random.choice(indices)
    return s[:i] + s[i] + s[i:]

def typo_adyacente(s):
    """Reemplaza una letra por su adyacente en teclado."""
    indices = [i for i in range(1, len(s)) if s[i].isalpha()]
    if not indices: return s
    i = random.choice(indices)
    return s[:i] + _letra_adyacente(s[i]) + s[i+1:]

TYPO_FUNCS = [typo_transponer, typo_faltante, typo_duplicado, typo_adyacente]

# ──────────────────────────────────────────────────────────────────────────────
# DATASET A — prueba_tipograficos_800.csv
# ──────────────────────────────────────────────────────────────────────────────
print("Generando Dataset A — prueba_tipograficos_800.csv …")

APELLIDOS = [
    'Quispe','Mamani','Flores','Vargas','García','López','Rodríguez','Díaz',
    'Chávez','Reyes','Torres','Huanca','Ccopa','Condori','Lazo','Medina',
    'Ramos','Aguilar','Cruz','Herrera','Gonzales','Mendoza','Vega','Paredes',
    'Salcedo','Tapia','Huillca','Apaza','Cusi','Inca','Llerena','Poma',
    'Huamán','Ccari','Nina','Suca','Chura','Ticona','Mamani','Yucra',
]
NOMBRES_P = [
    'Carlos','Juan','Pedro','Luis','María','Rosa','Ana','Jorge','Miguel','Carmen',
    'José','Lucía','Elena','Diego','Gabriela','Patricia','Ricardo','Silvia','César',
    'Fabiola','Alejandro','Sofía','Fernando','Paola','Eduardo','Cecilia','Raúl',
    'Claudia','Óscar','Pilar',
]
CARGOS = ['Analista','Coordinador','Jefe de área','Supervisor','Asistente',
          'Gerente','Técnico','Especialista','Director','Auditor']
AREAS  = ['Finanzas','Recursos Humanos','Operaciones','Ventas','Logística',
          'Tecnología','Legal','Contabilidad']
NIVEL_EDU = ['Secundaria','Técnico','Bachiller','Titulado','Maestría']
ESTADOS   = ['Activo','Inactivo','Licencia','Retirado']

N_A = 800
N_GRUPOS_A = 25   # grupos de duplicados tipográficos
GRUPO_SIZE = 3    # cada grupo tiene 3 registros

rows_a = []
entidad_id = 1
problemas_a = {
    'nulos': 0, 'salario_fuera_rango': 0, 'fechas_formato_inconsistente': 0,
    'valores_fuera_catalogo': 0, 'dni_duplicado': 0, 'outliers_salario': 0,
}

# Base names for the 25 duplicate groups
base_names = []
for _ in range(N_GRUPOS_A):
    apellido1 = random.choice(APELLIDOS)
    apellido2 = random.choice(APELLIDOS)
    nombre    = random.choice(NOMBRES_P)
    base_names.append(f"{apellido1} {apellido2}, {nombre}")

# Pregenerate some DNIs to duplicate
base_dnis = [rand_dni() for _ in range(10)]

# Generate group rows first
group_eid_list = []
for g, base_name in enumerate(base_names):
    eid = g + 1
    group_eid_list.append(eid)
    for variant in range(GRUPO_SIZE):
        if variant == 0:
            nombre = base_name
        else:
            # Apply 1-2 typo functions
            nombre = base_name
            for _ in range(random.randint(1, 2)):
                fn = random.choice(TYPO_FUNCS)
                nombre = fn(nombre)

        dni = rand_dni()
        salario = round(random.uniform(1200, 15000), 2)
        rows_a.append({
            'entidad_real_id': eid,
            'nombre_completo': nombre,
            'dni': dni,
            'cargo': random.choice(CARGOS),
            'area': random.choice(AREAS),
            'salario_pen': salario,
            'fecha_ingreso': rand_date('2010-01-01', '2023-12-31'),
            'fecha_ultima_evaluacion': rand_date('2022-01-01', '2024-12-31'),
            'nivel_educativo': random.choice(NIVEL_EDU),
            'email_corporativo': f"{(nombre.split(',')[1].strip() if ',' in nombre else nombre.split()[0]).lower().replace(' ', '.')}@empresa.pe",
            'telefono': rand_phone(),
            'estado_laboral': random.choice(ESTADOS),
        })
    entidad_id = eid + 1

# Fill remaining rows (non-duplicates)
remaining = N_A - N_GRUPOS_A * GRUPO_SIZE
eid_counter = N_GRUPOS_A + 1
for i in range(remaining):
    apellido1 = random.choice(APELLIDOS)
    apellido2 = random.choice(APELLIDOS)
    nombre_p  = random.choice(NOMBRES_P)
    nombre = f"{apellido1} {apellido2}, {nombre_p}"
    dni = rand_dni()
    salario = round(random.uniform(1200, 15000), 2)
    rows_a.append({
        'entidad_real_id': eid_counter,
        'nombre_completo': nombre,
        'dni': dni,
        'cargo': random.choice(CARGOS),
        'area': random.choice(AREAS),
        'salario_pen': salario,
        'fecha_ingreso': rand_date('2010-01-01', '2023-12-31'),
        'fecha_ultima_evaluacion': rand_date('2022-01-01', '2024-12-31'),
        'nivel_educativo': random.choice(NIVEL_EDU),
        'email_corporativo': f"{nombre_p.lower()}@empresa.pe",
        'telefono': rand_phone(),
        'estado_laboral': random.choice(ESTADOS),
    })
    eid_counter += 1

df_a = pd.DataFrame(rows_a).sample(frac=1, random_state=7).reset_index(drop=True)
df_a.insert(0, 'empleado_id', range(1, len(df_a)+1))

# Inject problems
# ~30 nulos en nombre_completo y cargo
nulo_idx = random.sample(list(df_a[df_a['entidad_real_id'] > N_GRUPOS_A].index), 28)
for i in nulo_idx[:15]: df_a.at[i, 'nombre_completo'] = None
for i in nulo_idx[15:]: df_a.at[i, 'cargo'] = None
problemas_a['nulos'] = 28

# ~20 salarios fuera de rango (< 0 o > 100 000)
sal_idx = random.sample(list(df_a[df_a['entidad_real_id'] > N_GRUPOS_A].index), 20)
for i in sal_idx[:10]: df_a.at[i, 'salario_pen'] = round(random.uniform(-5000, -1), 2)
for i in sal_idx[10:]: df_a.at[i, 'salario_pen'] = round(random.uniform(100001, 200000), 2)
problemas_a['salario_fuera_rango'] = 20

# ~15 fechas en formato inconsistente (DD/MM/YYYY)
fecha_idx = random.sample(list(df_a[df_a['entidad_real_id'] > N_GRUPOS_A].index), 15)
for i in fecha_idx:
    d = rand_date('2010-01-01', '2023-12-31', fmt='%d/%m/%Y')
    df_a.at[i, 'fecha_ingreso'] = d
problemas_a['fechas_formato_inconsistente'] = 15

# ~25 valores fuera de catálogo
cat_idx = random.sample(list(df_a[df_a['entidad_real_id'] > N_GRUPOS_A].index), 25)
CARGOS_BAD = ['Pasante','Freelance','Consultor Externo','N/A','Sin cargo']
for i in cat_idx[:15]: df_a.at[i, 'cargo'] = random.choice(CARGOS_BAD)
AREAS_BAD  = ['Desconocida','Externa','Sin área']
for i in cat_idx[15:]: df_a.at[i, 'area'] = random.choice(AREAS_BAD)
problemas_a['valores_fuera_catalogo'] = 25

# ~10 DNIs duplicados
dup_dnis = [rand_dni() for _ in range(5)]
dup_idx = random.sample(list(df_a[df_a['entidad_real_id'] > N_GRUPOS_A].index), 10)
for k, i in enumerate(dup_idx):
    df_a.at[i, 'dni'] = dup_dnis[k % 5]
problemas_a['dni_duplicado'] = 10

# ~12 outliers de salario (IQR extremo)
out_idx = random.sample(list(df_a[df_a['entidad_real_id'] > N_GRUPOS_A].index), 12)
for i in out_idx:
    df_a.at[i, 'salario_pen'] = round(random.uniform(80000, 95000), 2)
problemas_a['outliers_salario'] = 12

df_a.to_csv('tests/prueba_tipograficos_800.csv', index=False)
print(f"  ✅ {len(df_a)} filas × {len(df_a.columns)} columnas → prueba_tipograficos_800.csv")
print(f"  Grupos duplicados reales: {N_GRUPOS_A}")
print(f"  Pares de duplicados reales: {N_GRUPOS_A * (GRUPO_SIZE*(GRUPO_SIZE-1)//2)}")
print(f"  Problemas insertados: {problemas_a}")

# ──────────────────────────────────────────────────────────────────────────────
# DATASET B — prueba_tokens_600.csv
# ──────────────────────────────────────────────────────────────────────────────
print("\nGenerando Dataset B — prueba_tokens_600.csv …")

TIPOS_VIA = ['Av.','Jr.','Ca.','Psj.','Urb.','Clle.']
TIPO_VIA_FULL = {'Av.':'Avenida','Jr.':'Jirón','Ca.':'Calle','Psj.':'Pasaje','Urb.':'Urbanización','Clle.':'Callejón'}
NOMBRES_VIA = [
    'Arequipa','Cusco','Lima','Tacna','Javier Prado','Angamos','La Marina',
    'Larco','Salaverry','Universitaria','Abancay','Ica','Huancavelica',
    'Moquegua','Puno','Amazonas','Huánuco','Piura','Cajamarca','Ayacucho',
    'Grau','Bolognesi','San Martín','Leguía','Wilson','Petit Thouars',
    'Arenales','Emancipación','Camaná','Garcilazo de la Vega',
]
DISTRITOS = [
    'Miraflores','San Isidro','Lince','Surco','La Molina','Barranco',
    'San Borja','Jesús María','Magdalena','Pueblo Libre','Chorrillos',
    'San Miguel','Breña','Rímac','La Victoria',
]
USOS = ['Residencial','Comercial','Industrial','Mixto','Institucional']
ESTADOS_PREDIO = ['Activo','Inactivo','En litigio']

N_B = 600
N_GRUPOS_B = 20
GRUPO_B_SIZE = 3

def base_direccion():
    tipo = random.choice(TIPOS_VIA)
    nombre = random.choice(NOMBRES_VIA)
    numero = random.randint(100, 3500)
    interior = f"Int. {random.randint(1,20)}" if random.random() < 0.3 else ""
    distrito = random.choice(DISTRITOS)
    partes = [f"{tipo} {nombre}", str(numero)]
    if interior: partes.append(interior)
    partes.append(distrito)
    return ' '.join(partes), tipo, nombre, numero, interior, distrito

def variante_tokens(base, tipo, nombre, numero, interior, distrito):
    """Genera variante con tokens en distinto orden, faltantes o abreviaturas."""
    modo = random.choice(['orden_invertido', 'token_faltante', 'abreviatura'])
    if modo == 'orden_invertido':
        # Distrito al inicio
        return f"{distrito} {tipo} {nombre} {numero}"
    elif modo == 'token_faltante':
        # Quitar interior o tipo de vía
        if interior:
            return f"{tipo} {nombre} {numero} {distrito}"
        else:
            return f"{nombre} {numero} {distrito}"
    else:  # abreviatura: tipo completo ↔ abreviado
        tipo_full = TIPO_VIA_FULL.get(tipo, tipo)
        return f"{tipo_full} {nombre} {numero} {distrito}"

rows_b = []
eid_b = 1

# Groups
for g in range(N_GRUPOS_B):
    base, tipo, nombre, numero, interior, distrito = base_direccion()
    for v in range(GRUPO_B_SIZE):
        if v == 0:
            dir_ = base
        else:
            dir_ = variante_tokens(base, tipo, nombre, numero, interior, distrito)
        rows_b.append({
            'entidad_real_id': eid_b,
            'direccion': dir_,
            'codigo_predio': f"P{eid_b:05d}",
            'distrito': distrito,
            'tipo_via': tipo.rstrip('.'),
            'area_m2': round(random.uniform(50, 1500), 1),
            'fecha_registro': rand_date('2010-01-01', '2024-12-31'),
            'valor_tasacion_pen': round(random.uniform(50000, 2000000), 2),
            'uso': random.choice(USOS),
            'estado_predio': random.choice(ESTADOS_PREDIO),
        })
    eid_b += 1

# Fill remaining
remaining_b = N_B - N_GRUPOS_B * GRUPO_B_SIZE
for i in range(remaining_b):
    base, tipo, nombre, numero, interior, distrito = base_direccion()
    rows_b.append({
        'entidad_real_id': eid_b,
        'direccion': base,
        'codigo_predio': f"P{eid_b:05d}",
        'distrito': distrito,
        'tipo_via': tipo.rstrip('.'),
        'area_m2': round(random.uniform(50, 1500), 1),
        'fecha_registro': rand_date('2010-01-01', '2024-12-31'),
        'valor_tasacion_pen': round(random.uniform(50000, 2000000), 2),
        'uso': random.choice(USOS),
        'estado_predio': random.choice(ESTADOS_PREDIO),
    })
    eid_b += 1

df_b = pd.DataFrame(rows_b).sample(frac=1, random_state=7).reset_index(drop=True)
df_b.insert(0, 'predio_id', range(1, len(df_b)+1))

# Inject problems proportionally (~8% each type)
prob_b = {'nulos':0,'fuera_catalogo':0,'fechas_inconsistentes':0,'areas_fuera_rango':0,'tasacion_outlier':0}
non_dup_b = list(df_b[df_b['entidad_real_id'] > N_GRUPOS_B].index)

nulos_b = random.sample(non_dup_b, min(18, len(non_dup_b)))
for i in nulos_b[:9]:  df_b.at[i, 'direccion'] = None
for i in nulos_b[9:]:  df_b.at[i, 'uso'] = None
prob_b['nulos'] = 18

cat_b = random.sample(non_dup_b, min(15, len(non_dup_b)))
for i in cat_b[:8]:  df_b.at[i, 'uso'] = 'Sin definir'
for i in cat_b[8:]:  df_b.at[i, 'estado_predio'] = 'Demolido'
prob_b['fuera_catalogo'] = 15

fecha_b = random.sample(non_dup_b, min(12, len(non_dup_b)))
for i in fecha_b:
    d = rand_date('2010-01-01','2024-12-31', fmt='%d/%m/%Y')
    df_b.at[i, 'fecha_registro'] = d
prob_b['fechas_inconsistentes'] = 12

area_b = random.sample(non_dup_b, min(10, len(non_dup_b)))
for i in area_b: df_b.at[i, 'area_m2'] = round(random.uniform(-100, -1), 1)
prob_b['areas_fuera_rango'] = 10

tas_b = random.sample(non_dup_b, min(10, len(non_dup_b)))
for i in tas_b: df_b.at[i, 'valor_tasacion_pen'] = round(random.uniform(5_000_000, 10_000_000), 2)
prob_b['tasacion_outlier'] = 10

df_b.to_csv('tests/prueba_tokens_600.csv', index=False)
print(f"  ✅ {len(df_b)} filas × {len(df_b.columns)} columnas → prueba_tokens_600.csv")
print(f"  Grupos duplicados reales: {N_GRUPOS_B}")
print(f"  Pares de duplicados reales: {N_GRUPOS_B * (GRUPO_B_SIZE*(GRUPO_B_SIZE-1)//2)}")
print(f"  Problemas insertados: {prob_b}")

# ──────────────────────────────────────────────────────────────────────────────
# DATASET C — prueba_limpio_500.csv (caso de control)
# ──────────────────────────────────────────────────────────────────────────────
print("\nGenerando Dataset C — prueba_limpio_500.csv …")

PRODUCTOS_CAT = ['Electrónica','Ropa','Alimentos','Hogar','Deporte',
                 'Libros','Juguetes','Herramientas','Farmacia','Automotriz']
CANALES = ['Web','App móvil','Tienda física','Teléfono','Email']
REGIONES = ['Lima','Arequipa','Trujillo','Piura','Cusco']

N_C = 500
N_GRUPOS_C = 3   # solo 3 grupos de duplicados difusos
GRUPO_C_SIZE = 2

rows_c = []
eid_c = 1

# 3 groups of fuzzy duplicates (minimal variation)
base_products = [
    'Laptop Dell Inspiron 15 Core i7',
    'Smartphone Samsung Galaxy A54 128GB Azul',
    'Auriculares Sony WH-1000XM5 Negro',
]
for g, bp in enumerate(base_products):
    # Variant: very slight typo
    variant = typo_adyacente(bp)
    for v, nombre_prod in enumerate([bp, variant]):
        rows_c.append({
            'entidad_real_id': eid_c,
            'cliente_id': eid_c * 10 + v,
            'nombre_producto': nombre_prod,
            'categoria': PRODUCTOS_CAT[g % len(PRODUCTOS_CAT)],
            'precio_pen': round(random.uniform(50, 5000), 2),
            'cantidad': random.randint(1, 100),
            'canal': random.choice(CANALES),
            'region': random.choice(REGIONES),
            'fecha_compra': rand_date('2023-01-01', '2024-12-31'),
            'descuento_pct': round(random.uniform(0, 30), 1),
        })
    eid_c += 1

# Fill remaining — clean data
for i in range(N_C - N_GRUPOS_C * GRUPO_C_SIZE):
    nombre = f"{random.choice(['Laptop','Monitor','Teclado','Mouse','Auriculares','Cámara','Tablet','Proyector','Impresora','Disco SSD'])} {random.choice(['HP','Dell','Logitech','Sony','Samsung','LG','Asus','Acer','Canon','Kingston'])} {random.randint(1,9)}{random.choice(['00','50','A','X','Pro'])}"
    rows_c.append({
        'entidad_real_id': eid_c,
        'cliente_id': eid_c * 10,
        'nombre_producto': nombre,
        'categoria': random.choice(PRODUCTOS_CAT),
        'precio_pen': round(random.uniform(50, 5000), 2),
        'cantidad': random.randint(1, 100),
        'canal': random.choice(CANALES),
        'region': random.choice(REGIONES),
        'fecha_compra': rand_date('2023-01-01', '2024-12-31'),
        'descuento_pct': round(random.uniform(0, 30), 1),
    })
    eid_c += 1

df_c = pd.DataFrame(rows_c).sample(frac=1, random_state=7).reset_index(drop=True)
df_c.insert(0, 'producto_id', range(1, len(df_c)+1))

prob_c = {'nulos':0,'precio_fuera_rango':0,'descuento_fuera_rango':0,'fuera_catalogo':0,'outliers':0}
non_dup_c = list(df_c[df_c['entidad_real_id'] > N_GRUPOS_C].index)

# Inject only ~15 total problems spread across dimensions
nulos_c = random.sample(non_dup_c, 4)
for i in nulos_c: df_c.at[i, 'nombre_producto'] = None
prob_c['nulos'] = 4

precio_c = random.sample([x for x in non_dup_c if x not in nulos_c], 3)
for i in precio_c: df_c.at[i, 'precio_pen'] = round(random.uniform(-200, -1), 2)
prob_c['precio_fuera_rango'] = 3

desc_c = random.sample([x for x in non_dup_c if x not in nulos_c + precio_c], 2)
for i in desc_c: df_c.at[i, 'descuento_pct'] = round(random.uniform(101, 150), 1)
prob_c['descuento_fuera_rango'] = 2

cat_c = random.sample([x for x in non_dup_c if x not in nulos_c + precio_c + desc_c], 3)
for i in cat_c: df_c.at[i, 'categoria'] = 'Desconocida'
prob_c['fuera_catalogo'] = 3

out_c = random.sample([x for x in non_dup_c if x not in nulos_c + precio_c + desc_c + cat_c], 3)
for i in out_c: df_c.at[i, 'precio_pen'] = round(random.uniform(50000, 80000), 2)
prob_c['outliers'] = 3

df_c.to_csv('tests/prueba_limpio_500.csv', index=False)
print(f"  ✅ {len(df_c)} filas × {len(df_c.columns)} columnas → prueba_limpio_500.csv")
print(f"  Grupos duplicados reales: {N_GRUPOS_C}")
print(f"  Pares de duplicados reales: {N_GRUPOS_C * (GRUPO_C_SIZE*(GRUPO_C_SIZE-1)//2)}")
print(f"  Problemas insertados: {prob_c}  (total: {sum(prob_c.values())})")

print("\n✅ Los tres datasets se generaron correctamente.")
