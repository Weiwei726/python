import requests
import time
from datetime import datetime
# 設定區
API_BASE_URL = "http://10.110.59.126/iEMWebAPI"
DISCORD_WEBHOOK_URL = "https://discord.com/api/webhooks/1450308863206232265/3iiS0wxNl0hp1EUBHeTTnB5zg5Ds22y65zcULYakT0dR95fq9wndJBiZRhkPCozMRp_0"
CHECK_INTERVAL = 120  # 2分鐘
# 紀錄最後一次推播的 UID
last_notified_uid = None
def get_tag_values(tag_id):
    try:
        url = f"{API_BASE_URL}/IEMTags/{tag_id}/Value"
        resp = requests.get(url, timeout=10)
        if resp.status_code == 200:
            val_data = resp.json()
            return val_data.get("Actual", "N/A"), val_data.get("Expected", "N/A")
    except:
        pass
    return "N/A", "N/A"
def get_iem_details(uid, asset_id):
    try:
        #取得健康度基準值
        asset_url = f"{API_BASE_URL}/IEMAssets/{asset_id}/Details"
        asset_resp = requests.get(asset_url, timeout=10)
        hpi_thr = asset_resp.json().get("AssetHPIThr", "N/A") if asset_resp.status_code == 200 else "N/A"
        #取得預警詳情內容
        url = f"{API_BASE_URL}/IEMeWarnings/{uid}/Details"
        resp = requests.get(url, timeout=10)        
        # 初始化預設值，確保即使詳情抓取失敗也能回傳基礎資訊
        rules_str = "無"
        hpi_value = "N/A"
        tag_lines = ["無法取得詳情測點"]
        if resp.status_code == 200:
            data = resp.json()            
            # 有關聯規則才發送，沒關聯規則顯示無
            rules_list = data.get('Rules', [])
            if rules_list:
                rules_str = " | ".join([r.get('RuleName', '') for r in rules_list if r.get('RuleName')])
            else:
                rules_str = "無"
            #取得預警開始時的數據
            start_hpi = data.get("StartHPI", {}) 
            hpi_value = start_hpi.get("HPI", "N/A")
            relavants = start_hpi.get("Relavants", []) # [cite: 356]
            #處理前三大關聯測點資料
            if relavants:
                tag_lines = []
                for i, tag in enumerate(relavants[:3], 1):
                    t_id = tag.get("TagID")
                    t_name = tag.get("TagName", "未知")
                    actual, expected = get_tag_values(t_id)
                    tag_lines.append(f"異常關聯測點{i}：{t_name}\n實測值：{actual}，預測值：{expected}")            
        return "\n".join(tag_lines), hpi_value, hpi_thr, rules_str
    except Exception as e:
        return f"資料抓取異常: {e}", "N/A", "N/A", "資料抓取失敗"
def monitor_iem():
    global last_notified_uid
    print(f"[{datetime.now().strftime('%H:%M:%S')}] 正在檢查 API 更新...")
    try:
        # 獲取最新一筆預警資訊 [cite: 343]
        list_url = f"{API_BASE_URL}/IEMeWarnings?maxCount=1&timeSort=desc"
        resp = requests.get(list_url, timeout=10)        
        if resp.status_code == 200 and resp.json():
            latest = resp.json()[0]
            uid = latest.get('UID') # [cite: 346]
            asset_id = latest.get('AssetID') # [cite: 347]
            if uid != last_notified_uid:
                last_notified_uid = uid
                rel_info, hpi_val, hpi_thr, rules_info = get_iem_details(uid, asset_id)                
                # 組合訊息
                message = (f"【iEM預警通知】\n"
                    f"預警時間：{latest.get('StartTime')}\n" # [cite: 349]
                    f"設備編號：{latest.get('EWID')}\n" # [cite: 348]
                    f"設備名稱：{latest.get('AssetPath')}\n"
                    f"關聯規則：{rules_info}\n"  # 無論有沒有規則都會正常顯示
                    f"預警訊息：健康度值：{hpi_val}，健康度基準值：{hpi_thr}\n"
                    f"----------------------------------\n"
                    f"{rel_info}\n"
                    f"----------------------------------\n"
                    f"預警系統網址：http://10.110.59.126/iem/IEMModleState.aspx?modelid={asset_id}\n"
                    f"處理網址：http://10.110.59.126/iem/IEMModelTreatment.aspx?modelid={asset_id}&modelResultID={uid}")
                # 發送到 Discord
                requests.post(DISCORD_WEBHOOK_URL, json={"content": message}, timeout=10)
                print(f"[{datetime.now().strftime('%H:%M:%S')}] 偵測到新預警！UID: {uid} 已成功推播。")
            else:
                print(f"[{datetime.now().strftime('%H:%M:%S')}] 無新預警資料。")
    except Exception as e:
        print(f"監控執行異常: {e}")
if __name__ == "__main__":
    print(f"iEM 監控啟動，設定偵測頻率：每 {CHECK_INTERVAL} 秒一次。")    
    monitor_iem()    
    while True:
        time.sleep(CHECK_INTERVAL)
        monitor_iem()