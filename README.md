# 🎯 Shopify War Room

SaaS de inteligencia competitiva que monitorea tiendas Shopify,
guarda historial de precios y usa **Groq + LLaMA 3.3 70B** para
generar estrategias de mercado accionables.

---

## 📁 Estructura

```
shopify-war-room/
├── app.py           ← Servidor Flask (dashboard + API)
├── models.py        ← Modelos SQLAlchemy (DB)
├── scraper.py       ← Scraping de /products.json
├── ai_engine.py     ← Groq + LLaMA 3.3 70B
├── worker.py        ← Loop automático cada 1 hora
├── templates/
│   └── index.html   ← Dashboard dark mode
├── requirements.txt
├── Procfile         ← Railway deployment
└── .env.example
```

---

## 🚀 Setup Local

### 1. Clonar e instalar
```bash
git clone <tu-repo>
cd shopify-war-room
pip install -r requirements.txt
```

### 2. Configurar variables de entorno
```bash
cp .env.example .env
# Editar .env con tu GROQ_API_KEY y SECRET_KEY
```

### 3. Inicializar la base de datos
```bash
python -c "from app import create_app; from models import db; app = create_app(); app.app_context().push(); db.create_all(); print('DB creada ✓')"
```

### 4. Correr en local (2 terminales)

**Terminal 1 — Dashboard web:**
```bash
python app.py
# → http://localhost:5000
```

**Terminal 2 — Worker automático:**
```bash
python worker.py
```

---

## ☁️ Deploy en Railway

### Opción A: Railway CLI
```bash
railway login
railway init
railway up
```

### Opción B: GitHub
1. Subir el proyecto a GitHub
2. En Railway: **New Project → Deploy from GitHub**
3. Railway detecta el `Procfile` y crea dos procesos:
   - `web` → el dashboard Flask
   - `worker` → el loop de análisis

### Variables de entorno en Railway
En el panel de Railway, ir a **Variables** y agregar:
```
GROQ_API_KEY   = gsk_tu_clave_aqui
SECRET_KEY     = clave_aleatoria_segura
```
`DATABASE_URL` lo inyecta Railway automáticamente si agregás un plugin de PostgreSQL.

---

## 🔑 Conseguir la Groq API Key

1. Ir a [console.groq.com](https://console.groq.com)
2. Crear cuenta (gratis)
3. **API Keys → Create API Key**
4. Copiar la clave que empieza con `gsk_`

---

## 💡 Cómo funciona

1. **El usuario** agrega URLs de tiendas Shopify en el dashboard
2. **El worker** corre cada hora y:
   - Hace `GET {tienda}/products.json` → extrae precios
   - Guarda en `PriceHistory`
   - Manda los datos a LLaMA 3.3 70B
   - Guarda el análisis en `MarketAnalysis`
3. **El dashboard** muestra todo en tiempo real con:
   - Market Bias (AGGRESSIVE / DEFENSIVE / NEUTRAL)
   - Sentiment Score (0-100)
   - Alpha Opportunity (qué producto atacar)
   - High Conviction Bets (acciones concretas con % de éxito)

---

## 🛍️ Tiendas Shopify de ejemplo para probar

Cualquier tienda Shopify expone `/products.json` públicamente:
```
https://allbirds.com
https://gymshark.com
https://mvmtbrand.com
https://bombas.com
https://ruggable.com
```
