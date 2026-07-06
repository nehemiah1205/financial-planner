# -*- coding: utf-8 -*-
"""
家庭財務健康體檢與目標模擬系統 (網頁互動版)
由「財務試算表新版_2026_.xlsx」轉製，並優化為 Streamlit 互動式應用。
"""
import streamlit as st
import pandas as pd
import numpy_financial as npf
import datetime
import json

st.set_page_config(page_title="家庭財務健康體檢與目標模擬系統", page_icon="💰",
                    layout="wide", initial_sidebar_state="expanded")

# ==========================================================
# 共用常數
# ==========================================================
TUITION_PRESETS = {
    "不選擇": 0,
    "國內國立大學": 58728,
    "國內私立大學": 109994,
    "國外公立大學": 300000,
    "國外私立大學": 1000000,
    "國內研究所": 50000,
    "國外研究所": 300000,
    "博士班": 100000,
}
CHILD_RELATIONS = ["長子", "長女", "次子", "次女", "其他"]

INCOME_ITEMS = ["個人工作收入", "配偶工作收入", "年終及其他獎金", "理財收入(股息/租金/還本金)", "其他收入"]
GENERAL_EXPENSE_ITEMS = ["食", "衣", "住(房貸/租金)", "行", "育", "樂", "衛生保健", "稅務"]
FINANCE_EXPENSE_ITEMS = ["定期定額基金", "股票投資", "理財型保單", "定存單", "債券", "其他理財工具"]
INSURANCE_EXPENSE_ITEMS = ["健保", "勞保(公教保)", "個人商業保險(保障型)", "產物保險", "其他保險(1)", "其他保險(2)"]
OTHER_EXPENSE_ITEMS = ["父母奉養金", "十一奉獻", "帳戶儲蓄(固定儲蓄)", "其他支出(2)", "其他支出(3)", "其他支出(4)"]
ASSET_ITEMS = ["活期存款", "定期存款", "有價證券", "基金", "保單現價", "房地產", "其他資產"]
LIAB_ITEMS = ["房屋貸款", "車貸", "信用卡債", "信用貸款", "其他負債"]

GOAL_ROWS = [
    ("短期目標 (0~5年)", "財務金流控管", True),
    ("短期目標 (0~5年)", "結婚基金", False),
    ("短期目標 (0~5年)", "購 / 換車", True),
    ("短期目標 (0~5年)", "風險與保險規劃", True),
    ("短期目標 (0~5年)", "其他短期目標", False),
    ("中期目標 (5~10年)", "房屋頭期款準備", False),
    ("中期目標 (5~10年)", "子女教育金準備", True),
    ("中期目標 (5~10年)", "創業基金", False),
    ("中期目標 (5~10年)", "其他中期目標", False),
    ("長期目標 (10年以上)", "房屋貸款清償規劃", True),
    ("長期目標 (10年以上)", "退休生活規劃", True),
    ("長期目標 (10年以上)", "遺贈與資產傳承規劃", False),
    ("長期目標 (10年以上)", "信託規劃", False),
]

# ==========================================================
# 共用工具函式
# ==========================================================
def fv(pv, rate, years):
    return pv * ((1 + rate) ** years)


def pmt_for_target(rate, years, target):
    """算出每年需準備多少錢，才能在 years 年後累積到 target（年金終值）。"""
    if years <= 0:
        return 0.0
    if rate == 0:
        return target / years
    return -npf.pmt(rate, years, 0, target)


def money(x):
    try:
        return f"${x:,.0f}"
    except Exception:
        return "$0"


def age_from_dob(dob, ref_date=None):
    if pd.isnull(dob):
        return 0
    ref_date = ref_date or datetime.date.today()
    return ref_date.year - dob.year - ((ref_date.month, ref_date.day) < (dob.month, dob.day))


def item_table(key, items, per_row_label="金額(年)", step=1000):
    """建立一個可編輯的『項目-金額』表，回傳 {項目: 金額} 與加總。
    以同一份 DataFrame 作為 session_state 中的唯一資料來源，每次重新整理都直接沿用
    data_editor 上次回傳的結果，而不是從別處重建一份新的 DataFrame 餵給它，
    避免使用者剛輸入的數字被重置成 0（Streamlit data_editor 若每次收到「不同」的
    來源資料，會誤判成資料異動並重置編輯狀態）。"""
    df_key = key + "_df"
    if df_key not in st.session_state:
        st.session_state[df_key] = pd.DataFrame({"項目": items, per_row_label: [0] * len(items)})
    edited = st.data_editor(
        st.session_state[df_key], key=key + "_editor", hide_index=True, use_container_width=True,
        column_config={per_row_label: st.column_config.NumberColumn(per_row_label, step=step, format="%d", min_value=0)},
        disabled=["項目"],
    )
    st.session_state[df_key] = edited
    result = {row["項目"]: int(row[per_row_label] or 0) for _, row in edited.iterrows()}
    return result, sum(result.values())


def get_family_df():
    if "family_df" not in st.session_state:
        st.session_state.family_df = pd.DataFrame({
            "關係": ["本人", "配偶", "父親", "母親", "長子", "長女"],
            "姓名": ["S先生", "Y小姐", "老爸", "老媽", "大兒子", "小女兒"],
            "性別": ["男", "女", "男", "女", "男", "女"],
            "生日": [
                datetime.date(1991, 1, 1), datetime.date(1992, 1, 1),
                datetime.date(1960, 1, 1), datetime.date(1961, 1, 1),
                datetime.date(2013, 1, 1), datetime.date(2016, 1, 1),
            ],
        })
    return st.session_state.family_df


def get_person_names():
    df = get_family_df()
    names = df["姓名"].dropna().tolist()
    return names if names else ["本人"]


def get_default_retire_params():
    return {"退休年齡": 65, "養老年期": 25, "通貨膨脹率(%)": 3.0,
            "工作期間投報率(%)": 6.0, "退休後投報率(%)": 3.0, "平均餘命": 90}


def get_retire_params_df():
    """依家庭成員(本人/配偶)動態維護退休參數表。
    只有在『人員名單有變動』(新增/刪除家庭成員) 時才重建 DataFrame；
    平常編輯數字時直接沿用 session_state 裡同一份 DataFrame，
    避免每次重新整理都建立新物件餵給 data_editor 導致剛輸入的數字被重置。"""
    df = get_family_df()
    people = df[df["關係"].isin(["本人", "配偶"])]["姓名"].dropna().tolist()
    if not people:
        people = ["本人"]

    stored_df = st.session_state.get("retire_params_df")
    if stored_df is None or set(stored_df["姓名"].tolist()) != set(people):
        existing = stored_df.set_index("姓名").to_dict("index") if stored_df is not None else {}
        rows = [{"姓名": p, **existing.get(p, get_default_retire_params())} for p in people]
        stored_df = pd.DataFrame(rows)
        st.session_state.retire_params_df = stored_df
    return stored_df


# ==========================================================
# Step 1：基本資料與參數
# ==========================================================
def step1_basic_info():
    st.title("👨‍👩‍👧‍👦 Step 1：基本資料與參數設定")
    st.caption("此頁資料會自動連動到後續所有試算專題（退休、教育金、保險缺口分析等）。")

    ref_date = st.date_input("📅 客戶資料輸入日期", st.session_state.get("ref_date", datetime.date.today()))
    st.session_state.ref_date = ref_date
    st.divider()

    st.subheader("👥 家庭成員基本資料")
    st.info("💡 **表格操作**：雙擊儲存格可直接編輯；點表格最下方「+」新增一列；勾選最左側方塊後按 `Delete` 可刪除該列。")

    edited_df = st.data_editor(
        get_family_df(),
        column_config={
            "性別": st.column_config.SelectboxColumn("性別", options=["男", "女", "其他"], required=True),
            "生日": st.column_config.DateColumn("生日", format="YYYY-MM-DD", required=True),
            "關係": st.column_config.SelectboxColumn(
                "關係", options=["本人", "配偶", "父親", "母親"] + CHILD_RELATIONS),
        },
        num_rows="dynamic", use_container_width=True, hide_index=True, key="family_editor",
    )
    st.session_state.family_df = edited_df

    age_display = edited_df.copy()
    age_display["年齡"] = age_display["生日"].apply(lambda d: age_from_dob(d, ref_date))
    st.caption("目前年齡（依上方生日與資料輸入日期自動計算）")
    st.dataframe(age_display[["姓名", "年齡"]].set_index("姓名").T, use_container_width=True)

    st.divider()
    st.subheader("⚙️ 退休與經濟假設參數（依「本人 / 配偶」自動列出）")
    st.caption("此處設定的通膨率、投報率將直接套用於「專題 A：退休規劃」，兩處資料自動同步，不需重複輸入。")
    params_df = get_retire_params_df()
    edited_params = st.data_editor(
        params_df, hide_index=True, use_container_width=True, key="retire_params_editor",
        disabled=["姓名"],
        column_config={
            "通貨膨脹率(%)": st.column_config.NumberColumn(format="%.1f"),
            "工作期間投報率(%)": st.column_config.NumberColumn(format="%.1f"),
            "退休後投報率(%)": st.column_config.NumberColumn(format="%.1f"),
        },
    )
    st.session_state.retire_params_df = edited_params

    st.divider()
    st.subheader("📝 客戶現況說明")
    c1, c2 = st.columns(2)
    with c1:
        st.session_state["note_family"] = st.text_area(
            "🏠 家庭現況簡述", value=st.session_state.get("note_family",
            "夫妻兩人育有一子一女尚在求學階段，父母皆健在不需負擔奉養金。去年年底購置新屋，每月房貸負擔約5萬元。"), height=130)
        st.session_state["note_feeling"] = st.text_area(
            "🤔 當前財務現況感覺", value=st.session_state.get("note_feeling",
            "已開始工作多年並有記帳習慣，沒有豪奢消費，但帳戶現金存量不多，想重新檢視收支並針對財務目標擬定計畫。"), height=130)
    with c2:
        st.session_state["note_income"] = st.text_area(
            "💼 工作收入現況簡述", value=st.session_state.get("note_income", "兩人皆在科技業工作發展穩定，總年收入約為200萬。"), height=130)
        st.session_state["note_goal"] = st.text_area(
            "🎯 未來財務目標想法", value=st.session_state.get("note_goal",
            "提供子女大學畢業後100萬基金作為留學或創業之需，檢視現金流量清償房貸，同時為夫婦兩人做好退休準備。"), height=130)

    st.divider()
    c1, c2 = st.columns(2)
    with c1:
        st.text_input("所屬公司/單位", value=st.session_state.get("firm", "富邦人壽 - 竹耀通訊處"), key="firm")
    with c2:
        st.text_input("職稱", value=st.session_state.get("title", "處經理"), key="title")

    st.success("✅ 所有輸入即時自動儲存，可直接切換至左側其他頁面。")


# ==========================================================
# Step 2：財務目標設定
# ==========================================================
def step2_financial_goals():
    st.title("🎯 Step 2：財務目標設定")
    st.markdown("請勾選您的財務目標，並填寫預計金額與用途說明。此表將作為後續各專題試算的優先順序參考。")

    if "goals_df" not in st.session_state:
        st.session_state.goals_df = pd.DataFrame(
            [{"分類": c, "項目": n, "勾選": sel, "預估金額": 0, "用途說明": ""} for c, n, sel in GOAL_ROWS]
        )

    edited = st.data_editor(
        st.session_state.goals_df, hide_index=True, use_container_width=True, key="goals_editor",
        column_config={
            "分類": st.column_config.SelectboxColumn(
                "分類", options=["短期目標 (0~5年)", "中期目標 (5~10年)", "長期目標 (10年以上)"]),
            "勾選": st.column_config.CheckboxColumn("是否為目標"),
            "預估金額": st.column_config.NumberColumn(format="%d", step=10000),
        },
        num_rows="dynamic",
    )
    st.session_state.goals_df = edited

    st.divider()
    selected = edited[edited["勾選"] == True]
    if len(selected):
        st.subheader("📋 已選擇的財務目標總覽")
        for cat in ["短期目標 (0~5年)", "中期目標 (5~10年)", "長期目標 (10年以上)"]:
            rows = selected[selected["分類"] == cat]
            if len(rows):
                st.markdown(f"**{cat}**")
                st.dataframe(rows[["項目", "預估金額", "用途說明"]], hide_index=True, use_container_width=True)
    st.info("💡 設定好目標後，請前往左側「3. 收支與資產負債」輸入財務數據，才能為您計算達標可能性。")


# ==========================================================
# Step 3：收支與資產負債表
# ==========================================================
def _cashflow_block(suffix=""):
    st.markdown("#### 🟢 年度收入")
    income, total_income = item_table(f"income{suffix}", INCOME_ITEMS)
    st.success(f"**總收入：{money(total_income)} / 年**")

    st.markdown("#### 🔴 年度支出")
    t1, t2, t3, t4 = st.tabs(["一般支出", "理財支出", "保障型支出", "其他支出"])
    with t1:
        _, e1 = item_table(f"exp_general{suffix}", GENERAL_EXPENSE_ITEMS)
    with t2:
        _, e2 = item_table(f"exp_finance{suffix}", FINANCE_EXPENSE_ITEMS)
    with t3:
        _, e3 = item_table(f"exp_insurance{suffix}", INSURANCE_EXPENSE_ITEMS)
    with t4:
        _, e4 = item_table(f"exp_other{suffix}", OTHER_EXPENSE_ITEMS)
    total_expense = e1 + e2 + e3 + e4
    st.error(f"**總支出：{money(total_expense)} / 年**（一般 {money(e1)}、理財 {money(e2)}、保障 {money(e3)}、其他 {money(e4)}）")

    st.divider()
    net = total_income - total_expense
    st.metric("🏆 年度淨結餘 (總收入 - 總支出)", money(net))

    st.markdown("#### 資產與負債")
    a1, a2 = st.columns(2)
    with a1:
        st.markdown("**🟢 資產**")
        assets, total_assets = item_table(f"assets{suffix}", ASSET_ITEMS)
        st.success(f"**總資產：{money(total_assets)}**")
    with a2:
        st.markdown("**🔴 負債**")
        liabs, total_liab = item_table(f"liabs{suffix}", LIAB_ITEMS)
        st.error(f"**總負債：{money(total_liab)}**")
    st.metric("💎 家庭淨資產 (總資產 - 總負債)", money(total_assets - total_liab))

    liquid = assets.get("活期存款", 0) + assets.get("定期存款", 0) + assets.get("有價證券", 0)
    investable = assets.get("有價證券", 0) + assets.get("基金", 0) + assets.get("保單現價", 0) + assets.get("定期存款", 0)
    return {
        "total_income": total_income, "total_expense": total_expense, "net": net,
        "total_assets": total_assets, "total_liab": total_liab,
        "liquid_assets": liquid, "investable_assets": investable,
        "expense_breakdown": {"一般": e1, "理財": e2, "保障": e3, "其他": e4},
    }


def step3_cash_flow_and_assets():
    st.title("💵 Step 3：收支與資產負債表")
    st.markdown("請輸入家庭年度收支與目前資產負債狀況，系統會自動計算總額、淨結餘，並同步至財務健康看板。")

    tab_now, tab_adj = st.tabs(["📌 現況", "🛠️ 調整後建議（可選）"])
    with tab_now:
        result = _cashflow_block("")
        st.session_state.sf = result
    with tab_adj:
        st.caption("此頁可模擬「調整支出/資產配置後」的結果，供與現況比較，不影響現況資料。")
        result_adj = _cashflow_block("_adj")
        st.session_state.sf_adj = result_adj
        st.divider()
        c1, c2 = st.columns(2)
        c1.metric("現況年度淨結餘", money(st.session_state.sf["net"]))
        c2.metric("調整後年度淨結餘", money(result_adj["net"]),
                   delta=money(result_adj["net"] - st.session_state.sf["net"]))


# ==========================================================
# Step 4：財務健康看板
# ==========================================================
def step4_financial_health_dashboard():
    st.title("📊 Step 4：財務資料分析與四大帳戶")
    sf = st.session_state.get("sf")
    if not sf:
        st.warning("⚠️ 尚未輸入 Step 3 收支與資產負債資料，請先完成 Step 3。")
        return
    st.caption("以下數據自動取自 Step 3，無需重複輸入；如需調整請回到 Step 3 修改。")

    annual_income = sf["total_income"]
    annual_expense = sf["total_expense"]
    total_assets = sf["total_assets"]
    total_liab = sf["total_liab"]
    liquid_assets = sf["liquid_assets"]
    investable_assets = sf["investable_assets"]
    fixed_saving = sf["expense_breakdown"]["其他"]  # 含帳戶儲蓄等固定儲蓄項目的近似

    savings_rate = ((annual_income - annual_expense + 0) / annual_income * 100) if annual_income > 0 else 0
    debt_ratio = (total_liab / total_assets * 100) if total_assets > 0 else 0
    monthly_expense = annual_expense / 12 if annual_expense > 0 else 1
    emergency_months = liquid_assets / monthly_expense

    assumed_return = st.slider("假設生息資產年化投報率 (%)，用於估算財務自由度", 0.0, 10.0, 4.0, 0.5) / 100
    financial_freedom = (investable_assets * assumed_return) / annual_expense if annual_expense > 0 else 0

    st.subheader("💡 核心財務健康指標")
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        (st.success if savings_rate > 25 else st.error)(f"儲蓄率\n\n**{savings_rate:.1f}%**\n\n理想值 >25%")
    with col2:
        (st.success if debt_ratio <= 30 else st.warning)(f"負債比\n\n**{debt_ratio:.1f}%**\n\n理想值 ≤30%")
    with col3:
        if 3 <= emergency_months <= 6:
            st.success(f"生活週轉金\n\n**{emergency_months:.1f} 個月**\n\n理想值 3~6個月")
        elif emergency_months > 6:
            st.info(f"生活週轉金\n\n**{emergency_months:.1f} 個月**\n\n資金略顯閒置")
        else:
            st.error(f"生活週轉金\n\n**{emergency_months:.1f} 個月**\n\n準備不足")
    with col4:
        (st.success if financial_freedom > 1 else st.warning)(f"財務自由度\n\n**{financial_freedom:.2f}**\n\n理想值 >1.0")

    st.divider()
    st.subheader("🗂️ 四大帳戶總覽")
    ins_gap = st.session_state.get("ins_total_gap")
    b1, b2, b3, b4 = st.columns(4)
    with b1:
        st.markdown("**💵 現金類帳戶**")
        st.caption("準備3~6個月緊急預備金與靈活現金（財務安全）")
        st.metric("現況", money(liquid_assets))
    with b2:
        st.markdown("**🛡️ 保障類帳戶**")
        st.caption("壽險、意外險、重大疾病、醫療險等生老病死缺口（財務安全）")
        st.metric("保障缺口", money(ins_gap) if ins_gap is not None else "尚未計算")
        if ins_gap is None:
            st.caption("請至「專題 D：保險缺口分析」計算")
    with b3:
        st.markdown("**🏦 理財類帳戶**")
        st.caption("定存、年金、養老保險（教育與養老金來源，財務獨立）")
        st.metric("現況", money(st.session_state.get(f"assets", {}).get("保單現價", 0) +
                                 st.session_state.get(f"assets", {}).get("定期存款", 0)))
    with b4:
        st.markdown("**📈 投資類帳戶**")
        st.caption("股票、基金、債券等（創造非工資收入與財富，財務自由）")
        st.metric("現況", money(st.session_state.get(f"assets", {}).get("有價證券", 0) +
                                 st.session_state.get(f"assets", {}).get("基金", 0)))


# ==========================================================
# 專題 A：退休規劃
# ==========================================================
def module_retirement():
    st.title("🏖️ 專題 A：退休規劃試算")
    st.markdown("依「終值 (FV)」與「年金 (PMT)」公式，考量通膨率，精算退休時的真實資金缺口。")
    st.caption("通膨率、投報率等經濟假設已自Step 1 帶入，如需調整請回 Step 1 修改。")

    params_df = get_retire_params_df()
    df = get_family_df()
    cols = st.columns(len(params_df)) if len(params_df) else [st]

    total_gap_all = 0
    total_monthly_all = 0
    for i, row in params_df.iterrows():
        person = row["姓名"]
        person_row = df[df["姓名"] == person]
        cur_age = age_from_dob(person_row.iloc[0]["生日"], st.session_state.get("ref_date")) if len(person_row) else 35
        gender = person_row.iloc[0]["性別"] if len(person_row) else "男"
        icon = "👨" if gender == "男" else "👩"

        with cols[i]:
            st.subheader(f"{icon} {person}")
            retire_age = st.number_input("預計退休年齡", value=int(row["退休年齡"]), key=f"rt_age_{person}")
            retire_years = st.number_input("預計退休生活年期", value=int(row["養老年期"]), key=f"rt_years_{person}")
            work_years = max(0, retire_age - cur_age)
            inflation = row["通貨膨脹率(%)"] / 100
            invest_rate = row["工作期間投報率(%)"] / 100

            pv_expense = st.number_input("預計退休每月所需生活費 (現值/元)", value=30000, step=5000, key=f"rt_pv_{person}")
            prepared_pv = st.number_input("目前已準備退休金 (現值/元)", value=0, step=50000, key=f"rt_prep_{person}")
            social_ins = st.number_input("預估社會保險/其他已備資金 (退休時值/元)", value=0, step=100000, key=f"rt_social_{person}")
            st.divider()

            fv_expense = fv(pv_expense, inflation, work_years)
            total_needed = fv_expense * 12 * retire_years
            prepared_fv = fv(prepared_pv, invest_rate, work_years)
            gap = total_needed - prepared_fv - social_ins

            st.info(f"🔹 目前年齡：**{cur_age}** 歲，距退休尚有 **{work_years}** 年\n\n"
                    f"🔹 屆時每月所需金額（受通膨）：**{money(fv_expense)}**\n\n"
                    f"🔹 退休金應備總額：**{money(total_needed)}**\n\n"
                    f"🔹 已準備資金屆時價值：**{money(prepared_fv)}**")

            if gap > 0:
                annual_saving = pmt_for_target(invest_rate, work_years, gap)
                monthly_saving = annual_saving / 12
                st.error(f"🚨 **退休金總缺口：{money(gap)}**")
                st.metric("💡 每月應準備儲蓄金額", money(monthly_saving))
            else:
                gap = 0
                monthly_saving = 0
                st.success("🎉 **退休金無缺口！**")
            total_gap_all += gap
            total_monthly_all += monthly_saving

    st.session_state["ret_total_gap"] = total_gap_all
    st.session_state["ret_total_monthly"] = total_monthly_all


# ==========================================================
# 專題 B：教育金試算
# ==========================================================
def _education_level_block(prefix, label, default_years, default_choice):
    st.markdown(f"**{label}**")
    c1, c2, c3 = st.columns([2, 1, 1])
    with c1:
        choice = st.selectbox("學程", list(TUITION_PRESETS.keys()),
                               index=list(TUITION_PRESETS.keys()).index(default_choice), key=f"{prefix}_choice")
    with c2:
        years = st.number_input("年期", value=default_years, min_value=0, step=1, key=f"{prefix}_years")
    with c3:
        cost = st.number_input("費用/年", value=TUITION_PRESETS[choice], step=10000, key=f"{prefix}_cost")
    return years * cost


def module_education():
    st.title("🎓 專題 B：教育金試算")
    st.markdown("每位子女分別試算大學／碩士／博士三階段教育金需求，支援自訂學程費用。")

    df = get_family_df()
    children_df = df[df["關係"].isin(CHILD_RELATIONS)].reset_index(drop=True)
    ref_date = st.session_state.get("ref_date", datetime.date.today())

    if len(children_df) == 0:
        st.warning("尚未於 Step 1 新增子女資料。")
        return

    st.sidebar.markdown("### 📈 教育金環境參數")
    inflation_rate = st.sidebar.number_input("學費預估通膨率 (%)", value=3.0, step=0.5, key="edu_inf") / 100
    return_rate = st.sidebar.number_input("教育基金投資報酬率 (%)", value=5.0, step=0.5, key="edu_ret") / 100

    n = min(len(children_df), 4)
    cols = st.columns(n)
    total_gap_all = 0
    total_monthly_all = 0
    for i in range(n):
        c = children_df.iloc[i]
        icon = "👦" if c["性別"] == "男" else "👧"
        cur_age = age_from_dob(c["生日"], ref_date)
        with cols[i]:
            st.subheader(f"{icon} {c['姓名']}")
            current_age = st.number_input("目前年齡", value=int(cur_age), step=1, key=f"edu_age_{i}")
            college_age = st.number_input("預計就讀大學年齡", value=18, step=1, key=f"edu_cage_{i}")
            prepared = st.number_input("目前已準備教育金", value=0, step=50000, key=f"edu_prep_{i}")
            years_to_prep = max(0, college_age - current_age)

            pv_total = 0
            pv_total += _education_level_block(f"edu_{i}_u", "大學", 4, "國內私立大學")
            pv_total += _education_level_block(f"edu_{i}_m", "碩士", 2, "國外研究所")
            pv_total += _education_level_block(f"edu_{i}_p", "博士", 0, "不選擇")
            st.divider()

            if years_to_prep > 0:
                total_fv = fv(pv_total, inflation_rate, years_to_prep)
                gap = total_fv - prepared
                st.info(f"🔹 距上大學還有：**{years_to_prep} 年**\n\n🔹 屆時學費總額（受通膨）：**{money(total_fv)}**")
                if gap > 0:
                    annual_saving = pmt_for_target(return_rate, years_to_prep, gap)
                    monthly_saving = annual_saving / 12
                    st.error(f"🚨 **教育金總缺口：{money(gap)}**")
                    st.metric("💡 每月應存金額", money(monthly_saving))
                else:
                    gap = 0
                    monthly_saving = 0
                    st.success("🎉 **資金已充足！**")
                total_gap_all += gap
                total_monthly_all += monthly_saving
            else:
                st.warning("⚠️ 已達或超過就讀年齡，準備期不足。")

    st.session_state["edu_total_gap"] = total_gap_all
    st.session_state["edu_total_monthly"] = total_monthly_all


# ==========================================================
# 專題 C：購屋與購車試算（A/B/C 三計畫比較）
# ==========================================================
def _big_purchase_plan(prefix, plan_label, default_price, default_years,
                        default_prepared, default_old_asset, is_house=True):
    st.markdown(f"##### {plan_label}")
    years = st.number_input("預計時間 (年)", value=default_years, step=1, key=f"{prefix}_y")
    price_pv = st.number_input("目標市價 (現值)", value=default_price, step=100000, key=f"{prefix}_price")
    prepared_pv = st.number_input("目前已備資金 (現值)", value=default_prepared, step=50000, key=f"{prefix}_prep")
    old_pv = st.number_input("舊資產折抵現值 (舊換新可填)", value=default_old_asset, step=50000, key=f"{prefix}_old")
    loan_ratio = st.slider("預計貸款成數 (%)", 0, 100, 80 if is_house else 0, 5, key=f"{prefix}_lr") / 100
    loan_years = st.number_input("貸款年期", value=30 if is_house else 5, step=1, key=f"{prefix}_ly")
    loan_rate = st.number_input("貸款利率 (%)", value=2.1 if is_house else 3.5, step=0.1, key=f"{prefix}_lrate") / 100
    return_rate = st.session_state.get(f"{prefix}_ret_rate", 0.06)

    price_fv = fv(price_pv, st.session_state.get(f"{prefix}_infl", 0.03), years)
    prepared_fv = fv(prepared_pv, return_rate, years)
    old_fv = fv(old_pv, st.session_state.get(f"{prefix}_infl", 0.03), years) if is_house else old_pv

    down_needed = price_fv * (1 - loan_ratio)
    gap = down_needed - prepared_fv - old_fv
    loan_amount = price_fv * loan_ratio
    monthly_payment = -npf.pmt(loan_rate / 12, loan_years * 12, loan_amount, 0) if loan_years > 0 and loan_rate > 0 else 0

    st.info(f"🔹 {years} 年後市價（受通膨）：**{money(price_fv)}**\n\n"
            f"🔹 屆時需支付款項：**{money(down_needed)}**\n\n"
            f"🔹 已備資金屆時價值：**{money(prepared_fv)}**")
    monthly_saving = 0
    if gap > 0:
        st.error(f"🚨 資金缺口：**{money(gap)}**")
        if years > 0:
            monthly_saving = pmt_for_target(return_rate, years, gap) / 12
            st.metric("💡 每月需額外儲蓄", money(monthly_saving))
    else:
        gap = 0
        st.success(f"🎉 資金充足！預計還有 {money(abs(down_needed - prepared_fv - old_fv))} 盈餘。")
    st.warning(f"🏦 貸款總額：**{money(loan_amount)}**")
    st.metric("💸 每月還款金額", money(monthly_payment))

    st.session_state[f"{prefix}_result"] = {
        "label": plan_label, "gap": gap, "monthly": monthly_saving,
        "loan_payment": monthly_payment, "years": years,
    }
    return gap, monthly_payment


def module_house_and_car():
    st.title("🏠🚗 專題 C：購屋與購車試算")
    st.markdown("同時比較 A / B / C 三種計畫的頭期款缺口與每月還款負擔。")

    tab_house, tab_car = st.tabs(["🏠 購屋規劃", "🚗 購(換)車規劃"])
    with tab_house:
        inflation_rate = st.sidebar.number_input("房價預估通膨率 (%)", value=3.0, step=0.5, key="house_infl") / 100
        return_rate = st.sidebar.number_input("自備款投資報酬率 (%)", value=6.0, step=0.5, key="house_ret") / 100
        for p in ["hA", "hB", "hC"]:
            st.session_state[f"{p}_infl"] = inflation_rate
            st.session_state[f"{p}_ret_rate"] = return_rate
        cols = st.columns(3)
        defaults = [("A計畫(舊換新)", 10000000, 5, 2500000, 0),
                    ("B計畫(新購)", 12000000, 5, 2500000, 0),
                    ("C計畫(準備期長)", 10000000, 8, 1500000, 0)]
        for col, prefix, (label, price, yrs, prep, old) in zip(cols, ["hA", "hB", "hC"], defaults):
            with col:
                _big_purchase_plan(prefix, label, price, yrs, prep, old, is_house=True)

    with tab_car:
        inflation_rate_c = st.sidebar.number_input("車價預估通膨率 (%)", value=3.0, step=0.5, key="car_infl") / 100
        return_rate_c = st.sidebar.number_input("自備款投資報酬率 (%) ", value=6.0, step=0.5, key="car_ret") / 100
        for p in ["cA", "cB", "cC"]:
            st.session_state[f"{p}_infl"] = inflation_rate_c
            st.session_state[f"{p}_ret_rate"] = return_rate_c
        cols = st.columns(3)
        defaults = [("計畫A(舊換新)", 900000, 2, 900000, 0),
                    ("計畫B(新購車)", 1000000, 3, 500000, 0),
                    ("計畫C(晚點買)", 900000, 5, 900000, 0)]
        for col, prefix, (label, price, yrs, prep, old) in zip(cols, ["cA", "cB", "cC"], defaults):
            with col:
                _big_purchase_plan(prefix, label, price, yrs, prep, old, is_house=False)


# ==========================================================
# 專題 D：保險缺口分析
# ==========================================================
def module_insurance():
    st.title("🛡️ 專題 D：保險缺口分析")

    names = get_person_names()
    name = st.selectbox("選擇分析對象", names, key="ins_person")

    st.subheader("一、壽險保障分析")
    c1, c2 = st.columns(2)
    with c1:
        st.markdown("**應備金額**")
        l_living_yr = st.number_input("家人生活費用 (每年)", 0, step=10000, key="l_living_yr")
        l_living_n = st.number_input("需照顧年期", 0, step=1, value=10, key="l_living_n")
        l_par = st.number_input("本人父母孝養金 (總額)", 0, step=10000, key="l_par")
        l_mort = st.number_input("房貸餘額", 0, step=100000, key="l_mort")
        l_oth = st.number_input("其他貸款餘額", 0, step=10000, key="l_oth")
        l_fin = st.number_input("最後費用（喪葬等）", 0, step=10000, key="l_fin")
        total_l_need = l_living_yr * l_living_n + l_par + l_mort + l_oth + l_fin
        st.metric("應備總額", money(total_l_need))
    with c2:
        st.markdown("**已備保額**")
        l_term = st.number_input("定期壽險保額", 0, step=100000, key="l_term")
        l_whole = st.number_input("終身壽險保額", 0, step=100000, key="l_whole")
        l_labor = st.number_input("勞保／國保身故給付", 0, step=100000, key="l_labor")
        l_gov = st.number_input("軍公教保額", 0, step=100000, key="l_gov")
        total_l_exist = l_term + l_whole + l_labor + l_gov
        life_gap = max(0, total_l_need - total_l_exist)
        st.metric("壽險缺口", money(life_gap))

    st.divider()
    st.subheader("二、意外險保障分析")
    c3, c4 = st.columns(2)
    with c3:
        st.markdown("**應備金額**")
        a_dis = st.number_input("生活費用(殘扶) (每年)", 0, step=10000, key="a_dis")
        a_liv = st.number_input("家人生活費用 (每年)", 0, step=10000, key="a_liv")
        a_par = st.number_input("本人父母孝養金 (總額)", 0, step=10000, key="a_par")
        a_mort = st.number_input("房貸餘額", 0, step=100000, key="a_mort")
        a_oth = st.number_input("其他貸款", 0, step=10000, key="a_oth")
        total_a_need = a_dis + a_liv + a_par + a_mort + a_oth
        st.metric("應備總額", money(total_a_need))
    with c4:
        st.markdown("**已備保額**")
        a_grp = st.number_input("團體意外險保額", 0, step=100000, key="a_grp")
        a_gov = st.number_input("軍公教保額", 0, step=100000, key="a_gov2")
        a_com = st.number_input("商業保險保額", 0, step=100000, key="a_com")
        total_a_exist = a_grp + a_gov + a_com
        acc_gap = max(0, total_a_need - total_a_exist)
        st.metric("意外險缺口", money(acc_gap))

    st.divider()
    st.subheader("三、住院日額保障分析")
    people_cols = ["本人", "配偶", "子女1", "子女2"]
    if "hosp_need_df" not in st.session_state:
        st.session_state.hosp_need_df = pd.DataFrame({
            "項目": ["薪資補償", "看護費用", "病房差額"],
            **{p: [0, 0, 0] for p in people_cols}
        })
    st.markdown("**應備日額需求（元/日）**")
    need_edit = st.data_editor(st.session_state.hosp_need_df, hide_index=True, use_container_width=True,
                                key="hosp_need_editor", disabled=["項目"])
    st.session_state.hosp_need_df = need_edit
    need_total = {p: int(need_edit[p].sum()) for p in people_cols}
    st.dataframe(pd.DataFrame([need_total], index=["應備日額總計"]), use_container_width=True)

    d1, d2 = st.columns(2)
    with d1:
        d_whole = st.number_input("終身日額", 0, step=500, key="d_whole")
        d_term = st.number_input("定期日額", 0, step=500, key="d_term")
    with d2:
        d_real = st.number_input("實支實付（換算日額）", 0, step=500, key="d_real")
    total_d_exist = d_whole + d_term + d_real
    hosp_gap = max(0, need_total.get("本人", 0) - total_d_exist)
    st.metric("住院日額缺口（本人）", f"{hosp_gap:,.0f} 元/日")

    st.session_state["ins_total_gap"] = life_gap + acc_gap


# ==========================================================
# 資料存檔與讀取（下載/上傳備份，解決關閉分頁資料消失的問題）
# ==========================================================
# 記錄哪些 DataFrame 欄位是日期型別，匯出/匯入時需要特別轉換
DATE_COLUMNS_BY_DF = {"family_df": ["生日"]}


def _export_all_data():
    """掃描目前 session_state，自動打包所有『使用者資料』(不含 Streamlit 內部元件狀態)。
    採用自動掃描而非手動列出每個欄位，這樣以後新增頁面/欄位也不用再回來維護這個函式。"""
    dataframes, values = {}, {}
    for k, v in list(st.session_state.items()):
        if k.endswith("_editor") or k == "backup_uploader":
            continue  # Streamlit 元件自身的內部狀態，不屬於使用者資料，跳過
        if isinstance(v, pd.DataFrame):
            df = v.copy()
            for col in df.columns:
                if df[col].dtype == object:
                    df[col] = df[col].apply(
                        lambda x: x.isoformat() if isinstance(x, (datetime.date, datetime.datetime)) else x)
            dataframes[k] = df.to_dict(orient="records")
        elif isinstance(v, (datetime.date, datetime.datetime)):
            values[k] = {"__date__": v.isoformat()}
        else:
            try:
                json.dumps(v)
                values[k] = v
            except TypeError:
                continue  # 無法序列化的內容（例如上傳元件本身）直接跳過
    return {"exported_at": datetime.datetime.now().isoformat(), "dataframes": dataframes, "values": values}


def _import_all_data(uploaded_file):
    uploaded_file.seek(0)
    data = json.load(uploaded_file)
    for k, records in data.get("dataframes", {}).items():
        df = pd.DataFrame(records)
        for col in DATE_COLUMNS_BY_DF.get(k, []):
            if col in df.columns:
                df[col] = pd.to_datetime(df[col]).dt.date
        st.session_state[k] = df
    for k, v in data.get("values", {}).items():
        if isinstance(v, dict) and "__date__" in v:
            st.session_state[k] = datetime.date.fromisoformat(v["__date__"])
        else:
            st.session_state[k] = v
    # 清掉表格編輯元件的舊快取，強迫它們用剛匯入的新資料重新繪製
    for k in list(st.session_state.keys()):
        if k.endswith("_editor"):
            del st.session_state[k]


def module_data_management():
    st.title("💾 資料存檔與讀取")
    st.info("💡 本系統的資料只存在您目前瀏覽器的工作階段中，**關閉分頁或重新整理就會消失**。"
            "建議每次告一段落時先下載備份檔；下次要繼續分析，重新上傳同一份檔案即可無縫接軌。")

    col1, col2 = st.columns(2)
    with col1:
        st.subheader("⬇️ 匯出備份")
        client_name = ""
        fam = st.session_state.get("family_df")
        if fam is not None and len(fam):
            self_row = fam[fam["關係"] == "本人"]
            if len(self_row):
                client_name = str(self_row.iloc[0]["姓名"])
        fname = f"財務規劃備份_{client_name or '客戶'}_{datetime.date.today()}.json"

        export_data = _export_all_data()
        json_bytes = json.dumps(export_data, ensure_ascii=False, indent=2).encode("utf-8")
        st.download_button("📥 下載備份檔 (.json)", data=json_bytes, file_name=fname,
                            mime="application/json", type="primary", use_container_width=True)
        st.caption("涵蓋：家庭成員、財務目標、收支資產負債表（含調整後）、退休參數，"
                   "以及各專題（退休/教育金/購屋購車/保險）已輸入的數字與顧問建議。")

    with col2:
        st.subheader("⬆️ 匯入備份")
        uploaded = st.file_uploader("選擇先前下載的備份檔 (.json)", type=["json"], key="backup_uploader")
        if uploaded is not None:
            sig = f"{uploaded.name}_{uploaded.size}"
            if st.session_state.get("_last_import_sig") != sig:
                try:
                    _import_all_data(uploaded)
                    st.session_state["_last_import_sig"] = sig
                    st.success("✅ 資料讀取成功！請至左側選單查看各項分析結果。")
                    st.rerun()
                except Exception as e:
                    st.error(f"❌ 檔案格式錯誤或內容不符，請確認上傳的是本系統匯出的 .json 備份檔。（{e}）")
            else:
                st.success("✅ 這份備份檔的資料已經讀取完成，可切換至左側選單查看。")
        st.caption("⚠️ 匯入會覆蓋目前畫面上的資料，請先確認不需要目前的內容再上傳。")


# ==========================================================
# 客戶總覽報告（重點彙整，適合列印/分享）
# ==========================================================
def _health_metric_configs(sf):
    """計算四大健康指標，並附上繪製「指標尺」所需的座標與狀態。"""
    annual_income = sf["total_income"]
    annual_expense = sf["total_expense"]
    total_assets = sf["total_assets"]
    total_liab = sf["total_liab"]
    liquid = sf["liquid_assets"]
    investable = sf["investable_assets"]

    savings_rate = ((annual_income - annual_expense) / annual_income * 100) if annual_income > 0 else 0
    debt_ratio = (total_liab / total_assets * 100) if total_assets > 0 else 0
    monthly_expense = annual_expense / 12 if annual_expense > 0 else 1
    emergency_months = liquid / monthly_expense
    financial_freedom = (investable * 0.04) / annual_expense if annual_expense > 0 else 0

    def pct_of(v, lo, hi):
        return max(0.0, min(100.0, (v - lo) / (hi - lo) * 100))

    configs = [
        {"label": "儲蓄率", "value_str": f"{savings_rate:.1f}%", "ideal_text": "＞25%",
         "pct": pct_of(savings_rate, 0, 50), "ideal_lo": pct_of(25, 0, 50), "ideal_hi": 100,
         "status": "good" if savings_rate > 25 else "warn"},
        {"label": "負債比", "value_str": f"{debt_ratio:.1f}%", "ideal_text": "≤30%",
         "pct": pct_of(debt_ratio, 0, 100), "ideal_lo": 0, "ideal_hi": pct_of(30, 0, 100),
         "status": "good" if debt_ratio <= 30 else "warn"},
        {"label": "生活週轉金", "value_str": f"{emergency_months:.1f} 個月", "ideal_text": "3~6個月",
         "pct": pct_of(emergency_months, 0, 12), "ideal_lo": pct_of(3, 0, 12), "ideal_hi": pct_of(6, 0, 12),
         "status": "good" if 3 <= emergency_months <= 6 else "warn"},
        {"label": "財務自由度", "value_str": f"{financial_freedom:.2f}", "ideal_text": "＞1.0",
         "pct": pct_of(financial_freedom, 0, 2), "ideal_lo": pct_of(1, 0, 2), "ideal_hi": 100,
         "status": "good" if financial_freedom > 1 else "warn"},
    ]
    return configs


def _pick_plan_result(label, keys):
    options = {k: st.session_state.get(f"{k}_result") for k in keys if st.session_state.get(f"{k}_result")}
    if not options:
        return None
    pick = st.selectbox(label, list(options.keys()), format_func=lambda k: options[k]["label"], key=f"summary_pick_{label}")
    return options[pick]


def build_summary_text(fam_display, sf, health_configs, goal_rows, advisor_note):
    lines = ["家庭財務健康摘要報告", f"報告日期：{st.session_state.get('ref_date', datetime.date.today())}", ""]
    lines.append("【家庭成員】")
    for _, r in fam_display.iterrows():
        lines.append(f"- {r['關係']} {r['姓名']}（{r['性別']}，{r['年齡']}歲）")
    lines.append("")
    if sf:
        lines.append("【財務現況】")
        lines.append(f"年度總收入：{money(sf['total_income'])}")
        lines.append(f"年度總支出：{money(sf['total_expense'])}")
        lines.append(f"年度淨結餘：{money(sf['net'])}")
        lines.append(f"家庭淨資產：{money(sf['total_assets'] - sf['total_liab'])}")
        lines.append("")
        lines.append("【財務健康指標】")
        for c in health_configs:
            status_txt = "良好" if c["status"] == "good" else "需注意"
            lines.append(f"- {c['label']}：{c['value_str']}（理想值 {c['ideal_text']}）{status_txt}")
        lines.append("")
    if goal_rows:
        lines.append("【財務目標缺口】")
        for row in goal_rows:
            lines.append(f"- {row[0]}：缺口 {row[1]}，建議每月投入 {row[2]}")
        lines.append("")
    if advisor_note:
        lines.append("【顧問建議】")
        lines.append(advisor_note)
    return "\n".join(lines)


_REPORT_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Noto+Serif+TC:wght@600;700&family=Noto+Sans+TC:wght@400;500;700&family=IBM+Plex+Mono:wght@500;600&display=swap');
@media print { section[data-testid="stSidebar"], .stSidebar { display:none !important; } }

.fp-wrap { font-family:'Noto Sans TC', sans-serif; color:#1A2233; }
.fp-banner{
  background:linear-gradient(135deg,#14213D 0%,#1F3560 100%);
  border-bottom:3px solid #A9832B; border-radius:10px;
  padding:28px 32px; margin-bottom:28px;
}
.fp-eyebrow{ font-family:'IBM Plex Mono',monospace; font-size:11px; letter-spacing:.18em;
  color:#C9A85C; text-transform:uppercase; margin-bottom:8px; }
.fp-banner-title{ font-family:'Noto Serif TC',serif; font-weight:700; font-size:26px; color:#FFFFFF; margin-bottom:8px; }
.fp-banner-meta{ font-family:'IBM Plex Mono',monospace; font-size:12.5px; color:#B7C2D6; }

.fp-section-eyebrow{ display:flex; align-items:center; gap:10px; margin:8px 0 14px 0; }
.fp-section-eyebrow .line{ flex:0 0 3px; align-self:stretch; background:#A9832B; border-radius:2px; }
.fp-section-eyebrow .txt{ font-family:'Noto Serif TC',serif; font-weight:700; font-size:18px; color:#14213D; }

.fp-chiprow{ display:flex; flex-wrap:wrap; gap:10px; margin-bottom:6px; }
.fp-chip{ display:flex; align-items:center; gap:10px; background:#FFFFFF; border:1px solid #E4E7EC;
  border-radius:10px; padding:10px 14px; min-width:150px; }
.fp-chip-icon{ font-size:20px; }
.fp-chip-name{ font-weight:700; font-size:14px; }
.fp-chip-meta{ font-size:12px; color:#5B6472; font-family:'IBM Plex Mono',monospace; }

.fp-statrow{ display:grid; grid-template-columns:repeat(4,1fr); gap:14px; margin-bottom:8px; }
.fp-stat{ background:#FFFFFF; border:1px solid #E4E7EC; border-left:4px solid #A9832B;
  border-radius:8px; padding:16px 18px; }
.fp-stat-label{ font-size:12.5px; color:#5B6472; margin-bottom:6px; }
.fp-stat-value{ font-family:'IBM Plex Mono',monospace; font-weight:600; font-size:22px; color:#14213D; }

.fp-gaugerow{ display:grid; grid-template-columns:repeat(4,1fr); gap:14px; margin-bottom:8px; }
.fp-gauge-card{ background:#FFFFFF; border:1px solid #E4E7EC; border-radius:8px; padding:16px 18px; }
.fp-gauge-top{ display:flex; justify-content:space-between; align-items:center; margin-bottom:6px; }
.fp-gauge-label{ font-size:13px; font-weight:700; color:#14213D; }
.fp-gauge-value{ font-family:'IBM Plex Mono',monospace; font-weight:600; font-size:20px; margin-bottom:10px; }
.fp-gauge-track{ position:relative; height:8px; background:#EDEFF2; border-radius:4px; margin-bottom:6px; }
.fp-gauge-ideal{ position:absolute; top:0; bottom:0; background:rgba(169,131,43,.28); border-radius:4px; }
.fp-gauge-marker{ position:absolute; top:-4px; width:16px; height:16px; border-radius:50%;
  transform:translateX(-50%); border:2px solid #fff; box-shadow:0 0 0 1px rgba(0,0,0,.12); }
.fp-marker-good{ background:#2F7A4C; }
.fp-marker-warn{ background:#B5790A; }
.fp-gauge-scale{ font-size:11px; color:#5B6472; font-family:'IBM Plex Mono',monospace; }

.fp-badge{ display:inline-block; font-size:11px; font-weight:700; padding:3px 9px; border-radius:99px; }
.fp-badge-good{ background:#E6F2EA; color:#2F7A4C; }
.fp-badge-warn{ background:#FBEEDD; color:#B5790A; }

.fp-ledger{ background:#FFFFFF; border:1px solid #E4E7EC; border-radius:8px; overflow:hidden; margin-bottom:8px; }
.fp-ledger-head, .fp-ledger-row{ display:grid; grid-template-columns:2fr 1.1fr 1.3fr; gap:10px; padding:11px 16px; align-items:center; }
.fp-ledger-head{ background:#F7F7F5; font-size:12px; color:#5B6472; font-weight:700; }
.fp-ledger-row{ border-top:1px solid #F0F1F3; border-left:4px solid transparent; font-size:13.5px; }
.fp-ledger-row.warn{ border-left-color:#B5790A; }
.fp-ledger-row.good{ border-left-color:#2F7A4C; }
.fp-ledger-name{ font-weight:700; color:#14213D; }
.fp-ledger-gap{ font-family:'IBM Plex Mono',monospace; }
.fp-ledger-monthly{ font-family:'IBM Plex Mono',monospace; color:#5B6472; }

.fp-note-card{ background:#FFFDF7; border:1px solid #EFE3C6; border-left:4px solid #A9832B;
  border-radius:8px; padding:4px 6px 2px 6px; margin-bottom:10px; }

.fp-footer{ font-size:11.5px; color:#98A2B3; text-align:center; margin-top:18px; padding-top:12px; border-top:1px solid #E4E7EC; }
</style>
"""


def _badge(status):
    return f'<span class="fp-badge fp-badge-{status}">{"良好" if status == "good" else "需注意"}</span>'


def summary_report_page():
    st.markdown(_REPORT_CSS, unsafe_allow_html=True)
    st.markdown('<div class="fp-wrap">', unsafe_allow_html=True)

    ref_date = st.session_state.get("ref_date", datetime.date.today())
    firm = st.session_state.get("firm", "")
    title = st.session_state.get("title", "")
    df = get_family_df()
    fam_display = df.copy()
    fam_display["年齡"] = fam_display["生日"].apply(lambda d: age_from_dob(d, ref_date))
    self_row = fam_display[fam_display["關係"] == "本人"]
    client_name = self_row.iloc[0]["姓名"] if len(self_row) else "客戶"

    st.markdown(f"""
    <div class="fp-banner">
      <div class="fp-eyebrow">FINANCIAL HEALTH REPORT</div>
      <div class="fp-banner-title">{client_name} 家庭・財務健康摘要報告</div>
      <div class="fp-banner-meta">報告日期　{ref_date.strftime('%Y-%m-%d')}　　{(firm + ' ' + title) if (firm or title) else ''}</div>
    </div>
    """, unsafe_allow_html=True)

    st.markdown('<div class="fp-section-eyebrow"><div class="line"></div><div class="txt">👥 家庭成員</div></div>', unsafe_allow_html=True)
    icon_map = {"男": "👨", "女": "👩"}
    chips = "".join(
        f'<div class="fp-chip"><div class="fp-chip-icon">{icon_map.get(r["性別"], "🧑")}</div>'
        f'<div><div class="fp-chip-name">{r["姓名"]}</div><div class="fp-chip-meta">{r["關係"]}・{r["年齡"]}歲</div></div></div>'
        for _, r in fam_display.iterrows()
    )
    st.markdown(f'<div class="fp-chiprow">{chips}</div>', unsafe_allow_html=True)

    sf = st.session_state.get("sf")
    health_configs = []
    if sf:
        st.markdown('<div class="fp-section-eyebrow" style="margin-top:26px;"><div class="line"></div><div class="txt">💰 財務現況總覽</div></div>', unsafe_allow_html=True)
        stats = [
            ("年度總收入", money(sf["total_income"])), ("年度總支出", money(sf["total_expense"])),
            ("年度淨結餘", money(sf["net"])), ("家庭淨資產", money(sf["total_assets"] - sf["total_liab"])),
        ]
        stat_html = "".join(f'<div class="fp-stat"><div class="fp-stat-label">{lbl}</div><div class="fp-stat-value">{val}</div></div>' for lbl, val in stats)
        st.markdown(f'<div class="fp-statrow">{stat_html}</div>', unsafe_allow_html=True)

        st.markdown('<div class="fp-section-eyebrow" style="margin-top:26px;"><div class="line"></div><div class="txt">📐 財務健康指標尺</div></div>', unsafe_allow_html=True)
        health_configs = _health_metric_configs(sf)
        gauge_html = "".join(f"""
        <div class="fp-gauge-card">
          <div class="fp-gauge-top"><span class="fp-gauge-label">{c['label']}</span>{_badge(c['status'])}</div>
          <div class="fp-gauge-value">{c['value_str']}</div>
          <div class="fp-gauge-track">
            <div class="fp-gauge-ideal" style="left:{c['ideal_lo']}%;width:{max(0, c['ideal_hi'] - c['ideal_lo'])}%;"></div>
            <div class="fp-gauge-marker fp-marker-{c['status']}" style="left:{c['pct']}%;"></div>
          </div>
          <div class="fp-gauge-scale">理想區間　{c['ideal_text']}</div>
        </div>""" for c in health_configs)
        st.markdown(f'<div class="fp-gaugerow">{gauge_html}</div>', unsafe_allow_html=True)
    else:
        st.info("尚未輸入 Step 3 收支與資產負債資料。")

    st.markdown('<div class="fp-section-eyebrow" style="margin-top:26px;"><div class="line"></div><div class="txt">🎯 各項財務目標缺口彙總</div></div>', unsafe_allow_html=True)
    goal_rows = []
    ret_gap, ret_monthly = st.session_state.get("ret_total_gap"), st.session_state.get("ret_total_monthly")
    if ret_gap is not None:
        goal_rows.append(["退休規劃", money(ret_gap), f"{money(ret_monthly)}/月" if ret_monthly else "-"])
    edu_gap, edu_monthly = st.session_state.get("edu_total_gap"), st.session_state.get("edu_total_monthly")
    if edu_gap is not None:
        goal_rows.append(["子女教育金", money(edu_gap), f"{money(edu_monthly)}/月" if edu_monthly else "-"])
    ins_gap = st.session_state.get("ins_total_gap")
    if ins_gap is not None:
        goal_rows.append(["保障缺口（壽險＋意外險）", money(ins_gap), "依缺口規劃保費" if ins_gap > 0 else "-"])

    house_r = _pick_plan_result("選擇要顯示的購屋計畫", ["hA", "hB", "hC"])
    if house_r:
        goal_rows.append([f"購屋（{house_r['label']}）", money(house_r["gap"]),
                           f"{money(house_r['monthly'])}/月" if house_r["gap"] > 0 else "資金充足"])
    car_r = _pick_plan_result("選擇要顯示的購車計畫", ["cA", "cB", "cC"])
    if car_r:
        goal_rows.append([f"購車（{car_r['label']}）", money(car_r["gap"]),
                           f"{money(car_r['monthly'])}/月" if car_r["gap"] > 0 else "資金充足"])

    if goal_rows:
        rows_html = "".join(
            f'<div class="fp-ledger-row {"good" if ("充足" in str(row[2]) or row[1] in ("$0","-")) else "warn"}">'
            f'<div class="fp-ledger-name">{row[0]}</div><div class="fp-ledger-gap">{row[1]}</div>'
            f'<div class="fp-ledger-monthly">{row[2]}</div></div>' for row in goal_rows
        )
        st.markdown(f"""
        <div class="fp-ledger">
          <div class="fp-ledger-head"><div>財務目標</div><div>資金缺口</div><div>每月建議投入</div></div>
          {rows_html}
        </div>""", unsafe_allow_html=True)
    else:
        st.info("尚未計算任何專題試算，請先至左側「專題 A~D」完成試算後再回到本頁。")

    st.markdown('<div class="fp-section-eyebrow" style="margin-top:26px;"><div class="line"></div><div class="txt">📝 顧問建議</div></div>', unsafe_allow_html=True)
    st.markdown('<div class="fp-note-card">', unsafe_allow_html=True)
    advisor_note = st.text_area("給客戶的建議摘要（可自行編輯，會保留在本次工作階段）",
                                 value=st.session_state.get("advisor_note", ""), height=140,
                                 key="advisor_note", label_visibility="collapsed")
    st.markdown('</div>', unsafe_allow_html=True)

    c1, c2 = st.columns(2)
    with c1:
        st.caption("💡 輸出 PDF：使用瀏覽器「列印」（Ctrl/Cmd+P）→「另存為PDF」，本頁已針對列印優化，會自動隱藏側邊選單。")
    with c2:
        summary_text = build_summary_text(fam_display, sf, health_configs, goal_rows, advisor_note)
        st.download_button("⬇️ 下載文字摘要 (.txt)", data=summary_text.encode("utf-8"),
                            file_name=f"財務健康摘要_{ref_date}.txt", mime="text/plain")

    st.markdown(f'<div class="fp-footer">本報告由系統自動彙整試算結果，僅供財務規劃參考，實際保單/貸款/投資條件請以正式文件為準。{(firm) if firm else ""}</div>', unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)


# ==========================================================
# 側邊欄導航
# ==========================================================
def main():
    st.sidebar.title("💰 財務規劃系統")
    st.sidebar.markdown("---")

    menu_selection = st.sidebar.radio(
        "請選擇操作模組：",
        [
            "💾 資料存檔與讀取",
            "-----------------------",
            "1. 基本資料輸入 (Step 1)",
            "2. 財務目標設定 (Step 2)",
            "3. 收支與資產負債 (Step 3)",
            "4. 財務健康看板 (Step 4)",
            "-----------------------",
            "專題 A：退休規劃",
            "專題 B：教育金試算",
            "專題 C：購屋與購車",
            "專題 D：保險缺口分析",
            "-----------------------",
            "📋 客戶總覽報告",
        ],
    )

    st.sidebar.markdown("---")
    st.sidebar.caption("版本：2026 財務試算網頁互動版 v2.0")

    pages = {
        "💾 資料存檔與讀取": module_data_management,
        "1. 基本資料輸入 (Step 1)": step1_basic_info,
        "2. 財務目標設定 (Step 2)": step2_financial_goals,
        "3. 收支與資產負債 (Step 3)": step3_cash_flow_and_assets,
        "4. 財務健康看板 (Step 4)": step4_financial_health_dashboard,
        "專題 A：退休規劃": module_retirement,
        "專題 B：教育金試算": module_education,
        "專題 C：購屋與購車": module_house_and_car,
        "專題 D：保險缺口分析": module_insurance,
        "📋 客戶總覽報告": summary_report_page,
    }
    fn = pages.get(menu_selection)
    if fn:
        fn()


if __name__ == "__main__":
    main()
