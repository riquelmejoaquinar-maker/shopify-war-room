# app.py — Shopify War Room · Servidor Flask
#
# Rutas:
#   GET  /          → Dashboard principal
#   POST /add        → Agregar competidor
#   POST /delete/<id>→ Eliminar competidor
#   GET  /api/data   → JSON con todos los datos (para refresh live)
#   POST /run-now    → Disparar ciclo manualmente (debug)

import os
import json
import logging
from datetime import datetime
from dotenv import load_dotenv
load_dotenv()
from flask import Flask, render_template, request, redirect, url_for, jsonify, flash

from models import db, Competitor, PriceHistory, MarketAnalysis

log = logging.getLogger("war_room.app")


def create_app():
    """Factory de Flask. Usada también por worker.py."""
    app = Flask(__name__)

    # ── Configuración ────────────────────────────────────────────
    app.config["SECRET_KEY"]           = os.getenv("SECRET_KEY", "war-room-dev-secret-change-in-prod")
    app.config["SQLALCHEMY_DATABASE_URI"] = os.getenv("DATABASE_URL", "sqlite:///war_room.db")
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

    db.init_app(app)

    # ── Rutas ────────────────────────────────────────────────────
    @app.route("/")
    def index():
        """Dashboard principal."""
        competitors = Competitor.query.order_by(Competitor.created_at.desc()).all()

        # Para cada competidor, traer su análisis más reciente
        dashboard_data = []
        for comp in competitors:
            latest_analysis = (
                MarketAnalysis.query
                .filter_by(competitor_id=comp.id)
                .order_by(MarketAnalysis.timestamp.desc())
                .first()
            )
            latest_products = (
                PriceHistory.query
                .filter_by(competitor_id=comp.id)
                .order_by(PriceHistory.timestamp.desc())
                .limit(10)
                .all()
            )

            bets = []
            if latest_analysis and latest_analysis.high_conviction_bets:
                try:
                    bets = json.loads(latest_analysis.high_conviction_bets)
                except Exception:
                    pass

            dashboard_data.append({
                "competitor":  comp,
                "analysis":    latest_analysis,
                "products":    latest_products,
                "bets":        bets,
            })

        # Stats globales para el header
        total_analyses = MarketAnalysis.query.count()
        total_products = PriceHistory.query.count()
        last_update    = (
            MarketAnalysis.query.order_by(MarketAnalysis.timestamp.desc()).first()
        )

        return render_template(
            "index.html",
            dashboard_data   = dashboard_data,
            total_analyses   = total_analyses,
            total_products   = total_products,
            last_update      = last_update,
            now              = datetime.utcnow(),
        )

    @app.route("/add", methods=["POST"])
    def add_competitor():
        """Agrega una nueva tienda Shopify a monitorear."""
        url  = request.form.get("url", "").strip()
        name = request.form.get("name", "").strip()

        if not url or not name:
            flash("URL y nombre son requeridos.", "error")
            return redirect(url_for("index"))

        # Normalizar URL
        if not url.startswith("http"):
            url = "https://" + url
        url = url.rstrip("/")

        # Verificar que no exista ya
        existing = Competitor.query.filter_by(url=url).first()
        if existing:
            flash(f"'{name}' ya está en la lista.", "warning")
            return redirect(url_for("index"))

        competitor = Competitor(url=url, name=name)
        db.session.add(competitor)
        db.session.commit()

        flash(f"✓ '{name}' agregado. El worker lo analizará en el próximo ciclo.", "success")
        log.info(f"Nuevo competidor agregado: {name} ({url})")
        return redirect(url_for("index"))

    @app.route("/delete/<int:comp_id>", methods=["POST"])
    def delete_competitor(comp_id):
        """Elimina un competidor y toda su data."""
        comp = Competitor.query.get_or_404(comp_id)
        name = comp.name
        db.session.delete(comp)
        db.session.commit()
        flash(f"'{name}' eliminado.", "info")
        return redirect(url_for("index"))

    @app.route("/run-now/<int:comp_id>", methods=["POST"])
    def run_now(comp_id):
        """Dispara el análisis manual de un competidor (útil para testing)."""
        comp = Competitor.query.get_or_404(comp_id)
        lang = request.cookies.get("warroom_lang", "es")
        try:
            from scraper import scrape_shopify, save_price_history
            from ai_engine import generate_market_thesis

            products = scrape_shopify(comp.url)
            if products:
                save_price_history(comp.id, products, db, PriceHistory)
                generate_market_thesis(products, comp.id, comp.name, db, MarketAnalysis, lang=lang)
                flash(f"✓ Análisis de '{comp.name}' completado en {'español' if lang == 'es' else 'inglés'}.", "success")
            else:
                flash(f"Sin productos encontrados en '{comp.name}'.", "warning")
        except Exception as e:
            flash(f"Error analizando '{comp.name}': {str(e)}", "error")

        return redirect(url_for("index"))

    @app.route("/api/data")
    def api_data():
        """Endpoint JSON para refresh sin recargar la página."""
        competitors = Competitor.query.all()
        result = []
        for comp in competitors:
            analysis = (
                MarketAnalysis.query
                .filter_by(competitor_id=comp.id)
                .order_by(MarketAnalysis.timestamp.desc())
                .first()
            )
            result.append({
                "competitor": comp.to_dict(),
                "analysis":   analysis.to_dict() if analysis else None,
            })
        return jsonify(result)

    return app


# ── Entry point ──────────────────────────────────────────────────
if __name__ == "__main__":
    app = create_app()
    with app.app_context():
        db.create_all()
    port = int(os.getenv("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=os.getenv("FLASK_DEBUG", "false").lower() == "true")
