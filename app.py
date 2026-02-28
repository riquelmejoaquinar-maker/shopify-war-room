# app.py — Shopify War Room

import os
import json
import csv
import io
import logging
from datetime import datetime
from dotenv import load_dotenv
load_dotenv()

from flask import Flask, render_template, request, redirect, url_for, jsonify, flash, Response
from models import db, Competitor, PriceHistory, MarketAnalysis

log = logging.getLogger("war_room.app")


def create_app():
    app = Flask(__name__)
    app.config["SECRET_KEY"]              = os.getenv("SECRET_KEY", "war-room-dev-secret")
    app.config["SQLALCHEMY_DATABASE_URI"] = os.getenv("DATABASE_URL", "sqlite:///war_room.db")
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    db.init_app(app)

    # ── Dashboard principal ──────────────────────────────────────
    @app.route("/")
    def index():
        competitors = Competitor.query.order_by(Competitor.created_at.desc()).all()
        dashboard_data = []
        for comp in competitors:
            latest_analysis = (MarketAnalysis.query
                .filter_by(competitor_id=comp.id)
                .order_by(MarketAnalysis.timestamp.desc()).first())
            latest_products = (PriceHistory.query
                .filter_by(competitor_id=comp.id)
                .order_by(PriceHistory.timestamp.desc()).limit(10).all())
            bets = []
            if latest_analysis and latest_analysis.high_conviction_bets:
                try:
                    bets = json.loads(latest_analysis.high_conviction_bets)
                except Exception:
                    pass
            dashboard_data.append({
                "competitor": comp,
                "analysis":   latest_analysis,
                "products":   latest_products,
                "bets":       bets,
            })
        return render_template("index.html",
            dashboard_data = dashboard_data,
            total_analyses = MarketAnalysis.query.count(),
            total_products = PriceHistory.query.count(),
            now            = datetime.utcnow(),
        )

    # ── Agregar competidor ───────────────────────────────────────
    @app.route("/add", methods=["POST"])
    def add_competitor():
        url  = request.form.get("url", "").strip()
        name = request.form.get("name", "").strip()
        if not url or not name:
            flash("URL y nombre son requeridos.", "error")
            return redirect(url_for("index"))
        if not url.startswith("http"):
            url = "https://" + url
        url = url.rstrip("/")
        if Competitor.query.filter_by(url=url).first():
            flash(f"'{name}' ya está en la lista.", "warning")
            return redirect(url_for("index"))
        db.session.add(Competitor(url=url, name=name))
        db.session.commit()
        flash(f"✓ '{name}' agregado.", "success")
        return redirect(url_for("index"))

    # ── Eliminar competidor ──────────────────────────────────────
    @app.route("/delete/<int:comp_id>", methods=["POST"])
    def delete_competitor(comp_id):
        comp = Competitor.query.get_or_404(comp_id)
        name = comp.name
        db.session.delete(comp)
        db.session.commit()
        flash(f"'{name}' eliminado.", "info")
        return redirect(url_for("index"))

    # ── Analizar manualmente ─────────────────────────────────────
    @app.route("/run-now/<int:comp_id>", methods=["POST"])
    def run_now(comp_id):
        comp = Competitor.query.get_or_404(comp_id)
        lang = request.cookies.get("warroom_lang", "es")
        try:
            from scraper import scrape_shopify, save_price_history
            from ai_engine import generate_market_thesis
            products = scrape_shopify(comp.url)
            if products:
                save_price_history(comp.id, products, db, PriceHistory)
                generate_market_thesis(products, comp.id, comp.name, db, MarketAnalysis, lang=lang)
                flash(f"✓ '{comp.name}' analizado.", "success")
            else:
                flash(f"Sin productos en '{comp.name}'.", "warning")
        except Exception as e:
            flash(f"Error analizando '{comp.name}': {str(e)}", "error")
        return redirect(url_for("index"))

    # ── API: datos para gráficos (Chart.js) ─────────────────────
    @app.route("/api/price-history/<int:comp_id>")
    def price_history_api(comp_id):
        """Devuelve historial de precios por producto para Chart.js."""
        records = (PriceHistory.query
            .filter_by(competitor_id=comp_id)
            .order_by(PriceHistory.timestamp.asc())
            .all())

        # Agrupar por producto
        products = {}
        for r in records:
            name = r.product_name[:40]
            if name not in products:
                products[name] = {"labels": [], "prices": []}
            products[name]["labels"].append(r.timestamp.strftime("%d/%m %H:%M"))
            products[name]["prices"].append(r.price)

        # Devolver solo los 5 productos con más registros
        sorted_products = sorted(products.items(), key=lambda x: len(x[1]["prices"]), reverse=True)[:5]

        colors = ["#5c6cff", "#00d88a", "#ffc94d", "#ff3b5c", "#a78bfa"]
        datasets = []
        for i, (name, data) in enumerate(sorted_products):
            datasets.append({
                "label":       name,
                "data":        data["prices"],
                "borderColor": colors[i % len(colors)],
                "backgroundColor": colors[i % len(colors)] + "20",
                "tension":     0.3,
                "fill":        False,
            })

        # Labels = timestamps del producto con más datos
        labels = sorted_products[0][1]["labels"] if sorted_products else []

        return jsonify({"labels": labels, "datasets": datasets})

    # ── Exportar CSV ─────────────────────────────────────────────
    @app.route("/export/csv/<int:comp_id>")
    def export_csv(comp_id):
        """Descarga un CSV con todo el historial de precios y el análisis."""
        comp = Competitor.query.get_or_404(comp_id)
        records = (PriceHistory.query
            .filter_by(competitor_id=comp_id)
            .order_by(PriceHistory.timestamp.desc()).all())
        analysis = (MarketAnalysis.query
            .filter_by(competitor_id=comp_id)
            .order_by(MarketAnalysis.timestamp.desc()).first())

        output = io.StringIO()
        writer = csv.writer(output)

        # Header del reporte
        writer.writerow(["SHOPIFY WAR ROOM - Intelligence Report"])
        writer.writerow([f"Competitor: {comp.name}", f"URL: {comp.url}"])
        writer.writerow([f"Generated: {datetime.utcnow().strftime('%Y-%m-%d %H:%M')} UTC"])
        writer.writerow([])

        # Análisis IA
        if analysis:
            writer.writerow(["=== AI ANALYSIS ==="])
            writer.writerow(["Market Bias", analysis.bias])
            writer.writerow(["Sentiment Score", analysis.sentiment_score])
            writer.writerow(["Alpha Opportunity", analysis.alpha_opportunity])
            writer.writerow([])

            bets = []
            try:
                bets = json.loads(analysis.high_conviction_bets or "[]")
            except Exception:
                pass
            if bets:
                writer.writerow(["=== HIGH CONVICTION BETS ==="])
                writer.writerow(["Bet", "Probability", "Timeframe", "Reasoning"])
                for b in bets:
                    writer.writerow([b.get("bet",""), b.get("probability",""), b.get("timeframe",""), b.get("reasoning","")])
                writer.writerow([])

        # Historial de precios
        writer.writerow(["=== PRICE HISTORY ==="])
        writer.writerow(["Timestamp", "Product", "Price", "Currency"])
        for r in records:
            writer.writerow([
                r.timestamp.strftime("%Y-%m-%d %H:%M"),
                r.product_name,
                r.price,
                r.currency,
            ])

        output.seek(0)
        filename = f"war-room-{comp.name}-{datetime.utcnow().strftime('%Y%m%d')}.csv"
        return Response(
            output.getvalue(),
            mimetype="text/csv",
            headers={"Content-Disposition": f"attachment;filename={filename}"}
        )

    # ── Exportar CSV global (todos los competidores) ─────────────
    @app.route("/export/csv/all")
    def export_csv_all():
        competitors = Competitor.query.all()
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(["SHOPIFY WAR ROOM - Full Intelligence Report"])
        writer.writerow([f"Generated: {datetime.utcnow().strftime('%Y-%m-%d %H:%M')} UTC"])
        writer.writerow([])

        for comp in competitors:
            writer.writerow([f"=== {comp.name.upper()} ==="])
            analysis = (MarketAnalysis.query.filter_by(competitor_id=comp.id)
                .order_by(MarketAnalysis.timestamp.desc()).first())
            if analysis:
                writer.writerow(["Market Bias", analysis.bias])
                writer.writerow(["Sentiment Score", analysis.sentiment_score])
                writer.writerow(["Alpha Opportunity", analysis.alpha_opportunity])
            records = (PriceHistory.query.filter_by(competitor_id=comp.id)
                .order_by(PriceHistory.timestamp.desc()).limit(20).all())
            writer.writerow(["Timestamp", "Product", "Price"])
            for r in records:
                writer.writerow([r.timestamp.strftime("%Y-%m-%d %H:%M"), r.product_name, r.price])
            writer.writerow([])

        output.seek(0)
        filename = f"war-room-full-report-{datetime.utcnow().strftime('%Y%m%d')}.csv"
        return Response(
            output.getvalue(),
            mimetype="text/csv",
            headers={"Content-Disposition": f"attachment;filename={filename}"}
        )

    return app


if __name__ == "__main__":
    app = create_app()
    with app.app_context():
        db.create_all()
    port = int(os.getenv("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
