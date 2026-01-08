# ==========================================
# version = 1.3.5 date = 2026/01/09
# ==========================================

import streamlit as st
import pandas as pd
import math
from datetime import datetime
from zoneinfo import ZoneInfo
from streamlit_gsheets import GSheetsConnection
from streamlit_autorefresh import st_autorefresh
import streamlit.components.v1 as components # 【追加】JavaScript埋め込み用

# ==========================================
# 設定・定数
# ==========================================
VERSION = "ver 1.3.5" ###更新毎に書き換え

SHEET_URL = "https://docs.google.com/spreadsheets/d/1-GSNYQYulO-83vdMOn7Trqv4l6eCjo9uzaP20KQgSS4/edit" # 【要修正】あなたのスプレッドシートのURLに書き換えてください
WORKSHEET_NAME = "log"
JST = ZoneInfo("Asia/Tokyo")
AUTO_RELOAD_SEC = 10
AUTO_REFRESH_INTERVAL_MS = 5000

# ページ設定
st.set_page_config(page_title="駅伝けいそくん", page_icon="🎽", layout="wide")

# ==========================================
# CSSデザイン定義
# ==========================================
st.markdown("""
    <style>
    /* 画面からはみ出さないようにする */
    .stApp { overflow-x: hidden; }
    
    /* コンテナ設定 */
    .block-container {
        padding-top: 2.0rem;
        padding-bottom: 5rem;
        padding-left: 0.5rem;
        padding-right: 0.5rem;
    }
            
    /* ヘッダーのGridレイアウト */
    div[data-testid="stHorizontalBlock"] {
        display: grid !important;
        grid-template-columns: 1fr auto !important;
        gap: 10px !important;
        align-items: center !important;
    }
            
    /* 右カラム（更新ボタン） */
    div[data-testid="column"]:nth-of-type(2) {
        display: flex !important;
        justify-content: flex-end !important;
        width: auto !important;
    }
            
    /* 更新ボタンデザイン */
    div[data-testid="stHorizontalBlock"] button {
        height: 2.5em !important;
        width: 3em !important;
        padding: 0px !important;
        margin: 0px !important;
        border-radius: 8px !important;
        line-height: 1 !important;
        float: right !important;
    }

    /* 通常ボタン */
    div.stButton > button {
        height: 3em;
        font-size: 18px;
        font-weight: bold;
        border-radius: 10px;
        width: 100%;
    }
    
    /* Primaryボタン */
    div.stButton > button[kind="primary"] {
        background-color: #FF4B4B;
        color: white;
        height: 4.0em;
        font-size: 36px;
        width: 100%;
    }
    
    /* タイトル調整 */
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

# タイトル（バージョン情報付き）
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
        df = conn.read(spreadsheet=SHEET_URL, worksheet=WORKSHEET_NAME, ttl=AUTO_RELOAD_SEC)
        return df
    except Exception as e:
        return pd.DataFrame()

# 【修正】時刻保存用 (HH:MM:SS.f)
def get_time_str(dt):
    # マイクロ秒(6桁)を含む文字列を取得し、先頭10文字(コンマ1桁目まで)で切る
    # 例: 12:34:56.123456 -> 12:34:56.1
    return dt.strftime("%H:%M:%S.%f")[:10]

# 【修正】時刻読み込み用 (0.1秒対応)
def parse_time_str(time_str):
    now = datetime.now(JST)
    try:
        if "." in time_str:
            # 0.1秒単位(.X)がある場合、後ろに0を5つ足して(.X00000) datetimeとして読み込む
            # 文字列連結で簡易的にパース可能な形式にする
            t = datetime.strptime(time_str + "00000", "%H:%M:%S.%f").time()
        else:
            t = datetime.strptime(time_str, "%H:%M:%S").time()
        return datetime.combine(now.date(), t).replace(tzinfo=JST)
    except:
        return now

# HTML装飾用ヘルパー関数： ".X" の部分を小さく薄くするHTMLタグを付与
def style_decimal(time_str):
    if "." in time_str:
        main, dec = time_str.split(".")
        return f'{main}<span style="font-size: 0.6em; opacity: 0.7;">.{dec}</span>'
    return time_str    

# スプリット用 (h:mm:ss) ※0.1秒なし
def fmt_time(sec):
    sec = math.ceil(sec)
    m, s = divmod(int(sec), 60)
    h, m = divmod(m, 60)
    return f"{h:01}:{m:02}:{s:02}"

# ラップ用 (mm:ss.f)
def fmt_time_lap(sec):
    total_tenths = math.ceil(sec * 10)
    rem_tenths = total_tenths % 10
    total_sec = total_tenths // 10
    m, s = divmod(total_sec, 60)
    return f"{m:02}:{s:02}.{rem_tenths}"

def get_section_start_time(df, section_num):
    """指定した区間の開始時刻（前区間のRelay、またはStart）を取得"""
    if section_num == 1:
        # 1区ならStartの時刻
        row = df[df['Location'] == 'Start']
    else:
        # 2区以降なら、前の区間(section_num-1)のRelay時刻
        prev_section = f"{section_num - 1}区"
        row = df[(df['Section'] == prev_section) & (df['Location'] == 'Relay')]
    
    if not row.empty:
        return parse_time_str(row.iloc[0]['Time'])
    return None

# ▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼
# 【新機能】JavaScriptタイマー表示関数
# Pythonからは「現在何秒経過しているか」だけを渡し、
# ブラウザ(JS)側で高速カウントアップさせます。サーバー負荷はゼロです。
# ▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼
def show_js_timer(km_sec, sec_sec, split_sec):
    # ミリ秒単位に変換
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
        // Pythonから渡された「現在までの経過時間(ms)」
        // ページ読み込み時点のサーバー時間を基準に、開始タイムスタンプを逆算する
        const now = Date.now();
        const startKm = now - {km_ms};
        const startSec = now - {sec_ms};
        const startSplit = now - {split_ms};

        function fmtLap(ms) {{
            // 0.1秒単位で切り上げ (Math.ceil)
            // 100ms単位にする -> ceil -> 戻す
            const totalTenths = Math.ceil(ms / 100); 
            const totalSec = Math.floor(totalTenths / 10);
            const remTenths = totalTenths % 10;
            
            const m = Math.floor(totalSec / 60);
            const s = totalSec % 60;
            
            const mStr = String(m).padStart(2, '0');
            const sStr = String(s).padStart(2, '0');
            
            return `${{mStr}}:${{sStr}}<span class="decimal">.${{remTenths}}</span>`;
        }}

        function fmtSplit(ms) {{
            // 秒単位で切り上げ
            const totalSec = Math.ceil(ms / 1000);
            
            const h = Math.floor(totalSec / 3600);
            const rem = totalSec % 3600;
            const m = Math.floor(rem / 60);
            const s = rem % 60;

            const hStr = String(h).padStart(2, '0');
            const mStr = String(m).padStart(2, '0');
            const sStr = String(s).padStart(2, '0');
            
            return `${{hStr}}:${{mStr}}:${{sStr}}`;
        }}

        function update() {{
            const cur = Date.now();
            
            const diffKm = Math.max(0, cur - startKm);
            document.getElementById("km-val").innerHTML = fmtLap(diffKm);

            const diffSec = Math.max(0, cur - startSec);
            document.getElementById("sec-val").innerHTML = fmtLap(diffSec);

            const diffSplit = Math.max(0, cur - startSplit);
            document.getElementById("split-val").innerText = fmtSplit(diffSplit);
        }}

        // 50msごとに画面更新 (サーバー通信なし)
        setInterval(update, 50);
        update(); // 初回実行
    </script>
    </body>
    </html>
    """
    # iframeとして埋め込み (高さ調整)
    components.html(html_code, height=90)

# ==========================================
# メイン処理
# ==========================================
conn = st.connection("gsheets", type=GSheetsConnection)
df = load_data(conn)

# --- A. レース開始前 ---
if df.empty or len(df) == 0:
    st.info("レース開始前")
    
    # スタートボタン
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
        st_autorefresh(interval=10000, key="refresh_start")


# --- B. レース進行中 or 終了後 ---
else:
    last_row = df.iloc[-1]
    last_point = str(last_row['Location'])
    
    # 1. フィニッシュ済み
    if last_point == "Finish":
            # st.balloons()
        st.success("🏆 競技終了！お疲れ様でした！")
        
        st.metric("🏁 フィニッシュ時刻", last_row['Time'])
        st.metric("⏱️ 最終タイム", last_row['Split'])
        
        st.divider()
        st.markdown("### 📊 最終リザルト")
        st.dataframe(df, use_container_width=True)
        
        with st.expander("管理メニュー"):
            st.write("設定")
            # デフォルトをONにする仕様
            auto_reload_finish = st.toggle("🔄 自動更新", value=True, key="auto_reload_finish")
            
            st.divider()

            if st.button("⚠️ データ全消去（次のレースへ）"):
                conn.update(spreadsheet=SHEET_URL, worksheet=WORKSHEET_NAME, data=pd.DataFrame(columns=df.columns))
                st.cache_data.clear() # 即クリア
                st.rerun()
            
        if auto_reload_finish:
            st_autorefresh(interval=10000, key="refresh_finish")
    
    # 2. レース中
    else:
        last_time_obj = parse_time_str(last_row['Time'])
        first_time_obj = parse_time_str(df.iloc[0]['Time'])
            # now_for_record = datetime.now(JST)

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

        # ヘッダー表示
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
            if st.button("🔄", help="更新"):
                st.cache_data.clear()
                st.rerun()

        # ▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼
        # 【v1.3.7】JavaScriptタイマーの埋め込み
        # サーバー負荷ゼロで滑らかなカウントアップを実現
        # ▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼
        
        # 現在時点での経過時間（秒）を計算してJSに渡す
        now_calc = datetime.now(JST)
        
        # 1. キロラップ
        elapsed_km = (now_calc - last_time_obj).total_seconds()
        
        # 2. 区間ラップ
        sec_start = get_section_start_time(df, next_section_num)
        if sec_start:
            elapsed_sec = (now_calc - sec_start).total_seconds()
        else:
            elapsed_sec = 0
            
        # 3. スプリット
        elapsed_split = (now_calc - first_time_obj).total_seconds()

        # JSコンポーネント呼び出し
        show_js_timer(elapsed_km, elapsed_sec, elapsed_split)

        st.divider()

        # ここから下のボタン処理（ラップ・中継・Finish）は
        # now_for_record を再計算する必要があるので注意！
        now_for_record = datetime.now(JST) # ボタン押下時点の時刻

        # 操作ボタン類
        # 1. ラップ計測
        if st.button(f"⏱️ {next_km}km地点 ラップ", type="primary", use_container_width=True):
            lap_sec = (now_for_record - last_time_obj).total_seconds()
            total_sec = (now_for_record - first_time_obj).total_seconds()
            # 【追加】区間ラップの計算
            section_start_obj = get_section_start_time(df, next_section_num)
            if section_start_obj:
                section_lap_sec = (now_for_record - section_start_obj).total_seconds()
            else:
                section_lap_sec = 0
            
            # 保存データ作成（英語列名）
            new_row = pd.DataFrame([{
                "Section": f"{next_section_num}区", 
                "Location": f"{next_km}km",
                "Time": get_time_str(now_for_record), 
                "KM-Lap": fmt_time_lap(lap_sec), 
                "SEC-Lap": fmt_time_lap(section_lap_sec), 
                "Split": fmt_time(total_sec)
            }])
            conn.update(spreadsheet=SHEET_URL, worksheet=WORKSHEET_NAME, data=pd.concat([df, new_row]))
            st.cache_data.clear() # 即クリア
            st.toast(f"{next_km}km地点を記録！")
            st.rerun()

        # 2. 中継ボタン
        if st.button(f"🎽 次へ ({next_section_num+1}区へ)", use_container_width=True):
            lap_sec = (now_for_record - last_time_obj).total_seconds()
            total_sec = (now_for_record - first_time_obj).total_seconds()
            # 【追加】区間ラップの計算
            section_start_obj = get_section_start_time(df, next_section_num)
            if section_start_obj:
                section_lap_sec = (now_for_record - section_start_obj).total_seconds()
            else:
                section_lap_sec = 0
            
            # 保存データ作成（英語列名）
            new_row = pd.DataFrame([{
                "Section": f"{next_section_num}区", 
                "Location": "Relay",
                "Time": get_time_str(now_for_record), 
                "KM-Lap": fmt_time_lap(lap_sec), 
                "SEC-Lap": fmt_time_lap(section_lap_sec), 
                "Split": fmt_time(total_sec)
            }])
            conn.update(spreadsheet=SHEET_URL, worksheet=WORKSHEET_NAME, data=pd.concat([df, new_row]))
            st.cache_data.clear() # 即クリア
            st.success(f"{next_section_num+1}区へリレーしました！")
            st.rerun()
        
        # 3. Finishボタン
        if st.button("🏆 Finish", use_container_width=True):
            lap_sec = (now_for_record - last_time_obj).total_seconds()
            total_sec = (now_for_record - first_time_obj).total_seconds()
            # 【追加】区間ラップの計算
            section_start_obj = get_section_start_time(df, next_section_num)
            if section_start_obj:
                section_lap_sec = (now_for_record - section_start_obj).total_seconds()
            else:
                section_lap_sec = 0
            
            # 保存データ作成（英語列名）
            new_row = pd.DataFrame([{
                "Section": f"{next_section_num}区", 
                "Location": "Finish",
                "Time": get_time_str(now_for_record), 
                "KM-Lap": fmt_time_lap(lap_sec), 
                "SEC-Lap": fmt_time_lap(section_lap_sec), 
                "Split": fmt_time(total_sec)
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
        
        if auto_reload:
            st_autorefresh(interval=AUTO_REFRESH_INTERVAL_MS, key="datarefresh")
            # interval=10000 は 10,000ミリ秒 = 10秒 です
            # このコンポーネントを置くだけで勝手に更新されます（st.rerun不要）

