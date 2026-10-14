"""Restock suggestions: target = predicted demand + minimum stock; order = target - usable stock; with a "why"."""


def test_not_enough_history_uses_minimum_stock_rule(client, owner, world):
    body = client.get(f"/suggestions/seasonal/{world.neem}", headers=owner).get_json()
    assert body["basis"] == "minimum_stock_rule"
    assert body["predicted_demand"] is None
    assert body["current_stock"] == 30                       # 10 + 20 usable; the expired 50 do not count
    assert body["target_stock"] == 10                        # 2 x minimum stock (5)
    assert body["recommended_order"] == 0 and body["priority"] == "ok"
    assert "Not enough sales history" in body["why"]


def test_low_stock_without_history_says_order_now(client, owner, staff, world):
    client.post("/sales", json={"product_id": world.neem, "quantity_sold": 28}, headers=staff)   # leaves 2
    body = client.get(f"/suggestions/seasonal/{world.neem}", headers=owner).get_json()
    assert body["current_stock"] == 2
    assert body["recommended_order"] == 8                    # target 10 - stock 2
    assert body["priority"] == "order_now"                   # 2 <= minimum stock 5


def test_forecast_based_suggestion_follows_the_formula(client, owner, world, add_history):
    add_history(world.neem, [40] * 10)                       # steady 40 units a month for 10 months
    body = client.get(f"/suggestions/seasonal/{world.neem}", headers=owner).get_json()
    assert body["basis"] == "forecast"
    assert body["predicted_demand"] == 40
    assert body["target_stock"] == 40 + 5                    # demand + minimum stock
    assert body["recommended_order"] == 45 - 30              # target - usable stock
    assert body["priority"] == "order_now"                   # stock 30 is below the expected demand of 40
    assert "10 months of sales" in body["why"] and "order 15 more" in body["why"]


def test_enough_stock_means_no_order(client, owner, world, add_history):
    add_history(world.neem, [10] * 10)                       # demand 10, target 15, stock 30
    body = client.get(f"/suggestions/seasonal/{world.neem}", headers=owner).get_json()
    assert body["recommended_order"] == 0 and body["priority"] == "ok"
    assert "no order is needed" in body["why"]


def test_seasonal_product_uses_season_in_its_reasoning(client, owner, world, add_history):
    # Kharif product: 100/month in Jun-Oct, 10/month otherwise, 14 months of history
    import stock
    from datetime import timedelta
    first = stock.today().replace(day=1)
    months = []
    for k in range(14, 0, -1):
        m = first
        for _ in range(k):
            m = (m - timedelta(days=1)).replace(day=1)
        months.append(100 if m.month in (6, 7, 8, 9, 10) else 10)
    add_history(world.mono, months, world.mono_batch)
    body = client.get(f"/suggestions/seasonal/{world.mono}", headers=owner).get_json()
    assert body["method"] == "Season-aware regression"
    expected = 100 if body["in_season_next_month"] else 10
    assert abs(body["predicted_demand"] - expected) <= 1
    assert "Kharif season is" in body["why"]


def test_all_suggestions_summary_and_filter(client, owner, world):
    everything = client.get("/suggestions", headers=owner).get_json()
    assert everything["summary"]["total_products"] == 2
    ranks = {"order_now": 0, "order_soon": 1, "ok": 2}
    order = [ranks[s["priority"]] for s in everything["suggestions"]]
    assert order == sorted(order)                            # most urgent first
    only = client.get("/suggestions?only_needed=true", headers=owner).get_json()
    assert all(s["recommended_order"] > 0 for s in only["suggestions"])


def test_unknown_product_is_404(client, owner):
    assert client.get("/suggestions/seasonal/9999", headers=owner).status_code == 404


def test_forecast_history_fills_gaps_with_zero(client, owner, world, add_history):
    add_history(world.neem, [5, 0, 7])
    months = client.get(f"/forecast/history/{world.neem}", headers=owner).get_json()["months"]
    assert [m["quantity"] for m in months] == [5, 0, 7]
