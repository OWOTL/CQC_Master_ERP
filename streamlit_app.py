import streamlit as st
import pandas as pd
import sqlite3
from datetime import datetime
import uuid

# ==========================================
# 1. 工业级业财内核：支持多级组织架构
# ==========================================
class KingdeeStyleERP:
    def __init__(self):
        # 建立持久化数据库，支持多线程
        self.conn = sqlite3.connect('cqc_enterprise_v11.db', check_same_thread=False)
        self._bootstrap()

    def _bootstrap(self):
        c = self.conn.cursor()
        # A. 组织架构：业务员主表
        c.execute('CREATE TABLE IF NOT EXISTS md_salesman (id INTEGER PRIMARY KEY, name TEXT UNIQUE)')
        # B. 客户主数据：归属特定业务员
        c.execute('CREATE TABLE IF NOT EXISTS md_customer (cust_id TEXT PRIMARY KEY, cust_name TEXT UNIQUE, salesman_name TEXT)')
        # C. 业务全量账表：复刻截图中的所有字段逻辑
        c.execute('''CREATE TABLE IF NOT EXISTS tr_general_ledger (
            entry_id TEXT PRIMARY KEY,
            salesman TEXT,
            cust_name TEXT,
            contract_no TEXT,        -- 合同号/采购单号 (如 WST-19493)
            doc_date DATE,           -- 发生日期
            item_name TEXT,          -- 品名/项目 (如 威曼凳、托卡费)
            spec_color TEXT,         -- 颜色/规格 (如 黑色、7534C)
            qty REAL DEFAULT 0,      -- 数量
            unit_price REAL DEFAULT 0, -- 单价
            debit_amt REAL DEFAULT 0,  -- 借方发生额 (产生应收)
            credit_amt REAL DEFAULT 0, -- 贷方发生额 (回款/核销)
            doc_type TEXT,             -- 单据类型
            audit_status TEXT DEFAULT '已审核',
            is_void INTEGER DEFAULT 0  -- 红冲标记
        )''')
        self.conn.commit()

# 初始化 ERP 引擎
erp = KingdeeStyleERP()

# ==========================================
# 2. 界面排版：金蝶 K/3 Cloud 云端布局
# ==========================================
st.set_page_config(page_title="常青青集团-企业级业财中台", layout="wide")

st.markdown("""
<style>
    .stApp { background-color: #f0f2f5; }
    .stSidebar { background-color: #001529 !important; color: white !important; }
    .main-header { font-size: 26px; font-weight: bold; color: #1890ff; padding-bottom: 10px; border-bottom: 2px solid #e8e8e8; }
    .kingdee-table { font-size: 13px; }
</style>
""", unsafe_allow_html=True)

# 侧边栏：金蝶风格多级功能导航
with st.sidebar:
    st.title("💼 CQC Group ERP")
    st.caption("2026 生产级标准版")
    st.divider()
    
    # 核心：业务员-客户联动导航
    salesmen = pd.read_sql("SELECT name FROM md_salesman", erp.conn)['name'].tolist()
    sel_sm = st.selectbox("👤 当前业务员 (Salesman)", ["请选择"] + salesmen)
    
    if sel_sm != "请选择":
        cust_list = pd.read_sql(f"SELECT cust_name FROM md_customer WHERE salesman_name='{sel_sm}'", erp.conn)['cust_name'].tolist()
        sel_cust = st.selectbox("🔍 客户往来明细", ["请选择"] + cust_list)
    else:
        sel_cust = "请选择"
        
    st.divider()
    menu = st.radio("系统功能树", [
        "📊 集团应收总盘 (Dashboard)",
        "📋 穿透式往来对账 (Statement)",
        "📦 供应链入账 (Input)",
        "🏗️ 基础档案中心 (MDM)",
        "🕵️ 审计与红冲中心 (Audit)"
    ])

# ==========================================
# 3. 业务逻辑复刻：针对截图中的滚动余额与费用扣除
# ==========================================

# --- 模块：集团应收总盘 (复刻截图 1 逻辑) ---
if menu == "📊 集团应收总盘 (Dashboard)":
    st.markdown(f'<div class="main-header">📊 2025年应收账款汇总看板 (业务员: {sel_sm})</div>', unsafe_allow_html=True)
    
    where_clause = "" if sel_sm == "请选择" else f" WHERE salesman = '{sel_sm}'"
    df_all = pd.read_sql(f"SELECT cust_name, SUM(debit_amt) as debit, SUM(credit_amt) as credit FROM tr_general_ledger {where_clause} GROUP BY cust_name", erp.conn)
    
    if not df_all.empty:
        df_all['欠款余额'] = df_all['debit'] - df_all['credit']
        c1, c2, c3 = st.columns(3)
        c1.metric("累计应收额 (借方)", f"¥{df_all['debit'].sum():,.2f}")
        c2.metric("累计回款额 (贷方)", f"¥{df_all['credit'].sum():,.2f}")
        c3.metric("当前欠款净值", f"¥{df_all['欠款余额'].sum():,.2f}")
        st.dataframe(df_all, use_container_width=True)

# --- 模块：穿透式往来对账 (复刻截图 2 滚动应收金逻辑) ---
elif menu == "📋 穿透式往来对账 (Statement)":
    if sel_cust != "请选择":
        st.markdown(f'<div class="main-header">📋 {sel_cust} - 客户明细对账单</div>', unsafe_allow_html=True)
        # 获取该客户下所有合同的流水
        df = pd.read_sql(f"SELECT * FROM tr_general_ledger WHERE cust_name='{sel_cust}' AND is_void=0 ORDER BY doc_date ASC", erp.conn)
        
        if not df.empty:
            # 核心算法：复刻截图中的“应收金”滚动列
            df['滚动应收金'] = (df['debit_amt'] - df['credit_amt']).cumsum()
            
            # 字段对齐截图：日期、合同号、品名、规格、数量、单价、金额、收款、应收金
            display_cols = ['doc_date', 'contract_no', 'item_name', 'spec_color', 'qty', 'unit_price', 'debit_amt', 'credit_amt', '滚动应收金']
            st.dataframe(df[display_cols].style.format({
                'debit_amt': '{:,.2f}', 'credit_amt': '{:,.2f}', '滚动应收金': '{:,.2f}'
            }), use_container_width=True, height=600)
    else:
        st.info("请在左侧选择业务员及对应客户进行穿透查询。")

# --- 模块：供应链入账 (支持截图中的托卡、落箱费抵扣) ---
elif menu == "📦 供应链入账 (Input)":
    st.markdown('<div class="main-header">📦 业务单据录入与钩稽</div>', unsafe_allow_html=True)
    if sel_cust != "请选择":
        with st.form("ledger_input"):
            c1, c2, c3 = st.columns(3)
            f_date = c1.date_input("业务日期")
            f_con = c1.text_input("合同号/采购单号 (必填)")
            f_type = c2.selectbox("业务性质", ["销售出库", "托卡费", "落箱费", "银行到账", "抵扣项"])
            f_item = c2.text_input("品名描述 (如: 威曼凳)")
            f_spec = c3.text_input("颜色/规格")
            f_qty = c3.number_input("数量 (Qty)", value=0.0)
            f_val = c1.number_input("单价/总金额", value=0.0)
            
            if st.form_submit_button("🛡️ 审核并生成凭证"):
                # 财务逻辑：销售和费用进借方(debit)，收款和抵扣进贷方(credit)
                debit = f_qty * f_val if f_type in ["销售出库", "托卡费", "落箱费"] else 0
                credit = f_val if f_type in ["银行到账", "抵扣项"] else 0
                
                erp.conn.execute('''INSERT INTO tr_general_ledger 
                    (entry_id, salesman, cust_name, contract_no, doc_date, item_name, spec_color, qty, unit_price, debit_amt, credit_amt, doc_type)
                    VALUES (?,?,?,?,?,?,?,?,?,?,?,?)''', 
                    (str(uuid.uuid4())[:8], sel_sm, sel_cust, f_con, f_date, f_item, f_spec, f_qty, f_val, debit, credit, f_type))
                erp.conn.commit()
                st.success(f"凭证录入成功！合同号: {f_con}")
    else:
        st.error("操作受限：请先在侧边栏指定客户节点。")

# --- 模块：基础档案 (MDM - 解决多业务员架构) ---
elif menu == "🏗️ 基础档案中心 (MDM)":
    st.markdown('<div class="main-header">🏗️ 集团主数据维护中心</div>', unsafe_allow_html=True)
    t1, t2 = st.tabs(["业务员主表", "客户关联表"])
    with t1:
        new_sm = st.text_input("新增业务员姓名")
        if st.button("录入业务员"):
            erp.conn.execute("INSERT OR IGNORE INTO md_salesman (name) VALUES (?)", (new_sm,))
            erp.conn.commit()
            st.rerun()
    with t2:
        new_cust = st.text_input("新增客户名称")
        belong_to = st.selectbox("归属业务员", salesmen)
        if st.button("录入客户"):
            erp.conn.execute("INSERT OR IGNORE INTO md_customer (cust_id, cust_name, salesman_name) VALUES (?,?,?)", 
                            (str(uuid.uuid4())[:6], new_cust, belong_to))
            erp.conn.commit()
            st.rerun()
