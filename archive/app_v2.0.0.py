# ==========================================
# version = 2.0.0 date = 2026/01/11
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

# ==========================================
# 設定・定数
# ==========================================
VERSION = "ver 2.0.0"

SHEET_URL = "https://docs.google.com/spreadsheets/d/1-GSNYQYulO-83vdMOn7Trqv4l6eCjo9uzaP20KQgSS4/edit" # 【要修正】URL確認
WORKSHEET_LOG = "latest-log"
WORKSHEET_CONFIG = "config"
JST = ZoneInfo("Asia/Tokyo")
CACHE_TTL_SEC = 2.0
ADMIN_PASSWORD = "0000"

# ページ設定
st.set_page_config(page_title="えきでんくん", page_icon="🎽", layout="wide")

# ==========================================
# CSSデザイン定義
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
    
    /* ▼▼▼ 修正: Secondaryボタンの場合のみ、最後のボタン(Undo)を薄めグレーにする ▼▼▼ */
    div.block-container > div[data-testid="stVerticalBlock"] > div:last-child button[kind="secondary"] {
        background-color: #555555 !important; /* 薄めグレー */
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
        # 読み込み失敗時は空のDataFrameを返す（画面真っ白回避）
        return pd.DataFrame()

# Config読み込み
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

# レース初期化
def initialize_race(race_name, section_count, teams_dict, main_team_id):
    gc = get_gspread_client()
    sh = gc.open_by_url(SHEET_URL)
    
    try: ws_log = sh.worksheet(WORKSHEET_LOG)
    except: ws_log = sh.add_worksheet(WORKSHEET_LOG, 1000, 10)
    ws_log.clear()
    ws_log.append_row(["TeamID", "TeamName", "Section", "Location", "Time", "KM-Lap", "SEC-Lap", "Split", "Rank", "Race"])
    
    try: ws_conf = sh.worksheet(WORKSHEET_CONFIG)
    except: ws_conf = sh.add_worksheet(WORKSHEET_CONFIG, 100, 2)
    ws_conf.clear()
    ws_conf.append_row(["Key", "Value"])
    
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

# Configがなければセットアップへ
if config is None or "RaceName" not in config:
    st.session_state["app_mode"] = "🏁 レース作成"

# レース開始チェック
df_for_check = load_data(conn, WORKSHEET_LOG)
is_race_started = not df_for_check.empty

# ▼▼▼ サイドバー：タイトルとモード選択 ▼▼▼
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

# ▼▼▼ 修正: Configが有効(レース中)な場合のみセットアップを隠す (リセット時は隠さない) ▼▼▼
if is_race_started and config is not None:
    if "🏁 レース作成" in menu_options:
        menu_options.remove("🏁 レース作成")

# 選択ロジック
def change_mode(m):
    st.session_state["app_mode"] = m

for m in menu_options:
    disabled = False
    # Config未ロード時の制限
    if (config is None) and (m not in ["🏁 レース作成", "⚙️ 管理者モード"]):
        disabled = True
    
    k = "primary" if st.session_state["app_mode"] == m else "secondary"
    st.sidebar.button(m, on_click=change_mode, args=(m,), type=k, disabled=disabled)

current_mode = st.session_state["app_mode"]

# ==========================================
# 1. 🏁 レース作成
# ==========================================
if current_mode == "🏁 レース作成":
    # st.header("🏁 レース作成")

    # ▼▼▼ 修正: レース中なら強制的に記録点モードへ飛ばす ▼▼▼
    if is_race_started and config is not None:
        st.session_state["app_mode"] = "⏱️ 記録点モード"
        st.rerun()
    
    # 万が一入ってしまった場合のガード
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
    # ⏱️ 記録点モード & 🎽 中継点モード
    # -------------------------------------
    if current_mode in ["⏱️ 記録点モード", "🎽 中継点モード"]:
        
        # ▼▼▼ ページ上部タイトル (手動更新ボタンは削除) ▼▼▼
        # st.markdown(f"<h2 style='text-align:center; margin-bottom:15px;'>{current_mode}</h2>", unsafe_allow_html=True)
        
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

        # チームボタン一覧
        for tid in team_ids_ordered:
            status = team_status.get(tid)
            t_name = teams_info.get(tid, tid)
            is_main = (tid == main_team_id)
            btn_type = "primary" if is_main else "secondary"
            
            # ▼▼▼ 変更点: 全チームをPrimary(赤)として扱う ▼▼▼
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

            # ▼▼▼ 修正: 直前がRelayなら、現在は「次の区間」を走っているとみなす ▼▼▼
            try: 
                curr_sec_num = int(curr_sec_str.replace("区", ""))
            except: 
                curr_sec_num = 1

            if last_loc == "Relay":
                curr_sec_num += 1
                curr_sec_str = f"{curr_sec_num}区"
            # ▲▲▲ 修正ここまで ▲▲▲
            
            # ボタン生成
            if current_mode == "⏱️ 記録点モード":
                label = f"【No.{tid}】 {t_name}  ▶  {target_km}km"
                if st.button(label, key=f"btn_dist_{tid}", type=btn_type, use_container_width=True):
                    record_point(tid, curr_sec_str, f"{target_km}km")
                    st.rerun()

            elif current_mode == "🎽 中継点モード":
                try: curr_sec_num = int(curr_sec_str.replace("区", ""))
                except: curr_sec_num = 1
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
        
        # ▼▼▼ 追加: ひとつ戻るボタン (最下部・薄めグレー) ▼▼▼
        st.markdown("<hr style='margin: 15px 0;'>", unsafe_allow_html=True)
        if st.button("↩️ 元に戻す", use_container_width=True):
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
    # 📣 観戦モード
    # -------------------------------------
    elif current_mode == "📣 観戦モード":
        # st.markdown(f"<h2 style='text-align:center;'>{current_mode}</h2>", unsafe_allow_html=True)
        st.sidebar.markdown("---")
        watch_tid = st.sidebar.selectbox("表示チームを選択", team_ids_ordered, format_func=lambda x: teams_info.get(x, x))
        st_autorefresh(interval=5000, key="watch_refresh")
        
        t_df = df[df['TeamID'] == watch_tid]
        if t_df.empty:
            st.warning("データがありません")
        else:
            last = t_df.iloc[-1]
            last_time = parse_time_str(last['Time'])
            now = datetime.now(JST)
            t_name = teams_info.get(watch_tid, watch_tid)
            
            st.markdown(f"# 📣 {t_name} 応援中")
            c1, c2, c3 = st.columns(3)
            c1.metric("現在地", f"{last['Section']} - {last['Location']}")
            c1.caption(f"通過時刻: {last['Time']}")
            
            elapsed = (now - last_time).total_seconds()
            if last['Location'] == 'Finish':
                c2.metric("Total Time", last['Split'])
            else:
                c2.metric("通過から", fmt_time(elapsed))
            
            c3.metric("区間順位", f"{last['Rank']}位")
            st.divider()
            
            loc_df = df[(df['Section'] == last['Section']) & (df['Location'] == last['Location'])].sort_values("Time")
            my_idx = -1
            for i in range(len(loc_df)):
                if loc_df.iloc[i]['TeamID'] == watch_tid:
                    my_idx = i
                    break
            
            if my_idx > 0:
                prev_row = loc_df.iloc[my_idx - 1]
                prev_tname = teams_info.get(prev_row['TeamID'])
                prev_time = parse_time_str(prev_row['Time'])
                diff = (last_time - prev_time).total_seconds()
                st.info(f"⬆️ 前のチーム: **{prev_tname}** (差: {fmt_time(diff)})")
            elif my_idx == 0:
                st.success("👑 現在 **トップ** 通過です！")
                
            if my_idx >= 0 and my_idx < len(loc_df) - 1:
                next_row = loc_df.iloc[my_idx + 1]
                next_tname = teams_info.get(next_row['TeamID'])
                next_time = parse_time_str(next_row['Time'])
                diff = (next_time - last_time).total_seconds()
                st.write(f"⬇️ 後ろのチーム: **{next_tname}** (差: {fmt_time(diff)})")

            st.divider()
            st.dataframe(t_df.iloc[::-1][['Section','Location','Time','KM-Lap','Rank']], use_container_width=True)

    # -------------------------------------
    # 📈 分析モード
    # -------------------------------------
    elif current_mode == "📈 分析モード":
        # st.markdown(f"<h2 style='text-align:center;'>{current_mode}</h2>", unsafe_allow_html=True)
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