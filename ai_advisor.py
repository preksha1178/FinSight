import requests
import os
GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "your_groq_api_key_here")

def ask_finsight(question, kpis, chat_history=[]):

    system_prompt = f"""
You are FinSight, a smart and friendly AI financial advisor for Indian small businesses (SMEs).
You speak in simple, clear English. You always give a direct YES or NO first, then explain with data.

Current Company Financial Summary:
- Total Revenue: ₹{kpis['total_revenue']:,.0f}
- Total Expenses: ₹{kpis['total_expenses']:,.0f}  
- Net Profit: ₹{kpis['net_profit']:,.0f}
- Average Profit Margin: {kpis['avg_profit_margin']}%
- Current Cash Balance: ₹{kpis['current_cash']:,.0f}
- Cash Runway: {kpis['cash_runway_days']} days
- Monthly Burn Rate: ₹{kpis['burn_rate']:,.0f}
- Best Month: {kpis['best_month']}
- Worst Month: {kpis['worst_month']}
- Avg Revenue Growth: {kpis['avg_growth']}%

Rules:
- Always start with YES ✅ or NO ❌ or CAUTION ⚠️
- Use ₹ for all amounts
- Keep answers under 120 words
- Be direct, helpful and encouraging
- Reference actual numbers from the data above
- If asked something unrelated to finance, politely redirect
"""

    messages = [{"role": "system", "content": system_prompt}]

    for chat in chat_history:
        messages.append({"role": chat["role"], "content": chat["content"]})

    messages.append({"role": "user", "content": question})

    try:
        response = requests.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {GROQ_API_KEY}",
                "Content-Type": "application/json"
            },
            json={
                "model": "llama-3.1-8b-instant",
                "messages": messages,
                "max_tokens": 250,
                "temperature": 0.7
            },
            timeout=30
        )

        # ── Debug: print full response if something goes wrong
        if response.status_code != 200:
            return f"❌ API Error {response.status_code}: {response.json().get('error', {}).get('message', 'Unknown error')}. Please check your API key."

        result = response.json()

        if "choices" not in result:
            return f"❌ Unexpected response: {result}"

        return result["choices"][0]["message"]["content"]

    except requests.exceptions.Timeout:
        return "❌ Request timed out. Groq servers may be slow. Please try again."

    except requests.exceptions.ConnectionError:
        return "❌ No internet connection. Please check your network."

    except Exception as e:
        return f"❌ Unexpected error: {str(e)}"