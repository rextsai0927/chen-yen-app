import streamlit as st
import pandas as pd

# 設定網頁標題
st.set_page_config(page_title="商品自動分組系統", layout="wide")
st.title("📦 商品積分自動分組工具")

# --- 模擬資料庫 (你可以自行修改或讀取外部檔) ---
# 實際應用時，建議手動輸入的部分從一個 Master Excel 讀取品項清單
mock_db = {
    "電子類": {"手機": 5000, "平板": 3000, "耳機": 1200},
    "生活類": {"水杯": 200, "毛巾": 100, "抱枕": 450},
    "代碼搜尋": {"A001": 5000, "B002": 3000, "C003": 1200}  # 支援貨號直接輸入
}


# --- 核心演算法 ---
def run_grouping(data_list, target):
    """
    data_list: [{'name': 名字, 'value': 分數}, ...]
    """
    items = sorted(data_list, key=lambda x: x['value'], reverse=True)
    groups = []

    while items:
        current_group = []
        current_sum = 0
        first_item = items.pop(0)
        current_group.append(first_item)
        current_sum += first_item['value']

        while current_sum < target and items:
            best_idx = -1
            min_diff = float('inf')
            for i, item in enumerate(items):
                diff = abs((current_sum + item['value']) - target)
                if diff < min_diff:
                    min_diff = diff
                    best_idx = i

            best_item = items.pop(best_idx)
            current_group.append(best_item)
            current_sum += best_item['value']
            if current_sum >= target: break

        formula = " + ".join([f"{i['name']}({i['value']})" for i in current_group])
        groups.append({"明細": formula, "總計": current_sum, "差距": current_sum - target})
    return pd.DataFrame(groups)


# --- 介面設計 ---
tab_upload, tab_manual = st.tabs(["📤 上傳 Excel 檔", "✍️ 自行輸入項目"])

final_list = []  # 存放準備計算的清單

# 1. 上傳模式
with tab_upload:
    uploaded_file = st.file_uploader("請拖入 Excel 檔案", type=["xlsx"])
    if uploaded_file:
        # 根據你的描述對應欄位 (B:貨號, C:品名, D:數量, E:積分)
        df_excel = pd.read_excel(uploaded_file)
        st.write("檔案預覽：")
        st.dataframe(df_excel.head())

        # 轉換為計算格式
        for _, row in df_excel.iterrows():
            count = int(row.iloc[3]) if not pd.isna(row.iloc[3]) else 0
            for _ in range(count):
                final_list.append({'name': str(row.iloc[2]), 'value': float(row.iloc[4])})

# 2. 手動輸入模式
with tab_manual:
    if 'manual_items' not in st.session_state:
        st.session_state.manual_items = []

    col1, col2 = st.columns(2)
    with col1:
        st.subheader("方式 A：選單選擇")
        cat = st.selectbox("1. 選擇大項", list(mock_db.keys()))
        item = st.selectbox("2. 選擇品項", list(mock_db[cat].keys()))
        qty = st.number_input("3. 數量", min_value=1, value=1, key="qty_a")
        if st.button("加入清單 (選單)"):
            for _ in range(qty):
                st.session_state.manual_items.append({'name': item, 'value': mock_db[cat][item]})

    with col2:
        st.subheader("方式 B：貨號輸入")
        code = st.text_input("輸入貨號 (例如 A001)")
        qty_b = st.number_input("數量", min_value=1, value=1, key="qty_b")
        if st.button("加入清單 (貨號)"):
            if code in mock_db["代碼搜尋"]:
                for _ in range(qty_b):
                    st.session_state.manual_items.append({'name': code, 'value': mock_db["代碼搜尋"][code]})
            else:
                st.error("找不到該貨號")

    # 顯示目前已選列表
    st.divider()
    st.subheader("📋 目前選擇清單")
    if st.session_state.manual_items:
        temp_df = pd.DataFrame(st.session_state.manual_items)
        st.table(temp_df.groupby('name').agg({'value': 'first', 'name': 'count'}).rename(columns={'name': '數量'}))
        if st.button("清空重選"):
            st.session_state.manual_items = []
            st.rerun()
        final_list = st.session_state.manual_items

# --- 共同結尾：設定目標分組 ---
st.divider()
if final_list:
    target_score = st.number_input("請輸入幾分一組？", value=12000, step=100)
    if st.button("🔥 開始分組計算"):
        result_df = run_grouping(final_list, target_score)
        st.success("計算完成！")
        st.dataframe(result_df, use_container_width=True)

        # 下載按鈕
        csv = result_df.to_csv(index=False).encode('utf-8-sig')
        st.download_button("📥 下載分組結果 Excel", data=csv, file_name="分組結果.csv", mime="text/csv")
else:
    st.info("請先透過上傳或手動輸入資料。")