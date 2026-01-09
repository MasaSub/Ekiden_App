# ==========================================
# version = 1.4.1 date = 2026/01/09
# ==========================================

import streamlit as st
import pandas as pd
import math
import gspread
import altair as alt # ▼▼▼ v1.4.2 追加: 高度なグラフ描画用 ▼▼▼
from google.oauth2.service_account import Credentials
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from streamlit_gsheets import GSheetsConnection
from streamlit_autorefresh import st_autorefresh
import streamlit.components.v1 as components

# ==========================================
# 設定・定数
# ==========================================
VERSION = "ver 1.4.1"

SHEET_URL = "https://docs.google.com/spreadsheets/d/1-GSNYQYulO-83vdMOn7Trqv4l6eCjo9uzaP20KQgSS4/edit" # 【要修正】URL確認
WORKSHEET_NAME = "latest-log"
JST = ZoneInfo("Asia/Tokyo")
CACHE_TTL_SEC = 1.5
ADMIN_PASSWORD = "0000" # ▼▼▼ v1.4.1 追加: 管理者用パスワード ▼▼▼

# ページ設定
st.set_page_config(page_title="駅伝けいそくん", page_icon="🎽", layout="wide")

# ==========================================
# セッション状態の初期化 (必ず先頭で行う)
# ==========================================
if "app_mode" not in st.session_state:
    st.session_state["app_mode"] = "⏱️ 計測モード"

def set_mode(mode):
    st.session_state["app_mode"] = mode

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
    
    /* サイドバーの背景色をダークに */
    section[data-testid="stSidebar"] {
        background-color: #262730;
        color: white;
    }
    
    /* サイドバー内のボタンのスタイル調整 */
    section[data-testid="stSidebar"] button {
        text-align: left;
        padding-left: 20px;
        width: 100%;
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
    /* Primaryボタン(赤)のデザイン */
    div.stButton > button[kind="primary"] {
        background-color: #FF4B4B;
        color: white;
        height: 4.0em; /* メイン画面のボタンは大きく */
        font-size: 36px;
        width: 100%;
    }
    /* サイドバー内のPrimaryボタンはサイズを普通にする */
    section[data-testid="stSidebar"] div.stButton > button[kind="primary"] {
        height: 3em; 
        font-size: 18px;
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

# タイトル（サイドバーへ移動するか、共通ヘッダーとして残す）
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
# ▼▼▼ v1.4.1 変更: シート名を引数で指定できるように変更 ▼▼▼
def load_data(conn, sheet_name=WORKSHEET_NAME):
    try:
        # キャッシュTTLは閲覧モードでは少し長くても良いが、計測モードは短く
        ttl = CACHE_TTL_SEC
        df = conn.read(spreadsheet=SHEET_URL, worksheet=sheet_name, ttl=ttl)
        if not df.empty:
            cols_to_str = ['Time', 'KM-Lap', 'SEC-Lap', 'Split', 'Race']
            for col in cols_to_str:
                if col in df.columns:
                    df[col] = df[col].astype(str)
        return df
    except Exception as e:
        # 計測モード以外でエラーが出た場合は静かに空DFを返す
        return pd.DataFrame()
    
# ▼▼▼ [追加] シート一覧取得をキャッシュする関数 (API制限対策) ▼▼▼
@st.cache_data(ttl=30) # 60秒間は再通信しない
def get_sheet_names_cached():
    try:
        gc = get_gspread_client()
        sh = gc.open_by_url(SHEET_URL)
        return [ws.title for ws in sh.worksheets()]
    except Exception as e:
        return []

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

# ▼▼▼ v1.4.1 追加: グラフ用に時間を秒数(float)に変換する関数 ▼▼▼
def time_str_to_seconds(time_str):
    try:
        if pd.isna(time_str) or time_str == "": return 0.0
        # "MM:SS.f" 形式を想定
        if ":" in time_str:
            parts = time_str.split(":")
            if len(parts) == 2: # MM:SS.f
                m = int(parts[0])
                s = float(parts[1])
                return m * 60 + s
            elif len(parts) == 3: # HH:MM:SS
                h = int(parts[0])
                m = int(parts[1])
                s = float(parts[2])
                return h * 3600 + m * 60 + s
        return 0.0
    except:
        return 0.0

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
    
    # (HTMLコードは長いので省略せずそのまま記載します)
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
    components.html(html_code, height=70)

# ==========================================
# メイン処理（モード分岐）
# ==========================================
conn = st.connection("gsheets", type=GSheetsConnection)

st.sidebar.title("メニュー")

# ▼▼▼ v1.4.7 修正: type引数を使って、現在選択中のモードだけを赤(primary)にする ▼▼▼
# session_stateから現在のモードを取得（デフォルトは計測）
current_mode = st.session_state.get("app_mode", "⏱️ 計測モード")

# 各ボタンのタイプ（色）を決定
type_measure = "primary" if current_mode == "⏱️ 計測モード" else "secondary"
type_view    = "primary" if current_mode == "📈 閲覧モード" else "secondary"
type_admin   = "primary" if current_mode == "⚙️ 管理者モード" else "secondary"

# ボタン描画 (type引数を渡す)
st.sidebar.button("⏱️ 計測モード", on_click=set_mode, args=("⏱️ 計測モード",), type=type_measure, use_container_width=True)
st.sidebar.button("📈 閲覧モード", on_click=set_mode, args=("📈 閲覧モード",), type=type_view, use_container_width=True)
st.sidebar.button("⚙️ 管理者モード", on_click=set_mode, args=("⚙️ 管理者モード",), type=type_admin, use_container_width=True)

# 念のため app_mode 変数を更新
app_mode = current_mode

# 現在のモードをサイドバー下部に表示（確認用）
# st.sidebar.divider()
# st.sidebar.caption(f"現在のモード:\n**{app_mode}**")

# ==========================================
# 1. 計測モード (v1.4.0のロジックをここに集約)
# ==========================================
if app_mode == "⏱️ 計測モード":
    # 常に "log" シートを使用
    df = load_data(conn, WORKSHEET_NAME)

    # --- A. レース開始前 ---
    if df.empty or len(df) == 0:
        st.info("レース開始前")
        
        default_proj_name = f"Race_{datetime.now(JST).strftime('%Y%m%d')}"
        Race_name_input = st.text_input("📁 レース名", value=default_proj_name)
        
        if st.button("🔫 レーススタート (1区)", type="primary", use_container_width=True):
            now = datetime.now(JST)
            start_data = pd.DataFrame([{
                "Section": "1区", 
                "Location": "Start", 
                "Time": get_time_str(now),
                "KM-Lap": "00:00:00.0", 
                "SEC-Lap": "00:00:00.0", 
                "Split": "0:00:00",
                "Race": Race_name_input
            }])
            conn.update(spreadsheet=SHEET_URL, worksheet=WORKSHEET_NAME, data=start_data)
            st.cache_data.clear()
            st.success("レーススタート！")
            st.rerun()

        with st.expander("設定"):
            auto_reload_start = st.toggle("🔄 自動更新", value=True, key="auto_reload_start")
        
        if auto_reload_start:
            st_autorefresh(interval=2000, key="refresh_start")

    # --- B. レース進行中 or 終了後 ---
    else:
        last_row = df.iloc[-1]
        last_point = str(last_row['Location'])
        current_Race_name = df.iloc[0]['Race'] if 'Race' in df.columns else "Unknown"
        
        # フィニッシュ済み
        if last_point == "Finish":
            st.success("🏆 競技終了！お疲れ様でした！")
            st.metric("🏁 フィニッシュ時刻", last_row['Time'])
            st.metric("⏱️ 最終タイム", last_row['Split'])
            st.caption(f"📁 レース: {current_Race_name}")
            st.divider()
            st.markdown("### 📊 最終リザルト")
            st.dataframe(df, use_container_width=True)
            
            # 計測モード内の管理メニュー（アーカイブのみ残す）
            with st.expander("次のレースへ進む"):
                if st.button("📦 レース終了（ログ保存して次へ）", type="primary"):
                    try:
                        gc = get_gspread_client()
                        sh = gc.open_by_url(SHEET_URL)
                        
                        archive_name = f"{current_Race_name}_{datetime.now(JST).strftime('%Y%m%d_%H%M')}"
                        worksheet = sh.worksheet(WORKSHEET_NAME)
                        worksheet.update_title(archive_name)
                        
                        new_ws = sh.add_worksheet(title=WORKSHEET_NAME, rows=1000, cols=10)
                        new_ws.append_row(["Section", "Location", "Time", "KM-Lap", "SEC-Lap", "Split", "Race"])
                        new_ws.update_index(0)

                        st.cache_data.clear()
                        st.toast(f"ログを「{archive_name}」として保存しました！")
                        st.rerun()
                    except Exception as e:
                        st.error(f"保存エラー: {e}")
                
                # ※「デバッグ破棄」ボタンは管理者モードへ移動しました

            if st.toggle("🔄 自動更新", value=True, key="auto_reload_finish"):
                st_autorefresh(interval=10000, key="refresh_finish")
        
        # レース中
        else:
            @st.fragment(run_every=4)
            def show_race_dashboard():
                conn_frag = st.connection("gsheets", type=GSheetsConnection)
                current_df = load_data(conn_frag, WORKSHEET_NAME)
                if current_df.empty: return

                last_row = current_df.iloc[-1]
                last_point = str(last_row['Location'])
                last_time_obj = parse_time_str(last_row['Time'])
                first_time_obj = parse_time_str(current_df.iloc[0]['Time'])
                proj_name = current_df.iloc[0]['Race'] if 'Race' in current_df.columns else "Unknown"

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
                    st.caption(f"📁 Race: {proj_name}")
                with c_btn:
                    if st.button("🔄", help="即時更新"):
                        st.cache_data.clear()
                        st.rerun()

                now_calc = datetime.now(JST)
                elapsed_km = (now_calc - last_time_obj).total_seconds()
                sec_start = get_section_start_time(current_df, next_section_num)
                elapsed_sec = (now_calc - sec_start).total_seconds() if sec_start else 0
                elapsed_split = (now_calc - first_time_obj).total_seconds()
                show_js_timer(elapsed_km, elapsed_sec, elapsed_split)

                st.divider()

                now_for_record = datetime.now(JST)

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
                        fmt_time(total_sec),
                        proj_name
                    ]
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

            show_race_dashboard()
            
            if st.button("🏆 Finish", use_container_width=True):
                now_for_record = datetime.now(JST)
                last_row = df.iloc[-1]
                last_time_obj = parse_time_str(last_row['Time'])
                first_time_obj = parse_time_str(df.iloc[0]['Time'])
                proj_name = df.iloc[0]['Race'] if 'Race' in df.columns else "Unknown"

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
                    fmt_time(total_sec),
                    proj_name
                ]
                gc = get_gspread_client()
                gc.open_by_url(SHEET_URL).worksheet(WORKSHEET_NAME).append_row(values, value_input_option='USER_ENTERED')
                st.cache_data.clear()
                st.rerun()

            st.divider()
            with st.expander("📊 計測ログを表示"):
                st.dataframe(df.iloc[::-1], use_container_width=True)


# ==========================================
# 2. 閲覧モード (過去ログ & グラフ)
# ==========================================
elif app_mode == "📈 閲覧モード":
    st.header("📈 閲覧モード")
    
    # ▼▼▼ 修正: キャッシュ付き関数を使用 ▼▼▼
    sheet_names = get_sheet_names_cached()
    
    if sheet_names:
        # シート選択 (デフォルトは log)
        # リストに 'log' があればそれを初期値に、なければ先頭に
        default_index = 0
        if WORKSHEET_NAME in sheet_names:
            default_index = sheet_names.index(WORKSHEET_NAME)
        
        # シート選択 (デフォルトは latest-log)
        selected_sheet = st.selectbox("閲覧するシートを選択", sheet_names, index=0)
        
        if st.button("データを読み込む"):
            # 選択されたシートのデータを読み込む
            # st.cache_dataを効かせるため、conn.readを使うが、ttlは少し長めに
            view_df = load_data(conn, selected_sheet)
            
            if not view_df.empty:
                st.write(f"### {selected_sheet} の記録")
                
                # ▼▼▼ v1.4.1 追加: グラフ可視化 ▼▼▼
                st.subheader("📈 ペース推移")
                
                # ▼▼▼ v1.4.4 変更: KM-Lapを使用し、X軸を通算indexにして連続表示する ▼▼▼
                graph_df = view_df.copy()
                # SEC-LapではなくKM-Lapを使用
                graph_df['Seconds'] = graph_df['KM-Lap'].apply(time_str_to_seconds)
                # スタート地点を除外
                graph_df = graph_df[graph_df['Location'] != 'Start']
                
                # 連番（Seq）を振ってX軸を連続させる
                graph_df = graph_df.reset_index(drop=True)
                graph_df['Seq'] = graph_df.index + 1
                # ツールチップ用にラベル作成
                graph_df['Label'] = graph_df['Section'] + " - " + graph_df['Location']

                if not graph_df.empty:
                    base_date = datetime(2000, 1, 1)
                    graph_df['TimeObj'] = graph_df['Seconds'].apply(lambda s: base_date + timedelta(seconds=s))
                    
                    chart = alt.Chart(graph_df).mark_line(point=True, color='#4bd6ff').encode(
                        # X軸をSeq（連番）にして連続させる。タイトルは通過ポイントとする
                        x=alt.X('Seq', title='通過ポイント (順序)'),
                        y=alt.Y('TimeObj', title='キロラップ (分:秒)', axis=alt.Axis(format='%M:%S')),
                        tooltip=['Label', alt.Tooltip('TimeObj', format='%M:%S', title='タイム')]
                    ).properties(
                        height=400
                    ).interactive()
                    
                    st.altair_chart(chart, use_container_width=True)
                else:
                    st.info("グラフ表示用のデータがありません")

                st.divider()
                st.dataframe(view_df, use_container_width=True)

            else:
                st.warning("データが空か、読み込めませんでした。")
                        
    else:
        st.error("シート一覧を取得できませんでした (API制限の可能性があります。しばらく待って再読み込みしてください)")


# ==========================================
# 3. 管理者モード (デバッグ・メンテナンス)
# ==========================================
elif app_mode == "⚙️ 管理者モード":
    st.header("⚙️ 管理者メニュー")
    
    # 簡易パスワード認証
    pwd = ADMIN_PASSWORD # st.text_input("パスワードを入力してください", type="password")
    
    if pwd == ADMIN_PASSWORD:
        st.success("認証成功")
        st.divider()
        st.write("### 🚨 デバッグ・緊急操作エリア")
        st.warning("※ここでの操作は取り消せません。慎重に行ってください。")
        
        # ▼▼▼ v1.4.1: デバッグ用破棄ボタンを移動 ▼▼▼
        if st.button("🗑️ [デバッグ] logデータを強制破棄 (アーカイブなし)"):
            try:
                gc = get_gspread_client()
                sh = gc.open_by_url(SHEET_URL)
                
                worksheet = sh.worksheet(WORKSHEET_NAME)
                worksheet.clear()
                worksheet.append_row(["Section", "Location", "Time", "KM-Lap", "SEC-Lap", "Split", "Race"])
                worksheet.update_index(0)

                st.cache_data.clear()
                st.success("logシートを初期化しました。")
            except Exception as e:
                st.error(f"リセットエラー: {e}")
                
    elif pwd != "":
        st.error("パスワードが違います")