# ==========================================
# version = 1.3 date = 2026/01/08
# ==========================================

import streamlit as st
import pandas as pd
from datetime import datetime
from zoneinfo import ZoneInfo
from streamlit_gsheets import GSheetsConnection
from streamlit_autorefresh import st_autorefresh

# ==========================================
# 設定・定数
# ==========================================
SHEET_URL = "https://docs.google.com/spreadsheets/d/1-GSNYQYulO-83vdMOn7Trqv4l6eCjo9uzaP20KQgSS4/edit" # 【要修正】あなたのスプレッドシートのURLに書き換えてください
WORKSHEET_NAME = "log"
JST = ZoneInfo("Asia/Tokyo")

AUTO_RELOAD_SEC = 10

# ページ設定
st.set_page_config(page_title="EKIDEN-計測", page_icon="🎽")

# ==========================================
# CSSデザイン定義
# ==========================================
st.markdown("""
    <style>
    /* 画面からはみ出さないようにする */
    .stApp {
        overflow-x: hidden;
    }
    /* 全体の余白を詰めて画面を広く使う */
    .block-container {
        padding-top: 2.0rem;
        padding-bottom: 5rem;
        padding-left: 0.5rem;
        padding-right: 0.5rem;
    }
            
    /* スマホでもカラムを縦積みにせず、無理やり横に並べる設定 */
    div[data-testid="stHorizontalBlock"] {
        display: grid !important;
        grid-template-columns: 1fr auto !important;
        gap: 10px !important;
        align-items: center !important;
    }
            
    /* 右側のカラム（更新ボタン）を右端に寄せる設定 */
    div[data-testid="column"]:nth-of-type(2) {
        display: flex !important;
        justify-content: flex-end !important;
        width: auto !important;
    }
            
    /* 更新ボタン（ヘッダー内にあるボタン）の特別設定 */
    div[data-testid="stHorizontalBlock"] button {
        height: 2.5em !important;
        width: 3em !important;
        padding: 0px !important;
        margin: 0px !important;
        border-radius: 8px !important;
        line-height: 1 !important;
        float: right !important;
    }

    /* その他のボタン（ラップ・次へ・Finish） */
    div.stButton > button {
        height: 3em;
        font-size: 18px;
        font-weight: bold;
        border-radius: 10px;
        width: 100%;
    }
    
    /* ラップ計測ボタン（Primary）だけは少し大きく残す */
    div.stButton > button[kind="primary"] {
        background-color: #FF4B4B;
        color: white;
        height: 4.0em;
        font-size: 36px;
        width: 100%;
    }
    
    /* タイトルの余白を詰める */
    h3 {
        padding: 0px;
        margin: 0px;
        font-size: 1.3rem !important;
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
    }
    </style>
    """, unsafe_allow_html=True)

# タイトル（中央揃え・カスタムHTML）
st.markdown("""
    <h2 style='text-align: center; font-size: 24px; margin-bottom: 2px;'>
        🎽 EKIDEN-計測
    </h2>
""", unsafe_allow_html=True)

# ==========================================
# 関数定義
# ==========================================
def load_data(conn):
    try:
        df = conn.read(spreadsheet=SHEET_URL, worksheet=WORKSHEET_NAME, ttl=AUTO_RELOAD_SEC)
        return df
    except Exception as e:
        return pd.DataFrame()

def get_time_str(dt):
    return dt.strftime("%H:%M:%S")

def parse_time_str(time_str):
    now = datetime.now(JST)
    try:
        t = datetime.strptime(time_str, "%H:%M:%S").time()
        return datetime.combine(now.date(), t).replace(tzinfo=JST)
    except:
        return now
    
def fmt_time(sec):
    m, s = divmod(int(sec), 60)
    h, m = divmod(m, 60)
    return f"{h:02}:{m:02}:{s:02}"

# ==========================================
# メイン処理
# ==========================================
conn = st.connection("gsheets", type=GSheetsConnection)
df = load_data(conn)

# --- A. レース開始前 ---
if df.empty or len(df) == 0:
    st.info("レース開始前")
    
    if st.button("🔫 レーススタート (1区)", type="primary", use_container_width=True):
        now = datetime.now(JST)
        start_data = pd.DataFrame([{
            "区間": "1区",
            "地点": "Start",
            "時刻": get_time_str(now),
            "ラップ": "00:00:00",
            "スプリット": "00:00:00"
        }])
        conn.update(spreadsheet=SHEET_URL, worksheet=WORKSHEET_NAME, data=start_data)
        st.cache_data.clear() # 即クリア
        st.success("レーススタート！")
        st.rerun()

# --- B. レース進行中 or 終了後 ---
else:
    last_row = df.iloc[-1]
    last_point = str(last_row['地点'])
    
    # 1. フィニッシュ済み
    if last_point == "Finish":
        st.balloons()
        st.success("🏆 競技終了！お疲れ様でした！")
        
        st.metric("🏁 フィニッシュ時刻", last_row['時刻'])
        st.metric("⏱️ 最終タイム", last_row['スプリット'])
        
        st.divider()
        st.markdown("### 📊 最終リザルト")
        st.dataframe(df, use_container_width=True)
        
        with st.expander("管理メニュー"):
            if st.button("⚠️ データ全消去（次のレースへ）"):
                conn.update(spreadsheet=SHEET_URL, worksheet=WORKSHEET_NAME, data=pd.DataFrame(columns=df.columns))
                st.cache_data.clear() # 即クリア
                st.rerun()

    # 2. レース中
    else:
        last_time_obj = parse_time_str(last_row['時刻'])
        first_time_obj = parse_time_str(df.iloc[0]['時刻'])
        now_obj = datetime.now(JST)

        current_section_str = str(last_row['区間']) 
        try: current_section_num = int(current_section_str.replace("区", ""))
        except: current_section_num = 1

        if last_point == "Relay":
            next_section_num = current_section_num + 1
            next_km = 1
        else:
            next_section_num = current_section_num
            if "km" in last_point:
                try: last_km = int(last_point.replace("km", ""))
                except: last_km = 0
            else: last_km = 0
            next_km = last_km + 1

        elapsed_since_last = now_obj - last_time_obj
        mins, secs = divmod(elapsed_since_last.seconds, 60)
        elapsed_str = f"{mins:02}:{secs:02}"

        # ヘッダー（区間表示＋更新ボタン）
        c_title, c_btn = st.columns([1, 1])
        with c_title:
            st.markdown(f"### 🏃‍♂️ {next_section_num}区 走行中")
        with c_btn:
            if st.button("🔄", help="更新"):
                st.cache_data.clear() # 即クリア
                st.rerun()

        # 情報パネル
        st.markdown(f"""
        <div style="
            display: flex; 
            justify-content: space-between; 
            align-items: center;
            background-color: #262730;
            padding: 12px; 
            border-radius: 10px; 
            margin-bottom: 8px;
            border: 1px solid #444;
        ">
            <div style="text-align: center; flex: 1;">
                <div style="font-size: 12px; color: #aaa; margin-bottom: 4px;">前の通過</div>
                <div style="font-size: 20px; font-weight: bold; color: white; line-height: 1.2;">{last_point}</div>
            </div>
            <div style="text-align: center; flex: 1; border-left: 1px solid #555; border-right: 1px solid #555;">
                <div style="font-size: 12px; color: #aaa; margin-bottom: 4px;">通過時刻</div>
                <div style="font-size: 20px; font-weight: bold; color: white; line-height: 1.2;">{last_row['時刻'][:-3]}<span style="font-size: 14px;">{last_row['時刻'][-3:]}</span></div>
            </div>
            <div style="text-align: center; flex: 1;">
                <div style="font-size: 12px; color: #aaa; margin-bottom: 4px;">現在の経過</div>
                <div style="font-size: 26px; font-weight: bold; color: #FF4B4B; line-height: 1.0;">{elapsed_str}</div>
            </div>
        </div>
        """, unsafe_allow_html=True)

        st.divider()

        # 操作ボタン類
        # 1. ラップ計測
        if st.button(f"⏱️ {next_km}km地点 ラップ", type="primary", use_container_width=True):
            lap_sec = (now_obj - last_time_obj).total_seconds()
            total_sec = (now_obj - first_time_obj).total_seconds()
            new_row = pd.DataFrame([{
                "区間": f"{next_section_num}区", "地点": f"{next_km}km",
                "時刻": get_time_str(now_obj), "ラップ": fmt_time(lap_sec), "スプリット": fmt_time(total_sec)
            }])
            conn.update(spreadsheet=SHEET_URL, worksheet=WORKSHEET_NAME, data=pd.concat([df, new_row]))
            st.cache_data.clear() # 即クリア
            st.toast(f"{next_km}km地点を記録！")
            st.rerun()

        # 2. 中継ボタン
        if st.button(f"🎽 次へ ({next_section_num+1}区へ)", use_container_width=True):
            lap_sec = (now_obj - last_time_obj).total_seconds()
            total_sec = (now_obj - first_time_obj).total_seconds()
            new_row = pd.DataFrame([{
                "区間": f"{next_section_num}区", "地点": "Relay",
                "時刻": get_time_str(now_obj), "ラップ": fmt_time(lap_sec), "スプリット": fmt_time(total_sec)
            }])
            conn.update(spreadsheet=SHEET_URL, worksheet=WORKSHEET_NAME, data=pd.concat([df, new_row]))
            st.cache_data.clear() # 即クリア
            st.success(f"{next_section_num+1}区へリレーしました！")
            st.rerun()
        
        # 3. Finishボタン
        if st.button("🏆 Finish", use_container_width=True):
            lap_sec = (now_obj - last_time_obj).total_seconds()
            total_sec = (now_obj - first_time_obj).total_seconds()
            new_row = pd.DataFrame([{
                "区間": f"{next_section_num}区", "地点": "Finish",
                "時刻": get_time_str(now_obj), "ラップ": fmt_time(lap_sec), "スプリット": fmt_time(total_sec)
            }])
            conn.update(spreadsheet=SHEET_URL, worksheet=WORKSHEET_NAME, data=pd.concat([df, new_row]))
            st.cache_data.clear() # 即クリア
            st.rerun()

        # ログ表示
        with st.expander("📊 計測ログを表示（タップして開閉）"):
            st.dataframe(df.iloc[::-1], use_container_width=True)
        
        # 管理メニュー（自動更新機能の追加）
        with st.expander("管理メニュー"):
            st.write("設定")
            # デフォルトをONにする仕様
            auto_reload = st.toggle("🔄 自動更新", value=True)
            
            st.divider()
            
            if st.button("⚠️ データ全消去"):
                conn.update(spreadsheet=SHEET_URL, worksheet=WORKSHEET_NAME, data=pd.DataFrame(columns=df.columns))
                st.rerun()
        
        # ▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼
        # 【変更】streamlit-autorefresh による非同期更新
        # Pythonを止めることなく、ブラウザ側から10秒ごとに更新をかけます
        # ▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼
        if auto_reload:
            st_autorefresh(interval=AUTO_RELOAD_SEC*100, key="datarefresh")
            # interval=10000 は 10,000ミリ秒 = 10秒 です
            # このコンポーネントを置くだけで勝手に更新されます（st.rerun不要）