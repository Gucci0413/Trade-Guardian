import streamlit as st
import requests
import pandas as pd
import time
import yfinance as yf
from bs4 import BeautifulSoup

# --- ページ設定 ---
st.set_page_config(page_title="Trade Guardian Pro", page_icon="🛡️", layout="wide")

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
        """★AI分析 (安全性と効率性を追加)"""
        comment = f"**【{code} AI格付けレポート】**\n\n"
        
        # 1. 成長性 & 収益性
        if growth > 20 and margin > 10:
            comment += f"🚀 **S級の成長力:** 成長率{growth:.1f}%、利益率{margin:.1f}%。文句なしの本業の強さです。\n"
        elif growth > 10:
            comment += f"📈 **堅実な成長:** 事業は順調に拡大しています。\n"

        # 2. 効率性 (ROE) ★追加
        if roe >= 15:
            comment += f"👑 **超優秀な経営:** ROE{roe:.1f}%。資金効率が極めて高く、機関投資家が好む体質です。\n"
        elif roe >= 8:
            comment += f"✅ **合格ライン:** ROE{roe:.1f}%。日本企業の平均を超えています。\n"
        else:
            comment += f"⚠️ **効率難あり:** ROE{roe:.1f}%。資金の使い方が少し下手かもしれません。\n"

        # 3. 安全性 (自己資本比率) ★追加
        if equity_ratio >= 70:
            comment += f"🏰 **鉄壁の守り:** 自己資本比率{equity_ratio:.1f}%。倒産リスクはほぼありません。\n"
        elif equity_ratio < 30:
            comment += f"💣 **財務リスク:** 自己資本比率{equity_ratio:.1f}%。借金が多く、金利上昇に弱いです。\n"

        # 4. 割安性 (PER)
        if per and per < 15:
            comment += f"💎 **割安:** これだけの実力でPER{per:.1f}倍はお買い得です。\n"

        return comment

    def analyze_sector(self, sector_name, limit=30):
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
            status_text.text(f"プロ基準で審査中: {display_code} ...")
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
                        
                        # --- データ抽出 ---
                        op_now = float(latest.get("OperatingProfit", 0) or 0)
                        op_prev = float(prev.get("OperatingProfit", 0) or 0)
                        sales_now = float(latest.get("NetSales", 0) or 0)
                        
                        # ★追加指標のためのデータ
                        net_income = float(latest.get("ProfitLossAttributableToOwnersOfParent", 0) or 0) # 純利益
                        total_assets = float(latest.get("TotalAssets", 0) or 0) # 総資産
                        net_assets = float(latest.get("NetAssets", 0) or 0)     # 純資産(自己資本)

                        if op_prev > 0 and sales_now > 0 and total_assets > 0 and net_assets > 0:
                            # 1. 成長率
                            growth = ((op_now - op_prev) / op_prev) * 100
                            # 2. 利益率
                            margin = (op_now / sales_now) * 100
                            # 3. ROE (自己資本利益率) = 純利益 / 純資産
                            roe = (net_income / net_assets) * 100
                            # 4. 自己資本比率 = 純資産 / 総資産
                            equity_ratio = (net_assets / total_assets) * 100
                            
                            rank = "B"
                            if growth >= 20.0 and margin >= 10.0: rank = "S"
                            elif growth >= 10.0: rank = "A"

                            if rank in ["S", "A"]: 
                                price, per, ticker = self.get_stock_data_yf(code)
                                
                                ai_reason = self.generate_ai_comment(display_code, growth, margin, per, roe, equity_ratio)

                                results.append({
                                    "コード": display_code,
                                    "ランク": rank,
                                    "PER": per,
                                    "ROE(%)": round(roe, 1),           # 追加
                                    "自己資本比率(%)": round(equity_ratio, 1), # 追加
                                    "成長率": growth,
                                    "利益率": margin,
                                    "AI解説": ai_reason,
                                    "Ticker": ticker
                                })
            except: pass
        
        status_text.text("審査完了！")
        return results

# --- UI構築 ---
st.title("🛡️ Trade Guardian Pro (Institutional Grade)")

with st.sidebar:
    st.header("⚙️ 設定")
    refresh_token = st.text_input("J-Quantsトークン", type="password")
    st.divider()
    if "portfolio" not in st.session_state: st.session_state.portfolio = [{"code": "228A", "entry": 500}]
    
    new_code = st.text_input("コード"); new_price = st.number_input("単価", min_value=0)
    if st.button("追加"): st.session_state.portfolio.append({"code": new_code, "entry": new_price})

tab1, tab2 = st.tabs(["📊 監視 & チャート", "⚖️ 総合ファンダメンタルズ分析"])

with tab1:
    st.subheader("ポートフォリオ")
    if st.button("更新 🔄"):
        app = TradeGuardianUI(refresh_token)
        for item in st.session_state.portfolio:
            code = item["code"]
            entry = item["entry"]
            price, per, ticker = app.get_stock_data_yf(code)
            
            with st.container():
                cols = st.columns([1, 3])
                if price:
                    pct = ((price - entry) / entry) * 100
                    status = "🟢"
                    if pct <= -10: status = "⛔"
                    elif pct >= 20: status = "🎉"
                    with cols[0]:
                        st.metric(f"{code} {status}", f"{price:,.0f}円", f"{pct:+.2f}%")
                        if per: st.caption(f"PER: {per:.1f}倍")
                    with cols[1]:
                        if ticker: st.line_chart(ticker.history(period="1y")['Close'], height=150)
                st.divider()

with tab2:
    st.subheader("プロ基準スクリーニング (成長×割安×安全×効率)")
    st.markdown("""
    **4つのフィルタで厳選します:**
    - 🚀 **Growth:** 営業利益が伸びているか？
    - 💎 **Value:** 株価は割安か？ (PER)
    - 👑 **Efficiency:** 経営はうまいか？ (ROE)
    - 🏰 **Safety:** 倒産しないか？ (自己資本比率)
    """)
    
    col1, col2 = st.columns([2, 1])
    with col1: target_sector = st.selectbox("業種", ["情報･通信業", "電気機器", "サービス業", "医薬品", "輸送用機器", "化学", "建設業"])
    with col2: limit_num = st.number_input("上限", value=20)
    
    if st.button("最強の銘柄を探す 🔍", type="primary"):
        app = TradeGuardianUI(refresh_token)
        if app.authenticate():
            results = app.analyze_sector(target_sector, limit=limit_num)
            if results:
                st.success(f"{len(results)}件 ヒットしました")
                for res in results:
                    # バッジ判定 (Sランク かつ ROE8%以上 かつ 自己資本30%以上)
                    badge = "👑" if (res['ランク'] == 'S' and res['ROE(%)'] >= 8 and res['自己資本比率(%)'] >= 30) else ""
                    
                    # アコーディオン表示
                    title_text = f"{badge} {res['ランク']}ランク: {res['コード']} | ROE {res['ROE(%)']}% | 自己資本 {res['自己資本比率(%)']}%"
                    
                    with st.expander(title_text):
                        c1, c2 = st.columns([1, 1])
                        with c1:
                            st.info(res['AI解説'])
                            per_text = f"{res['PER']:.1f}倍" if res['PER'] else "不明"
                            st.table(pd.DataFrame({
                                "指標": ["成長率", "利益率", "ROE(効率)", "自己資本(安全)", "PER(割安)"],
                                "数値": [f"{res['成長率']:.1f}%", f"{res['利益率']:.1f}%", f"{res['ROE(%)']}%", f"{res['自己資本比率(%)']}%", per_text]
                            }))
                        with c2:
                            if res['Ticker']: st.line_chart(res['Ticker'].history(period="1y")['Close'])
            else: st.warning("なし")
        else: st.error("トークンエラー")
