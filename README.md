# ⚽ Simulador de la Primera Nacional Argentina

Simulador estadístico de la **Primera Nacional Argentina** desarrollado en Python. El proyecto utiliza un modelo de goles basado en la distribución de **Poisson** junto con **simulaciones Monte Carlo** para proyectar el desarrollo completo del campeonato, estimando probabilidades de ascenso, descenso y posiciones finales de cada equipo.

Los resultados de las simulaciones se exportan a archivos JSON y se presentan mediante un dashboard interactivo desarrollado con HTML, CSS y JavaScript.

---

## Características

- Simulación completa de la temporada.
- Modelo de goles basado en distribución de Poisson.
- Miles de simulaciones Monte Carlo.
- Proyección de la tabla final.
- Simulación de la Final por el Primer Ascenso.
- Simulación completa del Reducido.
- Probabilidades de ascenso para todos los equipos.
- Probabilidades de descenso.
- Tabla esperada con puntos y posición promedio.
- Dashboard web moderno e interactivo.

---

## Tecnologías utilizadas

- Python
- HTML5
- CSS3
- JavaScript
- JSON

---

## Estructura del proyecto

```
.
├── public/                  # Dashboard web
├── api/
│   └── index.py             # API FastAPI, deployable en Render/Vercel
├── datos/                   # Bases de datos y archivos auxiliares
├── modelos/                 # Modelos estadísticos
├── main.py                  # Programa principal
├── servidor.py              # Servidor local (uso manual/dev, sin FastAPI)
├── rutas.py                 # Resuelve rutas de datos (local/Render/Vercel)
├── calcular_tabla.py
├── actualizar_datos.py
├── actualizar_resultados.py
├── scraper_promedios.py
├── mapeo_equipos.py
├── render.yaml
├── vercel.json
├── requirements.txt
└── README.md
```

---

## Modelo estadístico

El simulador combina diferentes técnicas para obtener proyecciones realistas:

- Distribución de Poisson para estimar goles.
- Fortaleza ofensiva y defensiva de cada equipo.
- Ventaja de localía.
- Regresión a la media.
- Ponderación temporal de resultados recientes.
- Miles de simulaciones Monte Carlo para calcular probabilidades.

---

## Dashboard

El reporte generado incluye:

- 📊 Tabla final simulada.
- 🏆 Final por el Primer Ascenso.
- 🔥 Cuadro completo del Reducido.
- 📈 Probabilidades de ascenso.
- 📉 Probabilidades de descenso.
- 📋 Tabla de posiciones esperadas.

---

## Instalación

Clonar el repositorio:

```bash
git clone https://github.com/soydequilmes7/Simulador-Primera-B-Nacional.git
```

Ingresar al proyecto:

```bash
cd Simulador-Primera-B-Nacional
```

Instalar dependencias:

```bash
pip install -r requirements.txt
```

---

## Ejecución

Ejecutar el simulador:

```bash
python main.py
```

Para visualizar el dashboard HTML:

```bash
python servidor.py
```

Luego abrir el navegador en:

```
http://localhost:8000
```

---

## API (FastAPI)

Además de `servidor.py` (servidor local simple), el backend está expuesto
como una API FastAPI en `api/index.py`. En Render, ese mismo proceso también
sirve el dashboard de `public/`.

### Correrla en local

```bash
uvicorn api.index:app --reload
```

Endpoints:

- `GET /api/health`
- `POST /api/simular` — body opcional `{"n_sims": 500}` (50-5000). Corre la
  simulación y devuelve el resultado en la respuesta.
- `POST /api/actualizar` — body opcional `{"n_sims": 500}`. Scrapea
  Promiedos, actualiza Supabase y re-simula si hay partidos nuevos.
- `POST /api/simular-lpf`
- `POST /api/actualizar-lpf`
- `POST /api/simular-campeon`
- `POST /api/simular-campeon-lpf`

### Desplegar en Render

El repo incluye `render.yaml` para crear un Web Service de Python con:

- Build Command: `pip install -r requirements.txt`
- Start Command: `uvicorn api.index:app --host 0.0.0.0 --port $PORT`
- Health Check Path: `/api/health`
- Variables: `PYTHON_VERSION=3.12`, `RENDER=true`,
  `SUPABASE_DB_URL`, `SUPABASE_SCHEMA=public`

Pasos:

```bash
git push origin <tu-rama>
```

Luego en Render:

1. New > Blueprint.
2. Seleccionar este repositorio.
3. Confirmar el servicio `simulador-primera-nacional-backend`.
4. Desplegar.

Render va a exponer el backend y el dashboard en la URL `*.onrender.com`.
`/api/health` debe responder `{"ok": true}` cuando el deploy esté listo.

### Persistencia con Supabase

La persistencia runtime usa Supabase Postgres. No hay fallback a CSV: si
`SUPABASE_DB_URL` falta o la conexión falla, los endpoints que leen datos
fallan explícitamente.

Variables necesarias:

- `SUPABASE_DB_URL`: connection string Postgres/pooler de Supabase.
- `SUPABASE_SCHEMA`: schema a usar, por defecto `public`.

Crear schema y poblar datos iniciales sin depender de `psql`:

```bash
export SUPABASE_DB_URL='postgresql://postgres.<project_ref>:<password>@aws-...pooler.supabase.com:6543/postgres'
python3 scripts/apply_migrations.py
python3 scripts/seed_supabase.py
```

`https://<project_ref>.supabase.co` es la URL HTTP del proyecto, no la URL
Postgres. La connection string correcta se copia desde Supabase Dashboard >
Project Settings > Database > Connection string.

El script de seed lee los CSV commiteados en `datos/`, inserta/upsertea ligas,
temporadas, equipos, alias, partidos, tablas, goleadores, promedios LPF y Copa,
y se puede correr más de una vez sin duplicar datos.

### Desplegar en Vercel

```bash
vercel deploy        # preview
vercel deploy --prod # producción
```

`vercel.json` enruta `/api/*` a `api/index.py`. Vercel detecta FastAPI
desde `requirements.txt`, carga la variable `app`, y sirve los archivos
de `public/` como sitio estático (el dashboard). La versión de Python
queda fijada en `.python-version`.

En Vercel, `render.yaml` no carga variables de entorno. Configurar estas
variables en Project Settings > Environment Variables, o con la CLI, para
los ambientes que correspondan:

```bash
vercel env add SUPABASE_DB_URL production
vercel env add SUPABASE_SCHEMA production
```

Para previews, repetir con `preview`. Después de cambiar variables de entorno
hay que crear un deployment nuevo (`vercel deploy --prod` o redeploy desde el
dashboard), porque Vercel no las aplica a deployments anteriores.

Usar como `SUPABASE_DB_URL` el connection string del pooler de Supabase
compatible con IPv4, preferentemente el Transaction pooler en puerto `6543`:

```text
postgresql://postgres.<project_ref>:<password>@aws-<region>.pooler.supabase.com:6543/postgres
```

Evitar el host directo `db.<project_ref>.supabase.co:5432` en Vercel salvo que
el proyecto tenga conectividad IPv4 dedicada, porque el directo de Supabase
resuelve por IPv6 y Vercel no siempre puede conectarse a ese destino.

Para validar el build local antes de subir:

```bash
vercel pull --yes --environment preview  # solo si el proyecto no está linkeado
vercel build
```

Con Supabase configurado, Vercel y Render comparten la misma persistencia:
`/api/actualizar-*` escribe en Postgres, `simulation_outputs` cachea los JSON
del dashboard, y `/api/datos-*` construye CSV en memoria desde la base para el
worker Pyodide del navegador.

---

## Objetivo

Este proyecto fue desarrollado con fines de análisis estadístico y simulación deportiva, buscando ofrecer una herramienta que permita proyectar distintos escenarios de la Primera Nacional mediante modelos probabilísticos.

---

## Autor

**El gonza**

GitHub:
https://github.com/soydequilmes7
