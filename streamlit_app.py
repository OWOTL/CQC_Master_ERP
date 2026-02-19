import streamlit as st
import pandas as pd
import sqlite3
import plotly.express as px
from datetime import datetime
import uuid

# ==========================================
# 1. 后端：四层树状索引数据库引擎
# ==========================================
class EnterpriseERPEngine:
    def __init__(self):
        # 建立持久化本地数据库
        self.conn = sqlite3.connect('cqc_group_v10.db', check_same_thread=False)
        self._init_db()

    def _init_db(self):
        c = self.conn.cursor()
        # A. 业务员档案 (根节点)
        c.execute('''CREATE TABLE IF NOT EXISTS md_salesmen (name TEXT PRIMARY KEY)''')
        # B. 客户档案 (关联业务员)
        c.execute('''CREATE TABLE IF NOT EXISTS md_customers (
            cust_name TEXT PRIMARY KEY, salesman_name TEXT)''')
        # C. 核心业财总账 (支持截图中的所有费用项)
        c.execute('''CREATE TABLE IF NOT EXISTS tr_ledger (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            salesman_name TEXT,
            cust_name TEXT,
            contract_no TEXT,        -- 合同号 (如 WST-19493)
            doc_date DATE,           -- 日期
            item_desc TEXT,          -- 名称 (如 威曼凳、托卡费)
            spec_color TEXT,         -- 颜色/规格
            qty REAL DEFAULT 0,
            unit_price REAL DEFAULT 0,
            debit_amt REAL DEFAULT 0,  -- 借方：增加欠款 (金额列)
            credit_amt REAL DEFAULT 0, -- 贷方：减少欠款 (收款列)
            doc_type TEXT,             -- 业务类型
            is_void INTEGER DEFAULT 0, -- 红冲标志 (防误触)
            create_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )''')
        self.conn.commit()

# 初始化引擎
engine = EnterpriseERPEngine()

# ==========================================
# 2. UI 深度布局：层级穿透工作台
# ==========================================
st.set_page_config(page_title="CQC Group 业财一体化中台", layout="wide")

st.markdown("""
<style>
    .stApp { background-color: #f1f5f9; }
    .stSidebar { background-color: #0f172a !important; color: white; }
    .main-header { font-size: 28px; font-weight: 800; color: #1e40af; border-bottom: 3px solid #3b82f6; }
    .metric-card { background: white; padding: 15px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.05); }
</style>
""", unsafe_allow_html=True)

# 侧边栏：核心层级筛选器 (解决“业务员-客户”归属)
with st.sidebar:
    st.title("🛡️ 集团经营中台")
    st.divider()
    
    # 1. 业务员层
    salesmen = pd.read_sql("SELECT name FROM md_salesmen", engine.conn)['name'].tolist()
    sel_salesman = st.selectbox("👤 选择业务员", ["全部"] + salesmen)
    
    # 2. 客户层 (根据业务员动态过滤)
    cust_query = "SELECT cust_name FROM md_customers"
    if sel_salesman != "全部":
        cust_query += f" WHERE salesman_name = '{sel_salesman}'"
    
    customers = pd.read_sql(cust_query, engine.conn)['cust_name'].tolist()
    sel_customer = st.selectbox("🔍 选择客户明细", ["请选择"] + customers)
    
    st.divider()
    menu = st.radio("系统功能树", [
        "📊 集团看板", 
        "📋 穿透式对账明细", 
        "🏗️ 基础档案维护", 
        "📦 业务明细录入", 
        "🕵️ 审计与红冲中心"
    ])

# ==========================================
# 3. 核心功能实现 (复刻截图滚动余额逻辑)
# ==========================================

# --- 模块：穿透式对账明细 ---
if menu == "📋 穿透式对账明细":
    if sel_customer != "请选择":
        st.markdown(f'<div class="main-header">📋 {sel_customer} - 往来对账明细表</div>', unsafe_allow_html=True)
        
        # 获取明细数据
        df = pd.read_sql(f"SELECT * FROM tr_ledger WHERE cust_name = '{sel_customer}' AND is_void = 0 ORDER BY doc_date ASC", engine.conn)
        
        if not df.empty:
            # 滚动余额计算 (核心算法：复刻截图中的“应收金”)
            df['应收余额'] = (df['debit_amt'] - df['credit_amt']).cumsum()
            
            # 复刻截图排版
            display_cols = ['doc_date', 'contract_no', 'item_desc', 'spec_color', 'qty', 'unit_price', 'debit_amt', 'credit_amt', '应收余额', 'doc_type']
            st.dataframe(df[display_cols].style.format({
                'debit_amt': '{:,.2f}', 'credit_amt': '{:,.2f}', '应收余额': '{:,.2f}'
            }), use_container_width=True)
            
            st.download_button("📤 导出本表为 CSV", df[display_cols].to_csv(), f"{sel_customer}_Ledger.csv")
    else:
        st.warning("请在侧边栏先选择业务员和具体的客户名称。")

# --- 模块：业务明细录入 ---
elif menu == "📦 业务明细录入":
    st.markdown('<div class="main-header">📦 业务/费用明细钩稽入账</div>', unsafe_allow_html=True)
    with st.form("input_form"):
        c1, c2, c3 = st.columns(3)
        # 自动获取业务员归属
        f_cust = c1.selectbox("关联客户", customers)
        f_salesman = pd.read_sql(f"SELECT salesman_name FROM md_customers WHERE cust_name='{f_cust}'", engine.conn).iloc[0,0]
        f_date = c1.date_input("业务日期")
        f_contract = c2.text_input("合同号 (如 WST-19493)")
        f_type = c2.selectbox("单据类型", ["销售出库", "托卡费", "落箱费", "银行收款", "运费抵扣"])
        f_item = c3.text_input("名称 (如 39威曼凳)")
        f_spec = c3.text_input("规格/颜色")
        f_qty = c1.number_input("数量", value=0.0)
        f_price = c2.number_input("单价/总额", value=0.0)
        
        if st.form_submit_button("✅ 审核确认过账"):
            # 逻辑：销售和费用计入借方(debit)，收款和抵扣计入贷方(credit)
            debit = f_qty * f_price if f_type in ["销售出库", "托卡费", "落箱费"] else 0
            credit = f_price if f_type in ["银行收款", "运费抵扣"] else 0
            
            engine.conn.execute('''INSERT INTO tr_ledger 
                (salesman_name, cust_name, contract_no, doc_date, item_desc, spec_color, qty, unit_price, debit_amt, credit_amt, doc_type)
                VALUES (?,?,?,?,?,?,?,?,?,?,?)''', 
                (f_salesman, f_cust, f_contract, f_date, f_item, f_spec, f_qty, f_price, debit, credit, f_type))
            engine.conn.commit()
            st.success("单据已入账。")

# --- 模块：基础档案维护 ---
elif menu == "🏗️ 基础档案维护":
    st.markdown('<div class="main-header">🏗️ 企业组织架构档案</div>', unsafe_allow_html=True)
    col1, col2 = st.columns(2)
    with col1:
        st.subheader("👤 业务员档案")
        new_sm = st.text_input("新增业务员姓名")
        if st.button("添加业务员"):
            engine.conn.execute("INSERT OR IGNORE INTO md_salesmen (name) VALUES (?)", (new_sm,))
            engine.conn.commit()
            st.rerun()
    with col2:
        st.subheader("👥 客户及归属维护")
        new_cust = st.text_input("新增客户名称")
        belong_sm = st.selectbox("归属业务员", salesmen)
        if st.button("添加客户"):
            engine.conn.execute("INSERT OR IGNORE INTO md_customers (cust_name, salesman_name) VALUES (?,?)", (new_cust, belong_sm))
            engine.conn.commit()
            st.rerun()
