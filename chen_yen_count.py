import streamlit as st
import pandas as pd

st.set_page_config(page_title="商品自動分組系統", layout="wide")


# --- 1. 讀取產品資料庫 ---
@st.cache_data  # 這樣才不會每次按按鈕都重新讀取檔案，速度會快很多
def load_db():
    # 讀取你上傳的產品表
    df = pd.read_csv("丞燕產品表新版.xlsx - 工作表1.csv")
    # 確保欄位名稱乾淨
    df.columns = [c.strip() for c in df.columns]
    return df


try:
    product_db = load_db()
except:
    st.error("找不到產品表 CSV 檔案，請確認檔案名稱是否正確。")
    product_db = pd.DataFrame()


# --- 2. 核心分組演算法 ---
def solve_logic(items, target):
    # 複製一份清單避免影響原始資料
    items_copy = list(items)
    items_copy.sort(key=lambda x: x['value'], reverse=True)
    groups = []

    while items_copy:
        current_group = []
        current_sum = 0
        first_item = items_copy.pop(0)
        current_group.append(first_item)
        current_sum += first_item['value']

        while current_sum < target and items_copy:
            best_idx = -1
            min_diff = float('inf')
            for i, item in enumerate(items_copy):
                diff = abs((current_sum + item['value']) - target)
                if diff < min_diff:
                    min_diff = diff
                    best_idx = i
            best_item = items_copy.pop(best_idx)
            current_group.append(best_item)
            current_sum += best_item['value']
            if current_sum >= target: break

        detail_str = " + ".join([f"{i['name']}({int(i['value'])})" for i in current_group])
        groups.append({"名單明細": detail_str, "總計": current_sum, "誤差": current_sum - target})
    return pd.DataFrame(groups)


# --- 3. 網頁介面 ---
st.title("⚖️ 丞燕商品自動分組系統")

choice = st.sidebar.radio("請選擇輸入方式", ["Excel 上傳（外部檔案）", "手動輸入項目（讀取產品表）"])

ready_to_process = []

# --- 模式 A：Excel 上傳 ---
if choice == "Excel 上傳（外部檔案）":
    st.info("請上傳符合格式（A大項, B貨號, C品名, D數量, E積分...）的 Excel")
    file = st.file_uploader("請上傳 Excel", type=["xlsx", "csv"])
    if file:
        df_upload = pd.read_excel(file) if "xlsx" in file.name else pd.read_csv(file)
        for _, row in df_upload.iterrows():
            try:
                name = str(row.iloc[2])  # C品名
                count = int(row.iloc[3])  # D數量
                value = float(row.iloc[4])  # E積分
                for _ in range(count):
                    ready_to_process.append({"name": name, "value": value})
            except:
                continue
        st.success(f"已從檔案載入 {len(ready_to_process)} 筆項目")

# --- 模式 B：手動輸入（連動選單） ---
else:
    if 'temp_list' not in st.session_state:
        st.session_state.temp_list = []

    col1, col2 = st.columns(2)

    with col1:
        st.subheader("方式一：選單模式")
        # 1. 選擇大項 (從產品表 A 欄去重)
        categories = product_db.iloc[:, 0].unique().tolist()
        selected_cat = st.selectbox("1. 選擇大項", categories)

        # 2. 根據大項篩選品項 (從產品表 C 欄篩選)
        sub_df = product_db[product_db.iloc[:, 0] == selected_cat]
        selected_name = st.selectbox("2. 選擇品項", sub_df.iloc[:, 2].unique().tolist())

        # 取得該品項積分 (E 欄)
        item_score = sub_df[sub_df.iloc[:, 2] == selected_name].iloc[0, 4]
        st.write(f"ℹ️ 單件積分：{item_score}")

        m_qty = st.number_input("3. 數量", min_value=1, step=1, key="qty_menu")

        if st.button("加入清單 (選單)"):
            for _ in range(m_qty):
                st.session_state.temp_list.append({"name": selected_name, "value": float(item_score)})

    with col2:
        st.subheader("方式二：貨號搜尋")
        code_input = st.text_input("輸入貨號 (如: 100100)")
        m_qty_code = st.number_input("數量", min_value=1, step=1, key="qty_code")

        if st.button("加入清單 (貨號)"):
            # 搜尋 B 欄貨號
            matched = product_db[product_db.iloc[:, 1].astype(str) == str(code_input)]
            if not matched.empty:
                name_by_code = matched.iloc[0, 2]
                score_by_code = matched.iloc[0, 4]
                for _ in range(m_qty_code):
                    st.session_state.temp_list.append({"name": name_by_code, "value": float(score_by_code)})
                st.toast(f"已加入: {name_by_code}")
            else:
                st.error("找不到該貨號，請檢查輸入是否正確。")

    st.divider()
    st.subheader("📋 目前待分配清單")
    if st.session_state.temp_list:
        summary_df = pd.DataFrame(st.session_state.temp_list)
        # 顯示統計方便查看
        display_df = summary_df.groupby('name').agg({'value': 'first', 'name': 'count'}).rename(
            columns={'name': '數量'})
        st.table(display_df)
        if st.button("🗑️ 清空所有項目"):
            st.session_state.temp_list = []
            st.rerun()
    ready_to_process = st.session_state.temp_list

# --- 4. 分組執行 ---
if ready_to_process:
    st.divider()
    target = st.number_input("幾分一組？ (例如：12000)", value=12000)
    if st.button("🚀 開始自動分組"):
        results = solve_logic(ready_to_process, target)
        st.success(f"分組完成！共分成 {len(results)} 組")
        st.dataframe(results, use_container_width=True)

        csv = results.to_csv(index=False).encode('utf-8-sig')
        st.download_button("📥 下載分組結果 (CSV)", data=csv, file_name="分組結果.csv")