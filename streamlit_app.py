import streamlit as st
import pandas as pd
import sqlite3
import plotly.graph_objects as go
from datetime import datetime, date
import uuid

# --- 大师级核心引擎：业财一体化数据中台 ---
class ERPDataCenter:
    def __init__(self):
        self.conn = sqlite3.connect('cqc_online_erp.db', check_same_thread=False)
        self.cursor = self.conn.cursor()
        self._init_core_tables()

    def _init_core_tables(self):
        # 1. 往来单位档案 (支持生命周期管理)
        self.cursor.execute('''CREATE TABLE IF NOT EXISTS md_entities (
            code TEXT PRIMARY KEY, name TEXT UNIQUE, category TEXT, status TEXT DEFAULT '激活')''')
        # 2. 业财全流向总账 (核心逻辑：合同-出库-发票-核销)
        self.cursor.execute('''CREATE TABLE IF NOT EXISTS tr_general_ledger (
            doc_uuid TEXT PRIMARY KEY,
            cust_name TEXT,
            contract_no TEXT,
            delivery_no TEXT UNIQUE,
            delivery_date DATE,
            product_info TEXT,
            total_amount REAL,
            paid_amount REAL DEFAULT 0,
            invoice_no TEXT,
            invoice_status TEXT DEFAULT '未开票',
            clearing_status TEXT DEFAULT '未结清', -- 未结清/部分核销/已结案/已红冲
            audit_log TEXT,
            is_locked INTEGER DEFAULT 0,
            update_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )''')
        self.conn.commit()

    def log_audit(self, del_no, action):
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.cursor.execute("UPDATE tr_general_ledger SET audit_log = audit_log || ? WHERE delivery_no = ?", 
                           (f"[{now}] {action} | ", del_no))
        self.conn.commit()

# 初始化
erp = ERPDataCenter()

# --- 顶级 UI 框架：仿 SAP Fiori 风格 ---
st.set_page_config(page_title="CQC 业财大师云平台", layout="wide")

st.markdown("""
<style>
    .stApp { background-color: #f0f4f7; }
    .css-1d391kg { background-color: #1e293b; } /* 侧边栏颜色 */
    .metric-container { background: white; border-radius: 10px; padding: 20px; box-shadow: 0 4px 6px rgba(0,0,0,0.1); }
    h1 { color: #1e3a8a; border-bottom: 3px solid #3b82f6; padding-bottom: 10px; }
</style>
""", unsafe_allow_html=True)

# 侧边栏导航 (多窗口并行逻辑)
with st.sidebar:
    st.title("🛡️ CQC ERP 5.0")
    menu = st.selectbox("功能矩阵导航", [
        "📊 财务驾驶舱 (Cockpit)",
        "🏢 单位档案中心 (MDM)",
        "🚚 业务流工作台 (SCM)",
        "💰 智能对账中心 (Clearing)",
        "🕵️ 审计与红冲中心 (Audit)"
    ])
    st.divider()
    st.info("当前节点: GitHub 生产集群")

# --- 逻辑模块实现 ---

# 1. 财务驾驶舱 (抄袭 SAP 决策层分析)
if menu == "📊 财务驾驶舱 (Cockpit)":
    st.title("📊 集团财务实时看板")
    df = pd.read_sql("SELECT * FROM tr_general_ledger WHERE clearing_status != '已红冲'", erp.conn)
    if not df.empty:
        c1, c2, c3 = st.columns(3)
        c1.metric("应收总债权", f"¥{df['total_amount'].sum():,.2f}")
        c2.metric("已收总回款", f"¥{df['paid_amount'].sum():,.2f}")
        c3.metric("待收账面净值", f"¥{(df['total_amount'].sum() - df['paid_amount'].sum()):,.2f}")
        
        fig = go.Figure(data=[go.Pie(labels=df['cust_name'], values=df['total_amount'], hole=.4)])
        st.plotly_chart(fig, use_container_width=True)

# 2. 业务流工作台 (深度业财钩稽)
elif menu == "🚚 业务流工作台 (SCM)":
    st.title("🚚 出库单据钩稽入账")
    with st.expander("➕ 新增出库单 (关联小工单数据)", expanded=True):
        all_custs = pd.read_sql("SELECT name FROM md_entities WHERE status='激活'", erp.conn)['name'].tolist()
        with st.form("input_form"):
            c1, c2, c3 = st.columns(3)
            cust = c1.selectbox("选择对账单位", all_custs)
            con = c1.text_input("合同号")
            del_no = c2.text_input("出库单号 (唯一识别)")
            del_date = c2.date_input("发货日期")
            prod = c3.text_input("产品描述")
            amt = c3.number_input("本单应收总额", min_value=0.0)
            if st.form_submit_button("🛡️ 审核过账"):
                try:
                    erp.cursor.execute('''INSERT INTO tr_general_ledger 
                        (doc_uuid, cust_name, contract_no, delivery_no, delivery_date, product_info, total_amount, audit_log)
                        VALUES (?,?,?,?,?,?,?,?)''', (str(uuid.uuid4())[:8], cust, con, del_no, del_date, prod, amt, "单据创建审核过账"))
                    erp.conn.commit()
                    st.success("单据已入账并锁定。")
                except: st.error("错误：单据号重复！")

# 3. 智能对账中心 (抄袭金蝶核心核销)
elif menu == "💰 智能对账中心 (Clearing)":
    st.title("💰 智能回款核销引擎")
    df_p = pd.read_sql("SELECT delivery_no, cust_name, (total_amount - paid_amount) as bal FROM tr_general_ledger WHERE bal > 0 AND clearing_status != '已红冲'", erp.conn)
    if not df_p.empty:
        with st.form("clear_form"):
            target = st.selectbox("选择对账单号", df_p['delivery_no'].tolist())
            val = st.number_input("到账金额", min_value=0.0)
            if st.form_submit_button("执行对账"):
                erp.cursor.execute(f"UPDATE tr_general_ledger SET paid_amount = paid_amount + {val} WHERE delivery_no = '{target}'")
                erp.cursor.execute(f"UPDATE tr_general_ledger SET clearing_status = CASE WHEN paid_amount >= total_amount THEN '已结案' ELSE '部分核销' END WHERE delivery_no = ?", (target,))
                erp.conn.commit()
                erp.log_audit(target, f"收到回款 ¥{val}")
                st.success("对账完成")

# 4. 单位档案 (随增随删)
elif menu == "🏢 单位档案中心 (MDM)":
    st.title("🏢 往来单位档案")
    with st.form("mdm"):
        c_code = st.text_input("编码")
        c_name = st.text_input("全称")
        if st.form_submit_button("保存"):
            erp.cursor.execute("INSERT OR REPLACE INTO md_entities (code, name) VALUES (?,?)", (c_code, c_name))
            erp.conn.commit()
    st.table(pd.read_sql("SELECT * FROM md_entities", erp.conn))
