import yfinance as yf
import mplfinance as mpf
import matplotlib.pyplot as plt
import base64
import os
import requests
from io import BytesIO
from datetime import datetime, timedelta
import pandas as pd
import json
import re

openrouter_api_key = os.environ.get("OPENROUTER_API_KEY", None)
MODEL_NAME =  "google/gemini-2.0-flash-exp:free" #"google/gemini-2.0-flash-lite-preview-02-05:free" "google/gemini-2.0-flash-001"

# Function to fetch stock data
def get_stock_data(stock_symbol):
    print("getting stock data...")
    # end_date = datetime.today().date()
    # start_date = end_date - timedelta(days=90)  # Last 3 months
    data = yf.download(stock_symbol, period="3mo", interval="1d") # yf.download(stock_symbol, start=start_date, end=end_date)
    print(data.shape)
    print("data fetched")
    # Check if MultiIndex exists and fix it
    if isinstance(data.columns, pd.MultiIndex):
        data = data.droplevel(1, axis=1)  # Drop the first level (Ticker name)
    return data

# Function to create and save a candlestick chart
def generate_candlestick_chart(data):
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

    plt.show()

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
stock_symbol = input("Enter stock symbol: ").strip().upper()
stock_data = get_stock_data(stock_symbol)
print(stock_data.head())
req_prompt = f"What can you infer from this {stock_symbol} chart? Based on the chart, give me a score of 1-10 on whether you would hold this in your long only portfolio for the upcoming week and give your thought process. Give me json output with keys including score and thought_process."
if not stock_data.empty:
    base64_chart = generate_candlestick_chart(stock_data)
    data = send_to_openrouter(base64_chart, req_prompt)
    print(data)
    print(data.keys())
    req_answer = data['choices'][0]['message']['content']
    print()
    print(req_answer)

    # extract json part
    req_answer_json = extract_json_from_text(req_answer)
    print()
    print("Json is...")
    print(req_answer_json.keys())
    print(req_answer_json)

else:
    print("Failed to fetch stock data. Please check the symbol.")
