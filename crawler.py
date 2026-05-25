import os
import re
import json
import requests
import pandas as pd
from bs4 import BeautifulSoup
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

# 1. 讀取安全金鑰 (GitHub 執行時會自動生成這個 token.json)
SCOPES = ['https://www.googleapis.com/auth/drive']
creds = Credentials.from_service_account_file('token.json', scopes=SCOPES)
drive_service = build('drive', 'v3', credentials=creds)

# ⚠️ 請填入你的 Google Drive「個專-毛孩專案」資料夾的 ID ⚠️
FOLDER_ID = "14s8HcYo1-_OSNYWzXC9SgO79TajtHmHM" 
FILE_NAME = "doghome_gov_format.csv"

def download_existing_csv():
    try:
        query = f"'{FOLDER_ID}' in parents and name='{FILE_NAME}' and trashed=false"
        results = drive_service.files().list(q=query, fields="files(id)").execute()
        items = results.get('files', [])
        if items:
            file_id = items[0]['id']
            request = drive_service.files().get_media(fileId=file_id)
            with open(FILE_NAME, 'wb') as f:
                f.write(request.execute())
            print("📁 成功下載雲端現有 CSV，準備進行大聯盟合體...")
            return file_id
    except Exception as e:
        print(f"ℹ️ 雲端尚無檔案或下載失敗: {e}")
    return None

def upload_csv_to_drive(file_id=None):
    media = MediaFileUpload(FILE_NAME, mimetype='text/csv', resumable=True)
    if file_id:
        drive_service.files().update(fileId=file_id, media_body=media).execute()
        print("💾 覆蓋成功！雲端 CSV 已順利更新。")
    else:
        file_metadata = {'name': FILE_NAME, 'parents': [FOLDER_ID]}
        drive_service.files().create(body=file_metadata, media_body=media, fields='id').execute()
        print("💾 建立成功！初始 CSV 已上傳。")

def crawl_meetpets_data():
    """ 🐾 台灣認養地圖爬蟲 (GitHub Actions 穩定版) 🐾 """
    print("🔄 開始爬取台灣認養地圖...")
    url = "https://www.meetpets.org.tw/pets/dog"
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
    
    pet_list = []
    try:
        response = requests.get(url, headers=headers, timeout=15)
        soup = BeautifulSoup(response.text, 'html.parser')
        cards = soup.select('.view-content .views-row')
        
        for card in cards:
            a_tag = card.find('a', href=True)
            if not a_tag: continue
            story_url = a_tag['href'] if a_tag['href'].startswith('http') else f"https://www.meetpets.org.tw{a_tag['href']}"
            
            if any(x['詳細故事網址'] == story_url for x in pet_list): continue
            
            dog_name = a_tag.get_text().strip()
            img_tag = card.find('img')
            img_url = img_tag['src'] if img_tag else "https://raw.githubusercontent.com/sandy40432-afk/-/main/secret-final.png"
            
            card_text = card.get_text().strip()
            animal_sex = "M" if "公" in card_text else ("F" if "母" in card_text else "N")
            
            pet_list.append({
                "animal_subid": f"MP_{dog_name}",
                "animal_opendate": "2026-05-25", # 自動符合你的資料庫時間
                "animal_kind": "狗",
                "animal_bodytype": "MEDIUM",
                "animal_age": "ADULT",
                "animal_sex": animal_sex,
                "animal_place": "台北市",
                "shelter_tel": "請點選編號至官網聯絡送養人",
                "album_file": img_url,
                "animal_status": "OPEN",
                "詳細故事網址": story_url
            })
    except Exception as e:
        print(f"❌ 抓取錯誤: {e}")
    return pd.DataFrame(pet_list)

# 執行工作流
existing_id = download_existing_csv()
df_new = crawl_meetpets_data()

if not df_new.empty:
    if os.path.exists(FILE_NAME):
        df_old = pd.read_csv(FILE_NAME)
        df_old = df_old[~df_old["詳細故事網址"].isin(df_new["詳細故事網址"])]
        df_combined = pd.concat([df_old, df_new], ignore_index=True)
    else:
        df_combined = df_new
    df_combined.to_csv(FILE_NAME, index=False, encoding='utf-8-sig')
    upload_csv_to_drive(existing_id)
