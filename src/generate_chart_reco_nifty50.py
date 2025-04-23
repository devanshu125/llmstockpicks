import yfinance as yf
import mplfinance as mpf
import matplotlib.pyplot as plt
import base64
import os
import requests
from io import BytesIO
import pandas as pd
import json
import re
import time
import datetime as dt

# fetch components of nifty50
link = (
    "https://en.wikipedia.org/wiki/NIFTY_50"
)
nifty50_df = pd.read_html(link, header=0)[1]
print(nifty50_df.shape)
print(nifty50_df.head(10))

symbol_list = nifty50_df['Symbol'].tolist()
# yfinance will accept with ".NS" in the end
symbol_list = [f"{s}.NS" for s in symbol_list]
print(symbol_list[:5])

openrouter_api_key = os.environ.get("OPENROUTER_API_KEY", None)
MODEL_NAME = "google/gemini-2.0-flash-exp:free" # "google/gemini-2.0-flash-001" # ""google/gemini-2.0-flash-exp:free""

# Function to fetch stock data
def get_stock_data(stock_symbol):
    # end_date = datetime.today().date()
    # start_date = end_date - timedelta(days=90)  # Last 3 months
    data = yf.download(stock_symbol, period="3mo", interval="1d") # yf.download(stock_symbol, start=start_date, end=end_date)
    # Check if MultiIndex exists and fix it
    if isinstance(data.columns, pd.MultiIndex):
        data = data.droplevel(1, axis=1)  # Drop the first level (Ticker name)
    return data

# Function to create and save a candlestick chart
def generate_candlestick_chart(data, stock_symbol):
    """Generates a candlestick chart and returns it as a base64 image."""
    
    # Create a Matplotlib Figure and Axes
    fig, ax = plt.subplots(figsize=(8, 6))  

    # Ensure mplfinance plots on the given Axes
    mpf.plot(
        data, 
        type='candle', 
        style='charles', 
        ax=ax, 
        volume=False
    )

    # plt.show()

    # Save figure to a BytesIO buffer
    print("Saving figure...")
    buffer = BytesIO()
    fig.savefig(buffer, format="png", bbox_inches="tight")
    plt.close(fig)  # Prevents duplicate figures in memory

    # Convert image to Base64
    print("Converting to base_64...")
    buffer.seek(0)
    base64_str = base64.b64encode(buffer.read()).decode("utf-8")

    return f"data:image/png;base64,{base64_str}"

# Function to send chart to OpenRouter API
def send_to_openrouter(base64_image, req_prompt):
    print("Sending to openrouter...")
    url = "https://openrouter.ai/api/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {openrouter_api_key}",
        "Content-Type": "application/json"
    }

    data = {
        "model": MODEL_NAME,  # Ensure the model supports images
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": req_prompt},
                    {"type": "image_url", "image_url": {"url": base64_image}}
                ]
            }
        ]
    }

    response = requests.post(url, headers=headers, json=data)
    return response.json()


def extract_json_from_text(text):
    """
    Extracts JSON content from a given text. It handles both structured JSON (inside triple backticks)
    and inline JSON formats.
    
    :param text: The input text containing JSON.
    :return: Parsed JSON as a Python dictionary, or None if extraction fails.
    """
    try:
        # Attempt to extract JSON wrapped in triple backticks (```json ... ```)
        match = re.search(r"```json\s*([\s\S]+?)\s*```", text)
        
        if match:
            json_str = match.group(1).strip()  # Extract JSON part
        else:
            # Fallback: Extract inline JSON (first valid {...} block)
            match = re.search(r"\{[\s\S]*\}", text)
            if match:
                json_str = match.group().strip()
            else:
                return None  # No JSON found
        
        # Convert string to dictionary
        return json.loads(json_str)
    
    except json.JSONDecodeError:
        return None  # JSON extraction failed

# Main execution
data_list = []
for idx, stock_symbol in enumerate(symbol_list):

    if (idx+1) % 10 == 0:
        print("Sleeping for 2 seconds to avoid any rate limit issue...")
        time.sleep(2)

    print(f"Analysing for {stock_symbol}")
    req_stock_data = {}
    stock_data = get_stock_data(stock_symbol)
    req_prompt = f"What can you infer from this {stock_symbol} chart? Based on the chart, give me a score of 1-10 on whether you would hold this in your long only portfolio for the upcoming week and give your thought process. Give me json output with keys including score and thought_process."
    if not stock_data.empty:

        try:
            base64_chart = generate_candlestick_chart(stock_data, stock_symbol)
            data = send_to_openrouter(base64_chart, req_prompt)
            req_answer = data['choices'][0]['message']['content']
            req_stock_data['stock_name'] = stock_symbol
            req_stock_data['llm_output'] = req_answer

            # extract json part
            req_answer_json = extract_json_from_text(req_answer)
            req_stock_data['score'] = req_answer_json['score']
            req_stock_data['thought_process'] = req_answer_json['thought_process']

            data_list.append(req_stock_data)
            print()
        
        except Exception as e:
            print(f"Error with {stock_symbol}: {e}")
            continue

    else:
        print("Failed to fetch stock data. Please check the symbol.")

run_date = str(dt.datetime.now().date())
results_df = pd.DataFrame(data_list)
results_df = results_df.sort_values(by='score', ascending=False)
print("Top 20 stocks...")
print(results_df.head(20))
results_df.to_csv(f"../nifty50_data/recommendations_{run_date}.csv", index=False)
