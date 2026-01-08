# ==========================================
# version = 1.11 date = 2026/01/08
# ==========================================

import streamlit as st
import pandas as pd
from datetime import datetime
from zoneinfo import ZoneInfo
from streamlit_gsheets import GSheetsConnection

# ==========================================
# 設定・定数（必要に応じて変更してください）
# ==========================================

# 【重要】ご自身のスプレッドシートURLに書き換えてください
SHEET_URL = "https://docs.google.com/spreadsheets/d/1-GSNYQYulO-83vdMOn7Trqv4l6eCjo9uzaP20KQgSS4/edit" # 【要修正】あなたのスプレッドシートのURLに書き換えてください
WORKSHEET_NAME = "log"  # スプレッドシートのタブ名

# 日本時間のタイムゾーン設定
JST = ZoneInfo("Asia/Tokyo")

# ページ設定
st.set_page_config(page_title="EKIDEN-計測", page_icon="🎽")

# ▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼
# 【デザイン修正 1/3】 スマホ用CSS（スタイルシート）の注入
# ボタンを巨大化し、余白を削るためのコードです
# ▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼
st.markdown("""
    <style>
    /* 全体の余白を詰めて画面を広く使う */
    .block-container {
        padding-top: 1rem;
        padding-bottom: 5rem; /* 下部は誤操作防止で少し空ける */
        padding-left: 0.5rem;
        padding-right: 0.5rem;
    }
    /* ボタン全体のデザイン（高さ確保・文字サイズ大） */
    div.stButton > button {
        height: 3.5em;
        font-size: 20px;
        font-weight: bold;
        border-radius: 12px;
        width: 100%;
    }
    /* ラップ計測ボタン（Primary）だけさらに目立たせる */
    div.stButton > button[kind="primary"] {
        background-color: #FF4B4B;
        color: white;
        height: 4.5em; /* メインボタンは特に大きく */
        font-size: 24px;
        margin-bottom: 10px; /* 下のボタンとの間隔 */
    }
    </style>
    """, unsafe_allow_html=True)
# ▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲

# タイトル表示
st.title("🎽 EKIDEN-計測")

# ==========================================
# 関数定義
# ==========================================
def load_data(conn):
    try:
        # スプレッドシート読み込み（キャッシュなしで最新取得）
        df = conn.read(spreadsheet=SHEET_URL, worksheet=WORKSHEET_NAME, ttl=0)
        # 必要な列がなければ空のDFを返すなどのエラーハンドリング
        return df
    except Exception as e:
        return pd.DataFrame()

def get_time_str(dt):
    """datetimeオブジェクトを HH:MM:SS 文字列にする"""
    return dt.strftime("%H:%M:%S")

def parse_time_str(time_str):
    """HH:MM:SS 文字列を今日のdatetimeオブジェクトにする（計算用）"""
    now = datetime.now(JST)
    try:
        t = datetime.strptime(time_str, "%H:%M:%S").time()
        return datetime.combine(now.date(), t).replace(tzinfo=JST)
    except:
        return now # エラー時は現在時刻
    
def fmt_time(sec):
    """秒数を hh:mm:ss 形式にする"""
    m, s = divmod(int(sec), 60)
    h, m = divmod(m, 60)
    return f"{h:02}:{m:02}:{s:02}"

# ==========================================
# メイン処理
# ==========================================
conn = st.connection("gsheets", type=GSheetsConnection)
df = load_data(conn)

# --- A. レース開始前（データが空） ---
if df.empty or len(df) == 0:
    st.info("レース開始前")
    
    if st.button("🔫 レーススタート (1区)", type="primary", use_container_width=True):
        now = datetime.now(JST)
        # スタートデータの作成
        start_data = pd.DataFrame([{
            "区間": "1区",
            "地点": "Start",
            "時刻": get_time_str(now),
            "ラップ": "00:00:00",
            "スプリット": "00:00:00"
        }])
        conn.update(spreadsheet=SHEET_URL, worksheet=WORKSHEET_NAME, data=start_data)
        st.success("レーススタート！")
        st.rerun()

# --- B. レース進行中 or 終了後 ---
else:
    # 最新データの取得
    last_row = df.iloc[-1]
    last_point = str(last_row['地点'])
    
    # ------------------------------------
    # パターン1: すでにフィニッシュしている場合
    # ------------------------------------
    if last_point == "Finish":
        st.balloons() # お祝いのエフェクト！
        st.success("🏆 競技終了！お疲れ様でした！")
        
        st.metric("🏁 フィニッシュ時刻", last_row['時刻'])
        st.metric("⏱️ 最終タイム", last_row['スプリット'])
        
        st.divider()
        st.markdown("### 📊 最終リザルト")
        st.dataframe(df, use_container_width=True)
        
        # 管理用メニュー
        with st.expander("管理メニュー"):
            if st.button("⚠️ データ全消去（次のレースへ）"):
                conn.update(spreadsheet=SHEET_URL, worksheet=WORKSHEET_NAME, data=pd.DataFrame(columns=df.columns))
                st.rerun()

    # ------------------------------------
    # パターン2: まだレース中の場合
    # ------------------------------------
    else:
        # 時刻計算の準備
        last_time_obj = parse_time_str(last_row['時刻'])
        first_time_obj = parse_time_str(df.iloc[0]['時刻'])
        now_obj = datetime.now(JST)

        # 現在の区間などの判定
        current_section_str = str(last_row['区間']) 
        try:
            current_section_num = int(current_section_str.replace("区", ""))
        except:
            current_section_num = 1

        # 次の地点の予測
        if last_point == "Relay":
            next_section_num = current_section_num + 1
            next_km = 1
        else:
            next_section_num = current_section_num
            # "3km" -> 3 を取り出す
            if "km" in last_point:
                try:
                    last_km = int(last_point.replace("km", ""))
                except:
                    last_km = 0
            else:
                last_km = 0 # Startなど
            next_km = last_km + 1

        # 経過時間表示
        elapsed_since_last = now_obj - last_time_obj
        mins, secs = divmod(elapsed_since_last.seconds, 60)
        elapsed_str = f"{mins:02}:{secs:02}"

        st.markdown(f"### 🏃‍♂️ {next_section_num}区 走行中")

        # 状況パネル
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("前の通過", f"{last_point}")
        with col2:
            st.metric("通過時刻", last_row['時刻'])
        with col3:
            st.metric("⏱️ 現在の経過", elapsed_str)
            st.caption("※リロードで更新")

        if st.button("🔄 最新情報を取得"):
            st.rerun()

        st.divider()

        # ▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼
        # 【デザイン修正 2/3】 ボタン配置の大幅変更
        # 以前の「横並び3列」をやめ、ラップ計測ボタンを特大サイズで独立させます
        # ▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼
        
        # 1. ラップ計測ボタン（画面幅いっぱいに独立）
        # スマホで一番押しやすい位置に配置
        if st.button(f"⏱️ {next_km}km ラップ", type="primary", use_container_width=True):
            lap_sec = (now_obj - last_time_obj).total_seconds()
            total_sec = (now_obj - first_time_obj).total_seconds()
            new_row = pd.DataFrame([{
                "区間": f"{next_section_num}区", "地点": f"{next_km}km",
                "時刻": get_time_str(now_obj), "ラップ": fmt_time(lap_sec), "スプリット": fmt_time(total_sec)
            }])
            conn.update(spreadsheet=SHEET_URL, worksheet=WORKSHEET_NAME, data=pd.concat([df, new_row]))
            st.toast(f"{next_km}km地点を記録！")
            st.rerun()

        # 2. サブボタン（リレーとフィニッシュ）は横並び
        # ラップボタンの下に配置し、押し間違いを防ぎます
        c_relay, c_Finish = st.columns(2)

        with c_relay:
            if st.button(f"🎽 次へ ({next_section_num+1}区)", use_container_width=True):
                lap_sec = (now_obj - last_time_obj).total_seconds()
                total_sec = (now_obj - first_time_obj).total_seconds()
                new_row = pd.DataFrame([{
                    "区間": f"{next_section_num}区", "地点": "Relay",
                    "時刻": get_time_str(now_obj), "ラップ": fmt_time(lap_sec), "スプリット": fmt_time(total_sec)
                }])
                conn.update(spreadsheet=SHEET_URL, worksheet=WORKSHEET_NAME, data=pd.concat([df, new_row]))
                st.success(f"{next_section_num+1}区へリレーしました！")
                st.rerun()
        
        with c_Finish:
            if st.button("🏆 Finish", use_container_width=True):
                lap_sec = (now_obj - last_time_obj).total_seconds()
                total_sec = (now_obj - first_time_obj).total_seconds()
                new_row = pd.DataFrame([{
                    "区間": f"{next_section_num}区", "地点": "Finish",
                    "時刻": get_time_str(now_obj), "ラップ": fmt_time(lap_sec), "スプリット": fmt_time(total_sec)
                }])
                conn.update(spreadsheet=SHEET_URL, worksheet=WORKSHEET_NAME, data=pd.concat([df, new_row]))
                st.rerun()
        # ▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲

        # ▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼
        # 【デザイン修正 3/3】 ログの折りたたみ（Expander）
        # ログが増えてもボタンの位置が下がらないようにします
        # ▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼
        with st.expander("📊 計測ログを表示（タップして開閉）"):
            st.dataframe(df.iloc[::-1], use_container_width=True)
        # ▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲
        
        # 途中リセット用
        with st.expander("管理メニュー"):
            if st.button("⚠️ データ全消去"):
                conn.update(spreadsheet=SHEET_URL, worksheet=WORKSHEET_NAME, data=pd.DataFrame(columns=df.columns))
                st.rerun()