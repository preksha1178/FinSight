import pandas as pd
from sklearn.linear_model import LinearRegression
import numpy as np

def load_data(filepath):

    # ── Load with error handling ──
    try:
        income_df = pd.read_excel(filepath, sheet_name="Income")
        expense_df = pd.read_excel(filepath, sheet_name="Expenses")
        cash_df = pd.read_excel(filepath, sheet_name="Cash")
    except Exception as e:
        raise ValueError(
            f"❌ Excel error: {str(e)}. "
            f"Sheets must be named exactly: Income, Expenses, Cash"
        )

    def clean_df(df):
        df.columns = [str(c).strip().title() for c in df.columns]
        df.dropna(how="all", inplace=True)
        df.drop_duplicates(inplace=True)
        for col in df.select_dtypes(include="object").columns:
            df[col] = df[col].astype(str).str.strip()
        for col in df.columns:
            if col != "Month":
                try:
                    df[col] = df[col].astype(str)\
                        .str.replace(",", "")\
                        .str.replace("₹", "")\
                        .str.replace(" ", "")
                    df[col] = pd.to_numeric(df[col], errors="coerce")
                except:
                    pass
        numeric_cols = df.select_dtypes(include="number").columns
        df[numeric_cols] = df[numeric_cols].fillna(0)
        if "Month" in df.columns:
            df["Month"] = df["Month"].astype(str).str.strip()
            df = df[df["Month"].str.lower() != "nan"]
            df = df[df["Month"].str.lower() != "none"]
            df = df[df["Month"] != ""]
        return df

    income_df = clean_df(income_df)
    expense_df = clean_df(expense_df)
    cash_df = clean_df(cash_df)

    # ── Validate required columns ──
    required_income = ["Month", "Revenue", "Other_Income"]
    required_expense = ["Month", "Rent", "Salaries",
                        "Utilities", "Marketing", "Misc"]
    required_cash = ["Month", "Opening_Balance", "Cash_In", "Cash_Out"]

    for col in required_income:
        if col not in income_df.columns:
            raise ValueError(f"❌ Missing column '{col}' in Income sheet")
    for col in required_expense:
        if col not in expense_df.columns:
            raise ValueError(f"❌ Missing column '{col}' in Expenses sheet")
    for col in required_cash:
        if col not in cash_df.columns:
            raise ValueError(f"❌ Missing column '{col}' in Cash sheet")

    # ── Validate minimum data ──
    if len(income_df) < 2:
        raise ValueError("❌ Need at least 2 months of data for analysis")

    return income_df, expense_df, cash_df


def calculate_kpis(income_df, expense_df, cash_df):

    income_df["Total_Income"] = (
        income_df["Revenue"] + income_df["Other_Income"]
    )
    expense_df["Total_Expenses"] = expense_df[[
        "Rent","Salaries","Utilities","Marketing","Misc"
    ]].sum(axis=1)

    # ── Standardize Month before merge ──
    income_df["Month"] = income_df["Month"].astype(str).str.strip()
    expense_df["Month"] = expense_df["Month"].astype(str).str.strip()

    merged = pd.merge(income_df, expense_df, on="Month")

    if merged.empty:
        raise ValueError(
            "❌ Month values don't match between Income and Expenses. "
            "Check spelling e.g. 'Jan-2024' must match exactly."
        )

    # ── Safe profit margin ──
    merged["Net_Profit"] = merged["Total_Income"] - merged["Total_Expenses"]
    merged["Profit_Margin_%"] = merged.apply(
        lambda row: round(
            (row["Net_Profit"] / row["Total_Income"] * 100), 2)
        if row["Total_Income"] != 0 else 0, axis=1
    )

    avg_monthly_expense = expense_df["Total_Expenses"].mean()

    # ── Safe cash runway ──
    raw_cash = (
        cash_df["Opening_Balance"].iloc[-1] +
        cash_df["Cash_In"].iloc[-1] -
        cash_df["Cash_Out"].iloc[-1]
    )
    latest_cash = max(0, float(raw_cash))
    cash_runway_days = (
        int((latest_cash / avg_monthly_expense) * 30)
        if avg_monthly_expense > 0 else 999
    )

    expense_categories = {
        "Rent": expense_df["Rent"].sum(),
        "Salaries": expense_df["Salaries"].sum(),
        "Utilities": expense_df["Utilities"].sum(),
        "Marketing": expense_df["Marketing"].sum(),
        "Misc": expense_df["Misc"].sum()
    }

    # ── Safe growth calculation ──
    income_df["Revenue_Growth_%"] = income_df["Revenue"].pct_change() * 100
    avg_growth = (
        round(float(income_df["Revenue_Growth_%"].mean()), 2)
        if len(income_df) > 1 else 0.0
    )

    best_month = merged.loc[merged["Net_Profit"].idxmax(), "Month"]
    worst_month = merged.loc[merged["Net_Profit"].idxmin(), "Month"]

    # ── Meaningful burn rate = last month actual expenses ──
    burn_rate = float(expense_df["Total_Expenses"].iloc[-1])

    return {
        "total_revenue": float(income_df["Total_Income"].sum()),
        "total_expenses": float(expense_df["Total_Expenses"].sum()),
        "net_profit": float(merged["Net_Profit"].sum()),
        "avg_profit_margin": round(
            float(merged["Profit_Margin_%"].mean()), 2),
        "current_cash": latest_cash,
        "cash_runway_days": cash_runway_days,
        "monthly_data": merged,
        "expense_categories": expense_categories,
        "avg_growth": avg_growth,
        "best_month": str(best_month),
        "worst_month": str(worst_month),
        "burn_rate": burn_rate
    }


def get_health_warnings(kpis):
    warnings = []
    tips = []

    if kpis["avg_profit_margin"] < 20:
        warnings.append(
            "⚠️ Profit margin below 20% — business is under pressure")
        tips.append(
            "💡 Review and cut non-essential expenses like Marketing or Misc")

    if kpis["cash_runway_days"] < 60:
        warnings.append(
            "🚨 Cash runway under 60 days — urgent cash flow risk!")
        tips.append(
            "💡 Follow up on pending receivables and delay non-urgent payments")

    if kpis["avg_growth"] < 0:
        warnings.append("📉 Revenue is declining month over month")
        tips.append(
            "💡 Investigate which months dropped and check seasonal patterns")

    if kpis["burn_rate"] > kpis["total_revenue"] / 6:
        warnings.append(
            "🔥 Monthly burn rate is very high compared to revenue")
        tips.append(
            "💡 Salaries and Rent are fixed — focus on cutting variable costs")

    if not warnings:
        warnings.append("✅ Business financials look healthy!")
        tips.append("💡 Good time to plan expansion or build cash reserves")

    return warnings, tips


def forecast_revenue(income_df):
    try:
        # ── Guard: need at least 3 months ──
        if len(income_df) < 3:
            return None

        # ── Guard: all zero revenue ──
        if income_df["Revenue"].sum() == 0:
            return None

        X = np.array(range(len(income_df))).reshape(-1, 1)
        y = income_df["Revenue"].values

        model = LinearRegression()
        model.fit(X, y)

        next_3 = np.array([
            len(income_df),
            len(income_df)+1,
            len(income_df)+2
        ]).reshape(-1, 1)
        predictions = model.predict(next_3)

        # ── Guard: negative predictions ──
        predictions = np.maximum(predictions, 0)

        last_month = income_df["Month"].iloc[-1]
        try:
            last_date = pd.to_datetime(last_month)
            future_months = [
                (last_date + pd.DateOffset(months=i+1)).strftime("%b-%Y")
                for i in range(3)
            ]
        except:
            future_months = ["Month+1", "Month+2", "Month+3"]

        forecast_df = pd.DataFrame({
            "Month": future_months,
            "Forecasted_Revenue": predictions.round(2),
            "Type": ["Forecast"] * 3
        })

        history_df = pd.DataFrame({
            "Month": income_df["Month"].tolist(),
            "Forecasted_Revenue": income_df["Revenue"].tolist(),
            "Type": ["Actual"] * len(income_df)
        })

        combined = pd.concat([history_df, forecast_df], ignore_index=True)
        trend = ("📈 Growing" if predictions[-1] > predictions[0]
                 else "📉 Declining")
        avg_forecast = float(predictions.mean().round(2))

        return {
            "combined_df": combined,
            "forecast_df": forecast_df,
            "trend": trend,
            "avg_forecast": avg_forecast,
            "predictions": predictions
        }

    except Exception:
        return None


def get_company_position(kpis):
    revenue = kpis["total_revenue"]
    expenses = kpis["total_expenses"]
    margin = kpis["avg_profit_margin"]
    runway = kpis["cash_runway_days"]
    growth = kpis["avg_growth"]

    # Scores
    if margin >= 30: profit_score = 25
    elif margin >= 20: profit_score = 20
    elif margin >= 10: profit_score = 12
    elif margin >= 0: profit_score = 6
    else: profit_score = 0

    if runway >= 180: cash_score = 25
    elif runway >= 120: cash_score = 20
    elif runway >= 60: cash_score = 12
    elif runway >= 30: cash_score = 6
    else: cash_score = 0

    if growth >= 10: growth_score = 25
    elif growth >= 5: growth_score = 20
    elif growth >= 0: growth_score = 12
    elif growth >= -5: growth_score = 6
    else: growth_score = 0

    expense_ratio = (expenses / revenue * 100) if revenue > 0 else 100
    if expense_ratio <= 50: expense_score = 25
    elif expense_ratio <= 65: expense_score = 20
    elif expense_ratio <= 75: expense_score = 12
    elif expense_ratio <= 90: expense_score = 6
    else: expense_score = 0

    total_score = profit_score + cash_score + growth_score + expense_score

    if total_score >= 85:
        position = "Market Leader 🏆"
        position_color = "#00CC96"
        position_desc = "Excellent financial health. Strong position to expand, invest, or enter new markets."
    elif total_score >= 70:
        position = "Stable & Growing 📈"
        position_color = "#667eea"
        position_desc = "Good financial health. Solid fundamentals and growing steadily."
    elif total_score >= 55:
        position = "Moderate Risk ⚠️"
        position_color = "#FFA500"
        position_desc = "Average health. Needs attention in key areas to avoid decline."
    elif total_score >= 35:
        position = "High Risk 🔴"
        position_color = "#EF553B"
        position_desc = "Poor financial health. Immediate action needed."
    else:
        position = "Critical — Action Required 🚨"
        position_color = "#CC0000"
        position_desc = "Severe distress. Seek financial advisory urgently."

    breakdown = {
        "Profitability": {
            "score": profit_score, "max": 25,
            "value": f"{margin}%", "label": "Profit Margin",
            "status": ("✅ Strong" if profit_score >= 20
                       else "⚠️ Moderate" if profit_score >= 10
                       else "❌ Weak")
        },
        "Cash Health": {
            "score": cash_score, "max": 25,
            "value": f"{runway} days", "label": "Cash Runway",
            "status": ("✅ Strong" if cash_score >= 20
                       else "⚠️ Moderate" if cash_score >= 10
                       else "❌ Weak")
        },
        "Growth": {
            "score": growth_score, "max": 25,
            "value": f"{growth}%", "label": "Avg Monthly Growth",
            "status": ("✅ Strong" if growth_score >= 20
                       else "⚠️ Moderate" if growth_score >= 10
                       else "❌ Weak")
        },
        "Expense Control": {
            "score": expense_score, "max": 25,
            "value": f"{round(expense_ratio, 1)}%",
            "label": "Expense Ratio",
            "status": ("✅ Strong" if expense_score >= 20
                       else "⚠️ Moderate" if expense_score >= 10
                       else "❌ Weak")
        }
    }

    insights = []
    if profit_score < 20:
        insights.append({
            "area": "💰 Profitability",
            "problem": f"Profit margin {margin}% — below 20% benchmark",
            "action": "Review top expenses and negotiate vendor costs",
            "impact": "High"
        })
    if cash_score < 20:
        insights.append({
            "area": "💵 Cash Flow",
            "problem": f"Only {runway} days cash runway remaining",
            "action": "Follow up on pending receivables within 7 days",
            "impact": "Critical"
        })
    if growth_score < 20:
        insights.append({
            "area": "📈 Growth",
            "problem": f"Revenue growth averaging {growth}% monthly",
            "action": "Increase marketing in high-performing months",
            "impact": "Medium"
        })
    if expense_score < 20:
        insights.append({
            "area": "✂️ Expenses",
            "problem": f"Expenses consuming {round(expense_ratio,1)}% of revenue",
            "action": "Cut Misc and Marketing by 15% this quarter",
            "impact": "High"
        })
    if not insights:
        insights.append({
            "area": "🚀 Expansion",
            "problem": "No critical issues found",
            "action": "Invest surplus cash in expansion or FD",
            "impact": "Opportunity"
        })

    return {
        "total_score": total_score,
        "position": position,
        "position_color": position_color,
        "position_desc": position_desc,
        "breakdown": breakdown,
        "insights": insights,
        "expense_ratio": round(expense_ratio, 1)
    }