"""
suggestions.py - restock recommendations WITH reasoning  (Oct 14)

THE RULE (simple on purpose, so the owner can check it with a calculator):
    target stock   = predicted demand next month + minimum stock level (safety buffer)
    order quantity = max(0, target stock - usable stock now)

* "usable stock" = units in batches that have NOT expired.
* If there is not enough sales history for a forecast (< 8 months), we fall back to
  target = 2 x minimum stock level and say so in the "why" text.

Every suggestion carries a "why" sentence plus the numbers behind it (basis, season, stock).
"""
from datetime import timedelta

import forecast
import stock

PRIORITY_RANK = {"order_now": 0, "order_soon": 1, "ok": 2}


def _stock_numbers(db, product_id, today):
    today_s = today.strftime("%Y-%m-%d")
    soon_s = (today + timedelta(days=30)).strftime("%Y-%m-%d")
    usable = db.execute(
        "SELECT COALESCE(SUM(quantity_remaining), 0) AS q FROM batches WHERE product_id = ? AND expiry_date >= ?",
        (product_id, today_s),
    ).fetchone()["q"]
    expiring = db.execute(
        "SELECT COALESCE(SUM(quantity_remaining), 0) AS q FROM batches "
        "WHERE product_id = ? AND expiry_date >= ? AND expiry_date <= ?",
        (product_id, today_s, soon_s),
    ).fetchone()["q"]
    return int(usable), int(expiring)


def build_suggestion(db, product_id, today=None):
    """Returns a dict, or None if the product does not exist."""
    today = today or stock.today()
    product = db.execute(
        "SELECT product_id, name, season, min_stock_level, is_restricted FROM products WHERE product_id = ?",
        (product_id,),
    ).fetchone()
    if product is None:
        return None

    season = product["season"] or "Year-round"
    min_stock = int(product["min_stock_level"] or 0)
    current_stock, expiring = _stock_numbers(db, product_id, today)
    fc = forecast.forecast_product(db, product_id, today)

    result = {
        "product_id": product["product_id"],
        "product_name": product["name"],
        "season": season,
        "is_restricted": bool(product["is_restricted"]),
        "current_stock": current_stock,
        "expiring_within_30_days": expiring,
        "min_stock_level": min_stock,
    }

    if fc["enough_data"]:
        predicted = int(fc["predicted_demand"])
        target = predicted + min_stock
        result.update({
            "basis": "forecast",
            "method": fc["best_method_label"],
            "forecast_month": fc["forecast_month"],
            "in_season_next_month": fc["in_season_next_month"],
            "predicted_demand": predicted,
        })
        season_text = ""
        if season != "Year-round":
            season_text = (f" {season} season is active next month, so demand is expected to be higher."
                           if fc["in_season_next_month"]
                           else f" {season} season is not active next month, so demand is expected to be lower.")
        base_text = (f"Based on {fc['months_available']} months of sales, about {predicted} units are expected "
                     f"to sell in {fc['forecast_month']} ({fc['best_method_label']}).{season_text} "
                     f"Adding the safety stock of {min_stock} gives a target of {target}.")
    else:
        predicted = None
        target = 2 * min_stock
        result.update({
            "basis": "minimum_stock_rule",
            "method": None,
            "forecast_month": None,
            "in_season_next_month": None,
            "predicted_demand": None,
        })
        base_text = (f"Not enough sales history for a forecast ({fc['months_available']} complete month(s), "
                     f"8 needed), so the simple rule is used: keep 2 x the minimum stock level "
                     f"({min_stock}) = {target}.")

    order = max(0, target - current_stock)
    if order == 0:
        priority = "ok"
    elif current_stock <= min_stock or (predicted is not None and current_stock < predicted):
        priority = "order_now"
    else:
        priority = "order_soon"

    stock_text = f" Current usable stock is {current_stock}"
    stock_text += f", so order {order} more." if order > 0 else ", which already covers the target, so no order is needed."
    if expiring > 0:
        stock_text += f" Note: {expiring} unit(s) expire within 30 days and may not be sold in time."

    result.update({
        "target_stock": target,
        "recommended_order": order,
        "priority": priority,
        "why": (base_text + stock_text).strip(),
    })
    return result


def build_all_suggestions(db, today=None, only_needed=False):
    """Returns (summary, items) - items sorted with the most urgent first."""
    today = today or stock.today()
    ids = [r["product_id"] for r in db.execute("SELECT product_id FROM products ORDER BY product_id").fetchall()]
    items = [build_suggestion(db, pid, today) for pid in ids]

    summary = {
        "total_products": len(items),
        "order_now": sum(1 for i in items if i["priority"] == "order_now"),
        "order_soon": sum(1 for i in items if i["priority"] == "order_soon"),
        "ok": sum(1 for i in items if i["priority"] == "ok"),
        "total_units_to_order": sum(i["recommended_order"] for i in items),
    }
    if only_needed:
        items = [i for i in items if i["recommended_order"] > 0]
    items.sort(key=lambda i: (PRIORITY_RANK[i["priority"]], -i["recommended_order"], i["product_id"]))
    return summary, items
