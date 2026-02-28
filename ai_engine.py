# ai_engine.py — Shopify War Room · Motor de Inteligencia Artificial

import json
import logging
import os
import re
import time
from datetime import datetime
from dotenv import load_dotenv
load_dotenv()

log = logging.getLogger("war_room.ai")

GROQ_MODEL = "llama-3.3-70b-versatile"

SYSTEM_PROMPT_ES = """Eres un Lead Estratega de E-commerce y Data Quant.
Tu trabajo: analizar productos de competidores y devolver SOLO un JSON válido.
NUNCA escribas markdown, texto explicativo, ni bloques de código.
SOLO el objeto JSON crudo, sin nada antes ni después."""

SYSTEM_PROMPT_EN = """You are a Lead E-commerce Strategist & Data Quant.
Your job: analyze competitor products and return ONLY valid JSON.
NEVER write markdown, explanatory text, or code blocks.
ONLY the raw JSON object, nothing before or after."""


def build_analysis_prompt(productos_json, competitor_name="", lang="es"):
    products_text = "\n".join([
        f"- {p['product_name']} | Price: ${p['price']:.2f}"
        for p in productos_json
    ])
    prices    = [p["price"] for p in productos_json if p["price"] > 0]
    avg_price = sum(prices) / len(prices) if prices else 0
    min_price = min(prices) if prices else 0
    max_price = max(prices) if prices else 0
    lang_instruction = "IMPORTANT: Write ALL text values in SPANISH." if lang == "es" else "IMPORTANT: Write ALL text values in ENGLISH."

    return f"""{lang_instruction}
Competitor: {competitor_name}
Products:
{products_text}
Avg: ${avg_price:.2f} | Min: ${min_price:.2f} | Max: ${max_price:.2f}

Return ONLY this JSON structure filled with your analysis:
{{"market_bias":"AGGRESSIVE","sentiment_score":75,"sentiment_reasoning":"your text","alpha_opportunity":{{"product":"product name","reason":"why","suggested_action":"action","estimated_impact":"HIGH"}},"high_conviction_bets":[{{"bet":"action","probability":"80%","timeframe":"NOW","reasoning":"why"}},{{"bet":"action","probability":"70%","timeframe":"THIS_WEEK","reasoning":"why"}},{{"bet":"action","probability":"60%","timeframe":"THIS_MONTH","reasoning":"why"}}],"price_gap_analysis":"your text","risk_assessment":"your text"}}

market_bias: AGGRESSIVE=attack now | DEFENSIVE=protect margins | NEUTRAL=gather more data
{lang_instruction}"""


def clean_json_response(raw):
    """Extrae el JSON de la respuesta aunque tenga texto extra."""
    raw = re.sub(r"```(?:json)?", "", raw).strip().strip("`").strip()
    start = raw.find("{")
    end   = raw.rfind("}") + 1
    if start != -1 and end > start:
        return raw[start:end]
    return raw


def generate_market_thesis(productos_json, competitor_id, competitor_name, db, MarketAnalysis, lang="es"):
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        raise ValueError("GROQ_API_KEY no está configurada.")

    from groq import Groq
    import httpx

    system_prompt = SYSTEM_PROMPT_ES if lang == "es" else SYSTEM_PROMPT_EN

    try:
        http_client = httpx.Client(timeout=httpx.Timeout(60.0))
        client = Groq(api_key=api_key, http_client=http_client)
    except Exception:
        client = Groq(api_key=api_key)

    log.info(f"  Analizando {competitor_name} ({len(productos_json)} productos)...")

    last_error = None
    raw_text = ""
    for attempt in range(3):
        try:
            response = client.chat.completions.create(
                model=GROQ_MODEL,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user",   "content": build_analysis_prompt(productos_json, competitor_name, lang)},
                ],
                temperature=0.1,
                max_tokens=1200,
            )
            raw_text = response.choices[0].message.content.strip()
            log.info(f"  Respuesta recibida (intento {attempt+1})")
            break
        except Exception as e:
            last_error = e
            log.warning(f"  Intento {attempt+1} fallido: {e}")
            time.sleep(2 * (attempt + 1))
    else:
        raise Exception(f"Connection error: {last_error}")

    clean_text = clean_json_response(raw_text)

    try:
        analysis_data = json.loads(clean_text)
    except json.JSONDecodeError as e:
        log.error(f"  JSON invalido: {e} | Raw: {raw_text[:300]}")
        analysis_data = {
            "market_bias": "NEUTRAL",
            "sentiment_score": 50,
            "sentiment_reasoning": "Error al parsear respuesta.",
            "alpha_opportunity": {
                "product": productos_json[0]["product_name"] if productos_json else "N/A",
                "reason": "Analisis manual requerido.",
                "suggested_action": "Reintentar analisis.",
                "estimated_impact": "MEDIUM"
            },
            "high_conviction_bets": [],
            "price_gap_analysis": "Error en analisis automatico.",
            "risk_assessment": "Reintentar."
        }

    bias            = analysis_data.get("market_bias", "NEUTRAL")
    sentiment_score = int(analysis_data.get("sentiment_score", 50))
    alpha_opp       = analysis_data.get("alpha_opportunity", {})
    bets            = analysis_data.get("high_conviction_bets", [])

    alpha_text = (
        f"{alpha_opp.get('product','')} - {alpha_opp.get('reason','')} [{alpha_opp.get('suggested_action','')}]"
        if isinstance(alpha_opp, dict) else str(alpha_opp)
    )

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

    log.info(f"  Guardado: {bias} | Score: {sentiment_score}")
    return analysis_data
