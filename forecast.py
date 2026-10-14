"""
forecast.py - demand forecasting for InventoTrack  (Oct 12 + Oct 13)

WHAT IT DOES
  Step 1 (Oct 12)  monthly_history()   turns the sales table into "units sold per month"
  Step 2 (Oct 13)  forecast_product()  predicts next month's demand with 3 methods,
                                       tests each one on past months and keeps the best

THE THREE METHODS
  1. Moving average      : average of the last 3 months (simple, ignores seasons)
  2. Linear trend        : a straight line through the months (ML: LinearRegression)
  3. Season-aware        : learns two levels from the past - normal demand in the product's
                           crop season (e.g. Kharif = Jun-Oct) and normal demand outside it
                           (ML: LinearRegression on a 1/0 "in season" flag)

HOW WE TEST ("backtesting")
  For each of the last 4 months we pretend we are standing just before that month,
  predict it using only older data, and compare with what really sold.
  The average mistake is called MAE (smaller is better).

HOW WE CHOOSE
  * Seasonal product (Kharif / Rabi / Monsoon): always the season-aware model.
    Reason: the test months rarely contain a season change, so a method that cannot see
    seasons can look good in the test and still be badly wrong when a season starts or ends.
  * Year-round product: the method with the smallest MAE.
"""
import numpy as np
import pandas as pd
from sklearn.linear_model import LinearRegression

import stock

# Which calendar months (1 = Jan ... 12 = Dec) belong to each crop season.
# Same table as seed_data.py, so the demo data and the model agree.
SEASON_MONTHS = {
    "Kharif": [6, 7, 8, 9, 10],
    "Rabi": [11, 12, 1, 2, 3],
    "Monsoon": [6, 7, 8, 9],
    "Year-round": list(range(1, 13)),
}

MIN_MONTHS = 8    # need at least this many complete months of history
TEST_MONTHS = 4   # how many recent months are used to test each method
MA_WINDOW = 3     # moving average looks at this many months

METHOD_LABELS = {
    "season_regression": "Season-aware regression",
    "linear_trend": "Linear trend (regression)",
    "moving_average": "3-month moving average",
}


# ------------------------------------------------------------------
# STEP 1 (Oct 12): aggregate sales into a clean monthly table
# ------------------------------------------------------------------
def monthly_history(db, product_id, today=None):
    """
    Returns a pandas Series: index = month (2026-03), value = units sold that month.

    Rules that keep the table clean:
      * the current month is left out (it is not finished, so it would look too low)
      * months with no sales are filled with 0 (no gaps)
      * the table runs from the first sale up to LAST month
    """
    today = today or stock.today()

    rows = db.execute(
        "SELECT sale_date, quantity_sold FROM sales WHERE product_id = ?", (product_id,)
    ).fetchall()
    sales = pd.DataFrame(
        [(r["sale_date"], int(r["quantity_sold"])) for r in rows],
        columns=["sale_date", "quantity_sold"],
    )

    if sales.empty:
        return pd.Series(dtype=int)

    # "2026-03-14" and "2026-03-14 10:30:00" are both accepted; bad dates are dropped
    sales["sale_date"] = pd.to_datetime(sales["sale_date"], format="ISO8601", errors="coerce")
    sales = sales.dropna(subset=["sale_date"])
    if sales.empty:
        return pd.Series(dtype=int)

    sales["month"] = sales["sale_date"].dt.to_period("M")
    monthly = sales.groupby("month")["quantity_sold"].sum()

    last_complete_month = pd.Period(today, freq="M") - 1
    monthly = monthly[monthly.index <= last_complete_month]
    if monthly.empty:
        return pd.Series(dtype=int)

    every_month = pd.period_range(monthly.index.min(), last_complete_month, freq="M")
    return monthly.reindex(every_month, fill_value=0).astype(int)


# ------------------------------------------------------------------
# STEP 2 (Oct 13): the three prediction methods
# ------------------------------------------------------------------
def _in_season(month_number, season):
    months = SEASON_MONTHS.get(season, SEASON_MONTHS["Year-round"])
    return 1 if month_number in months else 0


def _clean(prediction):
    """Demand cannot be negative."""
    return max(0.0, float(prediction))


def _moving_average(values):
    return _clean(np.mean(values[-MA_WINDOW:]))


def _linear_trend(values, steps_ahead):
    t = np.arange(len(values)).reshape(-1, 1)             # 0, 1, 2, ... (month number in the table)
    model = LinearRegression().fit(t, values)
    future_t = len(values) - 1 + steps_ahead
    return _clean(model.predict([[future_t]])[0])


def _season_regression(values, month_numbers, season, target_month_number):
    # Each past month becomes one row with ONE feature: 1 = in the crop season, 0 = not.
    # The model learns "typical sales in season" and "typical sales out of season".
    # (We deliberately leave out a time trend: with under 2 years of data a trend cannot be
    #  told apart from the season and made the predictions worse in our tests.)
    X = np.array([[_in_season(m, season)] for m in month_numbers])
    model = LinearRegression().fit(X, values)
    return _clean(model.predict([[_in_season(target_month_number, season)]])[0])


def _predict(method, values, month_numbers, season, steps_ahead, target_month_number):
    if method == "moving_average":
        return _moving_average(values)
    if method == "linear_trend":
        return _linear_trend(values, steps_ahead)
    return _season_regression(values, month_numbers, season, target_month_number)


def _backtest_mae(method, values, month_numbers, season):
    """Average error over the last TEST_MONTHS months (smaller is better)."""
    errors = []
    for i in range(len(values) - TEST_MONTHS, len(values)):
        guess = _predict(method, values[:i], month_numbers[:i], season, 1, month_numbers[i])
        errors.append(abs(guess - values[i]))
    return float(np.mean(errors))


# ------------------------------------------------------------------
# STEP 3 (Oct 13): forecast one product / all products
# ------------------------------------------------------------------
def forecast_product(db, product_id, today=None):
    """Returns a dict (ready for jsonify), or None if the product does not exist."""
    today = today or stock.today()

    row = db.execute("SELECT name, season FROM products WHERE product_id = ?", (product_id,)).fetchone()
    if row is None:
        return None
    name, season = row["name"], row["season"]

    history = monthly_history(db, product_id, today)
    result = {
        "product_id": product_id,
        "product_name": name,
        "season": season,
        "months_available": int(len(history)),
        "history": [{"month": str(m), "quantity": int(q)} for m, q in history.items()],
    }

    if len(history) < MIN_MONTHS:
        result["enough_data"] = False
        result["message"] = (
            f"Not enough sales history yet: {len(history)} complete month(s) found, "
            f"at least {MIN_MONTHS} are needed."
        )
        return result

    values = history.to_numpy(dtype=float)
    month_numbers = [m.month for m in history.index]

    # we predict NEXT month; this month is unfinished and excluded, so that is 2 steps ahead
    target_period = pd.Period(today, freq="M") + 1
    steps_ahead = (target_period - history.index[-1]).n
    target_month_number = target_period.month

    methods = []
    for key in ("season_regression", "linear_trend", "moving_average"):
        methods.append({
            "method": key,
            "label": METHOD_LABELS[key],
            "mae": round(_backtest_mae(key, values, month_numbers, season), 2),
            "prediction": int(round(_predict(key, values, month_numbers, season, steps_ahead, target_month_number))),
        })

    methods.sort(key=lambda m: m["mae"])   # smallest mistake first; ties keep the order above
    lowest_error = methods[0]

    is_seasonal = season in SEASON_MONTHS and season != "Year-round"
    # the season effect can only be learned if the history contains BOTH in-season and off-season months
    season_learnable = len({_in_season(m, season) for m in month_numbers}) == 2

    if is_seasonal and season_learnable:
        chosen = next(m for m in methods if m["method"] == "season_regression")
        explanation = (
            f"{season} is a seasonal product, so the season-aware model is used: it is the only method "
            f"that knows when the season starts and ends. Moving-average and trend methods only "
            f"extrapolate recent months."
        )
    elif is_seasonal:
        chosen = lowest_error
        explanation = (
            f"The history does not yet contain both in-season and off-season months for {season}, so the "
            f"season effect cannot be learned. {chosen['label']} (smallest test error, {chosen['mae']} units) "
            f"is used instead. Treat this forecast with caution."
        )
    else:
        chosen = lowest_error
        explanation = (
            f"Year-round product: {chosen['label']} had the smallest average error "
            f"({chosen['mae']} units) over the last {TEST_MONTHS} months, so its prediction is used."
        )

    result.update({
        "enough_data": True,
        "backtest_months": TEST_MONTHS,
        "methods": methods,
        "lowest_error_method": lowest_error["method"],
        "best_method": chosen["method"],
        "best_method_label": chosen["label"],
        "forecast_month": str(target_period),
        "in_season_next_month": bool(_in_season(target_month_number, season)),
        "predicted_demand": chosen["prediction"],
        "explanation": explanation,
    })
    return result


def forecast_all(db, today=None):
    ids = [r["product_id"] for r in db.execute("SELECT product_id FROM products ORDER BY product_id").fetchall()]

    summary = []
    for pid in ids:
        f = forecast_product(db, pid, today)
        item = {
            "product_id": f["product_id"],
            "product_name": f["product_name"],
            "season": f["season"],
            "enough_data": f["enough_data"],
        }
        if f["enough_data"]:
            item.update({
                "forecast_month": f["forecast_month"],
                "predicted_demand": f["predicted_demand"],
                "best_method": f["best_method"],
                "best_method_label": f["best_method_label"],
            })
        else:
            item["message"] = f["message"]
        summary.append(item)
    return summary
