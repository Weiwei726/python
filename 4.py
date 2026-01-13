import requests
import time
from datetime import datetime
# 設定區
API_BASE_URL = "http://10.110.59.126/iEMWebAPI"
DISCORD_WEBHOOK_URL = "https://discord.com/api/webhooks/1450308863206232265/3iiS0wxNl0hp1EUBHeTTnB5zg5Ds22y65zcULYakT0dR95fq9wndJBiZRhkPCozMRp_0"
CHECK_INTERVAL = 120  #2分鐘
# 紀錄最後一次推播的 UID
last_notified_uid = None

def get_tag_values(tag_id):#取得測點的實測值與預測值
    try:
        url = f"{API_BASE_URL}/IEMTags/{tag_id}/Value"
        resp = requests.get(url, timeout=10)
        if resp.status_code == 200:
            val_data = resp.json()
            return val_data.get("Actual", "N/A"), val_data.get("Expected", "N/A")
    except:
        pass
    return "N/A", "N/A"

def get_iem_details(uid, asset_id):#獲取預警詳情與資產基準值
    try:
        # 1. 取得健康度基準值
        asset_url = f"{API_BASE_URL}/IEMAssets/{asset_id}/Details"
        asset_resp = requests.get(asset_url, timeout=10)
        hpi_thr = asset_resp.json().get("AssetHPIThr", "N/A") if asset_resp.status_code == 200 else "N/A"
        # 2. 取得預警詳情內容
        url = f"{API_BASE_URL}/IEMeWarnings/{uid}/Details"
        resp = requests.get(url, timeout=10)
        if resp.status_code != 200: return "無法取得詳情", "N/A", "N/A"        
        data = resp.json()
        start_hpi = data.get("StartHPI", {}) # 取得預警開始時的區段 [cite: 226, 353]
        hpi_value = start_hpi.get("HPI", "N/A") # 當時健康度 [cite: 228, 355]
        relavants = start_hpi.get("Relavants", []) # 關聯標籤清單 [cite: 229, 356]
        # 3. 處理前三大關聯測點資料
        tag_lines = []
        for i, tag in enumerate(relavants[:3], 1):
            t_id = tag.get("TagID")
            t_name = tag.get("TagName", "未知")
            actual, expected = get_tag_values(t_id)
            tag_lines.append(f"異常關聯測點{i}：關聯點tag{i}：\n{t_name}，實測值：{actual}，預測值：{expected}")            
        return "\n".join(tag_lines), hpi_value, hpi_thr
    except Exception as e:
        return f"資料抓取異常: {e}", "N/A", "N/A"
def monitor_iem():
    global last_notified_uid
    print(f"[{datetime.now().strftime('%H:%M:%S')}] 正在檢查 API 更新...")
    try:
        # 獲取最新一筆預警資訊
        list_url = f"{API_BASE_URL}/IEMeWarnings?maxCount=1&timeSort=desc"
        resp = requests.get(list_url, timeout=10)        
        if resp.status_code == 200 and resp.json():
            latest = resp.json()[0]
            uid = latest.get('UID')
            asset_id = latest.get('AssetID')
            # 如果 UID 改變，表示有新預警
            if uid != last_notified_uid:
                last_notified_uid = uid
                rel_info, hpi_val, hpi_thr = get_iem_details(uid, asset_id)                
                # 組合符合您截圖格式的訊息
                message = (f"【iEM預警通知】\n"
                    f"預警軟體：iEM\n"
                    f"預警時間：{latest.get('StartTime')}\n"
                    f"設備編號：{latest.get('EWID')}\n"
                    f"設備名稱：{latest.get('AssetPath')}\n"
                    f"預警訊息：健康度值：{hpi_val}，健康度基準值：{hpi_thr}，請確認設備是否有異常徵兆\n"
                    f"----------------------------------\n"
                    f"{rel_info}\n"
                    f"----------------------------------\n"
                    f"預警系統網址：http://10.110.59.126/iem/IEMModleState.aspx?modelid={asset_id}\n"
                    f"其他網址：http://10.110.59.126/iem/IEMModelTreatment.aspx?modelid={asset_id}&modelResultID={uid}")
                # 發送到 Discord
                requests.post(DISCORD_WEBHOOK_URL, json={"content": message}, timeout=10)
                print(f"[{datetime.now().strftime('%H:%M:%S')}] 偵測到新預警！UID: {uid} 已成功推播。")
            else:
                print(f"[{datetime.now().strftime('%H:%M:%S')}] 無新預警資料。")
    except Exception as e:
        print(f"監控執行異常: {e}")
if __name__ == "__main__":
    print(f"iEM 監控啟動，設定偵測頻率：每 {CHECK_INTERVAL} 秒一次。")    
    # 啟動時先執行一次，不要跳過第一筆
    monitor_iem()    
    while True:
        time.sleep(CHECK_INTERVAL)
        monitor_iem()