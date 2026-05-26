import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime

def send_alert_email(sender_email, sender_password, receiver_email, kpis, warnings):
    """Send financial alert email automatically"""

    # Build alert level
    critical = any("🚨" in w for w in warnings)
    subject_prefix = "🚨 CRITICAL" if critical else "⚠️ WARNING"

    subject = f"{subject_prefix} — FinSight Financial Alert | {datetime.now().strftime('%d %b %Y')}"

    # Build email body
    warnings_html = "".join([f"<li>{w}</li>" for w in warnings])

    body = f"""
    <html>
    <body style="font-family: Arial, sans-serif; max-width: 600px; margin: auto;">

        <div style="background: linear-gradient(135deg, #667eea, #764ba2);
                    padding: 20px; border-radius: 10px; color: white;">
            <h2 style="margin:0">📊 FinSight Financial Alert</h2>
            <p style="margin:0;opacity:0.9">{datetime.now().strftime('%d %B %Y')}</p>
        </div>

        <div style="padding: 20px; background: #f8f9fa; margin-top: 10px; border-radius: 10px;">
            <h3>📈 Current Financial Summary</h3>
            <table style="width:100%; border-collapse: collapse;">
                <tr style="background:#667eea; color:white;">
                    <th style="padding:10px; text-align:left">Metric</th>
                    <th style="padding:10px; text-align:right">Value</th>
                </tr>
                <tr style="background:white;">
                    <td style="padding:10px; border-bottom:1px solid #eee">💰 Total Revenue</td>
                    <td style="padding:10px; text-align:right; border-bottom:1px solid #eee">
                        ₹{kpis['total_revenue']:,.0f}</td>
                </tr>
                <tr style="background:#f8f9fa;">
                    <td style="padding:10px; border-bottom:1px solid #eee">📈 Net Profit</td>
                    <td style="padding:10px; text-align:right; border-bottom:1px solid #eee">
                        ₹{kpis['net_profit']:,.0f}</td>
                </tr>
                <tr style="background:white;">
                    <td style="padding:10px; border-bottom:1px solid #eee">📊 Profit Margin</td>
                    <td style="padding:10px; text-align:right; border-bottom:1px solid #eee">
                        {kpis['avg_profit_margin']}%</td>
                </tr>
                <tr style="background:#f8f9fa;">
                    <td style="padding:10px;">⏳ Cash Runway</td>
                    <td style="padding:10px; text-align:right;">
                        {kpis['cash_runway_days']} days</td>
                </tr>
            </table>
        </div>

        <div style="padding: 20px; background: #fff3cd;
                    margin-top: 10px; border-radius: 10px;
                    border-left: 5px solid #ffc107;">
            <h3>⚠️ Alerts Detected</h3>
            <ul>{warnings_html}</ul>
        </div>

        <div style="padding: 20px; background: #d1ecf1;
                    margin-top: 10px; border-radius: 10px;
                    border-left: 5px solid #17a2b8;">
            <h3>💡 Recommended Actions</h3>
            <ul>
                <li>Review your expense breakdown in FinSight dashboard</li>
                <li>Check cash flow for next 30 days immediately</li>
                <li>Use FinSight AI advisor for specific financial questions</li>
            </ul>
        </div>

        <div style="padding: 15px; text-align:center;
                    color: #666; margin-top: 10px;">
            <p>Sent automatically by <strong>FinSight AI</strong> —
            Your Financial Health Monitor</p>
        </div>

    </body>
    </html>
    """

    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = sender_email
        msg["To"] = receiver_email
        msg.attach(MIMEText(body, "html"))

        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(sender_email, sender_password)
            server.sendmail(sender_email, receiver_email, msg.as_string())

        return True, "✅ Alert email sent successfully!"

    except smtplib.SMTPAuthenticationError:
        return False, "❌ Gmail authentication failed. Check App Password."
    except Exception as e:
        return False, f"❌ Error: {str(e)}"

def check_alerts_needed(kpis):
    """Check if situation is serious enough to send alert"""
    reasons = []
    if kpis["cash_runway_days"] < 60:
        reasons.append(f"Cash runway critically low: {kpis['cash_runway_days']} days")
    if kpis["avg_profit_margin"] < 15:
        reasons.append(f"Profit margin dangerously low: {kpis['avg_profit_margin']}%")
    if kpis["net_profit"] < 0:
        reasons.append("Business is running at a LOSS")
    return reasons