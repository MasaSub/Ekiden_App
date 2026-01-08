# ==========================================
# version = 1.0 date = 2026/01/08
# ==========================================

import streamlit as st
import pandas as pd
from datetime import datetime
from zoneinfo import ZoneInfo
from streamlit_gsheets import GSheetsConnection

# ==========================================
# 設定・定数（必要に応じて変更してください）
# ==========================================
SHEET_URL = "https://docs.google.com/spreadsheets/d/1-GSNYQYulO-83vdMOn7Trqv4l6eCjo9uzaP20KQgSS4/edit" # 【要修正】あなたのスプレッドシートのURLに書き換えてください
WORKSHEET_NAME = "log"  # スプレッドシートのタブ名

# 日本時間のタイムゾーン設定
JST = ZoneInfo("Asia/Tokyo")

# ページ設定
st.set_page_config(page_title="EKIDEN-計測", page_icon="🎽")
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

# ==========================================
# メイン処理
# ==========================================
conn = st.connection("gsheets", type=GSheetsConnection)
df = load_data(conn)

# --- A. レース開始前（データが空） ---
if df.empty or len(df) == 0:
    st.info("データがありません。レースを開始してください。")
    
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

# --- B. レース進行中 ---
else:
    # 1. 最新データの取得と解析
    last_row = df.iloc[-1]
    
    # 最後の時刻とスタート時刻を復元
    last_time_obj = parse_time_str(last_row['時刻'])
    first_time_obj = parse_time_str(df.iloc[0]['時刻'])
    now_obj = datetime.now(JST)

    # 現在の状況解析
    current_section_str = str(last_row['区間']) # "1区" など
    current_point = str(last_row['地点'])       # "Start", "3km", "Relay" など
    
    # 区間番号を数値で取り出す（"1区" -> 1）
    try:
        current_section_num = int(current_section_str.replace("区", ""))
    except:
        current_section_num = 1

    # 次のアクションを決定するロジック
    # もし前回が「Relay」なら、次は「新しい区間の1km」
    # もし前回が「Start」や「km」なら、次は「同じ区間の+1km」または「Relay」
    if current_point == "Relay":
        next_section_num = current_section_num + 1
        next_km = 1
        is_new_section_start = True
    else:
        next_section_num = current_section_num
        # 地点から数値を取り出す（"Start"なら0, "3km"なら3）
        if "Start" in current_point:
            last_km = 0
        elif "km" in current_point:
            try:
                last_km = int(current_point.replace("km", ""))
            except:
                last_km = 0
        else:
            last_km = 0
        
        next_km = last_km + 1
        is_new_section_start = False

    # --- リアルタイム経過時間表示 ---
    # 最終計測からの経過時間
    elapsed_since_last = now_obj - last_time_obj
    elapsed_total = now_obj - first_time_obj
    
    # 秒数を「MM:SS」形式に
    mins, secs = divmod(elapsed_since_last.seconds, 60)
    elapsed_str = f"{mins:02}:{secs:02}"

    st.markdown(f"### 🏃‍♂️ {next_section_num}区 走行中")
    
    # メトリクス表示
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("前の通過", f"{current_section_str} {current_point}")
    with col2:
        st.metric("前の通過時刻", last_row['時刻'])
    with col3:
        # ここが「前ラップからの経過時間」
        st.metric("⏱️ 現在の経過", elapsed_str, delta_color="off")
        st.caption("※リロードで更新")

    if st.button("🔄 時間を更新（リロード）"):
        st.rerun()

    st.divider()

    # --- 計測ボタンエリア ---
    col_lap, col_relay = st.columns([2, 1])

    # 1. ラップ計測ボタン
    with col_lap:
        btn_label = f"⏱️ {next_km}km ラップ計測"
        if st.button(btn_label, type="primary", use_container_width=True):
            # タイム計算
            lap_seconds = (now_obj - last_time_obj).total_seconds()
            total_seconds = (now_obj - first_time_obj).total_seconds()
            
            # フォーマット
            def fmt_time(sec):
                m, s = divmod(int(sec), 60)
                h, m = divmod(m, 60)
                return f"{h:02}:{m:02}:{s:02}"

            new_row = pd.DataFrame([{
                "区間": f"{next_section_num}区",
                "地点": f"{next_km}km",
                "時刻": get_time_str(now_obj),
                "ラップ": fmt_time(lap_seconds),
                "スプリット": fmt_time(total_seconds)
            }])
            
            conn.update(spreadsheet=SHEET_URL, worksheet=WORKSHEET_NAME, data=pd.concat([df, new_row]))
            st.toast(f"{next_section_num}区 {next_km}km を記録しました！")
            st.rerun()

    # 2. タスキリレーボタン
    with col_relay:
        # まだスタートしたばかりでRelayはおかしいので、最低1回計測してから表示などの制御も可能ですが
        # ここでは常に表示します
        relay_label = f"🎽 {next_section_num}区→{next_section_num+1}区へ"
        if st.button(relay_label, use_container_width=True):
            # Relayも一種のラップ計測として処理
            lap_seconds = (now_obj - last_time_obj).total_seconds()
            total_seconds = (now_obj - first_time_obj).total_seconds()
            
            def fmt_time(sec):
                m, s = divmod(int(sec), 60)
                h, m = divmod(m, 60)
                return f"{h:02}:{m:02}:{s:02}"

            new_row = pd.DataFrame([{
                "区間": f"{next_section_num}区",
                "地点": "Relay", # ここをRelayと記録することで、次は区間が変わる
                "時刻": get_time_str(now_obj),
                "ラップ": fmt_time(lap_seconds),
                "スプリット": fmt_time(total_seconds)
            }])
            
            conn.update(spreadsheet=SHEET_URL, worksheet=WORKSHEET_NAME, data=pd.concat([df, new_row]))
            st.success(f"{next_section_num}区終了！ {next_section_num+1}区へタスキをつなぎました！")
            st.rerun()

    # --- ログ表示 ---
    st.divider()
    st.markdown("### 📊 計測ログ")
    st.dataframe(df.iloc[::-1], use_container_width=True) # 新しい順に表示

    # リセット機能（管理者用）
    with st.expander("管理メニュー"):
        if st.button("⚠️ データ全消去"):
            conn.update(spreadsheet=SHEET_URL, worksheet=WORKSHEET_NAME, data=pd.DataFrame(columns=df.columns))
            st.error("全データを消去しました")
            st.rerun()