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
        """AI分析コメント"""
        comment = f"**【{code} AI格付け】**\n\n"
        
        # 1. 成長性 & 収益性
        if growth > 20 and margin > 10:
            comment += f"🚀 **S級:** 成長率{growth:.1f}%、利益率{margin:.1f}%。本業最強。\n"
        elif growth > 10:
            comment += f"📈 **成長:** 順調に拡大中。\n"

        # 2. 効率性 (ROE)
        if roe is not None:
            if roe >= 15: comment += f"👑 **超優秀:** ROE{roe:.1f}%。資金効率◎。\n"
            elif roe >= 8: comment += f"✅ **合格:** ROE{roe:.1f}%。\n"
        
        # 3. 安全性
        if equity_ratio is not None:
            if equity_ratio >= 70: comment += f"🏰 **鉄壁:** 自己資本{equity_ratio:.1f}%。\n"
            elif equity_ratio < 30: comment += f"💣 **注意:** 自己資本{equity_ratio:.1f}%。\n"

        # 4. 割安性
        if per and per < 15:
            comment += f"💎 **割安:** PER{per:.1f}倍。\n"

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
            status_text.text(f"分析中: {display_code} ...")
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
                            total_assets = float(latest.get("TotalAssets", 0))
                            net_assets = float(latest.get("NetAssets", 0))
                        except:
                            net_income = 0
                            total_assets = 0
                            net_assets = 0

                        if op_prev > 0 and sales_now > 0:
                            growth = ((op_now - op_prev) / op_prev) * 100
                            margin = (op_now / sales_now) * 100
                            
                            roe = None
                            equity_ratio = None
                            if total_assets > 0 and net_assets > 0:
                                roe = (net_income / net_assets) * 100
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
                                    "ROE(%)": roe,           
                                    "自己資本比率(%)": equity_ratio,
                                    "成長率": growth,
                                    "利益率": margin,
                                    "AI解説": ai_reason,
                                    "Ticker": ticker
                                })
            except: pass
        
        status_text.text("完了！")
        return results

# --- UI構築 ---
st.title("🛡️ Trade Guardian Pro")

# --- サイドバー ---
with st.sidebar:
    st.header("⚙️ 設定 & 管理")
    refresh_token = st.text_input("J-Quantsトークン", type="password")
    st.divider()
    
    st.subheader("📝 監視リストの管理")
    if "portfolio" not in st.session_state:
        st.session_state.portfolio = [{"code": "228A", "entry": 500}]

    with st.expander("➕ 銘柄を追加する", expanded=True):
        col_add1, col_add2 = st.columns([2, 1])
        with col_add1:
            new_code = st.text_input("コード", placeholder="7203", key="input_code")
        with col_add2:
            new_price = st.number_input("単価", min_value=0, value=0, key="input_price")
        
        if st.button("追加", type="primary"):
            if new_code and new_price > 0:
                existing_codes = [p["code"] for p in st.session_state.portfolio]
                if new_code in existing_codes:
                    st.error("登録済みです")
                else:
                    st.session_state.portfolio.append({"code": new_code, "entry": new_price})
                    st.success(f"追加: {new_code}")
                    time.sleep(0.5)
                    st.rerun()

    st.write("---")
    st.caption("現在の監視リスト")
    if len(st.session_state.portfolio) == 0:
        st.info("なし")
    else:
        delete_index = -1
        for i, item in enumerate(st.session_state.portfolio):
            col_list1, col_list2 = st.columns([3, 1])
            with col_list1:
                st.write(f"**{item['code']}** (取得: {item['entry']}円)")
            with col_list2:
                if st.button("🗑️", key=f"del_{i}"):
                    delete_index = i
        if delete_index != -1:
            st.session_state.portfolio.pop(delete_index)
            st.rerun()

# --- メインコンテンツ ---
tab1, tab2 = st.tabs(["📊 監視 & チャート", "⚖️ Sランク分析"])

with tab1:
    st.subheader(f"ポートフォリオ監視 ({len(st.session_state.portfolio)}銘柄)")
    
    if st.button("株価を更新する 🔄", type="primary"):
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
                    
                    # --- ★ここが新機能: 段階的通知ロジック ---
                    status = "🟢 監視中"
                    bg_color = "white"
                    
                    # 下落サイド (-3%刻み)
                    if pct <= -10:
                        status = "⛔ 損切り (-10%)"
                        st.error(f"【緊急】{code} が損切りライン到達！ (-10%)")
                    elif pct <= -9:
                        status = "⚠️ 危険水域 (-9%)"
                        st.warning(f"【危険】{code} が-9%です。損切り準備を。")
                    elif pct <= -6:
                        status = "⚠️ 警戒レベル (-6%)"
                    elif pct <= -3:
                        status = "📉 軽微な下落 (-3%)"
                    
                    # 上昇サイド (+5%刻み)
                    elif pct >= 20:
                        status = "🎉 目標達成 (+20%)"
                        st.balloons() # お祝い演出
                        st.success(f"【祝】{code} が+20%達成！利益確定しましょう！")
                    elif pct >= 15:
                        status = "📈 利確準備 (+15%)"
                        st.toast(f"{code} もうすぐ目標達成です！")
                    elif pct >= 10:
                        status = "📈 含み益拡大 (+10%)"
                    elif pct >= 5:
                        status = "📈 上昇トレンド (+5%)"
                    
                    with cols[0]:
                        st.metric(label=status, value=f"{price:,.0f}円", delta=f"{pct:+.2f}%")
                        if per: st.caption(f"PER: {per:.1f}倍")
                    with cols[1]:
                        if ticker: st.line_chart(ticker.history(period="1y")['Close'], height=150)
                else:
                    st.error("株価取得エラー")
                    
                st.divider()

with tab2:
    st.subheader("プロ基準スクリーニング")
    col1, col2 = st.columns([2, 1])
    with col1: target_sector = st.selectbox("業種", ["情報･通信業", "電気機器", "サービス業", "医薬品", "輸送用機器", "化学", "建設業"])
    with col2: limit_num = st.number_input("上限", value=20)
    
    if st.button("銘柄を探す 🔍", type="primary"):
        app = TradeGuardianUI(refresh_token)
        if app.authenticate():
            results = app.analyze_sector(target_sector, limit=limit_num)
            if results:
                st.success(f"{len(results)}件 ヒットしました")
                for res in results:
                    roe_disp = f"{res['ROE(%)']:.1f}%" if res['ROE(%)'] is not None else "---"
                    eq_disp = f"{res['自己資本比率(%)']:.1f}%" if res['自己資本比率(%)'] is not None else "---"
                    badge = "👑" if res['ROE(%)'] is not None and res['ROE(%)'] >= 8 else ""
                    
                    with st.expander(f"{badge} {res['ランク']}ランク: {res['コード']} | ROE {roe_disp}"):
                        c1, c2 = st.columns([1, 1])
                        with c1:
                            st.info(res['AI解説'])
                            per_text = f"{res['PER']:.1f}倍" if res['PER'] else "不明"
                            st.table(pd.DataFrame({
                                "指標": ["成長率", "利益率", "ROE(効率)", "自己資本(安全)", "PER(割安)"],
                                "数値": [f"{res['成長率']:.1f}%", f"{res['利益率']:.1f}%", roe_disp, eq_disp, per_text]
                            }))
                        with c2:
                            if res['Ticker']: st.line_chart(res['Ticker'].history(period="1y")['Close'])
            else: st.warning("条件に合う銘柄なし")
        else: st.error("トークンエラー")
