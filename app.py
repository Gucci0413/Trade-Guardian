import streamlit as st
import requests
import pandas as pd
import time
import yfinance as yf # チャート用
from bs4 import BeautifulSoup
from datetime import datetime, timedelta

# --- ページ設定 ---
st.set_page_config(
    page_title="Trade Guardian AI",
    page_icon="🛡️",
    layout="wide"
)

# --- クラス定義 ---
class TradeGuardianUI:
    def __init__(self, refresh_token):
        self.base_url = "https://api.jquants.com/v1"
        self.refresh_token = refresh_token
        self.id_token = None
        
    def authenticate(self):
        """認証処理"""
        if not self.refresh_token: return False
        try:
            url = f"{self.base_url}/token/auth_refresh"
            params = {"refreshtoken": self.refresh_token}
            response = requests.post(url, params=params)
            if response.status_code == 200:
                self.id_token = response.json().get("idToken")
                return True
            else:
                return False
        except: return False

    def get_yahoo_price(self, code):
        """現在値取得"""
        try:
            search_code = code[:-1] if (len(code) == 5 and code.endswith('0')) else code
            url = f"https://finance.yahoo.co.jp/quote/{search_code}.T"
            headers = {"User-Agent": "Mozilla/5.0"}
            r = requests.get(url, headers=headers, timeout=5)
            if r.status_code == 200:
                soup = BeautifulSoup(r.text, 'html.parser')
                span = soup.select_one('span[class*="_3rXWJKZF"]') or soup.select_one('span[class*="StyledNumber__value"]')
                if span: return float(span.text.replace(',', ''))
        except: pass
        return None

    def get_stock_history(self, code):
        """★新機能: 過去1年間の株価データを取得"""
        try:
            search_code = code[:-1] if (len(code) == 5 and code.endswith('0')) else code
            # yfinanceを使ってデータを取得
            ticker = yf.Ticker(f"{search_code}.T")
            hist = ticker.history(period="1y")
            return hist
        except:
            return pd.DataFrame()

    def generate_ai_comment(self, code, growth, margin, op_profit):
        """★新機能: AIが「なぜ買いか」を分析して文章化"""
        comment = f"**【AI分析レポート: {code}】**\n\n"
        
        # 1. 成長性評価
        if growth > 100:
            comment += f"🚀 **爆発的な成長力:** 前期比で利益が{growth:.1f}%も増加しており、事業が急拡大フェーズにあります。\n"
        elif growth > 50:
            comment += f"📈 **高い成長性:** {growth:.1f}%の増益を達成しており、市場シェアを拡大している可能性が高いです。\n"
        else:
            comment += f"🟢 **安定成長:** {growth:.1f}%の堅実な成長を続けています。\n"

        # 2. 収益性評価
        if margin > 30:
            comment += f"💎 **圧倒的なブランド力:** 利益率{margin:.1f}%は驚異的です。他社が真似できない強力な強み（Moat）を持っています。\n"
        elif margin > 15:
            comment += f"💰 **高収益体質:** 利益率{margin:.1f}%と効率的に稼げています。優秀なビジネスモデルです。\n"
        
        # 3. 規模評価
        if op_profit > 1000: # 1000億円以上
            comment += f"🏰 **盤石な基盤:** 営業利益{op_profit:.0f}億円の大企業でありながら成長を維持している、極めて稀有な銘柄です。"
        else:
            comment += f"🌱 **未来のテンバガー候補:** まだ規模は小さいですが、この成長率が続けば株価数倍も現実的なシナリオです。"

        return comment

    def analyze_sector(self, sector_name, limit=30):
        """Sランク発掘"""
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
            
            display_code = code[:-1] if (len(code) == 5 and code.endswith('0')) else code
            status_text.text(f"AI分析中: {display_code} ...")
            time.sleep(0.1) 
            
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
                        
                        if op_prev != 0 and sales_now != 0:
                            growth = ((op_now - op_prev) / abs(op_prev)) * 100
                            margin = (op_now / sales_now) * 100
                            
                            rank = "B"
                            if growth >= 20.0 and margin >= 10.0: rank = "S"
                            elif growth >= 10.0: rank = "A"

                            if rank in ["S", "A"]: 
                                current_price = self.get_yahoo_price(code)
                                # AIコメント生成
                                ai_reason = self.generate_ai_comment(display_code, growth, margin, op_now/1e8)

                                results.append({
                                    "コード": display_code,
                                    "ランク": rank,
                                    "現在値": current_price,
                                    "成長率": growth,
                                    "利益率": margin,
                                    "AI解説": ai_reason # データとして持たせる
                                })
            except: pass
        
        status_text.text("分析完了！")
        return results # DataFrameではなくリストで返すように変更

# --- UI構築 ---
st.title("🛡️ Trade Guardian AI")

# サイドバー
with st.sidebar:
    st.header("⚙️ 設定")
    refresh_token = st.text_input("J-Quantsトークン", type="password")
    st.divider()
    st.subheader("📝 ポートフォリオ")
    if "portfolio" not in st.session_state:
        st.session_state.portfolio = [{"code": "228A", "entry": 500}]
    
    new_code = st.text_input("コード")
    new_price = st.number_input("単価", min_value=0)
    if st.button("追加"):
        st.session_state.portfolio.append({"code": new_code, "entry": new_price})

# タブ
tab1, tab2 = st.tabs(["📊 監視 & チャート", "🚀 Sランク発掘 (Hunter)"])

# --- タブ1: 監視 ---
with tab1:
    st.subheader("保有株のリアルタイム分析")
    if st.button("更新 🔄"):
        app = TradeGuardianUI(refresh_token)
        for item in st.session_state.portfolio:
            code = item["code"]
            entry = item["entry"]
            price = app.get_yahoo_price(code)
            
            # コンテナを作ってカード風に表示
            with st.container():
                cols = st.columns([1, 2, 3])
                if price:
                    pct = ((price - entry) / entry) * 100
                    status = "🟢"
                    if pct <= -10: status = "⛔"
                    elif pct >= 20: status = "🎉"
                    
                    with cols[0]:
                        st.metric(f"{code} {status}", f"{price:,.0f}円", f"{pct:+.2f}%")
                    
                    # ★ここでチャート表示
                    with cols[2]:
                        hist = app.get_stock_history(code)
                        if not hist.empty:
                            st.line_chart(hist['Close'], height=150)
                else:
                    st.error(f"{code}: 取得失敗")
                st.divider()

# --- タブ2: 発掘 ---
with tab2:
    st.subheader("AI決算スクリーニング")
    col1, col2 = st.columns([2, 1])
    with col1:
        target_sector = st.selectbox("業種", ["情報･通信業", "電気機器", "サービス業", "医薬品", "小売業"])
    with col2:
        limit_num = st.number_input("上限", value=30)
    
    if st.button("Sランクお宝株を探す 🔍", type="primary"):
        app = TradeGuardianUI(refresh_token)
        if app.authenticate():
            results = app.analyze_sector(target_sector, limit=limit_num)
            
            if results:
                st.success(f"{len(results)}件のお宝株を発見！")
                
                # ★リッチな表示（AI解説 + チャート）
                for res in results:
                    # アコーディオン（開閉式）パネル
                    with st.expander(f"{res['ランク']}ランク: {res['コード']} (成長率 +{res['成長率']:.1f}%)"):
                        c1, c2 = st.columns([1, 2])
                        
                        with c1:
                            st.markdown(f"### 現在値: **{res['現在値']:,.0f}円**")
                            st.info(res['AI解説']) # AIが生成した文章を表示
                            st.write(f"利益率: {res['利益率']:.1f}%")
                        
                        with c2:
                            st.write("▼ 過去1年のチャート")
                            hist = app.get_stock_history(res['コード'])
                            if not hist.empty:
                                st.line_chart(hist['Close'])
            else:
                st.warning("なし")
        else:
            st.error("トークンエラー")