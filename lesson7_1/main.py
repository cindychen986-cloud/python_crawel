import subprocess
import json
import streamlit as st
import pandas as pd
from datetime import datetime

def get_rates():
    # 執行外部爬蟲腳本，產生 rates.json
    subprocess.run(["python", "fetch_rates_cli.py"], check=True)
    with open("rates.json", "r", encoding="utf-8") as f:
        data = json.load(f)
    return data

def clean_data(data):
    # 過濾無法交易的貨幣（買入或賣出皆為空）
    filtered = []
    for item in data:
        buy = item['本行即期買入'].strip()
        sell = item['本行即期賣出'].strip()
        if buy == '' and sell == '':
            continue
        # 空值顯示"暫停交易"
        item['本行即期買入'] = buy if buy else "暫停交易"
        item['本行即期賣出'] = sell if sell else "暫停交易"
        filtered.append(item)
    return filtered

st.set_page_config(page_title="台幣匯率轉換", layout="wide")
st.title("台幣匯率轉換")

# 自動與手動更新
if 'last_update' not in st.session_state or 'rates' not in st.session_state:
    st.session_state['rates'] = clean_data(get_rates())
    st.session_state['last_update'] = datetime.now()

def update_rates():
    st.session_state['rates'] = clean_data(get_rates())
    st.session_state['last_update'] = datetime.now()

# 每10分鐘自動更新
if (datetime.now() - st.session_state['last_update']).seconds > 600:
    update_rates()

col1, col2 = st.columns(2)

with col1:
    st.header("台幣轉換其它貨幣")
    amount = st.number_input("請輸入台幣金額", min_value=0.0, value=1000.0)
    currency_options = [item['幣別'] for item in st.session_state['rates'] if item['本行即期賣出'] != "暫停交易"]
    currency = st.selectbox("選擇目標貨幣", currency_options)
    rate = next((item for item in st.session_state['rates'] if item['幣別'] == currency), None)
    if rate:
        try:
            sell_rate = float(rate['本行即期賣出'].replace(',', ''))
            converted = amount / sell_rate
            st.write(f"台幣 {amount:,.2f} 元 可兌換 {currency} 約 {converted:,.2f} 元")
        except:
            st.write("此貨幣暫停交易，無法換算。")
    if st.button("手動更新匯率"):
        update_rates()
        st.success("已更新匯率！")

with col2:
    st.header("即時匯率表")
    df = pd.DataFrame(st.session_state['rates'])
    st.dataframe(df, use_container_width=True)
    st.caption(f"最後更新時間：{st.session_state['last_update'].strftime('%Y-%m-%d %H:%M:%S')}")