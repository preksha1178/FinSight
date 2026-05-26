import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd
import datetime
from io import BytesIO
from financial_logic import (load_data, calculate_kpis,
                              get_health_warnings, forecast_revenue,
                              get_company_position)
from database import (mysql_save_financial_data, mysql_save_snapshot,
                      mysql_save_chat, mysql_get_snapshots,
                      mysql_get_chat_history, mysql_check_connection,
                      mysql_run_query)
from email_alerts import send_alert_email, check_alerts_needed
from ai_advisor import ask_finsight
from pdf_report import generate_pdf_report
from auth import (login_user, register_user, save_upload_history,
                  save_user_chat, save_email_history,
                  get_upload_history, get_user_chats,
                  get_email_history)

st.set_page_config(
    page_title="FinSight",
    page_icon="📊",
    layout="wide"
)

st.markdown("""
    <style>
    .main { background-color: #f0f2f6; }
    [data-testid="stSidebar"] {
        background-color: #1a1a2e !important;
    }
    [data-testid="stSidebar"] p,
    [data-testid="stSidebar"] span,
    [data-testid="stSidebar"] label,
    [data-testid="stSidebar"] div,
    [data-testid="stSidebar"] small {
        color: white !important;
    }
    [data-testid="stFileUploader"] {
        background-color: #2a2a4a !important;
        border: 2px dashed #667eea !important;
        border-radius: 10px !important;
        padding: 10px !important;
    }
    [data-testid="stFileUploader"] * { color: white !important; }
    [data-testid="stFileUploaderDropzone"] {
        background-color: #2a2a4a !important;
    }
    [data-testid="stSidebar"] .stRadio label span {
        color: white !important;
    }
    .warning-box {
        background: #fff3cd;
        border-left: 5px solid #ffc107;
        padding: 10px 15px;
        border-radius: 5px;
        margin: 5px 0;
        color: #333;
    }
    .tip-box {
        background: #d1ecf1;
        border-left: 5px solid #17a2b8;
        padding: 10px 15px;
        border-radius: 5px;
        margin: 5px 0;
        color: #333;
    }
    .header-box {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        padding: 20px;
        border-radius: 12px;
        color: white;
        margin-bottom: 20px;
    }
    .login-box {
        background: white;
        padding: 40px;
        border-radius: 16px;
        box-shadow: 0 4px 24px rgba(102,126,234,0.15);
        max-width: 420px;
        margin: auto;
    }
    </style>
""", unsafe_allow_html=True)

# ══════════════════════════════════
#     SESSION STATE INIT
# ══════════════════════════════════
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
if "user" not in st.session_state:
    st.session_state.user = None
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []
if "auth_page" not in st.session_state:
    st.session_state.auth_page = "login"

# ══════════════════════════════════
#         LOGIN / REGISTER
# ══════════════════════════════════
def show_auth_page():
    st.markdown("""
        <div style='text-align:center; padding: 30px 0 10px;'>
            <h1 style='color:#667eea; font-size:2.5em'>📊 FinSight</h1>
            <p style='color:#888; font-size:1.1em'>
            AI-Powered Financial Advisor for Indian SMEs</p>
        </div>
    """, unsafe_allow_html=True)

    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        tab1, tab2 = st.tabs(["🔐 Login", "📝 Register"])

        # ── LOGIN TAB ──
        with tab1:
            st.markdown("### Welcome back!")
            username = st.text_input("Username",
                                     key="login_user",
                                     placeholder="Enter username")
            password = st.text_input("Password",
                                     type="password",
                                     key="login_pass",
                                     placeholder="Enter password")

            if st.button("🔐 Login", type="primary",
                         use_container_width=True):
                if not username or not password:
                    st.warning("⚠️ Fill both fields")
                else:
                    with st.spinner("Verifying..."):
                        success, user, msg = login_user(
                            username, password)
                    if success:
                        st.session_state.logged_in = True
                        st.session_state.user = user
                        st.session_state.chat_history = []
                        st.success(msg)
                        st.rerun()
                    else:
                        st.error(msg)

        # ── REGISTER TAB ──
        with tab2:
            st.markdown("### Create your account")
            full_name = st.text_input("Full Name",
                                      placeholder="Preksha Jain")
            reg_email = st.text_input("Email",
                                      placeholder="you@gmail.com")
            reg_user = st.text_input("Username",
                                     placeholder="Choose a username")
            reg_pass = st.text_input("Password",
                                     type="password",
                                     placeholder="Min 6 characters")
            reg_pass2 = st.text_input("Confirm Password",
                                      type="password",
                                      placeholder="Repeat password")

            if st.button("📝 Create Account",
                         type="primary",
                         use_container_width=True):
                if not all([full_name, reg_email,
                             reg_user, reg_pass, reg_pass2]):
                    st.warning("⚠️ Fill all fields")
                elif reg_pass != reg_pass2:
                    st.error("❌ Passwords don't match")
                elif len(reg_pass) < 6:
                    st.warning("⚠️ Password must be 6+ characters")
                elif "@" not in reg_email:
                    st.warning("⚠️ Enter valid email")
                else:
                    with st.spinner("Creating account..."):
                        success, msg = register_user(
                            reg_user, reg_pass,
                            full_name, reg_email)
                    if success:
                        st.success(msg)
                        st.info("Switch to Login tab to sign in")
                    else:
                        st.error(msg)

# ══════════════════════════════════
#        EXPORT HELPER
# ══════════════════════════════════
def export_to_excel(monthly_data, expense_categories, kpis):
    output = BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        pl = monthly_data[[
            "Month","Total_Income","Total_Expenses",
            "Net_Profit","Profit_Margin_%"
        ]].copy()
        pl.columns = ["Month","Total Income (Rs)",
                      "Total Expenses (Rs)",
                      "Net Profit (Rs)","Profit Margin %"]
        pl.to_excel(writer, sheet_name="P&L Statement", index=False)
        exp = pd.DataFrame({
            "Category": list(expense_categories.keys()),
            "Total Spent (Rs)": list(expense_categories.values())
        })
        exp.to_excel(writer, sheet_name="Expense Breakdown",
                     index=False)
        kpi_df = pd.DataFrame({
            "Metric": ["Total Revenue","Total Expenses",
                       "Net Profit","Profit Margin %",
                       "Current Cash","Cash Runway (days)"],
            "Value": [kpis["total_revenue"], kpis["total_expenses"],
                      kpis["net_profit"], kpis["avg_profit_margin"],
                      kpis["current_cash"], kpis["cash_runway_days"]]
        })
        kpi_df.to_excel(writer, sheet_name="KPI Summary", index=False)
    return output.getvalue()

# ══════════════════════════════════
#         SHOW LOGIN OR APP
# ══════════════════════════════════
if not st.session_state.logged_in:
    show_auth_page()
    st.stop()

# ══════════════════════════════════
#         LOGGED IN — SIDEBAR
# ══════════════════════════════════
user = st.session_state.user

with st.sidebar:
    st.markdown("## 📊 FinSight")
    st.markdown("*AI Financial Advisor for Indian SMEs*")
    st.divider()

    # User info
    st.markdown(
        f"<div style='background:#2a2a4a;padding:10px;"
        f"border-radius:8px;margin-bottom:10px;'>"
        f"<p style='margin:0;font-size:0.8em;color:#aaa;'>"
        f"Logged in as</p>"
        f"<p style='margin:0;font-weight:bold;color:white;"
        f"font-size:1em;'>👤 {user['full_name']}</p>"
        f"<p style='margin:0;font-size:0.75em;color:#888;'>"
        f"{user['role'].upper()}</p>"
        f"</div>",
        unsafe_allow_html=True
    )

    page = st.radio("Navigate", [
        "📊 Dashboard",
        "📋 P&L Statement",
        "🏢 Company Position",
        "🔮 Revenue Forecast",
        "📧 Email Alerts",
        "🤖 Ask AI",
        "📜 My History",
        "🗄️ Database Viewer"
    ])
    st.divider()
    uploaded_file = st.file_uploader(
        "📂 Upload Excel File", type=["xlsx"])
    st.divider()
    st.markdown("**Made by:** Preksha Jain")
    st.markdown("**Project:** Final Year BCA")
    st.markdown("**Year:** 2026")
    st.divider()

    if st.button("🚪 Logout", use_container_width=True):
        st.session_state.logged_in = False
        st.session_state.user = None
        st.session_state.chat_history = []
        st.rerun()

# ══════════════════════════════════
#            MAIN APP
# ══════════════════════════════════
if uploaded_file:
    try:
        with st.spinner("📂 Loading and cleaning your data..."):
            income_df, expense_df, cash_df = load_data(uploaded_file)
            kpis = calculate_kpis(income_df, expense_df, cash_df)
            warnings, tips = get_health_warnings(kpis)
            cp = get_company_position(kpis)
    except ValueError as e:
        st.error(str(e))
        st.info("💡 Make sure sheets are: Income, Expenses, Cash")
        st.stop()
    except Exception as e:
        st.error(f"❌ Unexpected error: {str(e)}")
        st.stop()

    # Auto save to MySQL + upload history
    try:
        mysql_save_financial_data(income_df, expense_df, cash_df)
        mysql_save_snapshot(kpis, cp)
        save_upload_history(
            user["id"],
            uploaded_file.name,
            kpis, cp
        )
    except:
        st.sidebar.warning("⚠️ MySQL save failed. Is XAMPP running?")

    # ══════════════════════════════════
    #         PAGE 1 — DASHBOARD
    # ══════════════════════════════════
    if page == "📊 Dashboard":
        st.markdown("""
            <div class="header-box">
                <h2 style='margin:0'>📊 Financial Dashboard</h2>
                <p style='margin:0;opacity:0.85'>
                Real-time financial overview of your business</p>
            </div>
        """, unsafe_allow_html=True)

        col1, col2, col3, col4 = st.columns(4)
        col1.metric("💰 Total Revenue",
                    f"₹{kpis['total_revenue']:,.0f}")
        col2.metric("💸 Total Expenses",
                    f"₹{kpis['total_expenses']:,.0f}")
        col3.metric("📈 Net Profit",
                    f"₹{kpis['net_profit']:,.0f}")
        col4.metric("📊 Profit Margin",
                    f"{kpis['avg_profit_margin']}%")

        st.divider()

        col_a, col_b = st.columns(2)
        with col_a:
            st.subheader("📊 Revenue vs Expenses")
            fig = px.bar(kpis["monthly_data"], x="Month",
                         y=["Total_Income","Total_Expenses"],
                         barmode="group",
                         color_discrete_sequence=
                         ["#667eea","#f093fb"],
                         template="plotly_white")
            fig.update_layout(legend_title="", margin=dict(t=20))
            st.plotly_chart(fig, use_container_width=True)

        with col_b:
            st.subheader("🥧 Expense Breakdown")
            exp_data = pd.DataFrame({
                "Category": list(
                    kpis["expense_categories"].keys()),
                "Amount": list(
                    kpis["expense_categories"].values())
            })
            fig2 = px.pie(exp_data, names="Category",
                          values="Amount", hole=0.45,
                          color_discrete_sequence=
                          px.colors.qualitative.Pastel)
            fig2.update_layout(margin=dict(t=20))
            st.plotly_chart(fig2, use_container_width=True)

        col_c, col_d = st.columns(2)
        with col_c:
            st.subheader("📉 Net Profit Trend")
            fig3 = px.line(kpis["monthly_data"], x="Month",
                           y="Net_Profit", markers=True,
                           color_discrete_sequence=["#667eea"],
                           template="plotly_white")
            fig3.add_hline(y=0, line_dash="dash",
                           line_color="red",
                           annotation_text="Break Even")
            fig3.update_layout(margin=dict(t=20))
            st.plotly_chart(fig3, use_container_width=True)

        with col_d:
            st.subheader("📊 Profit Margin % by Month")
            fig4 = px.bar(kpis["monthly_data"], x="Month",
                          y="Profit_Margin_%",
                          color="Profit_Margin_%",
                          color_continuous_scale="RdYlGn",
                          template="plotly_white")
            fig4.add_hline(y=20, line_dash="dash",
                           line_color="orange",
                           annotation_text="Healthy (20%)")
            fig4.update_layout(margin=dict(t=20))
            st.plotly_chart(fig4, use_container_width=True)

        st.divider()
        st.subheader("📌 Quick Summary")
        col1, col2, col3 = st.columns(3)
        col1.success(f"🟢 Best Month: **{kpis['best_month']}**")
        col2.error(f"🔴 Worst Month: **{kpis['worst_month']}**")
        col3.info(f"📈 Avg Growth: **{kpis['avg_growth']}%**")

        st.divider()

        # PDF Download
        st.subheader("📄 Download Full Report")
        st.caption("All charts, KPIs, P&L, forecast & insights")
        if st.button("📥 Generate & Download PDF Report",
                     type="primary",
                     use_container_width=True):
            with st.spinner(
                    "Generating PDF — this may take 15 seconds..."):
                try:
                    fc = forecast_revenue(income_df)
                    pdf_bytes = generate_pdf_report(
                        kpis, cp, fc, warnings, tips)
                    st.download_button(
                        label="✅ Click here to Download PDF",
                        data=pdf_bytes,
                        file_name=f"FinSight_Report_"
                                  f"{datetime.datetime.now().strftime('%d_%b_%Y')}.pdf",
                        mime="application/pdf",
                        use_container_width=True
                    )
                    st.success("✅ PDF ready!")
                except Exception as e:
                    st.error(f"❌ PDF failed: {str(e)}")

    # ══════════════════════════════════
    #       PAGE 2 — P&L STATEMENT
    # ══════════════════════════════════
    elif page == "📋 P&L Statement":
        st.markdown("""
            <div class="header-box">
                <h2 style='margin:0'>📋 Profit & Loss Statement</h2>
                <p style='margin:0;opacity:0.85'>
                Month-wise financial breakdown</p>
            </div>
        """, unsafe_allow_html=True)

        try:
            excel_data = export_to_excel(
                kpis["monthly_data"],
                kpis["expense_categories"], kpis)
            st.download_button(
                label="📥 Download Full Report (Excel)",
                data=excel_data,
                file_name="FinSight_Report.xlsx",
                mime="application/vnd.openxmlformats-officedocument"
                     ".spreadsheetml.sheet"
            )
        except Exception as e:
            st.warning(f"⚠️ Export failed: {str(e)}")

        st.divider()

        pl_table = kpis["monthly_data"][[
            "Month","Total_Income","Total_Expenses",
            "Net_Profit","Profit_Margin_%"
        ]].copy()
        pl_table.columns = ["Month","Total Income (₹)",
                            "Total Expenses (₹)",
                            "Net Profit (₹)","Profit Margin (%)"]
        pl_table["Total Income (₹)"] = pl_table[
            "Total Income (₹)"].apply(lambda x: f"₹{x:,.0f}")
        pl_table["Total Expenses (₹)"] = pl_table[
            "Total Expenses (₹)"].apply(lambda x: f"₹{x:,.0f}")
        pl_table["Net Profit (₹)"] = pl_table[
            "Net Profit (₹)"].apply(lambda x: f"₹{x:,.0f}")
        pl_table["Profit Margin (%)"] = pl_table[
            "Profit Margin (%)"].apply(lambda x: f"{x}%")
        st.dataframe(pl_table, use_container_width=True,
                     hide_index=True)

        st.divider()
        st.subheader("📊 Period Totals")
        c1, c2, c3 = st.columns(3)
        c1.metric("Total Income",
                  f"₹{kpis['monthly_data']['Total_Income'].sum():,.0f}")
        c2.metric("Total Expenses",
                  f"₹{kpis['monthly_data']['Total_Expenses'].sum():,.0f}")
        c3.metric("Net Profit",
                  f"₹{kpis['monthly_data']['Net_Profit'].sum():,.0f}")

        st.divider()
        st.subheader("📦 Expense Category Summary")
        if kpis["total_expenses"] > 0:
            exp_summary = pd.DataFrame({
                "Category": list(kpis["expense_categories"].keys()),
                "Total Spent": [f"₹{v:,.0f}" for v in
                               kpis["expense_categories"].values()],
                "% of Total Expense": [
                    f"{(v/kpis['total_expenses']*100):.1f}%"
                    for v in kpis["expense_categories"].values()
                ]
            })
            st.dataframe(exp_summary, use_container_width=True,
                        hide_index=True)

    # ══════════════════════════════════
    #      PAGE 3 — COMPANY POSITION
    # ══════════════════════════════════
    elif page == "🏢 Company Position":
        st.markdown("""
            <div class="header-box">
                <h2 style='margin:0'>🏢 Company Health & Position</h2>
                <p style='margin:0;opacity:0.85'>
                Complete financial position analysis</p>
            </div>
        """, unsafe_allow_html=True)

        fig_gauge = go.Figure(go.Indicator(
            mode="gauge+number",
            value=cp["total_score"],
            title={"text": f"Overall Company Score<br>"
                          f"<span style='font-size:0.85em;"
                          f"color:{cp['position_color']}'>"
                          f"{cp['position']}</span>"},
            number={"suffix": "/100"},
            gauge={
                "axis": {"range": [0, 100]},
                "bar": {"color": cp["position_color"]},
                "steps": [
                    {"range": [0, 35],  "color": "#ffe0e0"},
                    {"range": [35, 55], "color": "#ffd0b0"},
                    {"range": [55, 70], "color": "#fff3cd"},
                    {"range": [70, 85], "color": "#d4edda"},
                    {"range": [85, 100],"color": "#b8f0d8"}
                ]
            }
        ))
        fig_gauge.update_layout(height=320, margin=dict(t=60, b=20))
        st.plotly_chart(fig_gauge, use_container_width=True)

        st.markdown(
            f"<div style='background:{cp['position_color']}22;"
            f"border-left:5px solid {cp['position_color']};"
            f"padding:15px;border-radius:8px;margin:10px 0;'>"
            f"<b>{cp['position']}</b> — {cp['position_desc']}"
            f"</div>",
            unsafe_allow_html=True
        )
        st.divider()

        st.subheader("📊 Score Breakdown")
        cols = st.columns(4)
        for i, (category, data) in enumerate(
                cp["breakdown"].items()):
            score_pct = (data["score"] / data["max"]) * 100
            color = ("#00CC96" if score_pct >= 80
                     else "#FFA500" if score_pct >= 48
                     else "#EF553B")
            with cols[i]:
                st.markdown(
                    f"<div style='background:white;padding:15px;"
                    f"border-radius:10px;"
                    f"box-shadow:0 2px 8px rgba(0,0,0,0.08);"
                    f"text-align:center;"
                    f"border-top:4px solid {color};'>"
                    f"<h4 style='margin:0;color:#333'>{category}</h4>"
                    f"<h2 style='margin:5px 0;color:{color}'>"
                    f"{data['score']}/{data['max']}</h2>"
                    f"<p style='margin:0;color:#666;font-size:0.85em'>"
                    f"{data['label']}</p>"
                    f"<p style='margin:4px 0;font-size:0.9em'>"
                    f"{data['value']}</p>"
                    f"<b style='color:{color}'>{data['status']}</b>"
                    f"</div>",
                    unsafe_allow_html=True
                )

        st.divider()

        st.subheader("🕸️ Company Health Radar")
        categories = list(cp["breakdown"].keys())
        scores = [cp["breakdown"][c]["score"] for c in categories]
        max_scores = [cp["breakdown"][c]["max"] for c in categories]
        pct_scores = [s/m*100 for s, m in zip(scores, max_scores)]

        fig_radar = go.Figure()
        fig_radar.add_trace(go.Scatterpolar(
            r=pct_scores + [pct_scores[0]],
            theta=categories + [categories[0]],
            fill="toself",
            fillcolor="rgba(102,126,234,0.2)",
            line=dict(color="#667eea", width=2),
            name="Your Company"
        ))
        fig_radar.add_trace(go.Scatterpolar(
            r=[100, 100, 100, 100, 100],
            theta=categories + [categories[0]],
            fill="toself",
            fillcolor="rgba(0,204,150,0.05)",
            line=dict(color="#00CC96", width=1, dash="dash"),
            name="Ideal"
        ))
        fig_radar.update_layout(
            polar=dict(radialaxis=dict(visible=True,
                                       range=[0, 100])),
            showlegend=True, height=400, margin=dict(t=40)
        )
        st.plotly_chart(fig_radar, use_container_width=True)

        st.divider()

        st.subheader("🎯 Actionable Business Insights")
        for insight in cp["insights"]:
            impact_color = (
                "#CC0000" if insight["impact"] == "Critical"
                else "#EF553B" if insight["impact"] == "High"
                else "#FFA500" if insight["impact"] == "Medium"
                else "#00CC96"
            )
            st.markdown(
                f"<div style='background:white;padding:15px;"
                f"border-radius:10px;margin:8px 0;"
                f"box-shadow:0 2px 8px rgba(0,0,0,0.06);"
                f"border-left:5px solid {impact_color};'>"
                f"<div style='display:flex;"
                f"justify-content:space-between;'>"
                f"<b style='font-size:1.05em'>{insight['area']}</b>"
                f"<span style='background:{impact_color}22;"
                f"color:{impact_color};padding:2px 10px;"
                f"border-radius:20px;font-size:0.85em;'>"
                f"{insight['impact']}</span></div>"
                f"<p style='margin:6px 0 4px;color:#555'>"
                f"⚠️ {insight['problem']}</p>"
                f"<p style='margin:0;color:#333'>"
                f"✅ <b>Action:</b> {insight['action']}</p>"
                f"</div>",
                unsafe_allow_html=True
            )

        st.divider()
        st.subheader("🤖 AI Full Company Analysis")
        if st.button("Generate AI Company Report",
                     type="primary"):
            question = (
                f"Company Score: {cp['total_score']}/100. "
                f"Position: {cp['position']}. "
                f"Profit Margin: {kpis['avg_profit_margin']}%. "
                f"Cash Runway: {kpis['cash_runway_days']} days. "
                f"Revenue Growth: {kpis['avg_growth']}%. "
                f"Total Revenue: ₹{kpis['total_revenue']:,.0f}. "
                f"Write a professional 5-6 line company health "
                f"report like a CA would write."
            )
            with st.spinner("Generating report..."):
                report = ask_finsight(
                    question, kpis,
                    st.session_state.chat_history)
            st.markdown(
                f"<div style='background:#f8f9ff;padding:20px;"
                f"border-radius:10px;"
                f"border-left:5px solid #667eea;"
                f"line-height:1.8;'>{report}</div>",
                unsafe_allow_html=True
            )

    # ══════════════════════════════════
    #      PAGE 4 — REVENUE FORECAST
    # ══════════════════════════════════
    elif page == "🔮 Revenue Forecast":
        st.markdown("""
            <div class="header-box">
                <h2 style='margin:0'>🔮 3-Month Revenue Forecast</h2>
                <p style='margin:0;opacity:0.85'>
                ML predicts next 3 months</p>
            </div>
        """, unsafe_allow_html=True)

        forecast = forecast_revenue(income_df)

        if forecast:
            col1, col2, col3 = st.columns(3)
            preds = forecast["predictions"]
            col1.metric("📅 Month 1", f"₹{preds[0]:,.0f}")
            col2.metric("📅 Month 2", f"₹{preds[1]:,.0f}")
            col3.metric("📅 Month 3", f"₹{preds[2]:,.0f}")
            st.divider()

            if "Growing" in forecast["trend"]:
                st.success(
                    f"Trend: {forecast['trend']} — "
                    f"Avg: ₹{forecast['avg_forecast']:,.0f}")
            else:
                st.warning(
                    f"Trend: {forecast['trend']} — "
                    f"Avg: ₹{forecast['avg_forecast']:,.0f}")

            st.divider()
            st.subheader("📊 Actual vs Forecasted Revenue")
            fig = px.bar(forecast["combined_df"],
                         x="Month", y="Forecasted_Revenue",
                         color="Type",
                         color_discrete_map={
                             "Actual": "#667eea",
                             "Forecast": "#f093fb"
                         },
                         template="plotly_white",
                         text="Forecasted_Revenue")
            fig.update_traces(texttemplate="₹%{text:,.0f}",
                              textposition="outside")
            fig.update_layout(legend_title="",
                             yaxis_title="Revenue (₹)",
                             margin=dict(t=40))
            st.plotly_chart(fig, use_container_width=True)

            st.divider()
            if st.button("Ask AI to interpret forecast"):
                question = (
                    f"Revenue forecast: Month 1: ₹{preds[0]:,.0f}, "
                    f"Month 2: ₹{preds[1]:,.0f}, "
                    f"Month 3: ₹{preds[2]:,.0f}. "
                    f"Trend: {forecast['trend']}. What should I do?"
                )
                with st.spinner("Analyzing..."):
                    answer = ask_finsight(
                        question, kpis,
                        st.session_state.chat_history)
                st.info(answer)
        else:
            st.error("❌ Need at least 3 months of data.")

    # ══════════════════════════════════
    #       PAGE 5 — EMAIL ALERTS
    # ══════════════════════════════════
    elif page == "📧 Email Alerts":
        st.markdown("""
            <div class="header-box">
                <h2 style='margin:0'>📧 Smart Email Alert System</h2>
                <p style='margin:0;opacity:0.85'>
                Automatic alerts when business needs attention</p>
            </div>
        """, unsafe_allow_html=True)

        alert_reasons = check_alerts_needed(kpis)
        if alert_reasons:
            st.error("🚨 Alert conditions detected:")
            for r in alert_reasons:
                st.markdown(f"- ❌ {r}")
        else:
            st.success("✅ Financials healthy")
            st.info("You can still send a summary email below")

        st.divider()
        st.subheader("📬 Send Financial Alert Email")

        with st.expander("ℹ️ How to get Gmail App Password"):
            st.markdown("""
            1. Go to myaccount.google.com
            2. Security → 2-Step Verification → Enable
            3. Search App Passwords
            4. Select Mail → Windows Computer → Generate
            5. Copy 16-digit password
            """)

        col1, col2 = st.columns(2)
        with col1:
            sender = st.text_input("📤 Your Gmail:")
            password = st.text_input("🔑 App Password:",
                                     type="password")
        with col2:
            receiver = st.text_input("📥 Send alert to:")
            st.markdown("")
            st.markdown("")
            send_btn = st.button("📧 Send Alert Email Now",
                                 type="primary",
                                 use_container_width=True)

        if send_btn:
            if not sender or not password or not receiver:
                st.warning("⚠️ Fill all 3 fields")
            elif "@" not in sender or "@" not in receiver:
                st.warning("⚠️ Enter valid email addresses")
            else:
                with st.spinner("Sending..."):
                    success, message = send_alert_email(
                        sender, password, receiver, kpis, warnings)
                if success:
                    st.success(message)
                    st.balloons()
                    # Save email history
                    save_email_history(
                        user["id"], receiver,
                        "Critical" if alert_reasons
                        else "Summary")
                else:
                    st.error(message)

        st.divider()
        st.subheader("👁️ Email Preview")
        st.markdown(f"""
        **Subject:** FinSight Alert | {datetime.datetime.now().strftime('%d %b %Y')}

        | Metric | Value |
        |---|---|
        | 💰 Total Revenue | ₹{kpis['total_revenue']:,.0f} |
        | 📈 Net Profit | ₹{kpis['net_profit']:,.0f} |
        | 📊 Profit Margin | {kpis['avg_profit_margin']}% |
        | ⏳ Cash Runway | {kpis['cash_runway_days']} days |
        """)

    # ══════════════════════════════════
    #         PAGE 6 — ASK AI
    # ══════════════════════════════════
    elif page == "🤖 Ask AI":
        st.markdown("""
            <div class="header-box">
                <h2 style='margin:0'>🤖 Ask FinSight AI</h2>
                <p style='margin:0;opacity:0.85'>
                Instant AI-powered financial advice</p>
            </div>
        """, unsafe_allow_html=True)

        if "chat_history" not in st.session_state:
            st.session_state.chat_history = []

        st.subheader("⚡ Quick Questions")
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            if st.button("👥 Can I hire staff?"):
                st.session_state.quick_q = \
                    "Can I afford to hire 2 more employees?"
        with col2:
            if st.button("🏢 Should I expand?"):
                st.session_state.quick_q = \
                    "Should I expand my business next month?"
        with col3:
            if st.button("💵 Cash flow safe?"):
                st.session_state.quick_q = \
                    "Is my cash flow safe for next 3 months?"
        with col4:
            if st.button("✂️ Cut expenses?"):
                st.session_state.quick_q = \
                    "Which expenses should I cut first?"

        st.divider()

        for chat in st.session_state.chat_history:
            if chat["role"] == "user":
                with st.chat_message("user"):
                    st.write(chat["content"])
            else:
                with st.chat_message("assistant", avatar="📊"):
                    st.write(chat["content"])

        if "quick_q" in st.session_state and \
                st.session_state.quick_q:
            question = st.session_state.quick_q
            st.session_state.quick_q = None
            with st.chat_message("user"):
                st.write(question)
            with st.chat_message("assistant", avatar="📊"):
                with st.spinner("Analyzing..."):
                    answer = ask_finsight(
                        question, kpis,
                        st.session_state.chat_history)
                st.write(answer)
            st.session_state.chat_history.append(
                {"role": "user", "content": question})
            st.session_state.chat_history.append(
                {"role": "assistant", "content": answer})
            try:
                mysql_save_chat(question, answer)
                save_user_chat(user["id"], question, answer)
            except:
                pass
            st.rerun()

        question = st.chat_input(
            "Ask anything about your finances...")
        if question:
            with st.chat_message("user"):
                st.write(question)
            with st.chat_message("assistant", avatar="📊"):
                with st.spinner("Analyzing..."):
                    answer = ask_finsight(
                        question, kpis,
                        st.session_state.chat_history)
                st.write(answer)
            st.session_state.chat_history.append(
                {"role": "user", "content": question})
            st.session_state.chat_history.append(
                {"role": "assistant", "content": answer})
            try:
                mysql_save_chat(question, answer)
                save_user_chat(user["id"], question, answer)
            except:
                pass
            st.rerun()

        if st.session_state.chat_history:
            if st.button("🗑️ Clear Chat"):
                st.session_state.chat_history = []
                st.rerun()

    # ══════════════════════════════════
    #       PAGE 7 — MY HISTORY
    # ══════════════════════════════════
    elif page == "📜 My History":
        st.markdown("""
            <div class="header-box">
                <h2 style='margin:0'>📜 My History</h2>
                <p style='margin:0;opacity:0.85'>
                All your activity in one place</p>
            </div>
        """, unsafe_allow_html=True)

        st.markdown(
            f"<p style='color:#667eea;font-size:1.1em;'>"
            f"👤 Showing history for: "
            f"<b>{user['full_name']}</b></p>",
            unsafe_allow_html=True
        )

        tab1, tab2, tab3 = st.tabs([
            "📂 Upload History",
            "🤖 AI Chat History",
            "📧 Email History"
        ])

        # ── Upload History ──
        with tab1:
            st.subheader("📂 Your Upload History")
            uploads = get_upload_history(user["id"])

            if uploads:
                # Score trend chart
                if len(uploads) > 1:
                    df_up = pd.DataFrame(uploads)
                    df_up["uploaded_at"] = pd.to_datetime(
                        df_up["uploaded_at"])
                    fig_trend = px.line(
                        df_up,
                        x="uploaded_at",
                        y="company_score",
                        markers=True,
                        title="Your Company Score Over Time",
                        color_discrete_sequence=["#667eea"],
                        template="plotly_white"
                    )
                    fig_trend.update_layout(
                        xaxis_title="Date",
                        yaxis_title="Score",
                        margin=dict(t=40)
                    )
                    st.plotly_chart(fig_trend,
                                   use_container_width=True)

                # Upload table
                for upload in uploads:
                    score = upload["company_score"]
                    score_color = (
                        "#00CC96" if score >= 75
                        else "#FFA500" if score >= 50
                        else "#EF553B"
                    )
                    st.markdown(
                        f"<div style='background:white;"
                        f"padding:15px;border-radius:10px;"
                        f"margin:6px 0;"
                        f"box-shadow:0 2px 8px rgba(0,0,0,0.06);"
                        f"border-left:5px solid {score_color};'>"
                        f"<div style='display:flex;"
                        f"justify-content:space-between;'>"
                        f"<b>📂 {upload['filename']}</b>"
                        f"<span style='color:#888;font-size:0.85em'>"
                        f"{str(upload['uploaded_at'])[:16]}</span>"
                        f"</div>"
                        f"<div style='display:flex;gap:20px;"
                        f"margin-top:8px;'>"
                        f"<span>💰 ₹{upload['total_revenue']:,.0f}</span>"
                        f"<span>📈 ₹{upload['net_profit']:,.0f}</span>"
                        f"<span style='color:{score_color};"
                        f"font-weight:bold;'>"
                        f"🏆 Score: {score}/100</span>"
                        f"<span style='color:{score_color}'>"
                        f"{upload['company_position']}</span>"
                        f"</div></div>",
                        unsafe_allow_html=True
                    )
            else:
                st.info("No upload history yet — "
                        "upload an Excel file to start tracking")

        # ── AI Chat History ──
        with tab2:
            st.subheader("🤖 Your AI Chat History")
            chats = get_user_chats(user["id"])

            if chats:
                st.caption(f"Total questions asked: {len(chats)}")
                for chat in chats:
                    with st.expander(
                            f"Q: {str(chat['question'])[:70]}..."):
                        st.markdown(
                            f"**Question:** {chat['question']}")
                        st.markdown(f"**Answer:** {chat['answer']}")
                        st.caption(
                            f"Asked at: {chat['asked_at']}")
            else:
                st.info("No chat history yet — "
                        "ask AI a question first")

        # ── Email History ──
        with tab3:
            st.subheader("📧 Your Email Alert History")
            emails = get_email_history(user["id"])

            if emails:
                for em in emails:
                    alert_color = (
                        "#EF553B"
                        if em["alert_type"] == "Critical"
                        else "#667eea"
                    )
                    st.markdown(
                        f"<div style='background:white;"
                        f"padding:12px;border-radius:8px;"
                        f"margin:5px 0;"
                        f"border-left:4px solid {alert_color};'>"
                        f"<b>📧 Sent to:</b> {em['sent_to']} | "
                        f"<b>Type:</b> "
                        f"<span style='color:{alert_color}'>"
                        f"{em['alert_type']}</span> | "
                        f"<b>Time:</b> "
                        f"{str(em['sent_at'])[:16]}"
                        f"</div>",
                        unsafe_allow_html=True
                    )
            else:
                st.info("No emails sent yet")

    # ══════════════════════════════════
    #      PAGE 8 — DATABASE VIEWER
    # ══════════════════════════════════
    elif page == "🗄️ Database Viewer":
        st.markdown("""
            <div class="header-box">
                <h2 style='margin:0'>🗄️ Database Viewer</h2>
                <p style='margin:0;opacity:0.85'>
                MySQL (XAMPP) financial data warehouse</p>
            </div>
        """, unsafe_allow_html=True)

        if mysql_check_connection():
            st.success("🟢 MySQL (XAMPP) — Connected")
        else:
            st.error("🔴 MySQL — Not Connected. Start XAMPP!")
            st.info("💡 Start XAMPP → Start MySQL → Refresh")

        st.divider()

        tab1, tab2, tab3, tab4 = st.tabs([
            "📊 Financial Data",
            "📸 Score Snapshots",
            "💬 AI Chat History",
            "🔍 Run SQL Query"
        ])

        with tab1:
            st.subheader("Financial Data in MySQL")
            if mysql_check_connection():
                table_choice = st.selectbox(
                    "Select table:",
                    ["Income", "Expenses", "Cash Flow"])
                table_map = {
                    "Income": "income",
                    "Expenses": "expenses",
                    "Cash Flow": "cash_flow"
                }
                df, err = mysql_run_query(
                    f"SELECT * FROM "
                    f"{table_map[table_choice]}")
                if err:
                    st.error(f"❌ {err}")
                elif df is not None:
                    st.success(f"✅ {len(df)} records")
                    st.dataframe(df, use_container_width=True,
                                hide_index=True)
            else:
                st.warning("Start XAMPP MySQL to view data")

        with tab2:
            st.subheader("Company Health Snapshots")
            mysql_snaps = mysql_get_snapshots()
            if mysql_snaps:
                df_snap = pd.DataFrame(mysql_snaps)
                st.dataframe(df_snap, use_container_width=True,
                            hide_index=True)
                if len(df_snap) > 1:
                    fig = px.line(df_snap,
                                 x="snapshot_date",
                                 y="company_score",
                                 markers=True,
                                 title="Score Over Time",
                                 color_discrete_sequence=
                                 ["#667eea"])
                    st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("No snapshots yet")

        with tab3:
            st.subheader("AI Chat History")
            mysql_chats = mysql_get_chat_history()
            if mysql_chats:
                for chat in mysql_chats[:15]:
                    q = str(chat['question'])[:60]
                    with st.expander(f"Q: {q}..."):
                        st.markdown(
                            f"**Q:** {chat['question']}")
                        st.markdown(
                            f"**A:** {chat['answer']}")
                        st.caption(
                            f"Asked: {chat['asked_at']}")
            else:
                st.info("No chat history yet")

        with tab4:
            st.subheader("🔍 Run Live SQL Queries")
            preset = st.selectbox("Preset Queries:", [
                "Custom",
                "All users",
                "Total revenue by month",
                "Highest expense month",
                "Average profit margin",
                "All company snapshots",
                "Upload history all users",
                "Recent AI questions"
            ])

            presets = {
                "All users":
                    "SELECT id, username, full_name, email, role, created_at FROM users",
                "Total revenue by month":
                    "SELECT month, revenue, total_income FROM income",
                "Highest expense month":
                    "SELECT month, total_expenses FROM expenses ORDER BY total_expenses DESC LIMIT 1",
                "Average profit margin":
                    "SELECT AVG((i.revenue - e.total_expenses) * 100.0 / i.revenue) AS avg_margin FROM income i JOIN expenses e ON i.month = e.month",
                "All company snapshots":
                    "SELECT * FROM company_snapshots ORDER BY snapshot_date DESC",
                "Upload history all users":
                    "SELECT u.username, h.filename, h.company_score, h.uploaded_at FROM upload_history h JOIN users u ON h.user_id = u.id ORDER BY h.uploaded_at DESC",
                "Recent AI questions":
                    "SELECT question, asked_at FROM ai_chat_history ORDER BY asked_at DESC LIMIT 10"
            }

            default_q = (presets.get(preset, "")
                        if preset != "Custom" else "")
            query = st.text_area("SQL Query:",
                                value=default_q, height=100)

            if st.button("▶️ Run Query", type="primary"):
                if not query.strip():
                    st.warning("⚠️ Enter a query first")
                elif mysql_check_connection():
                    with st.spinner("Running..."):
                        result, err = mysql_run_query(query)
                    if err:
                        st.error(f"❌ {err}")
                    elif result is not None and not result.empty:
                        st.success(f"✅ {len(result)} rows")
                        st.dataframe(result,
                                    use_container_width=True,
                                    hide_index=True)
                        csv = result.to_csv(
                            index=False).encode("utf-8")
                        st.download_button(
                            "📥 Download CSV", data=csv,
                            file_name="query_result.csv",
                            mime="text/csv")
                    else:
                        st.info("Query returned no rows")
                else:
                    st.error("❌ Start XAMPP MySQL first!")

# ══════════════════════════════════
#       NO FILE UPLOADED YET
# ══════════════════════════════════
else:
    if page == "📜 My History":
        st.markdown("""
            <div class="header-box">
                <h2 style='margin:0'>📜 My History</h2>
                <p style='margin:0;opacity:0.85'>
                All your activity in one place</p>
            </div>
        """, unsafe_allow_html=True)

        st.markdown(
            f"<p style='color:#667eea;font-size:1.1em;'>"
            f"👤 <b>{user['full_name']}</b></p>",
            unsafe_allow_html=True
        )

        tab1, tab2, tab3 = st.tabs([
            "📂 Upload History",
            "🤖 AI Chat History",
            "📧 Email History"
        ])

        with tab1:
            uploads = get_upload_history(user["id"])
            if uploads:
                if len(uploads) > 1:
                    df_up = pd.DataFrame(uploads)
                    fig_trend = px.line(
                        df_up, x="uploaded_at",
                        y="company_score",
                        markers=True,
                        title="Your Company Score Over Time",
                        color_discrete_sequence=["#667eea"],
                        template="plotly_white"
                    )
                    st.plotly_chart(fig_trend,
                                   use_container_width=True)
                for upload in uploads:
                    score = upload["company_score"]
                    score_color = (
                        "#00CC96" if score >= 75
                        else "#FFA500" if score >= 50
                        else "#EF553B"
                    )
                    st.markdown(
                        f"<div style='background:white;"
                        f"padding:15px;border-radius:10px;"
                        f"margin:6px 0;"
                        f"border-left:5px solid {score_color};'>"
                        f"<b>📂 {upload['filename']}</b> — "
                        f"{str(upload['uploaded_at'])[:16]}<br>"
                        f"💰 ₹{upload['total_revenue']:,.0f} | "
                        f"🏆 Score: "
                        f"<b style='color:{score_color}'>"
                        f"{score}/100</b> | "
                        f"{upload['company_position']}"
                        f"</div>",
                        unsafe_allow_html=True
                    )
            else:
                st.info("No upload history yet")

        with tab2:
            chats = get_user_chats(user["id"])
            if chats:
                for chat in chats:
                    with st.expander(
                            f"Q: {str(chat['question'])[:70]}..."):
                        st.markdown(
                            f"**Q:** {chat['question']}")
                        st.markdown(f"**A:** {chat['answer']}")
                        st.caption(f"{chat['asked_at']}")
            else:
                st.info("No chat history yet")

        with tab3:
            emails = get_email_history(user["id"])
            if emails:
                for em in emails:
                    st.markdown(
                        f"📧 **{em['sent_to']}** | "
                        f"{em['alert_type']} | "
                        f"{str(em['sent_at'])[:16]}")
            else:
                st.info("No emails sent yet")

    else:
        st.markdown("""
            <div class="header-box">
                <h1 style='margin:0'>📊 FinSight</h1>
                <p style='margin:0;font-size:1.2em;opacity:0.9'>
                AI-Powered Financial Advisor for Indian SMEs</p>
            </div>
        """, unsafe_allow_html=True)

        st.markdown(
            f"### 👋 Welcome, {user['full_name']}!")
        st.markdown(
            "### 👈 Upload your Excel file in the sidebar to begin")
        st.divider()

        col1, col2, col3, col4 = st.columns(4)
        col1.info("📊 **Dashboard**\n\nCharts + PDF download")
        col2.info("📋 **P&L Statement**\n\nMonth-wise breakdown")
        col3.info("🏢 **Company Position**\n\nHealth score + radar")
        col4.info("🤖 **Ask AI**\n\nChat with AI advisor")

        st.divider()
        st.markdown(
            "#### 📁 Excel needs 3 sheets: "
            "`Income`, `Expenses`, `Cash`")