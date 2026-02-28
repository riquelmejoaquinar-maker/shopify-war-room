# models.py — Shopify War Room · Modelos de Base de Datos
# SQLAlchemy + SQLite (Railway compatible)

from datetime import datetime
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()


class Competitor(db.Model):
    """
    Tiendas Shopify que el usuario quiere espiar.
    El usuario las agrega desde el dashboard.
    """
    __tablename__ = "competitors"

    id         = db.Column(db.Integer, primary_key=True)
    url        = db.Column(db.String(500), unique=True, nullable=False)
    name       = db.Column(db.String(200), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    is_active  = db.Column(db.Boolean, default=True)

    # Relaciones
    price_history = db.relationship("PriceHistory", backref="competitor", lazy=True, cascade="all, delete-orphan")
    analyses      = db.relationship("MarketAnalysis", backref="competitor", lazy=True, cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Competitor {self.name}>"

    def to_dict(self):
        return {
            "id":         self.id,
            "url":        self.url,
            "name":       self.name,
            "created_at": self.created_at.isoformat(),
            "is_active":  self.is_active,
        }


class PriceHistory(db.Model):
    """
    Historial de precios scrapeados de cada producto en cada tienda.
    Se guarda cada vez que el worker corre.
    """
    __tablename__ = "price_history"

    id            = db.Column(db.Integer, primary_key=True)
    competitor_id = db.Column(db.Integer, db.ForeignKey("competitors.id"), nullable=False)
    product_name  = db.Column(db.String(500), nullable=False)
    price         = db.Column(db.Float, nullable=False)
    currency      = db.Column(db.String(10), default="USD")
    product_handle= db.Column(db.String(500), default="")  # slug de Shopify
    updated_at    = db.Column(db.String(50), default="")   # updated_at de Shopify
    timestamp     = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<PriceHistory {self.product_name} @ {self.price}>"

    def to_dict(self):
        return {
            "id":           self.id,
            "product_name": self.product_name,
            "price":        self.price,
            "currency":     self.currency,
            "timestamp":    self.timestamp.isoformat(),
        }


class MarketAnalysis(db.Model):
    """
    Análisis de mercado generado por LLaMA 3.3 70B via Groq.
    Un registro por competidor por ciclo de análisis.
    """
    __tablename__ = "market_analysis"

    id                  = db.Column(db.Integer, primary_key=True)
    competitor_id       = db.Column(db.Integer, db.ForeignKey("competitors.id"), nullable=False)
    sentiment_score     = db.Column(db.Integer, default=50)       # 0-100
    bias                = db.Column(db.String(50), default="NEUTRAL")  # AGGRESSIVE | DEFENSIVE | NEUTRAL
    alpha_opportunity   = db.Column(db.Text, default="")           # producto/nicho a atacar
    high_conviction_bets= db.Column(db.Text, default="")           # JSON string con las apuestas
    raw_analysis        = db.Column(db.Text, default="")           # JSON completo de la IA
    timestamp           = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<MarketAnalysis {self.bias} @ {self.sentiment_score}>"

    def to_dict(self):
        import json
        bets = []
        try:
            bets = json.loads(self.high_conviction_bets) if self.high_conviction_bets else []
        except Exception:
            pass
        return {
            "id":                   self.id,
            "competitor_id":        self.competitor_id,
            "sentiment_score":      self.sentiment_score,
            "bias":                 self.bias,
            "alpha_opportunity":    self.alpha_opportunity,
            "high_conviction_bets": bets,
            "timestamp":            self.timestamp.isoformat(),
        }
