import subprocess
import json
import streamlit as st
import pandas as pd
from datetime import datetime

def get_rates():
    """執行外部爬蟲腳本,產生 rates.json"""
    try:
        # 執行爬蟲並捕獲輸出
        result = subprocess.run(
            ["python", "fetch_rates_cli.py"], 
            check=True,
            capture_output=True,
            text=True
        )
        
        # 讀取生成的 JSON 檔案
        with open("rates.json", "r", encoding="utf-8") as f:
            data = json.load(f)
        return data
    except subprocess.CalledProcessError as e:
        # 顯示詳細錯誤訊息
        st.error(f"爬蟲執行失敗:")
        st.code(f"錯誤輸出:\n{e.stderr}")
        return []
    except FileNotFoundError:
        st.error("找不到 rates.json 檔案")
        return []
    except json.JSONDecodeError as e:
        st.error(f"JSON 解析失敗: {str(e)}")
        return []
    except Exception as e:
        st.error(f"獲取匯率失敗: {str(e)}")
        return []

def clean_data(data):
    """過濾無法交易的貨幣(買入或賣出皆為空)"""
    filtered = []
    for item in data:
        buy = item.get('本行即期買入', '').strip()
        sell = item.get('本行即期賣出', '').strip()
        if buy == '' and sell == '':
            continue
        # 空值顯示"暫停交易"
        item['本行即期買入'] = buy if buy else "暫停交易"
        item['本行即期賣出'] = sell if sell else "暫停交易"
        filtered.append(item)
    return filtered

def update_rates():
    """更新匯率資料"""
    rates_data = get_rates()
    if rates_data:
        st.session_state['rates'] = clean_data(rates_data)
        st.session_state['last_update'] = datetime.now()
        return True
    return False

# 頁面設定
st.set_page_config(page_title="台幣匯率轉換", layout="wide")
st.title("台幣匯率轉換")

# 初始化 session state
if 'rates' not in st.session_state:
    st.session_state['rates'] = []
    st.session_state['last_update'] = None

# 首次載入或資料為空時取得匯率
if not st.session_state['rates'] or st.session_state['last_update'] is None:
    with st.spinner('正在載入匯率資料...'):
        update_rates()

# 自動更新:每10分鐘
if st.session_state['last_update']:
    time_diff = (datetime.now() - st.session_state['last_update']).total_seconds()
    if time_diff > 600:  # 600秒 = 10分鐘
        update_rates()

# 檢查是否有匯率資料
if not st.session_state['rates']:
    st.warning("無法載入匯率資料,請檢查錯誤訊息")
    st.info("💡 提示: 請確認 crawl4ai 套件已安裝,可執行: pip install crawl4ai")
    st.stop()

# 建立兩欄布局
col1, col2 = st.columns(2)

with col1:
    st.header("台幣轉換其它貨幣")
    
    # 輸入金額
    amount = st.number_input("請輸入台幣金額", min_value=0.0, value=1000.0, step=100.0)
    
    # 可交易的貨幣選項
    currency_options = [
        item['幣別'] 
        for item in st.session_state['rates'] 
        if item['本行即期賣出'] != "暫停交易"
    ]
    
    if not currency_options:
        st.warning("目前沒有可交易的貨幣")
    else:
        currency = st.selectbox("選擇目標貨幣", currency_options)
        
        # 找到對應的匯率
        rate = next(
            (item for item in st.session_state['rates'] if item['幣別'] == currency), 
            None
        )
        
        if rate:
            try:
                sell_rate = float(rate['本行即期賣出'].replace(',', ''))
                converted = amount / sell_rate
                st.success(f"💰 台幣 **{amount:,.2f}** 元 可兌換 **{currency}** 約 **{converted:,.2f}** 元")
            except (ValueError, ZeroDivisionError):
                st.error("此貨幣暫停交易,無法換算。")
    
    # 手動更新按鈕
    st.divider()
    if st.button("🔄 手動更新匯率", use_container_width=True):
        with st.spinner('正在更新匯率...'):
            if update_rates():
                st.success("✅ 已更新匯率!")
                st.rerun()
            else:
                st.error("更新失敗,請查看上方錯誤訊息")

with col2:
    st.header("即時匯率表")
    
    # 顯示匯率表格
    if st.session_state['rates']:
        df = pd.DataFrame(st.session_state['rates'])
        st.dataframe(df, use_container_width=True, hide_index=True)
        
        # 顯示最後更新時間
        if st.session_state['last_update']:
            update_time = st.session_state['last_update'].strftime('%Y-%m-%d %H:%M:%S')
            st.caption(f"📅 最後更新時間: {update_time}")
    else:
        st.info("暫無匯率資料")