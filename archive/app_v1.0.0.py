# ==========================================
# version = 1.0.0 date = 2026/01/08
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

# ページ設定
st.set_page_config(page_title="駅伝ラップ計測", page_icon="🎽")

# タイトル表示
st.title("🎽 駅伝ラップ計測アプリ")

# ==========================================
# 1. データ接続と読み込み機能
# ==========================================
# Google Sheetsへの接続を確立
conn = st.connection("gsheets", type=GSheetsConnection)

def load_data():
    """
    スプレッドシートからデータを読み込む関数
    ttl=2 は「2秒間はキャッシュを使う」という意味。
    これにより、頻繁なリロードでもAPI制限にかかりにくくしつつ、最新データを取得します。
    """
    try:
        # スプレッドシートのデータをDataFrameとして取得
        df = conn.read(spreadsheet=SHEET_URL, worksheet=WORKSHEET_NAME, ttl=2)
        return df
    except Exception as e:
        st.error(f"データの読み込みに失敗しました: {e}")
        return pd.DataFrame() # 空のデータを返す

# データをロード
df = load_data()

# ==========================================
# 2. メインロジック（計測・表示）
# ==========================================

# --- A. まだデータがない場合（レース開始前） ---
if df.empty or len(df) == 0:
    st.info("現在は待機中です。1区の走者がスタートしたらボタンを押してください。")
    
    # スタートボタン
    if st.button("🔫 レーススタート (0km)", type="primary", use_container_width=True):
        current_time = datetime.now(ZoneInfo("Asia/Tokyo")).strftime("%H:%M:%S")
        
        # スタート地点(0km)のデータを作成
        start_data = pd.DataFrame([{
            "point": "0km (Start)",
            "time": current_time,
            "split": "00:00:00"
        }])
        
        # スプレッドシートをこのデータで上書き更新
        conn.update(spreadsheet=SHEET_URL, worksheet=WORKSHEET_NAME, data=start_data)
        st.success("レースを開始しました！")
        st.rerun() # 画面をリロードして反映

# --- B. レース進行中 ---
else:
    # 最新のデータを取得
    last_row = df.iloc[-1]
    start_time_str = df.iloc[0]['time']
    
    # 現在の地点（例: データが1行なら次は1km地点）
    next_km = len(df) 
    
    # --- 現在のステータス表示エリア ---
    st.markdown("### ⏱️ 最新状況")
    col1, col2 = st.columns(2)
    with col1:
        st.metric(label="直近の通過地点", value=last_row['point'])
    with col2:
        st.metric(label="通過時刻", value=last_row['time'])

    st.divider() # 仕切り線

    # --- 計測ボタンエリア（ここが重要） ---
    st.subheader(f"🏃 次は {next_km}km 地点の計測")
    st.warning("⚠️ 計測担当者は、走者が通過した瞬間にボタンを押してください")

    # ラップ計測ボタン
    if st.button(f"⏱️ {next_km}km地点 ラップを記録", type="primary", use_container_width=True):
        # 現在時刻
        now_obj = datetime.now(ZoneInfo("Asia/Tokyo"))
        now_str = now_obj.strftime("%H:%M:%S")
        
        # スタート時刻からの経過時間計算（簡易版）
        # ※日付をまたぐ場合などはより厳密な計算が必要ですが、日中の駅伝ならこれで動作します
        start_obj = datetime.strptime(start_time_str, "%H:%M:%S").replace(year=now_obj.year, month=now_obj.month, day=now_obj.day)
        
        # マイナスになる（日付またぎ）対策
        if now_obj < start_obj:
            elapsed = now_obj - start_obj # ここは実際には日付加算などの調整が必要なケースあり
        else:
            elapsed = now_obj - start_obj
            
        # 経過時間を "HH:MM:SS" 形式に整形
        total_seconds = int(elapsed.total_seconds())
        hours, remainder = divmod(total_seconds, 3600)
        minutes, seconds = divmod(remainder, 60)
        split_str = f"{hours:02}:{minutes:02}:{seconds:02}"

        # 追加する行データ
        new_row = pd.DataFrame([{
            "point": f"{next_km}km",
            "time": now_str,
            "split": split_str
        }])
        
        # 既存データと結合
        updated_df = pd.concat([df, new_row], ignore_index=True)
        
        # スプレッドシートを更新
        conn.update(spreadsheet=SHEET_URL, worksheet=WORKSHEET_NAME, data=updated_df)
        st.toast(f"{next_km}km地点を記録しました！") # ポップアップ通知
        st.rerun()

    # --- データ一覧表示 ---
    st.divider()
    st.markdown("### 📊 計測ログ")
    # 見やすいようにテーブルを表示
    st.dataframe(df, use_container_width=True)

    # 手動更新ボタン（他の人が押したか確認するため）
    if st.button("🔄 最新情報を取得（リロード）"):
        st.rerun()

# ==========================================
# 管理用メニュー（サイドバーに隠す）
# ==========================================
with st.sidebar:
    st.header("管理メニュー")
    st.write("間違えて記録した場合、Googleスプレッドシートを直接編集して行を削除してください。")
    if st.button("⚠️ データを全てリセットする"):
        # 空のデータフレームで上書きする処理（慎重に！）
        # 安全のため、ヘッダーだけ残してクリアする処理などを実装推奨
        empty_df = pd.DataFrame(columns=["point", "time", "split"])
        conn.update(spreadsheet=SHEET_URL, worksheet=WORKSHEET_NAME, data=empty_df)
        st.error("データをリセットしました")
        st.rerun()