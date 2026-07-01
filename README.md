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
├── PAGINAHTML/              # Dashboard web
├── datos/                   # Bases de datos y archivos auxiliares
├── modelos/                 # Modelos estadísticos
├── main.py                  # Programa principal
├── servidor.py              # Servidor local
├── calcular_tabla.py
├── actualizar_datos.py
├── actualizar_resultados.py
├── scraper_promedios.py
├── mapeo_equipos.py
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

## Objetivo

Este proyecto fue desarrollado con fines de análisis estadístico y simulación deportiva, buscando ofrecer una herramienta que permita proyectar distintos escenarios de la Primera Nacional mediante modelos probabilísticos.

---

## Autor

**Matías Sosa**

GitHub:
https://github.com/soydequilmes7
