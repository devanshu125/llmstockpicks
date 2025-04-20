import streamlit as st
import yfinance as yf
import mplfinance as mpf
import matplotlib.pyplot as plt
import base64
import requests
import os
import json
import re
from io import BytesIO
from datetime import datetime, timedelta
import pandas as pd
import plotly.graph_objects as go

# API Key
openrouter_api_key = os.getenv("OPENROUTER_API_KEY")
MODEL_NAME = "google/gemini-2.0-flash-exp:free"

# Function to fetch stock data
def get_stock_data(stock_symbol):
    data = yf.download(stock_symbol, period="3mo", interval="1d")
    if isinstance(data.columns, pd.MultiIndex):
        data = data.droplevel(1, axis=1)
    return data

# Function to create and return a candlestick chart as an image
def generate_candlestick_chart(data):
    fig, ax = plt.subplots(figsize=(8, 6))
    mpf.plot(data, type='candle', style='charles', ax=ax, volume=False)
    buffer = BytesIO()
    fig.savefig(buffer, format="png", bbox_inches="tight")
    plt.close(fig)
    buffer.seek(0)
    return buffer

# Function to encode image to base64
def encode_image_to_base64(image_buffer):
    return base64.b64encode(image_buffer.read()).decode("utf-8")

# Function to send chart to OpenRouter API
def send_to_openrouter(base64_image, req_prompt):
    url = "https://openrouter.ai/api/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {openrouter_api_key}",
        "Content-Type": "application/json"
    }
    data = {
        "model": MODEL_NAME,
        "messages": [
            {"role": "user", "content": [
                {"type": "text", "text": req_prompt},
                {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{base64_image}"}}
            ]}
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

# Streamlit UI
st.title("Stock Analysis with AI Insights")
stock_symbol = st.text_input("Enter Stock Symbol:", "AAPL").upper()

if st.button("Analyze"):
    stock_data = get_stock_data(stock_symbol)
    if not stock_data.empty:
        st.write(f"### Candlestick Chart for {stock_symbol}")
        image_buffer = generate_candlestick_chart(stock_data)
        base64_chart = encode_image_to_base64(image_buffer)
        st.image(f"data:image/png;base64,{base64_chart}")
        
        req_prompt = f"What can you infer from this {stock_symbol} chart? Based on the chart, give me a score of 1-10 on whether you would hold this in your long only portfolio for the upcoming week and give your thought process. Give me JSON output with keys including score and thought_process."
        
        data = send_to_openrouter(base64_chart, req_prompt)
        print(data)
        print(data.keys())
        req_answer = data['choices'][0]['message']['content']
        
        req_answer_json = extract_json_from_text(req_answer)
        # if req_answer_json:
        #     st.subheader("AI Analysis")
        #     st.json(req_answer_json)
        # else:
        #     st.write("Failed to extract JSON response.")
        # After getting the JSON response, replace the simple st.json display with this:
        if req_answer_json:
            st.subheader("AI Analysis")
            
            # Extract values from JSON
            score = req_answer_json.get('score', 0)
            thought_process = req_answer_json.get('thought_process', 'No analysis provided')
            
            # Create columns for better layout
            col1, col2 = st.columns([1, 3])
            
            with col1:
                # Create a score gauge/indicator
                fig = go.Figure(go.Indicator(
                    mode="gauge+number",
                    value=score,
                    domain={'x': [0, 1], 'y': [0, 1]},
                    title={'text': "Investment Score"},
                    gauge={
                        'axis': {'range': [0, 10]},
                        'bar': {'color': "darkblue"},
                        'steps': [
                            {'range': [0, 4], 'color': "red"},
                            {'range': [4, 7], 'color': "yellow"},
                            {'range': [7, 10], 'color': "green"}
                        ],
                        'threshold': {
                            'line': {'color': "black", 'width': 4},
                            'thickness': 0.75,
                            'value': score
                        }
                    }
                ))
                fig.update_layout(height=200, margin=dict(l=20, r=20, t=30, b=20))
                st.plotly_chart(fig, use_container_width=True)
            
            with col2:
                # Display the thought process with better formatting
                st.markdown("### Analysis")
                st.markdown(f"**{thought_process}**")
            
            # Display any other fields that might be in the JSON
            for key, value in req_answer_json.items():
                if key not in ['score', 'thought_process']:
                    if isinstance(value, list):
                        st.markdown(f"### {key.replace('_', ' ').title()}")
                        for item in value:
                            st.markdown(f"- {item}")
                    elif isinstance(value, dict):
                        st.markdown(f"### {key.replace('_', ' ').title()}")
                        st.json(value)
                    elif key not in ['score', 'thought_process']:
                        st.markdown(f"**{key.replace('_', ' ').title()}:** {value}")
        else:
            st.error("Failed to extract JSON response.")
    else:
        st.error("Failed to fetch stock data. Please check the symbol.")
