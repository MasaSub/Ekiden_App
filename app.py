# ==========================================
# version = 1.4.0 date = 2026/01/09
# ==========================================

import streamlit as st
import pandas as pd
import math
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime
from zoneinfo import ZoneInfo
from streamlit_gsheets import GSheetsConnection
from streamlit_autorefresh import st_autorefresh # 【復活】これが抜けていました！
import streamlit.components.v1 as components

# ==========================================
# 設定・定数
# ==========================================
VERSION = "ver 1.4.0"

SHEET_URL = "https://docs.google.com/spreadsheets/d/1-GSNYQYulO-83vdMOn7Trqv4l6eCjo9uzaP20KQgSS4/edit" # 【要修正】URL確認
WORKSHEET_NAME = "log"
JST = ZoneInfo("Asia/Tokyo")
CACHE_TTL_SEC = 1.5

# ページ設定
st.set_page_config(page_title="駅伝けいそくん", page_icon="🎽", layout="wide")

# ==========================================
# CSSデザイン定義
# ==========================================
st.markdown("""
    <style>
    .stApp { overflow-x: hidden; }
    .block-container {
        padding-top: 2.0rem;
        padding-bottom: 5rem;
        padding-left: 0.5rem;
        padding-right: 0.5rem;
    }
    div[data-testid="stHorizontalBlock"] {
        display: grid !important;
        grid-template-columns: 1fr auto !important;
        gap: 10px !important;
        align-items: center !important;
    }
    div[data-testid="column"]:nth-of-type(2) {
        display: flex !important;
        justify-content: flex-end !important;
        width: auto !important;
    }
    div[data-testid="stHorizontalBlock"] button {
        height: 2.5em !important;
        width: 3em !important;
        padding: 0px !important;
        margin: 0px !important;
        border-radius: 8px !important;
        line-height: 1 !important;
        float: right !important;
    }
    div.stButton > button {
        height: 3em;
        font-size: 18px;
        font-weight: bold;
        border-radius: 10px;
        width: 100%;
    }
    div.stButton > button[kind="primary"] {
        background-color: #FF4B4B;
        color: white;
        height: 4.0em;
        font-size: 36px;
        width: 100%;
    }
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

# タイトル
st.markdown(f"""
    <h2 style='text-align: center; font-size: 24px; margin-bottom: 2px;'>
        🎽 駅伝けいそくん
    </h2>
    <div style="text-align: center; font-size: 12px; color: #888; margin-bottom: 20px;">
        {VERSION}
    </div>
""", unsafe_allow_html=True)

# ==========================================
# 関数定義
# ==========================================
def load_data(conn):
    try:
        df = conn.read(spreadsheet=SHEET_URL, worksheet=WORKSHEET_NAME, ttl=CACHE_TTL_SEC)
        if not df.empty:
            cols_to_str = ['Time', 'KM-Lap', 'SEC-Lap', 'Split']
            for col in cols_to_str:
                if col in df.columns:
                    df[col] = df[col].astype(str)
        return df
    except Exception as e:
        st.error(f"通信エラー（再接続中...）: {e}")
        return pd.DataFrame()

# 安全な追記書き込み用のクライアント取得関数
def get_gspread_client():
    scope = ['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive']
    credentials = dict(st.secrets["connections"]["gsheets"])
    creds = Credentials.from_service_account_info(credentials, scopes=scope)
    client = gspread.authorize(creds)
    return client

def get_time_str(dt):
    return dt.strftime("%H:%M:%S.%f")[:10]

def parse_time_str(time_str):
    now = datetime.now(JST)
    try:
        if "." in time_str:
            t = datetime.strptime(time_str + "00000", "%H:%M:%S.%f").time()
        else:
            t = datetime.strptime(time_str, "%H:%M:%S").time()
        return datetime.combine(now.date(), t).replace(tzinfo=JST)
    except:
        return now

def style_decimal(time_str):
    if "." in time_str:
        main, dec = time_str.split(".")
        return f'{main}<span style="font-size: 0.6em; opacity: 0.7;">.{dec}</span>'
    return time_str    

def fmt_time(sec):
    sec = math.ceil(sec)
    m, s = divmod(int(sec), 60)
    h, m = divmod(m, 60)
    return f"{h:01}:{m:02}:{s:02}"

def fmt_time_lap(sec):
    total_tenths = math.ceil(sec * 10)
    rem_tenths = total_tenths % 10
    total_sec = total_tenths // 10
    m, s = divmod(total_sec, 60)
    return f"{m:02}:{s:02}.{rem_tenths}"

def get_section_start_time(df, section_num):
    if section_num == 1:
        row = df[df['Location'] == 'Start']
    else:
        prev_section = f"{section_num - 1}区"
        row = df[(df['Section'] == prev_section) & (df['Location'] == 'Relay')]
    
    if not row.empty:
        return parse_time_str(row.iloc[0]['Time'])
    return None

def show_js_timer(km_sec, sec_sec, split_sec):
    km_ms = int(km_sec * 1000)
    sec_ms = int(sec_sec * 1000)
    split_ms = int(split_sec * 1000)

    html_code = f"""
    <!DOCTYPE html>
    <html>
    <head>
    <style>
        body {{ margin: 0; background-color: transparent; font-family: sans-serif; }}
        .timer-container {{
            display: flex; justify-content: space-between; align-items: center;
            background-color: #262730; padding: 10px; border-radius: 10px;
            border: 1px solid #444; color: white;
            box-sizing: border-box; width: 100%;
        }}
        .timer-box {{ text-align: center; flex: 1; }}
        .label {{ font-size: 11px; color: #aaa; margin-bottom: 2px; }}
        .value {{ font-size: 24px; font-weight: bold; line-height: 1.1; }}
        .value-split {{ font-size: 20px; font-weight: bold; color: #ffffff; line-height: 1.3; }}
        .separator {{ width: 1px; height: 40px; background-color: #555; }}
        .decimal {{ font-size: 0.6em; opacity: 0.7; }}
    </style>
    </head>
    <body>
    <div class="timer-container">
        <div class="timer-box">
            <div class="label">キロラップ</div>
            <div id="km-val" class="value" style="color: #4bd6ff;">--:--.--</div>
        </div>
        <div class="separator"></div>
        <div class="timer-box">
            <div class="label">区間ラップ</div>
            <div id="sec-val" class="value" style="color: #FF4B4B;">--:--.--</div>
        </div>
        <div class="separator"></div>
        <div class="timer-box">
            <div class="label">スタートから</div>
            <div id="split-val" class="value-split">--:--:--</div>
        </div>
    </div>
    <script>
        const now = Date.now();
        const startKm = now - {km_ms};
        const startSec = now - {sec_ms};
        const startSplit = now - {split_ms};

        function fmtLap(ms) {{
            const totalTenths = Math.ceil(ms / 100); 
            const totalSec = Math.floor(totalTenths / 10);
            const remTenths = totalTenths % 10;
            const m = Math.floor(totalSec / 60);
            const s = totalSec % 60;
            return `${{String(m).padStart(2,'0')}}:${{String(s).padStart(2,'0')}}<span class="decimal">.${{remTenths}}</span>`;
        }}
        function fmtSplit(ms) {{
            const totalSec = Math.ceil(ms / 1000);
            const h = Math.floor(totalSec / 3600);
            const rem = totalSec % 3600;
            const m = Math.floor(rem / 60);
            const s = rem % 60;
            return `${{String(h).padStart(2,'0')}}:${{String(m).padStart(2,'0')}}:${{String(s).padStart(2,'0')}}`;
        }}
        function update() {{
            const cur = Date.now();
            document.getElementById("km-val").innerHTML = fmtLap(Math.max(0, cur - startKm));
            document.getElementById("sec-val").innerHTML = fmtLap(Math.max(0, cur - startSec));
            document.getElementById("split-val").innerText = fmtSplit(Math.max(0, cur - startSplit));
        }}
        setInterval(update, 50);
        update(); 
    </script>
    </body>
    </html>
    """
    components.html(html_code, height=90)

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
            "Section": "1区", 
            "Location": "Start", 
            "Time": get_time_str(now),
            "KM-Lap": "00:00:00.0", 
            "SEC-Lap": "00:00:00.0", 
            "Split": "0:00:00"
        }])
        conn.update(spreadsheet=SHEET_URL, worksheet=WORKSHEET_NAME, data=start_data)
        st.cache_data.clear()
        st.success("レーススタート！")
        st.rerun()

    st.write("")

    with st.expander("管理メニュー"):
        st.write("設定")
        auto_reload_start = st.toggle("🔄 自動更新", value=True, key="auto_reload_start")
    
    if auto_reload_start:
        st_autorefresh(interval=2000, key="refresh_start")


# --- B. レース進行中 or 終了後 ---
else:
    last_row = df.iloc[-1]
    last_point = str(last_row['Location'])
    
    # 1. フィニッシュ済み
    if last_point == "Finish":
        st.success("🏆 競技終了！お疲れ様でした！")
        st.metric("🏁 フィニッシュ時刻", last_row['Time'])
        st.metric("⏱️ 最終タイム", last_row['Split'])
        
        st.divider()
        st.markdown("### 📊 最終リザルト")
        st.dataframe(df, use_container_width=True)
        
        with st.expander("管理メニュー"):
            st.write("設定")
            auto_reload_finish = st.toggle("🔄 自動更新", value=True, key="auto_reload_finish")
            st.divider()
            if st.button("⚠️ データ全消去（次のレースへ）"):
                conn.update(spreadsheet=SHEET_URL, worksheet=WORKSHEET_NAME, data=pd.DataFrame(columns=df.columns))
                st.cache_data.clear()
                st.rerun()
        if auto_reload_finish:
            st_autorefresh(interval=10000, key="refresh_finish")
    
    # 2. レース中
    else:
        @st.fragment(run_every=4)
        def show_race_dashboard():
            # Fragment内でデータ再取得
            conn_frag = st.connection("gsheets", type=GSheetsConnection)
            current_df = load_data(conn_frag)
            if current_df.empty: return

            last_row = current_df.iloc[-1]
            last_point = str(last_row['Location'])
            last_time_obj = parse_time_str(last_row['Time'])
            first_time_obj = parse_time_str(current_df.iloc[0]['Time'])
            
            # 区間判定
            current_section_str = str(last_row['Section']) 
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

            # ヘッダー
            if last_point in ["Start", "Relay"]:
                current_dist_val = 0
            elif "km" in last_point:
                try: current_dist_val = int(last_point.replace("km", ""))
                except: current_dist_val = 0
            else:
                current_dist_val = 0
            
            header_text = f"🏃‍♂️ {next_section_num}区 {current_dist_val} ~ {current_dist_val+1} km 走行中📣"
            
            c_title, c_btn = st.columns([1, 1])
            with c_title:
                st.markdown(f"### {header_text}")
            with c_btn:
                if st.button("🔄", help="即時更新"):
                    st.cache_data.clear()
                    st.rerun()

            # JSタイマー
            now_calc = datetime.now(JST)
            elapsed_km = (now_calc - last_time_obj).total_seconds()
            sec_start = get_section_start_time(current_df, next_section_num)
            elapsed_sec = (now_calc - sec_start).total_seconds() if sec_start else 0
            elapsed_split = (now_calc - first_time_obj).total_seconds()
            show_js_timer(elapsed_km, elapsed_sec, elapsed_split)

            st.divider()

            # --- ボタン処理（Fragment内：ラップ・中継） ---
            now_for_record = datetime.now(JST)

            # gspreadを直接使って追記する関数
            def append_record(loc_text):
                lap_sec = (now_for_record - last_time_obj).total_seconds()
                total_sec = (now_for_record - first_time_obj).total_seconds()
                section_start_obj = get_section_start_time(current_df, next_section_num)
                section_lap_sec = (now_for_record - section_start_obj).total_seconds() if section_start_obj else 0
                
                values = [
                    f"{next_section_num}区",
                    loc_text,
                    get_time_str(now_for_record),
                    fmt_time_lap(lap_sec),
                    fmt_time_lap(section_lap_sec),
                    fmt_time(total_sec)
                ]
                # gspreadクライアントを取得してappend_row
                gc = get_gspread_client()
                gc.open_by_url(SHEET_URL).worksheet(WORKSHEET_NAME).append_row(values, value_input_option='USER_ENTERED')
                
                st.cache_data.clear()
                st.rerun()

            if st.button(f"⏱️ {next_km}km地点 ラップ", type="primary", use_container_width=True):
                append_record(f"{next_km}km")
                st.toast(f"{next_km}km地点を記録！")

            if st.button(f"🎽 次へ ({next_section_num+1}区へ)", use_container_width=True):
                append_record("Relay")
                st.success("リレーしました！")

        # Fragment実行
        show_race_dashboard()
        
        # --- Finishボタン（Fragmentの外に配置） ---
        if st.button("🏆 Finish", use_container_width=True):
            now_for_record = datetime.now(JST)
            # 現在のデータ(df)を使って計算
            last_row = df.iloc[-1]
            last_time_obj = parse_time_str(last_row['Time'])
            first_time_obj = parse_time_str(df.iloc[0]['Time'])
            
            # 次の区間等の再計算
            current_section_str = str(last_row['Section']) 
            try: current_section_num = int(current_section_str.replace("区", ""))
            except: current_section_num = 1
            if str(last_row['Location']) == "Relay":
                next_section_num = current_section_num + 1
            else:
                next_section_num = current_section_num

            lap_sec = (now_for_record - last_time_obj).total_seconds()
            total_sec = (now_for_record - first_time_obj).total_seconds()
            section_start_obj = get_section_start_time(df, next_section_num)
            section_lap_sec = (now_for_record - section_start_obj).total_seconds() if section_start_obj else 0

            values = [
                f"{next_section_num}区",
                "Finish",
                get_time_str(now_for_record),
                fmt_time_lap(lap_sec),
                fmt_time_lap(section_lap_sec),
                fmt_time(total_sec)
            ]
            # gspreadクライアントを取得してappend_row
            gc = get_gspread_client()
            gc.open_by_url(SHEET_URL).worksheet(WORKSHEET_NAME).append_row(values, value_input_option='USER_ENTERED')
            st.cache_data.clear()
            st.rerun()

        # ログ表示
        st.divider()
        with st.expander("📊 計測ログを表示"):
            st.dataframe(df.iloc[::-1], use_container_width=True)