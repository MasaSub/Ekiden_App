# ==========================================
# version = 2.0.1 date = 2026/01/11
# ==========================================

import streamlit as st
import pandas as pd
import math
import gspread
import altair as alt
from google.oauth2.service_account import Credentials
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from streamlit_gsheets import GSheetsConnection
from streamlit_autorefresh import st_autorefresh
import streamlit.components.v1 as components

# ==========================================
# 設定・定数
# ==========================================
VERSION = "ver 2.0.1"

SHEET_URL = "https://docs.google.com/spreadsheets/d/1-GSNYQYulO-83vdMOn7Trqv4l6eCjo9uzaP20KQgSS4/edit" # 【要修正】URL確認
WORKSHEET_LOG = "latest-log"
WORKSHEET_CONFIG = "config"
JST = ZoneInfo("Asia/Tokyo")
CACHE_TTL_SEC = 2.0
ADMIN_PASSWORD = "0000"

# ページ設定
st.set_page_config(page_title="えきでんくん", page_icon="🎽", layout="wide")

# ==========================================
# CSSデザイン定義 (v2.0.0準拠)
# ==========================================
st.markdown("""
    <style>
    .stApp { overflow-x: hidden; }
    
    /* 全体の余白を詰める */
    .block-container { padding-top: 3rem; padding-bottom: 3rem; padding-left: 0.5rem; padding-right: 0.5rem; }
    
    section[data-testid="stSidebar"] { background-color: #262730; color: white; }
    
    /* ボタンのスタイル調整 */
    div.stButton > button {
        height: auto !important;
        min-height: 3.5em;
        padding: 0.2em 0.5em;
        font-size: 18px !important; 
        font-weight: bold !important; 
        border-radius: 10px; 
        width: 100%;
        margin-bottom: 0px !important;
        line-height: 1.2 !important;
    }
    
    /* Primaryボタン(赤) */
    div.stButton > button[kind="primary"] {
        background-color: #FF4B4B; 
        color: white; 
        border: 1px solid #555; 
    }
    
    /* Secondaryボタン(ダーク) */
    div.stButton > button[kind="secondary"] {
        background-color: #262730; 
        color: white;              
        border: 1px solid #555;    
    }
    div.stButton > button[kind="secondary"]:hover {
        background-color: #444;    
        border-color: #888;
        color: white;
    }
    
    /* 最後のボタン(Undo)を薄めグレーにする */
    div.block-container > div[data-testid="stVerticalBlock"] > div:last-child button[kind="secondary"] {
        background-color: #555555 !important;
        color: #eeeeee !important;
        border: 1px solid #777 !important;
    }

    /* 数値入力 */
    div[data-testid="stNumberInput"] input { font-size: 1.4rem; font-weight: bold; height: 3.0rem; text-align: center; }
    div[data-testid="stNumberInput"] button { height: 3.0rem; width: 3.0rem; }

    /* 見出し調整 */
    h1, h2, h3 { margin: 0; padding: 0; }
    </style>
    """, unsafe_allow_html=True)

# ==========================================
# 関数定義
# ==========================================
def get_gspread_client():
    scope = ['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive']
    credentials = dict(st.secrets["connections"]["gsheets"])
    creds = Credentials.from_service_account_info(credentials, scopes=scope)
    return gspread.authorize(creds)

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

def fmt_time(sec):
    sec = math.ceil(sec)
    m, s = divmod(int(sec), 60)
    h, m = divmod(m, 60)
    return f"{h:01}:{m:02}:{s:02}"

def fmt_lap(sec):
    total_tenths = math.ceil(sec * 10)
    rem_tenths = total_tenths % 10
    total_sec = total_tenths // 10
    m, s = divmod(total_sec, 60)
    return f"{m:02}:{s:02}.{rem_tenths}"

def load_data(conn, sheet_name):
    try:
        df = conn.read(spreadsheet=SHEET_URL, worksheet=sheet_name, ttl=CACHE_TTL_SEC)
        if not df.empty:
            for col in df.columns:
                df[col] = df[col].astype(str).str.replace(r'\.0$', '', regex=True)
        return df
    except Exception:
        return pd.DataFrame()

def fetch_config_from_sheet(conn):
    try:
        df = conn.read(spreadsheet=SHEET_URL, worksheet=WORKSHEET_CONFIG, ttl=0)
        if df.empty: return None
        config = {}
        for _, row in df.iterrows():
            config[str(row['Key'])] = str(row['Value'])
        return config
    except:
        return None

def initialize_race(race_name, section_count, teams_dict, main_team_id):
    gc = get_gspread_client()
    sh = gc.open_by_url(SHEET_URL)
    try: 
        ws_log = sh.worksheet(WORKSHEET_LOG)
        ws_log.clear()
        ws_log.append_row(["TeamID", "TeamName", "Section", "Location", "Time", "KM-Lap", "SEC-Lap", "Split", "Rank", "Race"])
    except: pass
    try: 
        ws_conf = sh.worksheet(WORKSHEET_CONFIG)
        ws_conf.clear()
        ws_conf.append_row(["Key", "Value"])
    except: pass
    
    config_data = [
        ["RaceName", race_name],
        ["SectionCount", str(section_count)],
        ["MainTeamID", str(main_team_id)],
        ["TeamCount", str(len(teams_dict))]
    ]
    for tid, tname in teams_dict.items():
        config_data.append([f"TeamName_{tid}", tname])
    
    ws_conf.append_rows(config_data)
    st.cache_data.clear()
    
    new_config = {}
    for item in config_data:
        new_config[item[0]] = item[1]
    st.session_state["race_config"] = new_config

# ▼▼▼ JavaScriptタイマー表示関数 (v2.0.1で追加) ▼▼▼
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
            background-color: #262730; padding: 10px 5px; border-radius: 12px;
            border: 1px solid #444; color: white;
            box-sizing: border-box; width: 100%; margin-bottom: 5px;
        }}
        .timer-box {{ text-align: center; flex: 1; }}
        .label {{ font-size: 10px; color: #aaa; margin-bottom: 2px; }}
        .value {{ font-size: 20px; font-weight: bold; line-height: 1.1; font-family: monospace; }}
        .separator {{ width: 1px; height: 35px; background-color: #555; }}
        .decimal {{ font-size: 0.6em; opacity: 0.7; }}
        .color-km {{ color: #4bd6ff; }}
        .color-sec {{ color: #ff4b4b; }}
        .color-total {{ color: #ffffff; }}
    </style>
    </head>
    <body>
    <div class="timer-container">
        <div class="timer-box">
            <div class="label">Last Lap</div>
            <div id="km-val" class="value color-km">--:--.--</div>
        </div>
        <div class="separator"></div>
        <div class="timer-box">
            <div class="label">Section</div>
            <div id="sec-val" class="value color-sec">--:--.--</div>
        </div>
        <div class="separator"></div>
        <div class="timer-box">
            <div class="label">Total</div>
            <div id="split-val" class="value color-total">--:--:--</div>
        </div>
    </div>
    <script>
        const now = Date.now();
        const startKm = now - {km_ms};
        const startSec = now - {sec_ms};
        const startSplit = now - {split_ms};

        function fmt(ms, isSplit) {{
            if (ms < 0) return "--:--.--";
            const totalTenths = Math.floor(ms / 100);
            const totalSec = Math.floor(ms / 1000);
            const h = Math.floor(totalSec / 3600);
            const m = Math.floor((totalSec % 3600) / 60);
            const s = totalSec % 60;
            const dec = Math.floor((ms % 1000) / 100); 
            const mStr = String(m).padStart(2,'0');
            const sStr = String(s).padStart(2,'0');
            if (isSplit) {{ return `${{h}}:${{mStr}}:${{sStr}}`; }} 
            else {{ return `${{mStr}}:${{sStr}}<span class="decimal">.${{dec}}</span>`; }}
        }}
        function update() {{
            const cur = Date.now();
            document.getElementById("km-val").innerHTML = fmt(cur - startKm, false);
            document.getElementById("sec-val").innerHTML = fmt(cur - startSec, false);
            document.getElementById("split-val").innerHTML = fmt(cur - startSplit, true);
        }}
        setInterval(update, 100);
        update();
    </script>
    </body>
    </html>
    """
    components.html(html_code, height=85)

# ==========================================
# アプリのモード管理 & Configロード
# ==========================================
conn = st.connection("gsheets", type=GSheetsConnection)

if "race_config" not in st.session_state:
    st.session_state["race_config"] = None

if st.session_state["race_config"] is None:
    loaded_conf = fetch_config_from_sheet(conn)
    if loaded_conf:
        st.session_state["race_config"] = loaded_conf

config = st.session_state["race_config"]

if "app_mode" not in st.session_state:
    st.session_state["app_mode"] = "🏁 レース作成"

if config is None or "RaceName" not in config:
    st.session_state["app_mode"] = "🏁 レース作成"

df_for_check = load_data(conn, WORKSHEET_LOG)
is_race_started = not df_for_check.empty

# サイドバー
st.sidebar.markdown(f"""
    <div style="margin-bottom: 20px;">
        <h2 style="margin:0; padding:0; color:white;">🎽 えきでんくん</h2>
        <div style="color: #aaa; font-size: 14px; margin-top: 4px;">{VERSION}</div>
    </div>
""", unsafe_allow_html=True)

st.sidebar.title("モード選択")

menu_options = [
    "🏁 レース作成",
    "⏱️ 記録点モード",
    "🎽 中継点モード",
    "📣 観戦モード",
    "📈 分析モード",
    "⚙️ 管理者モード"
]

if is_race_started and config is not None:
    if "🏁 レース作成" in menu_options:
        menu_options.remove("🏁 レース作成")

def change_mode(m):
    st.session_state["app_mode"] = m

for m in menu_options:
    disabled = False
    if (config is None) and (m not in ["🏁 レース作成", "⚙️ 管理者モード"]):
        disabled = True
    
    k = "primary" if st.session_state["app_mode"] == m else "secondary"
    st.sidebar.button(m, on_click=change_mode, args=(m,), type=k, disabled=disabled)

current_mode = st.session_state["app_mode"]

# ==========================================
# 1. 🏁 レース作成
# ==========================================
if current_mode == "🏁 レース作成":
    st.header("🏁 レース作成")
    
    if is_race_started and config is not None:
        st.session_state["app_mode"] = "⏱️ 記録点モード"
        st.rerun()
    
    if is_race_started:
        st.warning("レース進行中のため作成できません。")
        st.stop()

    team_count = st.number_input("チーム数", min_value=1, max_value=20, value=3)
    
    with st.form("setup_form"):
        race_name = st.text_input("レース名", value=f"Race_{datetime.now(JST).strftime('%Y%m%d')}")
        section_count = st.number_input("区間数", min_value=1, value=5)
        st.divider()
        st.write("チーム設定")
        teams_input = {}
        cols = st.columns(2)
        main_team_options = []
        for i in range(1, team_count + 1):
            with cols[(i-1)%2]:
                tid = st.text_input(f"Team{i} No.", value=str(i), key=f"tid_{i}")
                tname = st.text_input(f"Team{i} 名前", value=f"チーム{i}", key=f"tname_{i}")
                teams_input[tid] = tname
                main_team_options.append(tid)
        st.divider()
        main_team_sel = st.selectbox("★メインチーム", main_team_options)
        
        if st.form_submit_button("設定を保存してスタート", type="primary", use_container_width=True):
            initialize_race(race_name, section_count, teams_input, main_team_sel)
            st.success("セットアップ完了！")
            st.session_state["app_mode"] = "⏱️ 記録点モード"
            st.rerun()

# ==========================================
# 共通ロジック & 各種モード
# ==========================================
elif current_mode in ["⏱️ 記録点モード", "🎽 中継点モード", "📣 観戦モード", "📈 分析モード"]:
    if not config:
        st.error("設定が読み込めません。")
        st.stop()

    df = df_for_check
    
    teams_info = {}
    team_ids_ordered = []
    main_team_id = config.get("MainTeamID", "1")
    total_sections = int(config.get("SectionCount", 5))
    
    for k, v in config.items():
        if k.startswith("TeamName_"):
            tid = k.replace("TeamName_", "")
            teams_info[tid] = v
            team_ids_ordered.append(tid)
    
    if main_team_id in team_ids_ordered:
        team_ids_ordered.remove(main_team_id)
        team_ids_ordered.insert(0, main_team_id)

    team_status = {}
    if not df.empty:
        for tid in team_ids_ordered:
            t_df = df[df['TeamID'] == tid]
            if not t_df.empty:
                team_status[tid] = t_df.iloc[-1]
            else:
                team_status[tid] = None

    # -------------------------------------
    # ⏱️ 記録点モード & 🎽 中継点モード (v2.0.0仕様維持)
    # -------------------------------------
    if current_mode in ["⏱️ 記録点モード", "🎽 中継点モード"]:
        
        if df.empty:
            st.info("レース前")
            if st.button("🔫 スタート", type="primary", use_container_width=True):
                now = datetime.now(JST)
                start_rows = []
                for tid in team_ids_ordered:
                    start_rows.append([
                        tid, teams_info[tid], "1区", "Start", get_time_str(now),
                        "00:00:00.0", "00:00:00.0", "0:00:00", "1", config["RaceName"]
                    ])
                gc = get_gspread_client()
                gc.open_by_url(SHEET_URL).worksheet(WORKSHEET_LOG).append_rows(start_rows)
                st.cache_data.clear()
                st.rerun()
            st.stop()

        def record_point(tid, section, location, is_finish=False):
            now = datetime.now(JST)
            t_df = df[df['TeamID'] == tid]
            if t_df.empty: return
            last = t_df.iloc[-1]
            last_time = parse_time_str(last['Time'])
            
            try:
                start_row = t_df[t_df['Location'] == 'Start'].iloc[0]
                start_time = parse_time_str(start_row['Time'])
            except:
                start_time = now

            sec_start_time = start_time
            if section != "1区":
                prev_sec_end = t_df[(t_df['Section'] == f"{int(section.replace('区',''))-1}区") & (t_df['Location'] == 'Relay')]
                if not prev_sec_end.empty:
                    sec_start_time = parse_time_str(prev_sec_end.iloc[0]['Time'])

            km_lap = (now - last_time).total_seconds()
            sec_lap = (now - sec_start_time).total_seconds()
            split = (now - start_time).total_seconds()
            rank = len(df[(df['Section'] == section) & (df['Location'] == location)]) + 1

            new_row = [
                tid, teams_info[tid], section, location, get_time_str(now),
                fmt_lap(km_lap), fmt_lap(sec_lap), fmt_time(split), str(rank), config["RaceName"]
            ]
            gc = get_gspread_client()
            gc.open_by_url(SHEET_URL).worksheet(WORKSHEET_LOG).append_row(new_row)
            st.cache_data.clear()
            st.toast(f"{teams_info[tid]}: {location} 記録完了")

        target_km = 1
        if current_mode == "⏱️ 記録点モード":
            target_km = st.number_input("記録する地点 (km)", min_value=1, max_value=50, value=1)
        
        st.write("") 

        # チームボタン一覧 (ご指定の仕様通り)
        for tid in team_ids_ordered:
            status = team_status.get(tid)
            t_name = teams_info.get(tid, tid)
            is_main = (tid == main_team_id)
            btn_type = "primary" if is_main else "secondary"
            
            # 全チームをPrimary(赤)として扱う
            btn_type = "primary"
            
            if status is None:
                st.button(f"【{tid}】{t_name} (No Data)", disabled=True, key=f"btn_none_{tid}")
                continue
            
            last_loc = str(status['Location'])
            curr_sec_str = str(status['Section'])

            # Finish済みはボタンを押せなくする
            if last_loc == "Finish":
                st.button(f"🏁 【{tid}】{t_name} (Finish)", disabled=True, key=f"btn_fin_stat_{tid}")
                continue

            try: 
                curr_sec_num = int(curr_sec_str.replace("区", ""))
            except: 
                curr_sec_num = 1

            if last_loc == "Relay":
                curr_sec_num += 1
                curr_sec_str = f"{curr_sec_num}区"
            
            # ボタン生成
            if current_mode == "⏱️ 記録点モード":
                label = f"【No.{tid}】 {t_name}  ▶  {target_km}km"
                if st.button(label, key=f"btn_dist_{tid}", type=btn_type, use_container_width=True):
                    record_point(tid, curr_sec_str, f"{target_km}km")
                    st.rerun()

            elif current_mode == "🎽 中継点モード":
                is_anchor = (curr_sec_num >= total_sections)
                
                if is_anchor:
                    label = f"🏆 【No.{tid}】 {t_name}  ▶  Finish"
                    if st.button(label, key=f"btn_fin_{tid}", type="primary", use_container_width=True):
                        record_point(tid, curr_sec_str, "Finish", is_finish=True)
                        st.rerun()
                else:
                    next_sec = f"{curr_sec_num + 1}区"
                    label = f"🎽 【No.{tid}】 {t_name}  ▶  Relay ({next_sec})"
                    if st.button(label, key=f"btn_rel_{tid}", type=btn_type, use_container_width=True):
                        record_point(tid, curr_sec_str, "Relay")
                        st.rerun()
        
        # ひとつ戻るボタン
        st.markdown("<hr style='margin: 15px 0;'>", unsafe_allow_html=True)
        if st.button("↩️ 元に戻す", use_container_width=True, type="secondary"):
            try:
                gc = get_gspread_client()
                ws = gc.open_by_url(SHEET_URL).worksheet(WORKSHEET_LOG)
                all_vals = ws.get_all_values()
                if len(all_vals) > 1:
                    ws.delete_rows(len(all_vals))
                    st.cache_data.clear()
                    st.toast("直前の記録を削除しました")
                    st.rerun()
                else:
                    st.warning("削除できるデータがありません")
            except Exception as e:
                st.error(f"Undoエラー: {e}")

    # -------------------------------------
    # 📣 観戦モード (v2.0.1で改修)
    # -------------------------------------
    elif current_mode == "📣 観戦モード":
        # 5秒自動更新
        st_autorefresh(interval=5000, key="watch_refresh")
        
        # 1. チーム選択をメイン上部に配置
        if "watch_tid" not in st.session_state:
            st.session_state["watch_tid"] = main_team_id
        
        team_options = {tid: f"【{tid}】{teams_info.get(tid, '')}" for tid in team_ids_ordered}
        
        # チームID順序リストの中に保存されているIDがあるか確認し、あればそのインデックスを使う
        curr_idx = 0
        if st.session_state["watch_tid"] in team_ids_ordered:
            curr_idx = team_ids_ordered.index(st.session_state["watch_tid"])

        selected_tid = st.selectbox(
            "📣 応援するチームを選択", 
            options=team_ids_ordered, 
            format_func=lambda x: team_options[x],
            index=curr_idx
        )
        st.session_state["watch_tid"] = selected_tid

        t_df = df[df['TeamID'] == selected_tid]
        
        if t_df.empty:
            st.info("まだ記録がありません")
        else:
            last = t_df.iloc[-1]
            last_time = parse_time_str(last['Time'])
            now = datetime.now(JST)
            t_name = teams_info.get(selected_tid, selected_tid)
            
            # 2. ヘッダー情報
            st.markdown(f"""
                <div style='text-align: center; margin-top: -10px;'>
                    <h2 style='margin:0; font-size: 24px;'>📣 {t_name}</h2>
                    <div style='font-size: 18px; font-weight: bold; color: #4bd6ff;'>
                        {last['Section']} <span style='color: white;'>|</span> {last['Location']}
                        <span style='margin-left: 10px; font-size: 22px; color: #FF4B4B;'>{last['Rank']}位</span>
                    </div>
                </div>
            """, unsafe_allow_html=True)
            
            # 3. JSタイマー
            try:
                start_row = t_df[t_df['Location'] == 'Start'].iloc[0]
                start_time = parse_time_str(start_row['Time'])
            except:
                start_time = now

            sec_start_time = start_time
            if last['Section'] != "1区":
                prev_sec_num = int(last['Section'].replace("区", "")) - 1
                prev_relay = t_df[(t_df['Section'] == f"{prev_sec_num}区") & (t_df['Location'] == 'Relay')]
                if not prev_relay.empty:
                    sec_start_time = parse_time_str(prev_relay.iloc[0]['Time'])

            elapsed_km = (now - last_time).total_seconds()
            elapsed_sec = (now - sec_start_time).total_seconds()
            elapsed_split = (now - start_time).total_seconds()
            
            if last['Location'] == 'Finish':
                st.success(f"🏁 Finish Time: {last['Split']}")
            else:
                show_js_timer(elapsed_km, elapsed_sec, elapsed_split)

            # 追加: ペース表示
            try:
                def str_to_sec(s):
                    if ":" not in s: return 0
                    parts = s.split(":")
                    if len(parts)==2: return int(parts[0])*60 + float(parts[1])
                    if len(parts)==3: return int(parts[0])*3600 + int(parts[1])*60 + float(parts[2])
                    return 0
                
                last_lap_str = str(last['KM-Lap'])
                last_lap_val = str_to_sec(last_lap_str)
                
                if last_lap_val > 0 and "km" in last['Location']:
                    pace_min = int(last_lap_val // 60)
                    pace_sec = int(last_lap_val % 60)
                    st.markdown(f"""
                        <div style='text-align: center; background-color: #333; padding: 5px; border-radius: 5px; margin-bottom: 10px;'>
                            🏃 直近ペース: <span style='font-weight:bold; color:#4bd6ff;'>{pace_min}:{pace_sec:02} /km</span>
                        </div>
                    """, unsafe_allow_html=True)
            except: pass

            # 4. 前後チーム差
            loc_df = df[(df['Section'] == last['Section']) & (df['Location'] == last['Location'])].sort_values("Time").reset_index(drop=True)
            
            # インデックス取得
            my_indices = loc_df.index[loc_df['TeamID'] == selected_tid].tolist()
            if my_indices:
                my_idx = my_indices[0]
                c_prev, c_next = st.columns(2)
                
                with c_prev:
                    if my_idx > 0:
                        prev_row = loc_df.iloc[my_idx - 1]
                        prev_time_obj = parse_time_str(prev_row['Time'])
                        diff = (last_time - prev_time_obj).total_seconds()
                        prev_name = teams_info.get(prev_row['TeamID'], prev_row['TeamID'])
                        st.info(f"⬆️ 前: **{prev_name}**\n\n+{fmt_time(diff)}")
                    else:
                        st.success("👑 現在トップ！")

                with c_next:
                    if my_idx < len(loc_df) - 1:
                        next_row = loc_df.iloc[my_idx + 1]
                        next_time_obj = parse_time_str(next_row['Time'])
                        diff = (next_time_obj - last_time).total_seconds()
                        next_name = teams_info.get(next_row['TeamID'], next_row['TeamID'])
                        st.warning(f"⬇️ 後ろ: **{next_name}**\n\n-{fmt_time(diff)}")
                    else:
                        st.write("（後ろはいません）")

            # 5. 履歴テーブル
            st.write("📝 通過履歴")
            history_df = t_df[['Section', 'Location', 'Split', 'KM-Lap', 'Rank']].iloc[::-1]
            st.dataframe(history_df, use_container_width=True, hide_index=True)

    # -------------------------------------
    # 📈 分析モード
    # -------------------------------------
    elif current_mode == "📈 分析モード":
        if st.button("データ更新"):
            st.cache_data.clear()
            st.rerun()

        points = df[['Section', 'Location']].drop_duplicates()
        graph_data = []
        for _, pt in points.iterrows():
            sec, loc = pt['Section'], pt['Location']
            if loc == 'Start': continue
            p_df = df[(df['Section'] == sec) & (df['Location'] == loc)]
            if not p_df.empty:
                p_df = p_df.sort_values("Time")
                rank = 1
                for _, row in p_df.iterrows():
                    graph_data.append({
                        "Team": teams_info.get(row['TeamID'], row['TeamID']),
                        "Point": f"{sec}-{loc}",
                        "Rank": rank,
                        "Time": row['Time']
                    })
                    rank += 1
        
        if graph_data:
            g_df = pd.DataFrame(graph_data)
            import altair as alt
            chart = alt.Chart(g_df).mark_line(point=True).encode(
                x=alt.X('Point', sort=None, title='通過地点'),
                y=alt.Y('Rank', scale=alt.Scale(reverse=True), title='順位'),
                color='Team',
                tooltip=['Team', 'Point', 'Rank', 'Time']
            ).properties(height=500).interactive()
            st.altair_chart(chart, use_container_width=True)
        else:
            st.info("グラフデータがまだありません")

# ==========================================
# ⚙️ 管理者モード
# ==========================================
elif current_mode == "⚙️ 管理者モード":
    st.header("⚙️ 管理者モード")
    pwd = st.text_input("パスワード", type="password")
    
    if pwd == ADMIN_PASSWORD:
        st.success("認証成功")
        
        if st.button("設定データを強制リロード"):
            st.session_state["race_config"] = None
            st.cache_data.clear()
            st.rerun()

        st.divider()
        st.write("### 🚨 プロジェクトリセット")
        if st.button("🗑️ 現在のレースデータを全消去 (セットアップに戻る)"):
            gc = get_gspread_client()
            sh = gc.open_by_url(SHEET_URL)
            try: 
                ws_log = sh.worksheet(WORKSHEET_LOG)
                ws_log.clear()
                # 削除直後にヘッダーを書き込む
                ws_log.append_row(["TeamID", "TeamName", "Section", "Location", "Time", "KM-Lap", "SEC-Lap", "Split", "Rank", "Race"])
            except: pass
            
            try: sh.worksheet(WORKSHEET_CONFIG).clear()
            except: pass
            
            st.cache_data.clear()
            st.session_state["race_config"] = None
            st.session_state["app_mode"] = "🏁 レース作成"
            st.rerun()
            
        st.divider()
        st.write("### 📝 データ直接編集")
        edit_df = load_data(conn, WORKSHEET_LOG)
        if not edit_df.empty:
            edited = st.data_editor(edit_df, num_rows="dynamic")
            if st.button("保存"):
                conn.update(spreadsheet=SHEET_URL, worksheet=WORKSHEET_LOG, data=edited)
                st.cache_data.clear()
                st.toast("保存しました")

# ▼▼▼ 迷子防止（どのモードにも当てはまらない場合） ▼▼▼
else:
    st.session_state["app_mode"] = "🏁 レース作成"
    st.rerun()