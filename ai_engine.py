# ai_engine.py — Shopify War Room · Motor de Inteligencia Artificial

# 

# Usa Groq + LLaMA 3.3 70B para analizar precios de competidores

# y generar estrategias de mercado accionables en JSON.

import json
import logging
import os
import re
from datetime import datetime

from groq import Groq

log = logging.getLogger(“war_room.ai”)

GROQ_MODEL = “llama-3.3-70b-versatile”

SYSTEM_PROMPT_ES = “”“Eres un Lead Estratega de E-commerce y Data Quant con 15 años de experiencia
en inteligencia competitiva, estrategia de precios y dinámica del mercado Shopify.

Tu trabajo es analizar datos de productos de competidores y devolver una tesis de mercado precisa y accionable.

SIEMPRE respondes con un único objeto JSON válido. Sin markdown, sin explicación, sin preámbulo.
Solo el JSON crudo.

Tu análisis debe ser basado en datos, específico y brutalmente accionable. Pensá como un quant de hedge fund
aplicado al e-commerce: encontrá el edge, dimensioná la posición, ejecutá.”””

SYSTEM_PROMPT_EN = “”“You are a Lead E-commerce Strategist & Data Quant with 15 years of experience
in competitive intelligence, pricing strategy, and Shopify market dynamics.

Your job is to analyze competitor product data and return a precise, actionable market thesis.

You ALWAYS respond with a single valid JSON object. No markdown, no explanation, no preamble.
Just the raw JSON.

Your analysis must be data-driven, specific, and ruthlessly actionable. Think like a hedge fund
quant applied to e-commerce: find the edge, size the position, execute.”””

def build_analysis_prompt(productos_json: list[dict], competitor_name: str = “”, lang: str = “es”) -> str:
“”“Construye el prompt con los datos del competidor.”””

```
products_text = "\n".join([
    f"- {p['product_name']} | Price: ${p['price']:.2f} {p.get('currency','USD')} | Updated: {p.get('updated_at','N/A')[:10]}"
    for p in productos_json
])

prices = [p["price"] for p in productos_json if p["price"] > 0]
avg_price = sum(prices) / len(prices) if prices else 0
min_price = min(prices) if prices else 0
max_price = max(prices) if prices else 0

lang_instruction = (
    "Respond with all text fields in SPANISH (español). Numbers and keys stay in English."
    if lang == "es" else
    "Respond with all text fields in ENGLISH."
)

return f"""Analyze this competitor's product catalog and generate a market intelligence report.
```

{lang_instruction}

COMPETITOR: {competitor_name or “Unknown Store”}
PRODUCTS SCRAPED ({len(productos_json)} items):
{products_text}

PRICE STATS:

- Average: ${avg_price:.2f}
- Range: ${min_price:.2f} – ${max_price:.2f}
- Total products analyzed: {len(productos_json)}

Return ONLY this JSON structure (no extra text):

{{
“market_bias”: “AGGRESSIVE” | “DEFENSIVE” | “NEUTRAL”,
“sentiment_score”: <integer 0-100>,
“sentiment_reasoning”: “<2 sentences explaining the score>”,
“alpha_opportunity”: {{
“product”: “<exact product name from the list>”,
“reason”: “<why this product is the attack vector>”,
“suggested_action”: “<concrete action to take>”,
“estimated_impact”: “HIGH” | “MEDIUM” | “LOW”
}},
“high_conviction_bets”: [
{{
“bet”: “<specific actionable strategy>”,
“probability”: “<percentage chance of success>”,
“timeframe”: “<when to execute: NOW / THIS_WEEK / THIS_MONTH>”,
“reasoning”: “<data-driven reason>”
}},
{{
“bet”: “<specific actionable strategy>”,
“probability”: “<percentage chance of success>”,
“timeframe”: “<when to execute>”,
“reasoning”: “<data-driven reason>”
}},
{{
“bet”: “<specific actionable strategy>”,
“probability”: “<percentage chance of success>”,
“timeframe”: “<when to execute>”,
“reasoning”: “<data-driven reason>”
}}
],
“price_gap_analysis”: “<brief analysis of pricing gaps and opportunities>”,
“risk_assessment”: “<main risks to monitor>”
}}

MARKET_BIAS logic:

- AGGRESSIVE: clear pricing gaps, stock opportunities, competitor weaknesses visible → attack now
- DEFENSIVE: competitor is strong, prices are competitive, market is tight → protect your margins
- NEUTRAL: mixed signals, gather more data before moving

Be specific. Reference actual product names and prices from the data.”””

def generate_market_thesis(productos_json: list[dict], competitor_id: int,
competitor_name: str, db, MarketAnalysis, lang: str = “es”) -> dict:
“””
Función principal del motor IA.
lang: “es” para español, “en” para inglés.
“””
api_key = os.getenv(“GROQ_API_KEY”)
if not api_key:
raise ValueError(“GROQ_API_KEY no está configurada en las variables de entorno.”)

```
client = Groq(api_key=api_key, timeout=60.0, max_retries=2)
system_prompt = SYSTEM_PROMPT_ES if lang == "es" else SYSTEM_PROMPT_EN

log.info(f"  🤖 Enviando {len(productos_json)} productos a LLaMA 3.3 70B (lang={lang})...")

# ── Llamada a Groq ──────────────────────────────────────────
response = client.chat.completions.create(
    model=GROQ_MODEL,
    messages=[
        {"role": "system", "content": system_prompt},
        {"role": "user",   "content": build_analysis_prompt(productos_json, competitor_name, lang)},
    ],
    temperature=0.2,
    max_tokens=1500,
)

raw_text = response.choices[0].message.content.strip()
log.info(f"  ✓ Respuesta recibida ({len(raw_text)} chars)")

# ── Parsear JSON (limpiar backticks si los pone) ────────────
clean_text = re.sub(r"^```(?:json)?", "", raw_text).rstrip("```").strip()
analysis_data = json.loads(clean_text)

# ── Extraer campos ──────────────────────────────────────────
bias            = analysis_data.get("market_bias", "NEUTRAL")
sentiment_score = int(analysis_data.get("sentiment_score", 50))
alpha_opp       = analysis_data.get("alpha_opportunity", {})
bets            = analysis_data.get("high_conviction_bets", [])

alpha_text = (
    f"{alpha_opp.get('product','')} — {alpha_opp.get('reason','')} "
    f"[{alpha_opp.get('suggested_action','')}]"
    if isinstance(alpha_opp, dict) else str(alpha_opp)
)

# ── Guardar en base de datos ────────────────────────────────
record = MarketAnalysis(
    competitor_id        = competitor_id,
    sentiment_score      = sentiment_score,
    bias                 = bias,
    alpha_opportunity    = alpha_text,
    high_conviction_bets = json.dumps(bets, ensure_ascii=False),
    raw_analysis         = json.dumps(analysis_data, ensure_ascii=False),
    timestamp            = datetime.utcnow(),
)
db.session.add(record)
db.session.commit()

log.info(f"  💾 Análisis guardado: {bias} | Score: {sentiment_score} | Alpha: {alpha_opp.get('product','?')[:40]}")
return analysis_data
```
      
   
