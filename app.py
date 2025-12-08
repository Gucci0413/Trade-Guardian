import streamlit as st
import requests
import pandas as pd
import time
import yfinance as yf
from bs4 import BeautifulSoup

# --- ページ設定 (必ず一番上に書く) ---
st.set_page_config(page_title="Trade Guardian Pro", page_icon="🛡️", layout="wide")

# --- クラス定義 ---
class TradeGuardianUI:
    def __init__(self, refresh_token):
        self.base_url = "https://api.jquants.com/v1"
        self.refresh_token = refresh_token
        self.id_token = None
        
    def authenticate(self):
        if not self.refresh_token: return False
        try:
            url = f"{self.base_url}/token/auth_refresh"
            params = {"refreshtoken": self.refresh_token}
            response = requests.post(url, params=params)
            if response.status_code == 200:
                self.id_token = response.json().get("idToken")
                return True
            else: return False
        except: return False

    def get_stock_data_yf(self, code):
        """株価取得"""
        try:
            search_code = code[:-1] if (len(code) == 5 and code.endswith('0')) else code
            ticker = yf.Ticker(f"{search_code}.T")
            hist = ticker.history(period="1d")
            current_price = float(hist['Close'].iloc[-1]) if not hist.empty else None
            per = ticker.info.get('trailingPE', None)
            return current_price, per, ticker
        except: return None, None, None

    def analyze_sector(self, sector_name, limit=30):
        """Sランク分析"""
        if not self.id_token: return []
        
        url = f"{self.base_url}/listed/info"
        headers = {"Authorization": f"Bearer {self.id_token}"}
        resp = requests.get(url, headers=headers)
        
        target_list = []
        if resp.status_code == 200:
            for item in resp.json().get("info", []):
                if item.get("Sector33CodeName") == sector_name:
                    target_list.append(item.get("Code"))
        
        target_list = target_list[:limit]
        results = []
        
        progress_bar = st.progress(0)
        status_text = st.empty()

        for i, code in enumerate(target_list):
            progress = (i + 1) / len(target_list)
            progress_bar.progress(progress)
            status_text.text(f"分析中: {code} ...")
            time.sleep(0.05) 
            
            try:
                f_url = f"{self.base_url}/fins/statements"
                f_resp = requests.get(f_url, headers=headers, params={"code": code})
                if f_resp.status_code == 200:
                    data = f_resp.json().get("statements", [])
                    sorted_data = sorted(data, key=lambda x: x['DisclosedDate'])
                    if len(sorted_data) >= 2:
                        latest = sorted_data[-1]
                        prev = sorted_data[-2]
                        
                        op_now = float(latest.get("OperatingProfit", 0) or 0)
                        op_prev = float(prev.get("OperatingProfit", 0) or 0)
                        sales_now = float(latest.get("NetSales", 0) or 0)
                        
                        # データ取得 (欠損対応)
                        try:
                            net_income = float(latest.get("ProfitLossAttributableToOwnersOfParent", 0))
                            net_assets = float(latest.get("NetAssets", 0))
                            total_assets = float(latest.get("TotalAssets", 0))
                        except:
                            net_income = 0; net_assets = 0; total_assets = 0

                        if op_prev > 0 and sales_now > 0:
                            growth = ((op_now - op_prev) / op_prev) * 100
                            margin = (op_now / sales_now) * 100
                            
                            roe = (net_income / net_assets) * 100 if net_assets > 0 else None
                            equity_ratio = (net_assets / total_assets) * 100 if total_assets > 0 else None
                            
                            rank = "B"
                            if growth >= 20.0 and margin >= 10.0: rank = "S"
                            elif growth >= 10.0: rank = "A"

                            if rank in ["S", "A"]: 
                                price, per, ticker = self.get_stock_data_yf(code)
                                # AIコメント簡易生成
                                ai_comment = f"成長率{growth:.1f}% 利益率{margin:.1f}%"
                                if per and per < 15: ai_comment += " | 💎割安"
                                if roe and roe >= 8: ai_comment += " | 👑高効率"

                                results.append({
                                    "コード": code, "ランク": rank, "PER": per,
                                    "ROE(%)": roe, "自己資本比率(%)": equity_ratio,
                                    "成長率": growth, "利益率": margin,
                                    "AI解説": ai_comment, "Ticker": ticker
                                })
            except: pass
        
        status_text.text("完了！")
        return results

# --- UI構築 ---
st.title("🛡️ Trade Guardian Pro")

# --- サイドバー (ここを完全に修正しました) ---
with st.sidebar:
    st.header("⚙️ 設定 & 管理")
    refresh_token = st.text_input("J-Quantsトークン", type="password")
    st.divider()
    
    # --- 監視リスト管理 ---
    st.subheader("📝 監視リスト")
    
    # セッション初期化
    if "portfolio" not in st.session_state:
        st.session_state.portfolio = [{"code": "228A", "entry": 500}]

    # 1. 追加エリア
    with st.form("add_form", clear_on_submit=True):
        st.write("▼ 新規追加")
        col_in1, col_in2 = st.columns(2)
        with col_in1:
            in_code = st.text_input("コード", placeholder="7203")
        with col_in2:
            in_price = st.number_input("単価", min_value=0)
        
        submitted = st.form_submit_button("リストに追加")
        if submitted and in_code and in_price > 0:
            st.session_state.portfolio.append({"code": in_code, "entry": in_price})
            st.success("追加しました")
            st.rerun()

    # 2. 削除エリア (確実に表示させるロジック)
    st.write("---")
    st.write("▼ 現在のリスト (削除はゴミ箱)")
    
    if len(st.session_state.portfolio) == 0:
        st.info("登録なし")
    else:
        # 削除ボタンの処理
        for i, item in enumerate(st.session_state.portfolio):
            # カラム比率を変えてボタンを押しやすく
            col_text, col_btn = st.columns([3, 1])
            
            with col_text:
                st.text(f"{item['code']} (¥{item['entry']})")
            
            with col_btn:
                # 削除ボタン
                if st.button("🗑️", key=f"delete_{i}"):
                    st.session_state.portfolio.pop(i)
                    st.rerun()

# --- メイン画面 ---
tab1, tab2 = st.tabs(["📊 監視 & チャート", "⚖️ Sランク分析"])

with tab1:
    st.subheader(f"ポートフォリオ ({len(st.session_state.portfolio)}銘柄)")
    
    if st.button("株価更新 🔄", type="primary"):
        app = TradeGuardianUI(refresh_token)
        for item in st.session_state.portfolio:
            code = item["code"]
            entry = item["entry"]
            price, per, ticker = app.get_stock_data_yf(code)
            
            with st.container():
                st.markdown(f"#### {code}")
                cols = st.columns([2, 3])
                if price:
                    pct = ((price - entry) / entry) * 100
                    
                    # 段階的通知ロジック
                    status = "🟢 監視中"; color = "off"
                    if pct <= -10: status = "⛔ 損切り (-10%)"; color = "inverse"
                    elif pct <= -3: status = "⚠️ 警戒 (-3%〜)"
                    elif pct >= 20: status = "🎉 利確 (+20%)"
                    elif pct >= 5: status = "📈 上昇 (+5%〜)"

                    with cols[0]:
                        st.metric(label=status, value=f"{price:,.0f}円", delta=f"{pct:+.2f}%")
                    with cols[1]:
                        if ticker: st.line_chart(ticker.history(period="1y")['Close'], height=150)
                else:
                    st.error("取得エラー")
                st.divider()

with tab2:
    st.write("Sランク分析画面 (設定からトークンを入れてください)")
    col1, col2 = st.columns([2,1])
    with col1: target = st.selectbox("業種", ["情報･通信業", "電気機器", "サービス業", "医薬品"])
    with col2: limit = st.number_input("上限", value=10)
    
    if st.button("分析開始 🔍"):
        app = TradeGuardianUI(refresh_token)
        if app.authenticate():
            res = app.analyze_sector(target, limit)
            if res:
                for r in res:
                    with st.expander(f"{r['ランク']}ランク: {r['コード']}"):
                        st.write(r['AI解説'])
                        if r['Ticker']: st.line_chart(r['Ticker'].history(period="1y")['Close'])
            else: st.warning("なし")
        else: st.error("認証エラー")
