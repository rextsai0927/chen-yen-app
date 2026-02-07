import streamlit as st
import pandas as pd
import os

st.set_page_config(page_title="商品自動分組系統", layout="wide")


# --- 1. 讀取產品資料庫 ---
@st.cache_data
def load_db():
    # 這裡預設讀取 products.xlsx，請確保 GitHub 上檔名一致
    file_path = "丞燕產品表新版.xlsx"
    if os.path.exists(file_path):
        try:
            # 讀取 A-H 欄
            df = pd.read_excel(file_path)
            # 清除欄位名稱空格
            df.columns = [str(c).strip() for c in df.columns]
            return df, "success"
        except Exception as e:
            return None, f"讀取失敗: {e}"
    else:
        return None, "找不到 products.xlsx 檔案"


product_db, status = load_db()


# --- 核心分組演算法 ---
def solve_logic(items, target):
    items_copy = list(items)
    items_copy.sort(key=lambda x: x['value'], reverse=True)
    groups = []
    while items_copy:
        current_group, current_sum = [], 0
        first_item = items_copy.pop(0)
        current_group.append(first_item)
        current_sum += first_item['value']

        while current_sum < target and items_copy:
            best_idx, min_diff = -1, float('inf')
            for i, item in enumerate(items_copy):
                diff = abs((current_sum + item['value']) - target)
                if diff < min_diff:
                    min_diff, best_idx = diff, i
            best_item = items_copy.pop(best_idx)
            current_group.append(best_item)
            current_sum += best_item['value']
            if current_sum >= target: break

        detail_str = " + ".join([f"{i['name']}({int(i['value'])})" for i in current_group])
        groups.append({"名單明細": detail_str, "總計": current_sum, "誤差": current_sum - target})
    return pd.DataFrame(groups)


# --- 2. 介面邏輯 ---
if status != "success":
    st.error(status)
    st.stop()

st.title("⚖️ 產品積分自動分組系統")

choice = st.sidebar.radio("請選擇輸入方式", ["手動輸入項目 (連動選單)", "Excel 檔案整批上傳"])

# 存放最終待計算清單
if 'final_list' not in st.session_state:
    st.session_state.final_list = []

# --- 模式一：連動手動輸入 ---
if choice == "手動輸入項目 (連動選單)":
    col1, col2 = st.columns(2)

    with col1:
        st.subheader("方式 A：階層選單")
        # 取得所有唯一的大項 (第一欄)
        all_categories = product_db.iloc[:, 0].dropna().unique().tolist()
        selected_cat = st.selectbox("1. 選擇大項 (例如: 千禧)", all_categories)

        # 根據大項過濾出品名 (第三欄)
        filtered_df = product_db[product_db.iloc[:, 0] == selected_cat]
        all_products = filtered_df.iloc[:, 2].dropna().unique().tolist()
        selected_prod = st.selectbox(f"2. 選擇 {selected_cat} 內的品名", all_products)

        # 取得該品名對應的積分 (第五欄)
        item_data = filtered_df[filtered_df.iloc[:, 2] == selected_prod].iloc[0]
        points = float(item_data.iloc[4])

        qty = st.number_input("3. 輸入數量", min_value=1, value=1, step=1)

        if st.button("➕ 加入選擇項目"):
            for _ in range(qty):
                st.session_state.final_list.append({"name": selected_prod, "value": points})
            st.toast(f"已加入 {qty} 個 {selected_prod}")

    with col2:
        st.subheader("方式 B：貨號搜尋")
        code_input = st.text_input("輸入貨號 (例如: 100100)")
        qty_b = st.number_input("數量 ", min_value=1, value=1, step=1)

        if st.button("➕ 貨號快速加入"):
            # 貨號比對 (第二欄)
            match = product_db[product_db.iloc[:, 1].astype(str) == str(code_input)]
            if not match.empty:
                prod_name = match.iloc[0, 2]
                prod_pts = float(match.iloc[0, 4])
                for _ in range(qty_b):
                    st.session_state.final_list.append({"name": prod_name, "value": prod_pts})
                st.toast(f"已加入 {qty_b} 個 {prod_name}")
            else:
                st.error("找不到此貨號，請檢查 products.xlsx")

# --- 模式二：外部 Excel 上傳 ---
else:
    uploaded_file = st.file_uploader("上傳要計算的訂單 Excel (A-H 格式)", type=["xlsx"])
    if uploaded_file:
        df_up = pd.read_excel(uploaded_file)
        if st.button("📥 載入檔案數據"):
            new_items = []
            for _, row in df_up.iterrows():
                try:
                    name, count, pts = str(row.iloc[2]), int(row.iloc[3]), float(row.iloc[4])
                    for _ in range(count):
                        new_items.append({"name": name, "value": pts})
                except:
                    continue
            st.session_state.final_list = new_items
            st.success(f"成功載入 {len(new_items)} 個品項")

# --- 3. 顯示結果與計算 ---
st.divider()
if st.session_state.final_list:
    st.subheader("📋 目前清單內容")
    temp_df = pd.DataFrame(st.session_state.final_list)
    # 統計顯示
    summary = temp_df.groupby('name').agg({'value': 'first', 'name': 'count'}).rename(
        columns={'name': '數量', 'value': '單件積分'})
    st.table(summary)

    if st.button("🗑️ 清空重選"):
        st.session_state.final_list = []
        st.rerun()

    st.divider()
    target_val = st.number_input("🎯 設定分組目標積分 (例如: 12000)", value=12000, step=100)

    if st.button("🚀 開始自動分組"):
        final_res = solve_logic(st.session_state.final_list, target_val)
        st.success(f"分組完成！共計 {len(final_res)} 組")
        st.dataframe(final_res, use_container_width=True)

        csv = final_res.to_csv(index=False).encode('utf-8-sig')
        st.download_button("📥 下載分組結果 (Excel/CSV)", data=csv, file_name="分組結果.csv")