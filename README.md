# Data Quality Platform

Plataforma para analizar y puntuar la calidad de datasets estructurados (CSV, Excel), con análisis inteligente potenciado por Claude de Anthropic y generación de reportes en PDF.

## ¿Qué hace?

1. **Ingesta de archivos** — Acepta archivos CSV y Excel a través de una API REST construida con FastAPI.
2. **Análisis de calidad** — Evalúa el dataset en seis dimensiones estándar de calidad de datos:
   - **Completitud**: porcentaje de valores no nulos
   - **Unicidad**: detección de filas y valores duplicados
   - **Validez**: conformidad de los datos con tipos y formatos esperados
   - **Consistencia**: coherencia entre columnas relacionadas
   - **Puntualidad**: frescura de los datos cuando hay campos de fecha
   - **Exactitud**: detección de outliers y valores anómalos
3. **Score global** — Combina las dimensiones en un score de 0 a 100 con pesos configurables.
4. **Análisis con IA** — Envía los resultados a Claude (Anthropic) para obtener un diagnóstico narrativo y recomendaciones accionables.
5. **Reporte PDF** — Genera un reporte descargable con hallazgos, gráficos y recomendaciones usando ReportLab.

## Estructura del proyecto

```
data-quality-platform/
├── api/
│   └── main.py            # Endpoints FastAPI
├── engine/
│   ├── parsers.py         # Lectura de CSV y Excel
│   ├── scorer.py          # Orquestación del scoring
│   └── dimensions/        # Lógica por dimensión de calidad
├── ai/
│   └── claude_analyzer.py # Integración con Anthropic
├── tests/                 # Tests con pytest
├── requirements.txt
└── README.md
```

## Instalación

```bash
pip install -r requirements.txt
```

## Uso

```bash
uvicorn api.main:app --reload
```

Accede a la documentación interactiva en `http://localhost:8000/docs`.
