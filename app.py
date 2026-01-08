# ==========================================
# version = 1.3.2 date = 2026/01/08
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
VERSION = "ver 1.3.2" ###更新毎に書き換え

SHEET_URL = "https://docs.google.com/spreadsheets/d/1-GSNYQYulO-83vdMOn7Trqv4l6eCjo9uzaP20KQgSS4/edit" # 【要修正】あなたのスプレッドシートのURLに書き換えてください
WORKSHEET_NAME = "log"
JST = ZoneInfo("Asia/Tokyo")
AUTO_RELOAD_SEC = 10

# ページ設定
st.set_page_config(page_title="駅伝けいそくん", page_icon="🎽", layout="wide")

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

# ▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼
# 【修正】タイトル（バージョン情報付き）
# ユーザー指定のデザインに変更しました
# ▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼
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
            "KM-Lap": "00:00:00", 
            "SEC-Lap": "00:00:00", 
            "Split": "00:00:00"
        }])
        conn.update(spreadsheet=SHEET_URL, worksheet=WORKSHEET_NAME, data=start_data)
        
        # ▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼
        # 【重要】スタートした瞬間、サーバーのキャッシュを爆破する
        # これにより、待機中の他の人のスマホも次の更新で「走行中」に切り替わります
        # ▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼
        st.cache_data.clear()
        st.success("レーススタート！")
        st.rerun()

    st.write("")

    # ▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼
    # 【修正】スタート前だけ「2秒間隔」にして描画落ちを防ぐ
    # ▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼
    with st.expander("管理メニュー"):
        st.write("設定")
        auto_reload_start = st.toggle("🔄 自動更新", value=True, key="auto_reload_start")
    
    if auto_reload_start:
        # ここだけ * 200 (2000ms = 2秒) に設定します
        # 処理が軽すぎるため、1秒だと速すぎてメニューが表示されなくなるのを防ぎます
        st_autorefresh(interval=AUTO_RELOAD_SEC*1000, key="refresh_start")


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
            st_autorefresh(interval=AUTO_RELOAD_SEC*1000, key="refresh_finish")
    
    # 2. レース中
    else:
        last_time_obj = parse_time_str(last_row['Time'])
        first_time_obj = parse_time_str(df.iloc[0]['Time'])
        now_obj = datetime.now(JST)

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

        # ▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼
        # 【新機能】リアルタイム3大ラップ計算
        # ▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼
        
        # 1. キロラップ (KM-Lap): 前回の記録からの経過時間
        diff_km = (now_obj - last_time_obj).total_seconds()
        str_km_lap = fmt_time(diff_km) # mm:ss

        # 2. 区間ラップ (SEC-Lap): 現在走っている区間の開始からの経過時間
        section_start_obj = get_section_start_time(df, next_section_num)
        if section_start_obj:
            diff_sec = (now_obj - section_start_obj).total_seconds()
        else:
            diff_sec = 0
        str_sec_lap = fmt_time(diff_sec) # mm:ss

        # 3. スプリット (Split): レース開始からの総経過時間
        diff_split = (now_obj - first_time_obj).total_seconds()
        # h:mm:ss 表記にするため自作フォーマット
        h_split, rem = divmod(int(diff_split), 3600)
        m_split, s_split = divmod(rem, 60)
        str_split = f"{h_split}:{m_split:02}:{s_split:02}"

        # ▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼
        # 【新機能】ヘッダー表示：「X区 YYY済み」
        # ▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼
        if last_point == "Start":
            header_status = "Start済み"
        elif last_point == "Relay":
            header_status = "Relay済み"
        else:
            header_status = f"{last_point}通過済み"
        
        header_text = f"{current_section_str} {header_status}"

        c_title, c_btn = st.columns([1, 1])
        with c_title:
            st.markdown(f"### 🏃‍♂️ {header_text}")
        with c_btn:
            if st.button("🔄", help="更新"):
                st.cache_data.clear()
                st.rerun()

        # ▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼
        # 【新機能】3分割情報パネル (KM-Lap / SEC-Lap / Split)
        # ▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼
        st.markdown(f"""
<div style="display: flex; justify-content: space-between; align-items: center; background-color: #262730; padding: 10px; border-radius: 10px; margin-bottom: 8px; border: 1px solid #444;">
    <div style="text-align: center; flex: 1;">
        <div style="font-size: 11px; color: #aaa; margin-bottom: 2px;">キロラップ</div>
        <div style="font-size: 24px; font-weight: bold; color: #FF4B4B; line-height: 1.1;">{str_km_lap}</div>
    </div>
    <div style="width: 1px; height: 40px; background-color: #555;"></div>
    <div style="text-align: center; flex: 1;">
        <div style="font-size: 11px; color: #aaa; margin-bottom: 2px;">区間ラップ</div>
        <div style="font-size: 24px; font-weight: bold; color: #4bd6ff; line-height: 1.1;">{str_sec_lap}</div>
    </div>
    <div style="width: 1px; height: 40px; background-color: #555;"></div>
    <div style="text-align: center; flex: 1;">
        <div style="font-size: 11px; color: #aaa; margin-bottom: 2px;">スタートから</div>
        <div style="font-size: 20px; font-weight: bold; color: #ffffff; line-height: 1.3;">{str_split}</div>
    </div>
</div>
""", unsafe_allow_html=True)

        # 操作ボタン類
        # 1. ラップ計測
        if st.button(f"⏱️ {next_km}km地点 ラップ", type="primary", use_container_width=True):
            lap_sec = (now_obj - last_time_obj).total_seconds()
            total_sec = (now_obj - first_time_obj).total_seconds()
            # 【追加】区間ラップの計算
            section_start_obj = get_section_start_time(df, next_section_num)
            if section_start_obj:
                section_lap_sec = (now_obj - section_start_obj).total_seconds()
            else:
                section_lap_sec = 0
            
            # 保存データ作成（英語列名）
            new_row = pd.DataFrame([{
                "Section": f"{next_section_num}区", 
                "Location": f"{next_km}km",
                "Time": get_time_str(now_obj), 
                "KM-Lap": fmt_time(lap_sec), 
                "SEC-Lap": fmt_time(section_lap_sec), 
                "Split": fmt_time(total_sec)
            }])
            conn.update(spreadsheet=SHEET_URL, worksheet=WORKSHEET_NAME, data=pd.concat([df, new_row]))
            st.cache_data.clear() # 即クリア
            st.toast(f"{next_km}km地点を記録！")
            st.rerun()

        # 2. 中継ボタン
        if st.button(f"🎽 次へ ({next_section_num+1}区へ)", use_container_width=True):
            lap_sec = (now_obj - last_time_obj).total_seconds()
            total_sec = (now_obj - first_time_obj).total_seconds()
            # 【追加】区間ラップの計算
            section_start_obj = get_section_start_time(df, next_section_num)
            if section_start_obj:
                section_lap_sec = (now_obj - section_start_obj).total_seconds()
            else:
                section_lap_sec = 0
            
            # 保存データ作成（英語列名）
            new_row = pd.DataFrame([{
                "Section": f"{next_section_num}区", 
                "Location": "Relay",
                "Time": get_time_str(now_obj), 
                "KM-Lap": fmt_time(lap_sec), 
                "SEC-Lap": fmt_time(section_lap_sec), 
                "Split": fmt_time(total_sec)
            }])
            conn.update(spreadsheet=SHEET_URL, worksheet=WORKSHEET_NAME, data=pd.concat([df, new_row]))
            st.cache_data.clear() # 即クリア
            st.success(f"{next_section_num+1}区へリレーしました！")
            st.rerun()
        
        # 3. Finishボタン
        if st.button("🏆 Finish", use_container_width=True):
            lap_sec = (now_obj - last_time_obj).total_seconds()
            total_sec = (now_obj - first_time_obj).total_seconds()
            # 【追加】区間ラップの計算
            section_start_obj = get_section_start_time(df, next_section_num)
            if section_start_obj:
                section_lap_sec = (now_obj - section_start_obj).total_seconds()
            else:
                section_lap_sec = 0
            
            # 保存データ作成（英語列名）
            new_row = pd.DataFrame([{
                "Section": f"{next_section_num}区", 
                "Location": "Finish",
                "Time": get_time_str(now_obj), 
                "KM-Lap": fmt_time(lap_sec), 
                "SEC-Lap": fmt_time(section_lap_sec), 
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
        
        # ▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼
        # 【変更】streamlit-autorefresh による非同期更新
        # Pythonを止めることなく、ブラウザ側から10秒ごとに更新をかけます
        # ▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼
        if auto_reload:
            st_autorefresh(interval=AUTO_RELOAD_SEC*100, key="datarefresh")
            # interval=10000 は 10,000ミリ秒 = 10秒 です
            # このコンポーネントを置くだけで勝手に更新されます（st.rerun不要）

