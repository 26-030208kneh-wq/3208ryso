import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go

# ==========================================
# 0. 페이지 설정 & 기본 디자인
# ==========================================
st.set_page_config(page_title="Stock Tycoon: Auto Market Edition", layout="wide")

# ==========================================
# 1. 신용등급 정보 정의
# ==========================================
CREDIT_RATINGS = {
    1: {"name": "AAA (최우수)", "min_score": 900, "spread": 0.0,  "limit_mult": 2.0},
    2: {"name": "AA (우수)",   "min_score": 800, "spread": 0.5,  "limit_mult": 1.5},
    3: {"name": "A (보통)",     "min_score": 700, "spread": 1.0,  "limit_mult": 1.2},
    4: {"name": "BBB (주의)",   "min_score": 600, "spread": 2.0,  "limit_mult": 1.0},
    5: {"name": "BB (위험)",    "min_score": 500, "spread": 3.5,  "limit_mult": 0.7},
    6: {"name": "B (고위험)",   "min_score": 300, "spread": 5.0,  "limit_mult": 0.4},
    7: {"name": "C (최악)",     "min_score": 0,   "spread": 8.0,  "limit_mult": 0.1},
}

def get_credit_rating(score):
    for grade, info in CREDIT_RATINGS.items():
        if score >= info["min_score"]:
            return grade, info
    return 7, CREDIT_RATINGS[7]

MARGIN_REQ_RATIO = 1.5  # 공매도 증거금률 150%

# ==========================================
# 2. Session State 초기화
# ==========================================
if "cash" not in st.session_state:
    st.session_state.cash = 10_000_000         # 보유 현금
if "loan" not in st.session_state:
    st.session_state.loan = 0                  # 일반 대출 잔액
if "credit_score" not in st.session_state:
    st.session_state.credit_score = 650         # 신용 점수
if "base_rate" not in st.session_state:
    st.session_state.base_rate = 2.0            # 기준 금리 (%)
if "portfolio" not in st.session_state:
    st.session_state.portfolio = {"TechCorp": {"shares": 0, "avg_price": 0}}
if "short_position" not in st.session_state:
    st.session_state.short_position = {"shares": 0, "entry_price": 0, "margin": 0}
if "stock_data" not in st.session_state:
    np.random.seed(42)
    prices = 100000 + np.cumsum(np.random.randn(20) * 1500)
    st.session_state.stock_data = pd.DataFrame({"Turn": np.arange(1, 21), "Price": prices})

# ==========================================
# 3. 핵심 상태 및 금액 계산
# ==========================================
current_grade, grade_info = get_credit_rating(st.session_state.credit_score)
final_interest_rate = max(0.5, round(st.session_state.base_rate + grade_info["spread"], 2))
minus_rate = final_interest_rate + 1.0

current_price = int(st.session_state.stock_data["Price"].iloc[-1])
long_shares = st.session_state.portfolio["TechCorp"]["shares"]
long_val = long_shares * current_price

short_shares = st.session_state.short_position["shares"]
short_entry = st.session_state.short_position["entry_price"]
short_pnl = (short_entry - current_price) * short_shares if short_shares > 0 else 0

total_assets = st.session_state.cash + long_val + short_pnl + st.session_state.short_position["margin"]
net_asset = total_assets - st.session_state.loan
minus_limit = max(0, int(net_asset * grade_info["limit_mult"]))

# ==========================================
# 4. 반대매매 & 자동 턴 엔진 함수
# ==========================================
def check_forced_liquidation():
    """담보유지비율 미달 시 반대매매 집행"""
    total_debt = st.session_state.loan + (abs(st.session_state.cash) if st.session_state.cash < 0 else 0)
    if total_debt <= 0:
        return
        
    margin_ratio = (total_assets / total_debt) * 100
    
    if margin_ratio < 140.0 and long_shares > 0:
        discount_price = int(current_price * 0.85)
        liquidation_val = long_shares * discount_price
        
        st.session_state.portfolio["TechCorp"]["shares"] = 0
        st.session_state.cash += liquidation_val
        st.session_state.credit_score = max(0, st.session_state.credit_score - 100)
        st.error(f"🚨 [반대매매 집행] 담보비율({margin_ratio:.1f}%) 미달! 주식 {long_shares}주가 강제 청산되었습니다.")

def run_market_tick():
    """시장이 1턴 진행될 때 실행되는 백엔드 로직"""
    current_turn = len(st.session_state.stock_data) + 1
    last_price = st.session_state.stock_data["Price"].iloc[-1]
    
    # 주가 변동
    change_percent = np.random.normal(0, 0.03)
    new_price = max(1000, int(last_price * (1 + change_percent)))
    new_row = pd.DataFrame({"Turn": [current_turn], "Price": [new_price]})
    st.session_state.stock_data = pd.concat([st.session_state.stock_data, new_row], ignore_index=True)
    
    # 기준금리 변동
    rate_change = round(np.random.uniform(-0.3, 0.3), 2)
    st.session_state.base_rate = max(0.5, min(10.0, round(st.session_state.base_rate + rate_change, 2)))
    
    # 대출 및 마이너스 이자 차감
    if st.session_state.loan > 0:
        interest_fee = int(st.session_state.loan * (final_interest_rate / 100))
        st.session_state.cash -= interest_fee
        
    if st.session_state.cash < 0:
        minus_balance = abs(st.session_state.cash)
        minus_fee = int(minus_balance * (minus_rate / 100))
        st.session_state.cash -= minus_fee
        if minus_balance > minus_limit:
            st.session_state.credit_score = max(0, st.session_state.credit_score - 30)

    check_forced_liquidation()

# ==========================================
# 5. UI 메인 대시보드
# ==========================================
st.title("📈 주식 타이쿤: Real-time Market Edition")

# --- 보유 수량이 명확히 보이는 상단 6개 대시보드 ---
m1, m2, m3, m4, m5, m6 = st.columns(6)
m1.metric("순자산", f"{net_asset:,} 원")
m2.metric("보유 현금", f"{st.session_state.cash:,} 원")
m3.metric("보유 주식 (현물)", f"{long_shares:,} 주", f"평가액 {long_val:,}원")
m4.metric("공매도 잔고 (숏)", f"{short_shares:,} 주", f"손익 {short_pnl:+,}원")
m5.metric("신용등급", f"{grade_info['name']}", f"{st.session_state.credit_score}점")
m6.metric("대출/마이너스 이율", f"{final_interest_rate}% / {minus_rate}%")

st.divider()

# --- 20초마다 자동으로 실행되는 실시간 시장 루프 ---
@st.fragment(run_every=20)
def auto_market_component():
    # 20초 주기 자동 턴 경과 실행
    run_market_tick()
    
    st.subheader("⏱️ 실시간 시장 현황 (20초마다 자동 변동)")
    st.caption("화면이 20초마다 자동으로 새로고침되며 주가 및 금리 변화, 이자 수납이 반영됩니다.")
    
    curr_p = int(st.session_state.stock_data["Price"].iloc[-1])
    
    df = st.session_state.stock_data.tail(30)
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=df["Turn"], y=df["Price"], mode='lines+markers', name='Price', line=dict(color='#00FFAA', width=3)))
    fig.update_layout(height=350, template="plotly_dark", margin=dict(l=20, r=20, t=20, b=20))
    st.plotly_chart(fig, use_container_width=True)

auto_market_component()

st.divider()

# --- 매매 및 금융 거래 영역 ---
left_col, right_col = st.columns([2, 1])

with left_col:
    st.subheader("🛒 매매 거래소")
    tab_long, tab_short = st.tabs(["🔴 롱 (현물 매수/매도)", "📉 숏 (공매도)"])
    
    # [탭 1: 현물]
    with tab_long:
        st.write(f"현재 보유 현물 수량: **{long_shares:,} 주** | 평가손익 평단가 반영")
        trade_qty = st.number_input("수량 입력", min_value=1, value=10, key="long_qty")
        cost = trade_qty * current_price
        
        c1, c2 = st.columns(2)
        with c1:
            if st.button("🔴 매수", use_container_width=True):
                if (st.session_state.cash + minus_limit) >= cost:
                    st.session_state.cash -= cost
                    st.session_state.portfolio["TechCorp"]["shares"] += trade_qty
                    st.session_state.credit_score = min(1000, st.session_state.credit_score + 2)
                    st.success(f"{trade_qty}주 매수 완료!")
                    st.rerun()
                else:
                    st.error("마이너스 한도 초과!")
        with c2:
            if st.button("🔵 매도", use_container_width=True):
                if long_shares >= trade_qty:
                    st.session_state.cash += cost
                    st.session_state.portfolio["TechCorp"]["shares"] -= trade_qty
                    st.session_state.credit_score = min(1000, st.session_state.credit_score + 2)
                    st.success(f"{trade_qty}주 매도 완료!")
                    st.rerun()
                else:
                    st.error("보유 주식이 부족합니다.")

    # [탭 2: 공매도]
    with tab_short:
        st.write(f"현재 공매도 수량: **{short_shares:,} 주** | 진입가: **{short_entry:,} 원**")
        short_qty = st.number_input("공매도 수량 입력", min_value=1, value=10, key="short_qty")
        req_margin = int(short_qty * current_price * MARGIN_REQ_RATIO)
        
        sc1, sc2 = st.columns(2)
        with sc1:
            if st.button("📉 공매도 진입", use_container_width=True):
                if (st.session_state.cash + minus_limit) >= req_margin:
                    st.session_state.cash -= req_margin
                    prev_s = st.session_state.short_position["shares"]
                    prev_e = st.session_state.short_position["entry_price"]
                    prev_m = st.session_state.short_position["margin"]
                    
                    new_s = prev_s + short_qty
                    new_e = int(((prev_s * prev_e) + (short_qty * current_price)) / new_s)
                    
                    st.session_state.short_position = {"shares": new_s, "entry_price": new_e, "margin": prev_m + req_margin}
                    st.success(f"{short_qty}주 공매도 진입!")
                    st.rerun()
                else:
                    st.error("증거금이 부족합니다!")
        with sc2:
            if st.button("🔄 숏 커버링 (청산)", use_container_width=True):
                if short_shares >= short_qty:
                    cover_ratio = short_qty / short_shares
                    ret_margin = int(st.session_state.short_position["margin"] * cover_ratio)
                    pnl = (short_entry - current_price) * short_qty
                    
                    st.session_state.cash += (ret_margin + pnl)
                    st.session_state.short_position["shares"] -= short_qty
                    st.session_state.short_position["margin"] -= ret_margin
                    
                    if st.session_state.short_position["shares"] == 0:
                        st.session_state.short_position["entry_price"] = 0
                    st.info(f"{short_qty}주 숏 커버링 완료!")
                    st.rerun()

with right_col:
    st.subheader("🏦 금융 센터")
    if st.session_state.cash < 0:
        st.warning(f"💳 **마이너스 통장 사용 중**: {st.session_state.cash:,} 원")
    else:
        st.info(f"💳 **마이너스 통장 한도**: **{minus_limit:,} 원**")
        
    loan_amt = st.number_input("일반 대출/상환 신청액", min_value=0, value=1_000_000, step=500_000)
    max_loan = max(0, int(net_asset * grade_info["limit_mult"]))
    
    lc1, lc2 = st.columns(2)
    with lc1:
        if st.button("💵 일반 대출 실행", use_container_width=True):
            if st.session_state.loan + loan_amt <= max_loan:
                st.session_state.loan += loan_amt
                st.session_state.cash += loan_amt
                st.success("대출 실행 완료!")
                st.rerun()
            else:
                st.error("대출 한도 초과!")
    with lc2:
        if st.button("💳 대출 원금 상환", use_container_width=True):
            if loan_amt <= st.session_state.loan:
                st.session_state.loan -= loan_amt
                st.session_state.cash -= loan_amt
                st.session_state.credit_score = min(1000, st.session_state.credit_score + 10)
                st.success("대출 상환 완료!")
                st.rerun()

    st.divider()
    if st.button("⏩ 수동으로 턴 즉시 진행", type="primary", use_container_width=True):
        run_market_tick()
        st.rerun()
