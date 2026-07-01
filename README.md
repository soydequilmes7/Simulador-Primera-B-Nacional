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
├── public/                  # Dashboard web (se sirve estático en Vercel)
├── api/
│   └── index.py             # API FastAPI, deployable como Vercel Function
├── datos/                   # Bases de datos y archivos auxiliares
├── modelos/                 # Modelos estadísticos
├── main.py                  # Programa principal
├── servidor.py              # Servidor local (uso manual/dev, sin FastAPI)
├── rutas.py                 # Resuelve rutas de datos (local vs Vercel)
├── calcular_tabla.py
├── actualizar_datos.py
├── actualizar_resultados.py
├── scraper_promedios.py
├── mapeo_equipos.py
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

## API (FastAPI) y despliegue en Vercel

Además de `servidor.py` (servidor local simple), el backend está expuesto
como una API FastAPI en `api/index.py`, pensada para desplegarse como
Vercel Function.

### Correrla en local

```bash
uvicorn api.index:app --reload
```

Endpoints:

- `GET /api/health`
- `POST /api/simular` — body opcional `{"n_sims": 1000}` (50-5000). Corre la
  simulación y devuelve el resultado en la respuesta.
- `POST /api/actualizar` — body opcional `{"n_sims": 1000}`. Scrapea
  Promiedos, actualiza `datos/` y re-simula si hay partidos nuevos.

### Desplegar en Vercel

```bash
vercel deploy        # preview
vercel deploy --prod # producción
```

`vercel.json` ya enruta `/api/*` a `api/index.py` y sirve `public/`
como sitio estático (el dashboard).

### ⚠️ Limitación importante: persistencia en Vercel

El filesystem de un deploy de Vercel es de **solo lectura** (salvo
`/tmp`, que no persiste entre cold starts, no se comparte entre
instancias y se pierde en cada redeploy). Esto afecta a `/api/actualizar`,
que scrapea Promiedos y actualiza `datos/fixture.csv`, `resultados.csv`,
`tabla.csv` y `goleadores.csv`:

- Esos cambios se escriben en `/tmp` (ver `rutas.py`), así que el endpoint
  funciona de punta a punta dentro de una misma instancia tibia.
- Pero no son durables: una instancia nueva (cold start, redeploy, otra
  región) vuelve a arrancar desde los CSV commiteados en el repo.

Si necesitás que los datos actualizados persistan de verdad entre
requests, las opciones son: migrar `datos/` a una base de datos real
(Vercel Postgres, KV, etc.), o seguir corriendo `actualizar_resultados.py`
en un entorno con filesystem persistente (local, o un job de CI que
commitee los CSV actualizados) y dejar que Vercel solo sirva `/api/simular`
y el dashboard estático.

`/api/simular` no tiene este problema: es puramente de lectura + cómputo,
no necesita escribir nada.

---

## Objetivo

Este proyecto fue desarrollado con fines de análisis estadístico y simulación deportiva, buscando ofrecer una herramienta que permita proyectar distintos escenarios de la Primera Nacional mediante modelos probabilísticos.

---

## Autor

**El gonza**

GitHub:
https://github.com/soydequilmes7
