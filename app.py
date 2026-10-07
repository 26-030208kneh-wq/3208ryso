import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go

# ==========================================
# 0. 페이지 설정 & 스타일
# ==========================================
st.set_page_config(page_title="Stock Tycoon: Ultimate Edition", layout="wide")

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
    st.session_state.cash = 10_000_000         # 보유 현금 (마이너스 통장 사용 시 음수 가능)
if "loan" not in st.session_state:
    st.session_state.loan = 0                  # 일반 대출 잔액
if "credit_score" not in st.session_state:
    st.session_state.credit_score = 650         # 신용 점수 (초기 4등급)
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
# 3. 주요 계산 알고리즘
# ==========================================
current_grade, grade_info = get_credit_rating(st.session_state.credit_score)
final_interest_rate = max(0.5, round(st.session_state.base_rate + grade_info["spread"], 2))
minus_rate = final_interest_rate + 1.0  # 마이너스 통장 이율 (기존 대출금리 + 1%)

current_price = int(st.session_state.stock_data["Price"].iloc[-1])
long_shares = st.session_state.portfolio["TechCorp"]["shares"]
long_val = long_shares * current_price

short_shares = st.session_state.short_position["shares"]
short_entry = st.session_state.short_position["entry_price"]
short_pnl = (short_entry - current_price) * short_shares if short_shares > 0 else 0

# 순자산 = (현금 + 주식 평가액 + 숏 손익 + 공매도 증거금) - 일반 대출금
total_assets = st.session_state.cash + long_val + short_pnl + st.session_state.short_position["margin"]
net_asset = total_assets - st.session_state.loan

# 마이너스 통장 한도 = 순자산 * 신용등급별 배율
minus_limit = max(0, int(net_asset * grade_info["limit_mult"]))

# ==========================================
# 4. 반대매매 & 턴 진행 엔진
# ==========================================
def check_forced_liquidation():
    """담보유지비율 미달 시 반대매매 집행"""
    total_debt = st.session_state.loan + (abs(st.session_state.cash) if st.session_state.cash < 0 else 0)
    if total_debt <= 0:
        return
        
    total_collateral = total_assets
    margin_ratio = (total_collateral / total_debt) * 100
    
    if margin_ratio < 140.0 and long_shares > 0:
        discount_price = int(current_price * 0.85)
        liquidation_val = long_shares * discount_price
        
        st.session_state.portfolio["TechCorp"]["shares"] = 0
        st.session_state.cash += liquidation_val
        st.session_state.credit_score = max(0, st.session_state.credit_score - 100)
        
        st.error(f"🚨 [반대매매 집행] 담보비율({margin_ratio:.1f}%) 미달! 주식 {long_shares}주가 강제 청산되었습니다. (신용점수 -100점)")

def next_turn():
    """다음 턴 진행 엔진 (주가변동, 금리변동, 대출/마이너스 이자 차감)"""
    current_turn = len(st.session_state.stock_data) + 1
    last_price = st.session_state.stock_data["Price"].iloc[-1]
    
    # 1. 주가 변동
    change_percent = np.random.normal(0, 0.03)
    new_price = max(1000, int(last_price * (1 + change_percent)))
    new_row = pd.DataFrame({"Turn": [current_turn], "Price": [new_price]})
    st.session_state.stock_data = pd.concat([st.session_state.stock_data, new_row], ignore_index=True)
    
    # 2. 기준금리 변동
    rate_change = round(np.random.uniform(-0.3, 0.3), 2)
    st.session_state.base_rate = max(0.5, min(10.0, round(st.session_state.base_rate + rate_change, 2)))
    
    # 3. 일반 대출 이자 차감
    if st.session_state.loan > 0:
        interest_fee = int(st.session_state.loan * (final_interest_rate / 100))
        st.session_state.cash -= interest_fee
        st.toast(f"💸 일반대출 이자 차감: -{interest_fee:,} 원", icon="🏦")
        
    # 4. 마이너스 통장 이자 차감 (현금이 음수일 경우)
    if st.session_state.cash < 0:
        minus_balance = abs(st.session_state.cash)
        minus_fee = int(minus_balance * (minus_rate / 100))
        st.session_state.cash -= minus_fee
        st.toast(f"📉 마이너스통장 이자 발생: -{minus_fee:,} 원 (이율 {minus_rate}%)", icon="💳")
        
        # 한도 초과 시 신용점수 감점
        if minus_balance > minus_limit:
            st.session_state.credit_score = max(0, st.session_state.credit_score - 30)
            st.toast("⚠️ 마이너스 한도 초과! 신용점수 -30점 차감", icon="🚨")

    # 5. 반대매매 체크
    check_forced_liquidation()

# ==========================================
# 5. UI 메인 대시보드
# ==========================================
st.title("📈 주식 타이쿤: Ultimate Financial Simulator")

# 상단 메트릭 대시보드
m1, m2, m3, m4, m5 = st.columns(5)
m1.metric("순자산", f"{net_asset:,} 원")
m2.metric("보유 현금 / 마이너스", f"{st.session_state.cash:,} 원", delta=f"한도 {minus_limit:,}원" if st.session_state.cash < 0 else None, delta_color="inverse")
m3.metric("신용등급", f"{grade_info['name']}", f"{st.session_state.credit_score}점")
m4.metric("대출 이율 (일반/마이너스)", f"{final_interest_rate}% / {minus_rate}%")
m5.metric("대출 잔액", f"{st.session_state.loan:,} 원")

st.divider()

left_col, right_col = st.columns([2, 1])

# --- [좌측] 차트 & 현물 / 공매도 주문 ---
with left_col:
    st.subheader("📊 차트 및 매매 센터")
    df = st.session_state.stock_data.tail(30)
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=df["Turn"], y=df["Price"], mode='lines+markers', name='Price', line=dict(color='#00FFAA', width=3)))
    fig.update_layout(height=320, template="plotly_dark")
    st.plotly_chart(fig, use_container_width=True)

    tab_long, tab_short = st.tabs(["🔴 롱 (현물 매수/매도)", "📉 숏 (공매도)"])
    
    # [탭 1: 현물 매수/매도]
    with tab_long:
        trade_qty = st.number_input("수량 입력", min_value=1, value=10, key="long_qty")
        cost = trade_qty * current_price
        
        c1, c2 = st.columns(2)
        with c1:
            if st.button("🔴 매수", use_container_width=True):
                # 마이너스 통장 한도까지 현금 사용 가능
                available_cash = st.session_state.cash + minus_limit
                if available_cash >= cost:
                    st.session_state.cash -= cost
                    st.session_state.portfolio["TechCorp"]["shares"] += trade_qty
                    st.session_state.credit_score = min(1000, st.session_state.credit_score + 2)
                    st.success(f"{trade_qty}주 매수 완료!")
                    st.rerun()
                else:
                    st.error("마이너스 한도 초과로 매수 불가!")
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
        short_qty = st.number_input("공매도 수량", min_value=1, value=10, key="short_qty")
        req_margin = int(short_qty * current_price * MARGIN_REQ_RATIO)
        st.caption(f"필요 증거금(150%): **{req_margin:,} 원** | 현재 숏 잔고: **{short_shares} 주** (평가손익: {short_pnl:+,}원)")
        
        sc1, sc2 = st.columns(2)
        with sc1:
            if st.button("📉 공매도 진입", use_container_width=True):
                available_cash = st.session_state.cash + minus_limit
                if available_cash >= req_margin:
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
                    st.info(f"{short_qty}주 숏 커버링 완료! (손익: {pnl:+,}원)")
                    st.rerun()

# --- [우측] 대출 및 은행 창구 ---
with right_col:
    st.subheader("🏦 중앙은행 및 신용 센터")
    
    # 마이너스 통장 상태 안내
    if st.session_state.cash < 0:
        st.warning(f"💳 **마이너스 통장 사용 중**: {st.session_state.cash:,} 원\n- 적용 이율: **{minus_rate}%**\n- 한도 잔여: **{minus_limit + st.session_state.cash:,} 원**")
    else:
        st.info(f"💳 **마이너스 통장 한도**: **{minus_limit:,} 원** (현금 부족 시 자동 결제)")
        
    st.divider()
    
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
                st.success("대출 상환 완료! (신용점수 +10점)")
                st.rerun()

    st.divider()
    if st.button("⏩ 다음 턴 진행 (시장 및 이자 반영)", type="primary", use_container_width=True):
        next_turn()
        st.rerun()
