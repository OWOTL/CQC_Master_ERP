import streamlit as st
import pandas as pd
import sqlite3
import plotly.graph_objects as go
from datetime import datetime, date
import uuid

# ==========================================
# 1. 后端：四层树状组织架构数据库引擎
# ==========================================
class EnterpriseERPEngine:
    def __init__(self):
        self.db_name = 'enterprise_master_v8.db'
        self.conn = sqlite3.connect(self.db_name, check_same_thread=False)
        self.bootstrap()

    def bootstrap(self):
        c = self.conn.cursor()
        # 1. 业务员表 (Salesmen)
        c.execute('''CREATE TABLE IF NOT EXISTS md_salesmen (
            id INTEGER PRIMARY KEY, name TEXT UNIQUE, dept TEXT)''')
        # 2. 客户表 (Customers - 关联业务员)
        c.execute('''CREATE TABLE IF NOT EXISTS md_customers (
            cust_id TEXT PRIMARY KEY, cust_name TEXT UNIQUE, 
            salesman_name TEXT, credit_limit REAL)''')
        # 3. 合同表 (Contracts)
        c.execute('''CREATE TABLE IF NOT EXISTS md_contracts (
            contract_no TEXT PRIMARY KEY, cust_name TEXT, 
            sign_date DATE, total_budget REAL, status TEXT DEFAULT '执行中')''')
        # 4. 核心账务明细表 (Transactions - 深度复刻截图逻辑)
        c.execute('''CREATE TABLE IF NOT EXISTS tr_ledger (
            entry_uuid TEXT PRIMARY KEY,
            salesman_name TEXT,
            cust_name TEXT,
            contract_no TEXT,
            doc_date DATE,
            item_desc TEXT,        -- 威曼凳、托卡费、落箱费等
            spec_color TEXT,
            qty REAL DEFAULT 0,
            price REAL DEFAULT 0,
            debit_amt REAL DEFAULT 0,  -- 借方：出库金额/增加欠款
            credit_amt REAL DEFAULT 0, -- 贷方：回款/减少欠款
            doc_type TEXT,             -- 出库单/费用单/回款单/红冲单
            is_void INTEGER DEFAULT 0, -- 0:正常, 1:已红冲
            operator TEXT,
            audit_trail TEXT,          -- 审计日志记录
            create_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )''')
        self.conn.commit()

    def query(self, sql, params=()):
        return pd.read_sql(sql, self.conn, params=params)

    def execute(self, sql, params=()):
        self.conn.execute(sql, params)
        self.conn.commit()

erp = EnterpriseERPEngine()

# ==========================================
# 2. UI 深度布局：工业化侧边栏与多窗口任务
# ==========================================
st.set_page_config(page_title="CQC Group 业财一体化平台", layout="wide")

st.markdown("""
    <style>
    .main { background: #f4f7f9; }
    .stSidebar { background-color: #0f172a !important; color: white !important; }
    .metric-card { background: #ffffff; padding: 20px; border-radius: 10px; border: 1px solid #e2e8f0; }
    .status-active { color: #059669; font-weight: bold; }
    .status-void { color: #dc2626; text-decoration: line-through; }
    </style>
""", unsafe_allow_html=True)

# 侧边栏：多维导航
with st.sidebar:
    st.image("https://cdn-icons-png.flaticon.com/512/3201/3201521.png", width=60)
    st.title("集团业财中台")
    st.divider()
    
    # 全局业务员筛选 (顶层隔离)
    salesmen_list = erp.query("SELECT name FROM md_salesmen")['name'].tolist()
    sel_salesman = st.selectbox("👤 当前业务员切换", ["全部业务员"] + salesmen_list)
    
    st.divider()
    menu = st.radio("系统功能矩阵", [
        "📊 集团看板 (Dashboard)",
        "🏗️ 组织架构管理 (MDM)",
        "📋 合同/业务流 (Transactions)",
        "💰 财务结算中心 (Clearing)",
        "📒 穿透式明细账 (Ledger)"
    ])
    st.divider()
    st.caption("版本: V8.2 Enterprise | 生产集群")

# ==========================================
# 3. 核心业务模块：严谨逻辑实现
# ==========================================

# --- 模块：组织架构 (实现业务员-客户-合同关联) ---
if menu == "🏗️ 组织架构管理 (MDM)":
    st.header("🏗️ 组织架构与档案中心")
    t1, t2, t3 = st.tabs(["业务员档案", "客户主数据", "合同台账"])
    
    with t1:
        with st.form("add_salesman"):
            n = st.text_input("业务员姓名")
            d = st.text_input("所属部门")
            if st.form_submit_button("新增业务员"):
                erp.execute("INSERT OR IGNORE INTO md_salesmen (name, dept) VALUES (?,?)", (n, d))
        st.dataframe(erp.query("SELECT * FROM md_salesmen"), use_container_width=True)

    with t2:
        with st.form("add_cust"):
            c_name = st.text_input("客户全称")
            belongs_to = st.selectbox("归属业务员", salesmen_list)
            if st.form_submit_button("保存客户档案"):
                erp.execute("INSERT OR IGNORE INTO md_customers (cust_id, cust_name, salesman_name) VALUES (?,?,?)", 
                            (str(uuid.uuid4())[:8], c_name, belongs_to))
        st.dataframe(erp.query("SELECT * FROM md_customers"), use_container_width=True)

# --- 模块：业务流 (实现合同号下的精准录入) ---
elif menu == "📋 合同/业务流 (Transactions)":
    st.header("📋 业务单据录入工作台")
    
    # 动态联动筛选：业务员 -> 客户 -> 合同
    c1, c2, c3 = st.columns(3)
    salesman = c1.selectbox("业务员", salesmen_list)
    custs = erp.query(f"SELECT cust_name FROM md_customers WHERE salesman_name='{salesman}'")['cust_name'].tolist()
    cust = c2.selectbox("关联客户", custs)
    
    with st.expander("➕ 录入出库/费用/回款明细 (多维钩稽)", expanded=True):
        with st.form("input_form"):
            cc1, cc2, cc3 = st.columns(3)
            f_contract = cc1.text_input("合同号 (Contract ID)")
            f_date = cc1.date_input("发生日期")
            f_type = cc2.selectbox("单据类型", ["销售出库", "托卡费", "落箱费", "运费抵扣", "银行回款"])
            f_item = cc2.text_input("品名/费用详情")
            f_spec = cc3.text_input("规格/颜色")
            f_amt = cc3.number_input("涉及金额", min_value=0.0)
            
            if st.form_submit_button("🛡️ 审核并过账"):
                debit = f_amt if f_type in ["销售出库", "托卡费", "落箱费"] else 0
                credit = f_amt if f_type in ["银行回款", "运费抵扣"] else 0
                
                erp.execute('''INSERT INTO tr_ledger 
                    (entry_uuid, salesman_name, cust_name, contract_no, doc_date, item_desc, spec_color, debit_amt, credit_amt, doc_type)
                    VALUES (?,?,?,?,?,?,?,?,?,?)''', 
                    (str(uuid.uuid4())[:8], salesman, cust, f_contract, f_date, f_item, f_spec, debit, credit, f_type))
                st.success("单据已入账，滚动余额已实时计算。")

# --- 模块：穿透式明细账 (解决你看到的 Excel 逻辑问题) ---
elif menu == "📒 穿透式明细账 (Ledger)":
    st.header("📒 穿透式往来对账明细")
    
    # 过滤器
    f_c1, f_c2, f_c3 = st.columns(3)
    q_salesman = f_c1.selectbox("筛选业务员", ["全部"] + salesmen_list)
    
    where_clause = "WHERE is_void = 0"
    if q_salesman != "全部":
        where_clause += f" AND salesman_name = '{q_salesman}'"
        
    df = erp.query(f"SELECT * FROM tr_ledger {where_clause} ORDER BY doc_date ASC")
    
    if not df.empty:
        # 核心滚动余额算法 (大师级复刻)
        df['滚动欠款余额'] = (df['debit_amt'] - df['credit_amt']).cumsum()
        
        # 格式化显示
        display_cols = ['doc_date', 'salesman_name', 'cust_name', 'contract_no', 'item_desc', 'spec_color', 'debit_amt', 'credit_amt', '滚动欠款余额', 'doc_type']
        st.dataframe(df[display_cols].style.format({
            'debit_amt': '¥{:,.2f}', 
            'credit_amt': '¥{:,.2f}', 
            '滚动欠款余额': '¥{:,.2f}'
        }), use_container_width=True)
        
        # 导出功能
        st.download_button("📤 导出当前对账单", df.to_csv(), "Detailed_Ledger.csv")

# --- 模块：集团看板 (多维透视) ---
elif menu == "📊 集团看板 (Dashboard)":
    st.header("📊 集团经营监控大屏")
    df_all = erp.query("SELECT * FROM tr_ledger WHERE is_void = 0")
    
    if not df_all.empty:
        c1, c2, c3 = st.columns(3)
        c1.metric("全集团应收净额", f"¥{(df_all['debit_amt'].sum() - df_all['credit_amt'].sum()):,.2f}")
        c2.metric("活跃合同总数", len(df_all['contract_no'].unique()))
        c3.metric("本月回款总额", f"¥{df_all['credit_amt'].sum():,.2f}")
        
        # 业务员业绩排行榜
        st.subheader("👨‍💼 业务员应收账款穿透分析")
        perf = df_all.groupby('salesman_name')[['debit_amt', 'credit_amt']].sum()
        perf['欠款余额'] = perf['debit_amt'] - perf['credit_amt']
        st.bar_chart(perf['欠款余额'])
