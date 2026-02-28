# scraper.py — Shopify War Room · Motor de Scraping
#
# Shopify expone un endpoint público en /products.json que devuelve
# todos los productos sin necesidad de auth. Lo usamos a nuestro favor.

import requests
import logging
from datetime import datetime

log = logging.getLogger("war_room.scraper")

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json",
}

MAX_PRODUCTS = 10  # últimos productos a analizar por tienda


def clean_url(url: str) -> str:
    """Normaliza la URL: quita trailing slash, asegura https."""
    url = url.strip().rstrip("/")
    if not url.startswith("http"):
        url = "https://" + url
    return url


def scrape_shopify(tienda_url: str) -> list[dict]:
    """
    Hace un GET a {tienda_url}/products.json y extrae los últimos MAX_PRODUCTS
    productos con: title, handle, updated_at, price (primera variante).

    Retorna una lista de dicts listos para guardar en PriceHistory.
    Lanza una excepción si la tienda no responde o no es Shopify.
    """
    url = clean_url(tienda_url)
    endpoint = f"{url}/products.json?limit={MAX_PRODUCTS}&sort_by=created-descending"

    log.info(f"  Scrapeando: {endpoint}")

    response = requests.get(endpoint, headers=HEADERS, timeout=15)
    response.raise_for_status()

    data = response.json()
    products_raw = data.get("products", [])

    if not products_raw:
        log.warning(f"  Sin productos en {tienda_url}")
        return []

    products = []
    for p in products_raw[:MAX_PRODUCTS]:
        # Tomamos el precio de la primera variante disponible
        variants = p.get("variants", [])
        price = 0.0
        currency = "USD"
        if variants:
            try:
                price = float(variants[0].get("price", 0))
            except (ValueError, TypeError):
                price = 0.0

        product = {
            "product_name":   p.get("title", "Sin título"),
            "price":          price,
            "currency":       currency,
            "product_handle": p.get("handle", ""),
            "updated_at":     p.get("updated_at", ""),
        }
        products.append(product)
        log.info(f"    ✓ {product['product_name'][:50]} → ${product['price']:.2f}")

    log.info(f"  Total scrapeado: {len(products)} productos")
    return products


def save_price_history(competitor_id: int, products: list[dict], db, PriceHistory):
    """
    Guarda la lista de productos scrapeados en la tabla PriceHistory.
    Recibe db y PriceHistory como parámetros para evitar imports circulares.
    """
    now = datetime.utcnow()
    saved = 0

    for p in products:
        record = PriceHistory(
            competitor_id  = competitor_id,
            product_name   = p["product_name"],
            price          = p["price"],
            currency       = p.get("currency", "USD"),
            product_handle = p.get("product_handle", ""),
            updated_at     = p.get("updated_at", ""),
            timestamp      = now,
        )
        db.session.add(record)
        saved += 1

    db.session.commit()
    log.info(f"  💾 {saved} registros guardados en PriceHistory (competitor_id={competitor_id})")
    return saved
