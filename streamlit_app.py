import streamlit as st
import pandas as pd
import sqlite3
import plotly.express as px
from datetime import datetime
import uuid

# ==========================================
# 1. 工业级核心内核：多维组织架构引擎
# ==========================================
class Enterprise_Master_Kernel:
    def __init__(self):
        # 数据库持久化连接
        self.conn = sqlite3.connect('cqc_group_v9.db', check_same_thread=False)
        self._bootstrap()

    def _bootstrap(self):
        c = self.conn.cursor()
        # A. 组织架构：业务员档案
        c.execute('''CREATE TABLE IF NOT EXISTS md_salesmen (name TEXT PRIMARY KEY)''')
        # B. 客户主数据：关联业务员
        c.execute('''CREATE TABLE IF NOT EXISTS md_customers (
            cust_name TEXT PRIMARY KEY, salesman TEXT)''')
        # C. 业务总账：深度复刻截图字段 (支持负数冲减、滚动余额)
        c.execute('''CREATE TABLE IF NOT EXISTS tr_ledger (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            salesman TEXT,
            cust_name TEXT,
            doc_date DATE,
            contract_no TEXT,        -- 合同号
            item_desc TEXT,          -- 品名/费用项
            spec_color TEXT,         -- 颜色规格
            qty REAL DEFAULT 0,
            price REAL DEFAULT 0,
            debit_amt REAL DEFAULT 0,  -- 借方：出库/扣费 (增加欠款)
            credit_amt REAL DEFAULT 0, -- 贷方：回款/抵扣 (减少欠款)
            doc_type TEXT,             -- 销售/托卡/落箱/收款
            is_void INTEGER DEFAULT 0, -- 红冲标志
            audit_log TEXT
        )''')
        self.conn.commit()

kernel = Enterprise_Master_Kernel()

# ==========================================
# 2. 界面排版：仿 SAP Fiori 全屏工作台
# ==========================================
st.set_page_config(page_title="常青青集团-业财大数据平台", layout="wide")

st.markdown("""
    <style>
    .stApp { background-color: #f4f7f6; }
    .stSidebar { background-image: linear-gradient(#1e293b, #0f172a); color: white; }
    .main-header { font-size: 24px; font-weight: 800; color: #1e40af; border-bottom: 2px solid #3b82f6; }
    </style>
""", unsafe_allow_html=True)

# 侧边栏：多层级筛选（核心逻辑：层级穿透）
with st.sidebar:
    st.title("🛡️ 集团经营中台")
    # 1. 顶层：业务员切换
    salesmen_list = pd.read_sql("SELECT name FROM md_salesmen", kernel.conn)['name'].tolist()
    sel_salesman = st.selectbox("👤 选择业务员", ["全部"] + salesmen_list)
    
    st.divider()
    menu = st.radio("功能模块", [
        "📊 集团看板 (Dashboard)",
        "📋 业务员专属对账 (Ledger)",
        "🏗️ 基础档案 (MDM)",
        "📦 批量单据录入 (Input)",
        "🕵️ 财务审计/红冲 (Audit)"
    ])

# ==========================================
# 3. 功能模块实现 (深度复刻截图逻辑)
# ==========================================

# --- 模块：业务员专属对账 (实现滚动余额逻辑) ---
if menu == "📋 业务员专属对账 (Ledger)":
    st.markdown(f'<div class="main-header">📋 对账明细表 (业务员: {sel_salesman})</div>', unsafe_allow_html=True)
    
    # 动态联动：选择客户
    cust_query = "SELECT cust_name FROM md_customers"
    if sel_salesman != "全部":
        cust_query += f" WHERE salesman = '{sel_salesman}'"
    
    cust_list = pd.read_sql(cust_query, kernel.conn)['cust_name'].tolist()
    sel_cust = st.selectbox("🔍 选择客户", cust_list)
    
    if sel_cust:
        df = pd.read_sql(f"SELECT * FROM tr_ledger WHERE cust_name = '{sel_cust}' AND is_void = 0 ORDER BY doc_date ASC", kernel.conn)
        
        # 大师级核心逻辑：滚动余额计算 (debit 增，credit 减)
        if not df.empty:
            df['滚动应收余额'] = (df['debit_amt'] - df['credit_amt']).cumsum()
            
            # 复刻截图列：编号、日期、合同号、品名、规格、数量、单价、金额、收款、应收金
            display_df = df[['doc_date', 'contract_no', 'item_desc', 'spec_color', 'qty', 'price', 'debit_amt', 'credit_amt', '滚动应收余额', 'doc_type']]
            
            st.dataframe(display_df.style.format({
                'debit_amt': '¥{:,.2f}', 'credit_amt': '¥{:,.2f}', '滚动应收余额': '¥{:,.2f}'
            }), use_container_width=True)
            
            st.download_button("📤 导出对账单 (Excel)", display_df.to_csv(), f"{sel_cust}_Statement.csv")

# --- 模块：单据录入 (支持截图中的各种复杂项) ---
elif menu == "📦 批量单据录入 (Input
