import streamlit as st
import pandas as pd
import os

st.set_page_config(page_title="商品自動分組系統", layout="wide")


# --- 1. 讀取產品資料庫 ---
@st.cache_data
def load_db():
    file_path = "丞燕產品表新版.xlsx"
    if os.path.exists(file_path):
        try:
            df = pd.read_excel(file_path)
            # 清除欄位名稱空格
            df.columns = [str(c).strip() for c in df.columns]
            return df, "success"
        except Exception as e:
            return None, f"讀取失敗: {e}"
    else:
        return None, "找不到 products.xlsx 檔案"


product_db, status = load_db()


# --- 2. 核心分組演算法 (新增價格計算) ---
def solve_logic(items, target):
    items_copy = list(items)
    # 依積分從大到小排序
    items_copy.sort(key=lambda x: x['points'], reverse=True)
    groups = []

    while items_copy:
        current_group, current_sum_pts, current_sum_price = [], 0, 0
        first_item = items_copy.pop(0)
        current_group.append(first_item)
        current_sum_pts += first_item['points']
        current_sum_price += first_item['price']

        while current_sum_pts < target and items_copy:
            best_idx, min_diff = -1, float('inf')
            for i, item in enumerate(items_copy):
                diff = abs((current_sum_pts + item['points']) - target)
                if diff < min_diff:
                    min_diff, best_idx = diff, i

            best_item = items_copy.pop(best_idx)
            current_group.append(best_item)
            current_sum_pts += best_item['points']
            current_sum_price += best_item['price']
            if current_sum_pts >= target: break

        detail_str = " + ".join([f"{i['name']}" for i in current_group])
        groups.append({
            "名單明細": detail_str,
            "積分總計": current_sum_pts,
            "價格總計": current_sum_price,
            "積分誤差": current_sum_pts - target
        })
    return pd.DataFrame(groups)


# --- 3. 介面邏輯 ---
if status != "success":
    st.error(status)
    st.stop()

st.title("⚖️ 產品積分與價格自動分組系統")

choice = st.sidebar.radio("請選擇輸入方式", ["手動輸入項目 (連動選單)", "Excel 檔案整批上傳"])

if 'final_list' not in st.session_state:
    st.session_state.final_list = []

# --- 模式一：連動手動輸入 ---
if choice == "手動輸入項目 (連動選單)":
    col1, col2 = st.columns(2)

    with col1:
        st.subheader("方式 A：階層選單")
        all_categories = product_db.iloc[:, 0].dropna().unique().tolist()
        selected_cat = st.selectbox("1. 選擇大項", all_categories)

        filtered_df = product_db[product_db.iloc[:, 0] == selected_cat]
        all_products = filtered_df.iloc[:, 2].dropna().unique().tolist()
        selected_prod = st.selectbox(f"2. 選擇 {selected_cat} 內的品名", all_products)

        # 取得積分(E欄, index 4) 與 價格(G欄, index 6)
        item_data = filtered_df[filtered_df.iloc[:, 2] == selected_prod].iloc[0]
        pts = float(item_data.iloc[4])
        price = float(item_data.iloc[6])

        st.info(f"💰 單件資訊 -> 積分: {pts} | 價格: ${price}")
        qty = st.number_input("3. 輸入數量", min_value=1, value=1, step=1)

        if st.button("➕ 加入選擇項目"):
            for _ in range(qty):
                st.session_state.final_list.append({"name": selected_prod, "points": pts, "price": price})
            st.toast(f"已加入 {qty} 個 {selected_prod}")

    with col2:
        st.subheader("方式 B：貨號搜尋")
        code_input = st.text_input("輸入貨號")
        qty_b = st.number_input("數量 ", min_value=1, value=1, step=1)

        if st.button("➕ 貨號快速加入"):
            match = product_db[product_db.iloc[:, 1].astype(str) == str(code_input)]
            if not match.empty:
                p_name = match.iloc[0, 2]
                p_pts = float(match.iloc[0, 4])
                p_price = float(match.iloc[0, 6])
                for _ in range(qty_b):
                    st.session_state.final_list.append({"name": p_name, "points": p_pts, "price": p_price})
                st.toast(f"已加入 {qty_b} 個 {p_name}")
            else:
                st.error("找不到此貨號")

# --- 模式二：外部 Excel 上傳 ---
else:
    uploaded_file = st.file_uploader("上傳訂單 Excel", type=["xlsx"])
    if uploaded_file:
        df_up = pd.read_excel(uploaded_file)
        if st.button("📥 載入檔案數據"):
            new_items = []
            for _, row in df_up.iterrows():
                try:
                    # C品名(2), D數量(3), E積分(4), G價格(6)
                    n, q, pt, pr = str(row.iloc[2]), int(row.iloc[3]), float(row.iloc[4]), float(row.iloc[6])
                    for _ in range(q):
                        new_items.append({"name": n, "points": pt, "price": pr})
                except:
                    continue
            st.session_state.final_list = new_items
            st.success(f"成功載入 {len(new_items)} 個品項")

# --- 4. 顯示目前清單與計算 ---
st.divider()
if st.session_state.final_list:
    st.subheader("📋 目前清單內容 (含價格)")
    temp_df = pd.DataFrame(st.session_state.final_list)

    # 顯示統計表格
    summary = temp_df.groupby('name').agg({
        'points': 'first',
        'price': 'first',
        'name': 'count'
    }).rename(columns={'name': '數量', 'points': '單件積分', 'price': '單件價格'})

    # 計算總金額預覽
    total_p = temp_df['price'].sum()
    total_s = temp_df['points'].sum()
    st.table(summary)
    st.write(f"📊 **當前總計清單：** 積分總和 `{total_s}` | 金額總額 `${total_p}`")

    if st.button("🗑️ 清空重選"):
        st.session_state.final_list = []
        st.rerun()

    st.divider()
    target_val = st.number_input("🎯 設定分組目標積分", value=12000, step=100)

    if st.button("🚀 開始自動分組"):
        final_res = solve_logic(st.session_state.final_list, target_val)
        st.success(f"分組完成！共計 {len(final_res)} 組")

        # 顯示結果表格
        st.dataframe(final_res, use_container_width=True)

        csv = final_res.to_csv(index=False).encode('utf-8-sig')
        st.download_button("📥 下載分組結果 (CSV)", data=csv, file_name="分組結果.csv")