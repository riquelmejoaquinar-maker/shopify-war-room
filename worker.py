# worker.py — Shopify War Room · Worker de Tareas en Background
#
# Corre independientemente de Flask. En Railway se despliega como
# un proceso separado definido en el Procfile.
#
# Ciclo cada 1 hora:
#   1. Lee todos los competidores activos de la DB
#   2. Scrapea cada tienda Shopify
#   3. Pasa los datos a LLaMA 3.3 70B
#   4. Guarda todo en la base de datos

import os
import sys
import time
import logging
from datetime import datetime

# ── Setup de logging ────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        logging.StreamHandler(sys.stdout),
    ]
)
log = logging.getLogger("war_room.worker")

CYCLE_INTERVAL_SECONDS = 60 * 60  # 1 hora


def run_cycle(app, db, Competitor, PriceHistory, MarketAnalysis):
    """
    Un ciclo completo de inteligencia:
    Leer → Scrapear → Analizar → Guardar
    """
    from scraper import scrape_shopify, save_price_history
    from ai_engine import generate_market_thesis

    with app.app_context():
        competitors = Competitor.query.filter_by(is_active=True).all()

        if not competitors:
            log.info("  Sin competidores en la base de datos. Esperando...")
            return

        log.info(f"  Procesando {len(competitors)} competidor(es)...")

        for comp in competitors:
            log.info(f"\n{'─'*50}")
            log.info(f"  🎯 Competidor: {comp.name} ({comp.url})")

            # ── 1. Scraping ─────────────────────────────────────
            try:
                products = scrape_shopify(comp.url)
                if not products:
                    log.warning(f"  Sin productos scrapeados para {comp.name}")
                    continue

                save_price_history(comp.id, products, db, PriceHistory)

            except Exception as e:
                log.error(f"  ✗ Error scraping {comp.name}: {e}")
                continue

            # ── 2. Análisis IA ──────────────────────────────────
            try:
                generate_market_thesis(
                    productos_json  = products,
                    competitor_id   = comp.id,
                    competitor_name = comp.name,
                    db              = db,
                    MarketAnalysis  = MarketAnalysis,
                )
            except Exception as e:
                log.error(f"  ✗ Error en IA para {comp.name}: {e}")
                continue

            # Pausa entre tiendas para no spammear
            time.sleep(3)

        log.info(f"\n{'═'*50}")
        log.info(f"  ✅ Ciclo completado — {datetime.utcnow().strftime('%H:%M:%S')} UTC")
        log.info(f"  Próximo ciclo en {CYCLE_INTERVAL_SECONDS // 60} minutos")
        log.info(f"{'═'*50}\n")


def main():
    # Importar Flask app para tener contexto de DB
    from app import create_app
    from models import db, Competitor, PriceHistory, MarketAnalysis

    app = create_app()

    # Crear tablas si no existen
    with app.app_context():
        db.create_all()
        log.info("✓ Base de datos inicializada")

    log.info("🚀 Shopify War Room Worker iniciado")
    log.info(f"   Intervalo: cada {CYCLE_INTERVAL_SECONDS // 60} minutos")
    log.info(f"   Groq Model: llama-3.3-70b-versatile")
    log.info("   Ctrl+C para detener\n")

    # ── Loop principal ──────────────────────────────────────────
    while True:
        try:
            log.info(f"\n{'═'*50}")
            log.info(f"  ⚡ INICIANDO CICLO — {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC")
            log.info(f"{'═'*50}")

            run_cycle(app, db, Competitor, PriceHistory, MarketAnalysis)

        except KeyboardInterrupt:
            log.info("\n⛔ Worker detenido manualmente.")
            break
        except Exception as e:
            log.error(f"Error inesperado en el ciclo: {e}")

        time.sleep(CYCLE_INTERVAL_SECONDS)


if __name__ == "__main__":
    main()
