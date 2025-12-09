import streamlit as st
import requests
import pandas as pd
import time
import yfinance as yf
from bs4 import BeautifulSoup
import json # データを保存するためのライブラリ
import os   # ファイル操作用

# --- ページ設定 ---
st.set_page_config(page_title="Trade Guardian Pro", page_icon="🛡️", layout="wide")

# --- データ保存・読み込み用の関数 ---
PORTFOLIO_FILE = "my_portfolio.json"

def load_portfolio():
    """保存されたファイルからリストを読み込む"""
    if os.path.exists(PORTFOLIO_FILE):
        try:
            with open(PORTFOLIO_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            pass # 読み込み失敗時はデフォルトを返す
    # ファイルがない場合の初期値
    return [{"code": "228A", "entry": 500}]

def save_portfolio(data):
    """リストをファイルに保存する"""
    try:
        with open(PORTFOLIO_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4, ensure_ascii=False)
    except Exception as e:
        st.error(f"保存に失敗しました: {e}")

# --- クラス定義 ---
class TradeGuardianUI:
    def __init__(self, refresh_token, discord_url=None):
        self.base_url = "https://api.jquants.com/v1"
        self.refresh_token = refresh_token
        self.discord_url = discord_url
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

    def send_discord(self, message):
        if not self.discord_url: return
        try: requests.post(self.discord_url, json={"content": message})
        except: pass

    def get_stock_data_yf(self, code):
        """株価・PER取得"""
        try:
            search_code = code[:-1] if (len(code) == 5 and code.endswith('0')) else code
            ticker = yf.Ticker(f"{search_code}.T")
            hist = ticker.history(period="1d")
            current_price = float(hist['Close'].iloc[-1]) if not hist.empty else None
            per = ticker.info.get('trailingPE', None)
            return current_price, per, ticker
        except: return None, None, None

    def generate_ai_comment(self, code, growth, margin, per, roe, equity_ratio):
        """詳細なAI分析コメント"""
        comment = f"**【{code} AI分析】**\n\n"
        if growth > 20 and margin > 10:
            comment += f"🚀 **S級成長:** 成長率{growth:.1f}%、利益率{margin:.1f}%。\n"
        elif growth > 10:
            comment += f"📈 **成長株:** 順調に拡大中。\n"
        if roe is not None and roe >= 8: comment += f"✅ **高効率:** ROE{roe:.1f}%。\n"
        if equity_ratio is not None and equity_ratio >= 70: comment += f"🏰 **鉄壁:** 自己資本{equity_ratio:.1f}%。\n"
        if per and per < 15: comment += f"💎 **割安:** PER{per:.1f}倍。\n"
        return comment

    def analyze_sector(self, sector_name, limit=30):
        """Sランク詳細分析"""
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
            status_text.text(f"詳細分析中: {display_code} ...")
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
                                ai_reason = self.generate_ai_comment(display_code, growth, margin, per, roe, equity_ratio)
                                results.append({
                                    "コード": display_code, "ランク": rank, "PER": per,
                                    "ROE(%)": roe, "自己資本比率(%)": equity_ratio,
                                    "成長率": growth, "利益率": margin,
                                    "AI解説": ai_reason, "Ticker": ticker
                                })
            except: pass
        
        status_text.text("完了！")
        return results

# --- UI構築 ---
st.title("🛡️ Trade Guardian Pro (自動保存版)")

# --- サイドバー ---
with st.sidebar:
    st.header("⚙️ 設定 & 管理")
    refresh_token = st.text_input("J-Quantsトークン", type="password")
    discord_webhook = st.text_input("Discord Webhook URL", type="password")
    st.divider()
    
    st.subheader("📝 監視リスト")
    
    # ★起動時にファイルから読み込む
    if "portfolio" not in st.session_state:
        st.session_state.portfolio = load_portfolio()

    with st.form("add_form", clear_on_submit=True):
        st.write("▼ 新規追加")
        col_in1, col_in2 = st.columns(2)
        with col_in1: in_code = st.text_input("コード", placeholder="7203")
        with col_in2: in_price = st.number_input("単価", min_value=0)
        
        if st.form_submit_button("リストに追加"):
            if in_code and in_price > 0:
                # 重複チェック
                existing_codes = [p["code"] for p in st.session_state.portfolio]
                if in_code in existing_codes:
                    st.error("登録済みです")
                else:
                    st.session_state.portfolio.append({"code": in_code, "entry": in_price})
                    save_portfolio(st.session_state.portfolio) # ★保存実行
                    st.success("追加・保存しました")
                    time.sleep(0.5); st.rerun()

    st.write("---")
    st.write("▼ 現在のリスト")
    if len(st.session_state.portfolio) == 0: st.info("登録なし")
    else:
        for i, item in enumerate(st.session_state.portfolio):
            col_text, col_btn = st.columns([3, 1])
            with col_text: st.text(f"{item['code']} (¥{item['entry']})")
            with col_btn:
                if st.button("🗑️", key=f"delete_{i}"):
                    st.session_state.portfolio.pop(i)
                    save_portfolio(st.session_state.portfolio) # ★削除時も保存
                    st.rerun()

# --- メイン画面 ---
tab1, tab2 = st.tabs(["📊 監視 & チャート", "⚖️ Sランク分析"])

with tab1:
    st.subheader(f"ポートフォリオ ({len(st.session_state.portfolio)}銘柄)")
    
    if st.button("株価更新 🔄", type="primary"):
        app = TradeGuardianUI(refresh_token, discord_url=discord_webhook)
        discord_alerts = []

        for item in st.session_state.portfolio:
            code = item["code"]
            entry = item["entry"]
            price, per, ticker = app.get_stock_data_yf(code)
            
            with st.container():
                st.markdown(f"#### {code}")
                cols = st.columns([2, 3])
                if price:
                    pct = ((price - entry) / entry) * 100
                    status = "🟢 監視中"; 
                    if pct <= -10:
                        status = "⛔ 損切り (-10%)"; st.error(f"【緊急】{code} 損切り到達！")
                        discord_alerts.append(f"⛔ **【緊急売却】** `{code}` が-10%に到達！")
                    elif pct <= -3: status = "⚠️ 警戒 (-3%〜)"
                    elif pct >= 20:
                        status = "🎉 利確 (+20%)"; st.balloons()
                        discord_alerts.append(f"🎉 **【利確推奨】** `{code}` が+20%達成！")
                    elif pct >= 5: status = "📈 上昇 (+5%〜)"

                    with cols[0]:
                        st.metric(label=status, value=f"{price:,.0f}円", delta=f"{pct:+.2f}%")
                        if per: st.caption(f"PER: {per:.1f}倍")
                    with cols[1]:
                        if ticker: st.line_chart(ticker.history(period="1y")['Close'], height=150)
                else: st.error("取得エラー")
                st.divider()
        
        if discord_alerts:
            app.send_discord("\n".join(discord_alerts))
            st.toast("Discord通知送信")

with tab2:
    st.write("Sランク分析 (ROE, 自己資本比率, PER, 段階アラート搭載)")
    col1, col2 = st.columns([2,1])
    with col1: target = st.selectbox("業種", ["情報･通信業", "電気機器", "サービス業", "医薬品", "化学", "建設業"])
    with col2: limit = st.number_input("上限", value=15)
    
    if st.button("詳細分析開始 🔍", type="primary"):
        app = TradeGuardianUI(refresh_token)
        if app.authenticate():
            results = app.analyze_sector(target, limit)
            if results:
                st.success(f"{len(results)}件 ヒット")
                for res in results:
                    roe_disp = f"{res['ROE(%)']:.1f}%" if res['ROE(%)'] is not None else "---"
                    eq_disp = f"{res['自己資本比率(%)']:.1f}%" if res['自己資本比率(%)'] is not None else "---"
                    per_disp = f"{res['PER']:.1f}倍" if res['PER'] else "---"
                    badge = "👑" if res['ROE(%)'] is not None and res['ROE(%)'] >= 8 else ""
                    if res['PER'] and res['PER'] < 15: badge += "💎"
                    
                    with st.expander(f"{badge} {res['ランク']}ランク: {res['コード']} | ROE:{roe_disp}"):
                        c1, c2 = st.columns([1, 1])
                        with c1:
                            st.info(res['AI解説'])
                            st.table(pd.DataFrame({
                                "指標": ["成長率", "利益率", "ROE", "自己資本", "PER"],
                                "数値": [f"{res['成長率']:.1f}%", f"{res['利益率']:.1f}%", roe_disp, eq_disp, per_disp]
                            }))
                        with c2:
                            if res['Ticker']: st.line_chart(res['Ticker'].history(period="1y")['Close'])
            else: st.warning("なし")
        else: st.error("認証エラー")
