# ==========================================
# version = 2.0.6 date = 2026/01/17
# ==========================================

import streamlit as st
import pandas as pd
import math
import gspread
import altair as alt
from google.oauth2.service_account import Credentials
from datetime import datetime
from zoneinfo import ZoneInfo
from streamlit_gsheets import GSheetsConnection
from streamlit_autorefresh import st_autorefresh
import streamlit.components.v1 as components

# ==========================================
# 設定・定数
# ==========================================
VERSION = "ver 2.0.6"

SHEET_URL = "https://docs.google.com/spreadsheets/d/1-GSNYQYulO-83vdMOn7Trqv4l6eCjo9uzaP20KQgSS4/edit" # 【要修正】URL確認
WORKSHEET_LOG = "latest-log"
WORKSHEET_CONFIG = "config"
WORKSHEET_INDEX = "race_index"
JST = ZoneInfo("Asia/Tokyo")

# 軽量化: キャッシュと更新間隔を長めにとる
CACHE_TTL_SEC = 15.0 
AUTOREFRESH_INTERVAL = 15000 # 15秒

ADMIN_PASSWORD = "0000"

st.set_page_config(page_title="えきでんくん", page_icon="🎽", layout="wide")

# ==========================================
# CSSデザイン
# ==========================================
st.markdown("""
    <style>
    .stApp { overflow-x: hidden; }
    .block-container { padding-top: 3rem; padding-bottom: 3rem; padding-left: 0.5rem; padding-right: 0.5rem; }
    section[data-testid="stSidebar"] { background-color: #262730; color: white; }
    
    div.stButton > button {
        height: auto !important; min-height: 3.5em; padding: 0.2em 0.5em;
        font-size: 18px !important; font-weight: bold !important; border-radius: 10px; 
        width: 100%; margin-bottom: 0px !important; line-height: 1.2 !important;
    }
    /* メインチーム用 (赤) */
    div.stButton > button[kind="primary"] { background-color: #FF4B4B; color: white; border: 1px solid #555; }
    /* その他チーム用 (黒) */
    div.stButton > button[kind="secondary"] { background-color: #262730; color: white; border: 1px solid #555; }
    div.stButton > button[kind="secondary"]:hover { background-color: #444; border-color: #888; color: white; }
    
    /* Undoボタン等は少し薄く */
    div.block-container > div[data-testid="stVerticalBlock"] > div:last-child button[kind="secondary"] {
        background-color: #555555 !important; color: #eeeeee !important; border: 1px solid #777 !important;
    }
    div[data-testid="stNumberInput"] input { font-size: 1.4rem; font-weight: bold; height: 3.0rem; text-align: center; }
    div[data-testid="stNumberInput"] button { height: 3.0rem; width: 3.0rem; }
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

def get_time_str(dt): return dt.strftime("%H:%M:%S.%f")[:10]

def parse_time_str(time_str):
    now = datetime.now(JST)
    if not isinstance(time_str, str) or not time_str: return now
    try:
        if "." in time_str: t = datetime.strptime(time_str + "00000", "%H:%M:%S.%f").time()
        else: t = datetime.strptime(time_str, "%H:%M:%S").time()
        return datetime.combine(now.date(), t).replace(tzinfo=JST)
    except: return now

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

def str_to_sec(time_str):
    if not isinstance(time_str, str) or not time_str: return 0.0
    try:
        parts = time_str.split(':')
        if len(parts) == 3: return int(parts[0])*3600 + int(parts[1])*60 + float(parts[2])
        elif len(parts) == 2: return int(parts[0])*60 + float(parts[1])
        return 0.0
    except: return 0.0

def fmt_diff(sec):
    if sec is None: return "-"
    sign = "+" if sec > 0 else "-" if sec < 0 else "±"
    return f"{sign}{fmt_time(abs(sec))}"

def load_data(conn, sheet_name):
    """
    データを読み込み、アプリ側でラップ・スプリット・順位を自動計算して付与する。
    """
    try:
        df = conn.read(spreadsheet=SHEET_URL, worksheet=sheet_name, ttl=CACHE_TTL_SEC)
        if df.empty: return pd.DataFrame()
        
        # 数値変換など
        for col in df.columns:
            df[col] = df[col].astype(str).str.replace(r'\.0$', '', regex=True)
        
        # --- 自動計算ロジック (v2.0.6) ---
        df['dt'] = df['Time'].apply(parse_time_str)
        df = df.sort_values('dt')
        
        df['SplitSeconds'] = 0.0
        df['SectionSeconds'] = 0.0
        df['PointSeconds'] = 0.0
        
        try:
            start_time = df[df['Location'] == 'Start']['dt'].min()
        except:
            start_time = datetime.now(JST)

        team_groups = df.groupby('TeamID')
        calculated_rows = []
        
        for tid, group in team_groups:
            group = group.sort_values('dt')
            group['SplitSeconds'] = (group['dt'] - start_time).dt.total_seconds()
            
            # Point Lap (直前との差)
            group['PointSeconds'] = group['SplitSeconds'].diff().fillna(0)
            
            # Section Lap (簡易ロジック: Start/Relayからの差)
            sec_laps = []
            last_relay_time = start_time
            
            for _, row in group.iterrows():
                current_time = row['dt']
                sec_val = (current_time - last_relay_time).total_seconds()
                sec_laps.append(sec_val)
                if row['Location'] == 'Relay' or row['Location'] == 'Start':
                    last_relay_time = current_time 
            
            group['SectionSeconds'] = sec_laps
            calculated_rows.append(group)
            
        if calculated_rows:
            df_calc = pd.concat(calculated_rows)
            df_calc['Split'] = df_calc['SplitSeconds'].apply(fmt_time)
            df_calc['KM-Lap'] = df_calc['PointSeconds'].apply(fmt_lap) # KM-Lapカラムを再利用(実質PointLap)
            df_calc['SEC-Lap'] = df_calc['SectionSeconds'].apply(fmt_lap)
            
            # 順位計算 (通過順)
            df_calc['Rank'] = df_calc.groupby(['Section', 'Location'])['dt'].rank(method='first').astype(int)
            return df_calc.sort_index()
            
        return df
    except Exception:
        return pd.DataFrame()

def fetch_config_from_sheet(conn, sheet_name=WORKSHEET_CONFIG):
    try:
        df = conn.read(spreadsheet=SHEET_URL, worksheet=sheet_name, ttl=0)
        if df.empty: return None
        config = {}
        for _, row in df.iterrows():
            config[str(row['Key'])] = str(row['Value'])
        return config
    except: return None

# --- UI描画ロジック (分析画面) ---
def render_analysis_dashboard(df, teams_info):
    analysis_data = []
    points_order = df[['Section', 'Location']].drop_duplicates()
    points_order = points_order[points_order['Location'] != 'Start']
    
    for _, pt in points_order.iterrows():
        sec, loc = pt['Section'], pt['Location']
        pt_label = f"{sec} {loc}"
        p_df = df[(df['Section'] == sec) & (df['Location'] == loc)].copy()
        if p_df.empty: continue
        
        # load_dataで計算済みだが、念のため安全に取得
        if 'SplitSeconds' not in p_df.columns:
             p_df['SplitSeconds'] = p_df['Split'].apply(str_to_sec)
        
        p_df = p_df.sort_values('SplitSeconds')
        top_time = p_df.iloc[0]['SplitSeconds']
        p_df['TrueRank'] = range(1, len(p_df) + 1)
        
        for _, row in p_df.iterrows():
            tid = row['TeamID']
            analysis_data.append({
                "TeamID": tid, "Team": teams_info.get(tid, tid), "PointLabel": pt_label, 
                "Section": sec, "Location": loc, "Rank": row['TrueRank'],
                "Split": row['Split'], "SplitSeconds": row['SplitSeconds'], 
                "GapSeconds": row['SplitSeconds'] - top_time, 
                "LapStr": row['SEC-Lap'], 
                "KMLapStr": row.get('KM-Lap', '-'),
            })
    ana_df = pd.DataFrame(analysis_data)
    
    if ana_df.empty:
        st.warning("データ不足のため表示できません")
        return

    # --- 色設定 (25色対応) ---
    config = st.session_state.get("race_config", {})
    main_tid = config.get("MainTeamID", "1")
    main_team_name = teams_info.get(str(main_tid), str(main_tid))

    # 25色のパレット
    palette = [
        '#FF4B4B', # 赤 (Main)
        '#1f77b4', '#ff7f0e', '#2ca02c', '#9467bd', '#8c564b', 
        '#e377c2', '#7f7f7f', '#bcbd22', '#17becf', '#aec7e8', 
        '#ffbb78', '#98df8a', '#ff9896', '#c5b0d5', '#c49c94', 
        '#f7b6d2', '#c7c7c7', '#dbdb8d', '#9edae5', '#393b79', 
        '#637939', '#8c6d31', '#843c39', '#7b4173'
    ]
    domain = ana_df['Team'].unique().tolist()
    range_colors = []
    color_idx = 1
    
    for team in domain:
        if team == main_team_name:
            range_colors.append('#FF4B4B')
        else:
            range_colors.append(palette[color_idx % len(palette)])
            color_idx += 1

    tab1, tab2, tab3 = st.tabs(["📈 レース推移", "⚔️ チーム比較", "📍 地点別詳細"])
    
    with tab1:
        graph_type = st.radio("グラフ種類", ["順位変動(通過順)", "トップ差"], horizontal=True, key=f"gtype_{len(df)}")
        max_rank = len(teams_info) if len(teams_info) > 0 else 1
        rank_ticks = list(range(1, max_rank + 1))
        
        if graph_type == "順位変動(通過順)":
            chart = alt.Chart(ana_df).mark_line(point=True).encode(
                x=alt.X('PointLabel', sort=None, title='地点'),
                y=alt.Y('Rank', scale=alt.Scale(domain=[1, max_rank], zero=False, nice=False), 
                        axis=alt.Axis(values=rank_ticks, format='d'), title='通過順').scale(reverse=True),
                color=alt.Color('Team', scale=alt.Scale(domain=domain, range=range_colors)),
                tooltip=['Team', 'PointLabel', 'Rank', 'Split']
            ).properties(height=500).interactive(bind_y=False)
            st.altair_chart(chart, use_container_width=True)
        else:
            chart = alt.Chart(ana_df).mark_line(point=True).encode(
                x=alt.X('PointLabel', sort=None, title='地点'),
                y=alt.Y('GapSeconds', scale=alt.Scale(reverse=True, nice=True), title='トップ差(秒)'),
                color=alt.Color('Team', scale=alt.Scale(domain=domain, range=range_colors)),
                tooltip=['Team', 'PointLabel', 'Rank', 'GapSeconds']
            ).properties(height=500).interactive(bind_y=False)
            st.altair_chart(chart, use_container_width=True)

    with tab2:
        cols = st.columns(2)
        tl = list(teams_info.values())
        # メインチームをデフォルト選択
        try: main_idx = tl.index(main_team_name)
        except: main_idx = 0
        
        if tl:
            with cols[0]: ta = st.selectbox("チームA", tl, index=main_idx, key=f"ta_{len(df)}")
            with cols[1]: tb = st.selectbox("チームB", tl, index=(main_idx + 1) % len(tl) if len(tl) > 1 else 0, key=f"tb_{len(df)}")
            
            if ta and tb:
                tid_a = [k for k, v in teams_info.items() if v == ta][0]
                tid_b = [k for k, v in teams_info.items() if v == tb][0]
                da, db = ana_df[ana_df['TeamID']==tid_a].set_index('PointLabel'), ana_df[ana_df['TeamID']==tid_b].set_index('PointLabel')
                cp = da.index.intersection(db.index)
                if not cp.empty:
                    rr = []
                    for pt in cp:
                        ra, rb = da.loc[pt], db.loc[pt]
                        ds = ra['SplitSeconds'] - rb['SplitSeconds']
                        # 修正: カラム名を変更
                        rr.append({
                            "地点": pt, 
                            f"{ta} 通過順": f"{ra['Rank']}", 
                            f"{tb} 通過順": f"{rb['Rank']}", 
                            "タイム差": fmt_time(abs(ds)), 
                            f"{ta} P-Lap": ra['KMLapStr'], 
                            f"{tb} P-Lap": rb['KMLapStr']
                        })
                    st.dataframe(pd.DataFrame(rr), use_container_width=True, hide_index=True)

    with tab3:
        popts = ana_df['PointLabel'].unique()
        tpt = st.selectbox("地点", popts, key=f"tpt_{len(df)}")
        if tpt:
            pdf = ana_df[ana_df['PointLabel']==tpt].copy()
            # 修正: 表示項目整理
            ddf = pdf[['Rank','Team','Split','GapSeconds','LapStr']].sort_values('Rank')
            ddf.columns = ["通過順","チーム","タイム","トップ差","区間タイム"]
            ddf['トップ差'] = ddf['トップ差'].apply(lambda x: f"+{fmt_time(x)}" if x>0 else "-")
            st.dataframe(ddf, use_container_width=True, hide_index=True)

def render_result_list(df):
    finish_df = df[df['Location'] == 'Finish'].copy()
    if finish_df.empty:
        st.warning("完走したチームはありません")
        return

    # load_dataで計算済みならSplitSecondsを使う
    if 'SplitSeconds' not in finish_df.columns:
        finish_df['SplitSeconds'] = finish_df['Split'].apply(str_to_sec)
        
    finish_df = finish_df.sort_values('SplitSeconds').reset_index(drop=True)
    
    for idx, row in finish_df.iterrows():
        rank = idx + 1
        medal = "🥇" if rank==1 else "🥈" if rank==2 else "🥉" if rank==3 else f"{rank}位"
        bg = "#FFD700" if rank==1 else "#C0C0C0" if rank==2 else "#CD7F32" if rank==3 else "#eee"
        
        st.markdown(f"""
            <div style="display: flex; align-items: center; justify-content: space-between;
                background-color: white; color: black; padding: 15px 20px; border-radius: 10px; margin-bottom: 10px;
                border-left: 10px solid {bg}; box-shadow: 0 2px 5px rgba(0,0,0,0.1);">
                <div style="font-size: 24px; font-weight: bold; width: 60px;">{medal}</div>
                <div style="flex-grow: 1; font-size: 20px; font-weight: bold;">{row['TeamName']}</div>
                <div style="font-size: 24px; font-family: monospace; font-weight: bold;">{row['Split']}</div>
            </div>
        """, unsafe_allow_html=True)

def initialize_race(race_name, section_count, teams_dict, main_team_id):
    gc = get_gspread_client()
    sh = gc.open_by_url(SHEET_URL)
    
    try: sh.worksheet(WORKSHEET_INDEX)
    except: 
        ws_idx = sh.add_worksheet(title=WORKSHEET_INDEX, rows=100, cols=10)
        ws_idx.append_row(["RaceID", "RaceName", "Date", "LogSheet", "ConfigSheet", "Note"])

    try: 
        ws_log = sh.worksheet(WORKSHEET_LOG)
        ws_log.clear()
        ws_log.append_row(["TeamID", "TeamName", "Section", "Location", "Time", "Race"])
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
    for item in config_data: new_config[item[0]] = item[1]
    st.session_state["race_config"] = new_config

# ▼▼▼ JSタイマー (Point Lap表記) ▼▼▼
def show_js_timer(km_sec, sec_sec, split_sec):
    km_ms, sec_ms, split_ms = int(km_sec * 1000), int(sec_sec * 1000), int(split_sec * 1000)
    html_code = f"""
    <!DOCTYPE html><html><head><style>
        @import url('https://fonts.googleapis.com/css2?family=Chakra+Petch:wght@600&display=swap');
        body {{ margin: 0; background-color: transparent; font-family: sans-serif; }}
        .timer-container {{ display: flex; justify-content: space-between; align-items: center; background-color: #262730; padding: 10px 5px; border-radius: 12px; border: 1px solid #444; color: white; box-sizing: border-box; width: 100%; margin-bottom: 5px; overflow: hidden; }}
        .timer-box {{ text-align: center; flex: 1; min-width: 0; }}
        label {{ font-size: 11px; color: #ccc; margin-bottom: 4px; letter-spacing: 0.5px; white-space: nowrap; }}
        .value {{ font-family: 'Chakra Petch', sans-serif; font-weight: 600; font-style: italic; font-size: 26px; line-height: 1.1; letter-spacing: 1px; }}
        .separator {{ width: 1px; height: 35px; background-color: #555; }}
        .decimal {{ font-size: 0.6em; opacity: 0.7; }}
        .color-km {{ color: #4bd6ff; }} .color-sec {{ color: #ff4b4b; }} .color-total {{ color: #ffffff; }}
        @media (max-width: 480px) {{ .value {{ font-size: 20px; letter-spacing: 0; }} .label {{ font-size: 9px; }} .timer-container {{ padding: 8px 2px; }} }}
    </style></head><body>
    <div class="timer-container">
        <div class="timer-box"><div class="label">Point Lap</div><div id="km-val" class="value color-km">--:--.--</div></div>
        <div class="separator"></div>
        <div class="timer-box"><div class="label">Section Lap</div><div id="sec-val" class="value color-sec">--:--.--</div></div>
        <div class="separator"></div>
        <div class="timer-box"><div class="label">Total</div><div id="split-val" class="value color-total">--:--:--</div></div>
    </div>
    <script>
        const now = Date.now();
        const startKm = now - {km_ms}; const startSec = now - {sec_ms}; const startSplit = now - {split_ms};
        function fmt(ms, isSplit) {{
            if (ms < 0) return "--:--.--";
            const totalTenths = Math.floor(ms / 100); const totalSec = Math.floor(ms / 1000);
            const h = Math.floor(totalSec / 3600); const m = Math.floor((totalSec % 3600) / 60); const s = totalSec % 60; const dec = Math.floor((ms % 1000) / 100); 
            const mStr = String(m).padStart(2,'0'); const sStr = String(s).padStart(2,'0');
            if (isSplit) {{ return `${{h}}:${{mStr}}:${{sStr}}`; }} else {{ return `${{mStr}}:${{sStr}}<span class="decimal">.${{dec}}</span>`; }}
        }}
        function update() {{
            const cur = Date.now();
            document.getElementById("km-val").innerHTML = fmt(cur - startKm, false);
            document.getElementById("sec-val").innerHTML = fmt(cur - startSec, false);
            document.getElementById("split-val").innerHTML = fmt(cur - startSplit, true);
        }}
        setInterval(update, 100); update();
    </script></body></html>
    """
    components.html(html_code, height=110)

# ==========================================
# アプリのモード管理 & Configロード
# ==========================================
conn = st.connection("gsheets", type=GSheetsConnection)

if "race_config" not in st.session_state: st.session_state["race_config"] = None
if st.session_state["race_config"] is None:
    loaded_conf = fetch_config_from_sheet(conn)
    if loaded_conf: st.session_state["race_config"] = loaded_conf

config = st.session_state["race_config"]
# 修正: デフォルトを観戦モードに
if "app_mode" not in st.session_state: st.session_state["app_mode"] = "📣 観戦モード"

if (config is None or "RaceName" not in config) and st.session_state["app_mode"] not in ["📂 過去のレース", "⚙️ 管理者モード"]:
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
    "🏁 レース作成", "⏱️ 記録点モード", "🎽 中継点モード",
    "📣 観戦モード", "📈 分析モード", "🏆 最終結果",
    "📂 過去のレース", "⚙️ 管理者モード"
]

if is_race_started and config is not None:
    if "🏁 レース作成" in menu_options: menu_options.remove("🏁 レース作成")

def change_mode(m):
    st.session_state["app_mode"] = m
    if m == "📣 観戦モード" and config and "MainTeamID" in config:
             st.session_state["watch_tid"] = config["MainTeamID"]

for m in menu_options:
    disabled = False
    if (config is None) and (m not in ["🏁 レース作成", "⚙️ 管理者モード", "📂 過去のレース"]): disabled = True
    k = "primary" if st.session_state["app_mode"] == m else "secondary"
    st.sidebar.button(m, on_click=change_mode, args=(m,), type=k, disabled=disabled)

current_mode = st.session_state["app_mode"]

# ==========================================
# 1. 🏁 レース作成
# ==========================================
if current_mode == "🏁 レース作成":
    st.header("🏁 レース作成")
    if is_race_started and config is not None: st.session_state["app_mode"] = "⏱️ 記録点モード"; st.rerun()
    if is_race_started: st.warning("レース進行中のため作成できません。"); st.stop()
    
    team_count = st.number_input("チーム数", min_value=1, max_value=25, value=3)
    
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
# 共通ロジック
# ==========================================
elif current_mode in ["⏱️ 記録点モード", "🎽 中継点モード", "📣 観戦モード", "📈 分析モード", "🏆 最終結果"]:
    if not config: st.error("設定が読み込めません。"); st.stop()
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
    
    team_status = {}
    finish_count = 0
    if not df.empty:
        for tid in team_ids_ordered:
            t_df = df[df['TeamID'] == tid]
            if not t_df.empty:
                last_row = t_df.iloc[-1]
                team_status[tid] = last_row
                if last_row['Location'] == "Finish": finish_count += 1
            else: team_status[tid] = None

    # ⏱️ 記録点 & 🎽 中継点
    if current_mode in ["⏱️ 記録点モード", "🎽 中継点モード"]:
        if df.empty:
            st.info("レース前")
            if st.button("🔫 スタート", type="primary", use_container_width=True):
                now = datetime.now(JST)
                start_rows = []
                for tid in team_ids_ordered:
                    start_rows.append([tid, teams_info[tid], "1区", "Start", get_time_str(now), config["RaceName"]])
                gc = get_gspread_client()
                gc.open_by_url(SHEET_URL).worksheet(WORKSHEET_LOG).append_rows(start_rows)
                st.cache_data.clear()
                st.rerun()
            st.stop()
        
        def record_point(tid, section, location, is_finish=False):
            now = datetime.now(JST)
            new_row = [tid, teams_info[tid], section, location, get_time_str(now), config["RaceName"]]
            gc = get_gspread_client()
            gc.open_by_url(SHEET_URL).worksheet(WORKSHEET_LOG).append_row(new_row)
            st.cache_data.clear()
            st.toast(f"{teams_info[tid]}: {location} 記録完了")

        target_point = 1
        if current_mode == "⏱️ 記録点モード":
            target_point = st.number_input("記録する地点番号 (P_)", min_value=1, max_value=50, value=1)
        st.write("") 

        for tid in team_ids_ordered:
            status = team_status.get(tid)
            t_name = teams_info.get(tid, tid)
            btn_type = "primary" if str(tid) == str(main_team_id) else "secondary"

            if status is None:
                st.button(f"【{tid}】{t_name} (No Data)", disabled=True, key=f"btn_none_{tid}")
                continue
            last_loc, curr_sec_str = str(status['Location']), str(status['Section'])
            if last_loc == "Finish":
                st.button(f"🏁 【{tid}】{t_name} (Finish)", disabled=True, key=f"btn_fin_stat_{tid}")
                continue
            try: curr_sec_num = int(curr_sec_str.replace("区", ""))
            except: curr_sec_num = 1
            if last_loc == "Relay":
                curr_sec_num += 1
                curr_sec_str = f"{curr_sec_num}区"
            
            if current_mode == "⏱️ 記録点モード":
                label = f"【No.{tid}】 {t_name}  ▶  P{target_point}"
                if st.button(label, key=f"btn_dist_{tid}", type=btn_type, use_container_width=True):
                    record_point(tid, curr_sec_str, f"P{target_point}")
                    st.rerun()
            elif current_mode == "🎽 中継点モード":
                is_anchor = (curr_sec_num >= total_sections)
                if is_anchor:
                    if st.button(f"🏆 【No.{tid}】 {t_name}  ▶  Finish", key=f"btn_fin_{tid}", type=btn_type, use_container_width=True):
                        record_point(tid, curr_sec_str, "Finish", is_finish=True)
                        st.rerun()
                else:
                    if st.button(f"🎽 【No.{tid}】 {t_name}  ▶  Relay ({curr_sec_num + 1}区)", key=f"btn_rel_{tid}", type=btn_type, use_container_width=True):
                        record_point(tid, curr_sec_str, "Relay")
                        st.rerun()
        
        st.markdown("<hr style='margin: 15px 0;'>", unsafe_allow_html=True)
        if st.button("↩️ 元に戻す", use_container_width=True, type="secondary"):
            try:
                gc = get_gspread_client()
                ws = gc.open_by_url(SHEET_URL).worksheet(WORKSHEET_LOG)
                all_vals = ws.get_all_values()
                if len(all_vals) > 1: ws.delete_rows(len(all_vals)); st.cache_data.clear(); st.toast("削除しました"); st.rerun()
            except Exception as e: st.error(f"Undoエラー: {e}")

    # 📣 観戦モード
    elif current_mode == "📣 観戦モード":
        st_autorefresh(interval=AUTOREFRESH_INTERVAL, key="watch_refresh")
        
        if "watch_tid" not in st.session_state: st.session_state["watch_tid"] = main_team_id
        team_options = {tid: f"No.{tid} {teams_info.get(tid, '')}" for tid in team_ids_ordered}
        curr_idx = 0
        if st.session_state["watch_tid"] in team_ids_ordered: curr_idx = team_ids_ordered.index(st.session_state["watch_tid"])
        selected_tid = st.selectbox("チーム選択", options=team_ids_ordered, format_func=lambda x: team_options[x], index=curr_idx)
        st.session_state["watch_tid"] = selected_tid

        t_df = df[df['TeamID'] == selected_tid]
        if t_df.empty: st.info("まだ記録がありません")
        else:
            last = t_df.iloc[-1]
            last_time = last['dt']
            now = datetime.now(JST)
            try: start_time = df[df['Location'] == 'Start'].iloc[0]['dt']
            except: start_time = now
            sec_start_time = start_time
            if last['Section'] != "1区":
                prev_relay = t_df[(t_df['Section'] == f"{int(last['Section'].replace('区',''))-1}区") & (t_df['Location'] == 'Relay')]
                if not prev_relay.empty: sec_start_time = prev_relay.iloc[0]['dt']
            
            elapsed_km, elapsed_sec, elapsed_split = (now - last_time).total_seconds(), (now - sec_start_time).total_seconds(), (now - start_time).total_seconds()
            
            loc_raw = last['Location']
            display_loc = f"{last['Section']} {loc_raw}"
            if "P" in loc_raw: display_loc = f"🏃‍♂️ 現在地: {last['Section']} {loc_raw} 〜"
            elif loc_raw == "Start": display_loc = "🏃‍♂️ 現在地: スタート地点"
            elif loc_raw == "Relay": display_loc = f"🏃‍♂️ 現在地: {last['Section']} 中継所"
            elif loc_raw == "Finish": display_loc = "🏃‍♂️ 現在地: フィニッシュ"

            st.markdown(f"""
                <style>
                .info-panel {{ background-color: #262730; padding: 15px; border-radius: 10px; margin-bottom: 20px; border: 1px solid #4f4f4f; text-align: center; width: 100%; box-sizing: border-box; }}
                .loc-text {{ font-size: 20px; color: white; font-weight: bold; }}
                .sub-text {{ font-size: 14px; color: #aaa; margin-top: 5px; }}
                </style>
                <div class="info-panel">
                    <div class="loc-text">{display_loc}</div>
                    <div class="sub-text">通過順: {int(last['Rank'])}番目</div>
                </div>
            """, unsafe_allow_html=True)

            if last['Location'] == 'Finish':
                st.markdown(f"""
                    <div style="border: 4px solid #FFD700; border-radius: 15px; background: linear-gradient(135deg, #262730, #444); padding: 30px; text-align: center; color: white; margin-bottom: 20px; box-shadow: 0 0 20px rgba(255, 215, 0, 0.4);">
                        <div style="font-size: 16px; color: #FFD700; letter-spacing: 2px;">OFFICIAL FINISHER</div>
                        <h1 style="font-size: 48px; margin: 10px 0; font-family: 'Arial Black', sans-serif;">FINISH!</h1>
                        <hr style="border: 1px solid #777; width: 60%;">
                        <div style="font-size: 24px; font-weight: bold; margin-top: 20px;">TIME: {last['Split']}</div>
                    </div>
                """, unsafe_allow_html=True)
            else: show_js_timer(elapsed_km, elapsed_sec, elapsed_split)

            try:
                last_lap = str(last.get('KM-Lap', '-'))
                if last_lap and last_lap != "nan":
                    st.markdown(f"<div style='text-align: center; background-color: #333; padding: 8px; border-radius: 5px; margin-bottom: 10px; margin-top: 10px;'>⏱️ 直近ラップ(P): <span style='font-weight:bold; color:#4bd6ff; font-family: monospace; font-size: 1.1em;'>{last_lap}</span></div>", unsafe_allow_html=True)
            except: pass

            # 前後差
            loc_df = df[(df['Section'] == last['Section']) & (df['Location'] == last['Location'])].copy()
            if 'SplitSeconds' in loc_df.columns:
                loc_df = loc_df.sort_values("SplitSeconds").reset_index(drop=True)
                my_indices = loc_df.index[loc_df['TeamID'].astype(str) == str(selected_tid)].tolist()
                if my_indices:
                    my_idx = my_indices[0]
                    my_split = loc_df.iloc[my_idx]['SplitSeconds']
                    c_prev, c_next = st.columns(2)
                    with c_prev:
                        if my_idx > 0:
                            prev_row = loc_df.iloc[my_idx - 1]
                            diff = my_split - prev_row['SplitSeconds']
                            prev_name = teams_info.get(str(prev_row['TeamID']), prev_row['TeamName'])
                            st.info(f"⬆️ 前: **{prev_name}**\n\n+{fmt_time(diff)}")
                        else: st.success("👑 現在トップ！")
                    with c_next:
                        if my_idx < len(loc_df) - 1:
                            next_row = loc_df.iloc[my_idx + 1]
                            diff = next_row['SplitSeconds'] - my_split
                            next_name = teams_info.get(str(next_row['TeamID']), next_row['TeamName'])
                            st.warning(f"⬇️ 後ろ: **{next_name}**\n\n-{fmt_time(diff)}")
                        else: st.write("（後ろはいません）")

            st.divider()
            st.write("📝 通過履歴")
            st.dataframe(t_df[['Section', 'Location', 'Split', 'KM-Lap']].iloc[::-1], use_container_width=True, hide_index=True)

    # 📈 分析モード
    elif current_mode == "📈 分析モード":
        st.header("📈 レース分析")
        if st.button("🔄 データ更新", type="secondary", use_container_width=False): st.cache_data.clear(); st.rerun()
        if df.empty: st.info("データがありません。")
        else: render_analysis_dashboard(df, teams_info)

    # 🏆 最終結果
    elif current_mode == "🏆 最終結果":
        st.markdown("""<div style="text-align: center; padding: 40px; background: linear-gradient(to right, #000, #434343); border-radius: 20px; color: white; margin-bottom: 30px;"><h1 style="font-size: 50px; margin-bottom: 10px;">🏆 RACE RESULT</h1><p>レース終了！お疲れ様でした！</p></div>""", unsafe_allow_html=True)
        render_result_list(df)

# ==========================================
# 📂 過去のレース閲覧
# ==========================================
elif current_mode == "📂 過去のレース":
    st.header("📂 過去のレース閲覧")
    idx_df = load_data(conn, WORKSHEET_INDEX)
    
    if idx_df.empty:
        st.info("アーカイブされたレースはありません")
    else:
        idx_df = idx_df.sort_values(by="Date", ascending=False)
        race_options = {row['RaceID']: f"{row['Date']} - {row['RaceName']}" for _, row in idx_df.iterrows()}
        selected_rid = st.selectbox("閲覧するレースを選択", list(race_options.keys()), format_func=lambda x: race_options[x])
        
        if selected_rid:
            target_row = idx_df[idx_df['RaceID'] == selected_rid].iloc[0]
            log_sheet = target_row['LogSheet']
            conf_sheet = target_row['ConfigSheet']
            
            old_df = load_data(conn, log_sheet)
            old_conf = fetch_config_from_sheet(conn, conf_sheet)
            
            if old_df.empty or not old_conf:
                st.error("データの読み込みに失敗しました")
            else:
                old_teams = {}
                for k, v in old_conf.items():
                    if k.startswith("TeamName_"): old_teams[k.replace("TeamName_", "")] = v
                st.divider()
                st.subheader(f"Archive: {target_row['RaceName']}")
                v_tab1, v_tab2 = st.tabs(["📊 分析ビュー", "🏆 結果リスト"])
                with v_tab1: render_analysis_dashboard(old_df, old_teams)
                with v_tab2: render_result_list(old_df)

# ==========================================
# ⚙️ 管理者モード
# ==========================================
elif current_mode == "⚙️ 管理者モード":
    st.header("⚙️ 管理者モード")
    pwd = st.text_input("パスワード", type="password")
    
    if pwd == ADMIN_PASSWORD:
        st.success("認証成功")
        if st.button("設定データを強制リロード", use_container_width=True): st.session_state["race_config"]=None; st.cache_data.clear(); st.rerun()

        st.divider()
        st.write("### 📦 レースのアーカイブ")
        if st.button("📦 レースを終了してアーカイブ", type="primary", use_container_width=True):
            if not config: st.error("configがありません"); st.stop()
            try:
                gc = get_gspread_client()
                sh = gc.open_by_url(SHEET_URL)
                try: ws_idx = sh.worksheet(WORKSHEET_INDEX)
                except: 
                    ws_idx = sh.add_worksheet(WORKSHEET_INDEX, 100, 10)
                    ws_idx.append_row(["RaceID", "RaceName", "Date", "LogSheet", "ConfigSheet", "Note"])
                
                ts = datetime.now(JST).strftime('%Y%m%d_%H%M%S')
                race_id = f"race_{ts}"
                log_name = f"log_{ts}"
                conf_name = f"conf_{ts}"
                
                ws_log = sh.worksheet(WORKSHEET_LOG)
                ws_conf = sh.worksheet(WORKSHEET_CONFIG)
                ws_log.duplicate(new_sheet_name=log_name)
                ws_conf.duplicate(new_sheet_name=conf_name)
                
                ws_idx.append_row([race_id, config.get("RaceName", "Unknown"), datetime.now(JST).strftime('%Y-%m-%d %H:%M'), log_name, conf_name, ""])
                ws_log.clear(); ws_log.append_row(["TeamID", "TeamName", "Section", "Location", "Time", "Race"])
                ws_conf.clear(); ws_conf.append_row(["Key", "Value"])
                
                st.cache_data.clear()
                st.session_state["race_config"] = None
                st.session_state["app_mode"] = "🏁 レース作成"
                st.success(f"アーカイブ完了！: {race_id}")
                st.rerun()
            except Exception as e: st.error(f"アーカイブエラー: {e}")

        st.write("#### 🗑️ アーカイブ削除")
        idx_df = load_data(conn, WORKSHEET_INDEX)
        if not idx_df.empty and "RaceID" in idx_df.columns:
            del_targets = st.multiselect("削除するアーカイブを選択", idx_df['RaceID'].tolist())
            if del_targets and st.button("選択したアーカイブを削除 (復元不可)", type="secondary"):
                gc = get_gspread_client()
                sh = gc.open_by_url(SHEET_URL)
                ws_idx = sh.worksheet(WORKSHEET_INDEX)
                for rid in del_targets:
                    row = idx_df[idx_df['RaceID'] == rid].iloc[0]
                    try: sh.del_worksheet(sh.worksheet(row['LogSheet']))
                    except: pass
                    try: sh.del_worksheet(sh.worksheet(row['ConfigSheet']))
                    except: pass
                
                new_idx_data = idx_df[~idx_df['RaceID'].isin(del_targets)].values.tolist()
                ws_idx.clear()
                ws_idx.append_row(["RaceID", "RaceName", "Date", "LogSheet", "ConfigSheet", "Note"])
                if new_idx_data: ws_idx.append_rows(new_idx_data)
                st.cache_data.clear(); st.success("削除しました"); st.rerun()

        st.divider()
        st.write("### 🔧 設定(Config)の直接編集")
        conf_df = load_data(conn, WORKSHEET_CONFIG)
        if not conf_df.empty:
            edited_conf = st.data_editor(conf_df, num_rows="dynamic", key="edit_conf")
            if st.button("設定を保存", key="save_conf"):
                conn.update(spreadsheet=SHEET_URL, worksheet=WORKSHEET_CONFIG, data=edited_conf)
                st.session_state["race_config"] = None
                st.cache_data.clear()
                st.success("更新しました"); st.rerun()

        st.write("### 📝 ログデータの直接編集")
        st.warning("時刻(Time)を修正すると、ラップなどは自動再計算されます。")
        log_df = load_data(conn, WORKSHEET_LOG)
        if not log_df.empty:
            column_config = {
                "Time": st.column_config.TextColumn("Time (HH:MM:SS.f)"),
                "Split": st.column_config.TextColumn("Split (自動計算)", disabled=True),
                "KM-Lap": st.column_config.TextColumn("Point-Lap (自動計算)", disabled=True),
                "Rank": st.column_config.TextColumn("Rank (自動計算)", disabled=True),
            }
            raw_columns = ["TeamID", "TeamName", "Section", "Location", "Time", "Race"]
            display_cols = [c for c in raw_columns if c in log_df.columns]
            
            edited_log = st.data_editor(log_df[display_cols], num_rows="dynamic", column_config=column_config, key="edit_log")
            
            col_save, col_check = st.columns([1, 2])
            with col_check: confirm_save = st.checkbox("編集内容を反映する（取り消せません）")
            with col_save:
                if st.button("ログを保存", key="save_log", type="primary", disabled=not confirm_save):
                    conn.update(spreadsheet=SHEET_URL, worksheet=WORKSHEET_LOG, data=edited_log)
                    st.cache_data.clear(); st.success("更新しました"); st.rerun()

        st.divider()
        st.write("### 🚨 プロジェクトリセット")
        if st.button("🗑️ データを全消去してリセット"):
            gc = get_gspread_client()
            sh = gc.open_by_url(SHEET_URL)
            try: 
                ws_log = sh.worksheet(WORKSHEET_LOG)
                ws_log.clear()
                ws_log.append_row(["TeamID", "TeamName", "Section", "Location", "Time", "Race"])
            except: pass
            try: sh.worksheet(WORKSHEET_CONFIG).clear()
            except: pass
            st.cache_data.clear()
            st.session_state["race_config"] = None
            st.session_state["app_mode"] = "🏁 レース作成"
            st.rerun()

# ▼▼▼ 迷子防止 ▼▼▼
else:
    st.session_state["app_mode"] = "🏁 レース作成"
    st.rerun()