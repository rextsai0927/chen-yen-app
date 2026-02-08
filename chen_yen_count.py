import streamlit as st
import pandas as pd
import os

st.set_page_config(page_title="商品自動分組系統", layout="wide")


# --- 1. 讀取產品資料庫 ---
@st.cache_data
def load_db():
    file_path = "products.xlsx"
    if os.path.exists(file_path):
        try:
            df = pd.read_excel(file_path)
            df.columns = [str(c).strip() for c in df.columns]
            return df, "success"
        except Exception as e:
            return None, f"讀取失敗: {e}"
    else:
        return None, "找不到 products.xlsx 檔案"


product_db, status = load_db()


# --- 2. 核心分組演算法 ---
def solve_logic(items, target):
    items_copy = list(items)
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
    st.error(status);
    st.stop()

st.title("⚖️ 產品積分分組系統 (含刪除功能)")

if 'final_list' not in st.session_state:
    st.session_state.final_list = []

choice = st.sidebar.radio("請選擇輸入方式", ["手動輸入項目", "Excel 檔案整批上傳"])

# --- 模式一：手動輸入 ---
if choice == "手動輸入項目":
    col1, col2 = st.columns(2)
    with col1:
        st.subheader("方式 A：選單模式")
        all_cats = product_db.iloc[:, 0].dropna().unique().tolist()
        s_cat = st.selectbox("1. 選擇大項", all_cats)
        f_df = product_db[product_db.iloc[:, 0] == s_cat]
        s_prod = st.selectbox(f"2. 選擇 {s_cat} 內的品名", f_df.iloc[:, 2].dropna().unique().tolist())

        item_data = f_df[f_df.iloc[:, 2] == s_prod].iloc[0]
        pts, pr = float(item_data.iloc[4]), float(item_data.iloc[6])
        st.info(f"💰 積分: {pts} | 價格: ${pr}")
        qty = st.number_input("3. 數量", min_value=1, value=1)

        if st.button("➕ 加入清單"):
            for _ in range(qty):
                st.session_state.final_list.append({"name": s_prod, "points": pts, "price": pr})
            st.rerun()

    with col2:
        st.subheader("方式 B：貨號搜尋")
        c_in = st.text_input("輸入貨號")
        q_b = st.number_input("數量 ", min_value=1, value=1)
        if st.button("➕ 貨號加入"):
            match = product_db[product_db.iloc[:, 1].astype(str) == str(c_in)]
            if not match.empty:
                n, p, pr = match.iloc[0, 2], float(match.iloc[0, 4]), float(match.iloc[0, 6])
                for _ in range(q_b):
                    st.session_state.final_list.append({"name": n, "points": p, "price": pr})
                st.rerun()
            else:
                st.error("找不到貨號")

# --- 模式二：Excel 上傳 ---
else:
    u_file = st.file_uploader("上傳訂單 Excel", type=["xlsx"])
    if u_file:
        df_up = pd.read_excel(u_file)
        if st.button("📥 載入檔案"):
            new_i = []
            for _, r in df_up.iterrows():
                try:
                    for _ in range(int(r.iloc[3])):
                        new_i.append({"name": str(r.iloc[2]), "points": float(r.iloc[4]), "price": float(r.iloc[6])})
                except:
                    continue
            st.session_state.final_list = new_i
            st.rerun()

# --- 4. 目前清單內容 (新增刪除功能) ---
st.divider()
if st.session_state.final_list:
    st.subheader("📋 目前清單內容")

    # 建立一個彙整後的表單供使用者閱讀
    temp_df = pd.DataFrame(st.session_state.final_list)
    summary = temp_df.groupby('name').agg({'points': 'first', 'price': 'first', 'name': 'count'}).rename(
        columns={'name': '數量', 'points': '積分', 'price': '價格'})

    # 顯示總計
    st.write(f"**總積分：{temp_df['points'].sum()} | 總金額：${temp_df['price'].sum()}**")

    # --- 刪除功能區 ---
    with st.expander("🔍 查看/刪除個別項目"):
        for i, item in enumerate(st.session_state.final_list):
            c1, c2, c3, c4 = st.columns([3, 1, 1, 1])
            c1.write(item['name'])
            c2.write(f"分: {item['points']}")
            c3.write(f"$: {item['price']}")
            if c4.button("🗑️ 刪除", key=f"del_{i}"):
                st.session_state.final_list.pop(i)
                st.rerun()

    if st.button("⚠️ 全部清空"):
        st.session_state.final_list = []
        st.rerun()

    # --- 5. 分組計算 ---
    st.divider()
    t_val = st.number_input("🎯 設定分組目標積分", value=12000, step=100)
    if st.button("🚀 開始自動分組"):
        res = solve_logic(st.session_state.final_list, t_val)
        st.success(f"分組完成！共 {len(res)} 組")
        st.dataframe(res, use_container_width=True)
        csv = res.to_csv(index=False).encode('utf-8-sig')
        st.download_button("📥 下載分組結果", data=csv, file_name="result.csv")