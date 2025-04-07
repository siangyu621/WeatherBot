from flask import Flask, request, abort
import requests, json, time
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import MessageEvent, TextMessage, TextSendMessage, QuickReply, QuickReplyButton, MessageAction, ImageSendMessage
from datetime import datetime
import os
app = Flask(__name__)

# 設定LINE Bot Token 和 Secret用於驗證和授權
LINE_CHANNEL_ACCESS_TOKEN =os.getenv('LINE_CHANNEL_ACCESS_TOKEN')
LINE_CHANNEL_SECRET =os.getenv('LINE_CHANNEL_SECRET')
CWA_API_KEY = os.getenv('CWA_API_KEY')
line_bot_api = LineBotApi(LINE_CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(LINE_CHANNEL_SECRET)

# 區域與縣市對應表定義台灣各區域以及各區域包含的縣市
REGIONS = {
    "北部": ["基隆市", "臺北市", "新北市", "桃園市", "新竹市", "新竹縣"],
    "中部": ["苗栗縣", "臺中市", "彰化縣", "南投縣", "雲林縣"],
    "南部": ["嘉義市", "嘉義縣", "臺南市", "高雄市", "屏東縣"],
    "東部": ["宜蘭縣", "花蓮縣", "臺東縣"],
    "離島": ["澎湖縣", "金門縣", "連江縣"]
}

# 取得天氣資訊的函數，根據指定的縣市名稱來取得天氣資訊
def get_weather(city_name):
    api_url = f"https://opendata.cwa.gov.tw/api/v1/rest/datastore/F-C0032-001?Authorization={CWA_API_KEY}&locationName={city_name}"
    response = requests.get(api_url)  # 向中央氣象局的API請求天氣資料
    data = response.json()  # 解析回應的JSON資料
    
    # 檢查資料中是否包含天氣資訊
    if "records" in data and "location" in data["records"]:
        location = data["records"]["location"][0]
        weather_elements = location["weatherElement"]
        description = weather_elements[0]["time"][0]["parameter"]["parameterName"]
        temp_low = weather_elements[2]["time"][0]["parameter"]["parameterName"]
        temp_high = weather_elements[4]["time"][0]["parameter"]["parameterName"]
        comfort = weather_elements[3]["time"][0]["parameter"]["parameterName"]
        rain_prob = int(weather_elements[1]["time"][0]["parameter"]["parameterName"])
        
        # 根據天氣資料產生天氣提醒
        reminder = ""
        if rain_prob >=40:
            reminder += "⚠️ 降雨機率較高，記得攜帶雨具！\n"
        if int(temp_high) >= 30:
            reminder += "🥵 天氣炎熱，請注意防曬和補充水分！\n"
        if int(temp_low) <= 12:
            reminder += "🥶 氣溫較低，記得穿著保暖衣物！\n"
        if not reminder:
            reminder = "🌤 天氣狀況良好，適合外出活動"
        
        date_today = datetime.now().strftime('%Y-%m-%d')
        
        return (f"📅 日期：{date_today}\n"
                f"🌆 {city_name} 3小時內天氣預報：\n"
                f"🌤 天氣狀況：{description}\n"
                f"🌡 溫度：{temp_low}~{temp_high}°C\n"
                f"😊 舒適度：{comfort}\n"
                f"☔ 降雨機率：{rain_prob}%\n"
                f"📢 小提醒：\n{reminder}")
    else:
        return "無法取得天氣資訊，請稍後再試。"

# 地震資訊函式，取得最新的地震資訊
def earthquake():
    msg = ['找不到地震資訊', 'https://example.com/demo.jpg']
    try:
        url = f'https://opendata.cwa.gov.tw/api/v1/rest/datastore/E-A0016-001?Authorization={CWA_API_KEY}'
        e_data = requests.get(url)  # 向中央氣象局API請求地震資料
        e_data_json = e_data.json()  # 解析回應的JSON資料
        eq = e_data_json['records']['Earthquake']
        for i in eq:
            loc = i['EarthquakeInfo']['Epicenter']['Location']
            val = i['EarthquakeInfo']['EarthquakeMagnitude']['MagnitudeValue']
            dep = i['EarthquakeInfo']['FocalDepth']
            eq_time = i['EarthquakeInfo']['OriginTime']
            img = i['ReportImageURI']
            msg = [f'{loc}，芮氏規模 {val} 級，深度 {dep} 公里，發生時間 {eq_time}。', img]
            break
        return msg
    except:
        return msg

# 取得空氣品質資訊的函數，取得並顯示全台灣的空氣品質資訊
def get_air_quality():
    result = []
    url = 'https://data.moenv.gov.tw/api/v2/aqx_p_432?api_key=e8dd42e6-9b8b-43f8-991e-b3dee723a52d&limit=1000&sort=ImportDate%20desc&format=JSON'
    req = requests.get(url)  # 向環保署的API請求空氣品質資料
    data = req.json()  # 解析回應的JSON資料
    records = data['records']
    for item in records:
        county = item['county']      # 縣市
        sitename = item['sitename']  # 區域
        aqi = int(item['aqi'])       # AQI 數值
        aqi_status = ['良好','普通','對敏感族群不健康','對所有族群不健康','非常不健康','危害']
        msg = aqi_status[aqi//50]    # 除以五十之後無條件捨去，取得整數
        result.append((aqi, f"{county}{sitename}: AQI {aqi}, 狀態: {msg}"))  # 記錄結果
    
    result.sort(reverse=True, key=lambda x: x[0])  # 按 AQI 大小排序
    air_quality_info = [info for _, info in result]
    
    date_today = datetime.now().strftime('%Y-%m-%d')
    return "📅 日期：{}\n{}".format(date_today, '\n'.join(air_quality_info))
# 接收來自LINE的訊息
@app.route("/callback", methods=['POST'])
def callback():
    signature = request.headers['X-Line-Signature']  # 從請求標頭中取得簽名
    body = request.get_data(as_text=True)  # 取得請求的body
    try:
        handler.handle(body, signature)  # 驗證簽名並處理訊息
    except InvalidSignatureError:
        abort(400)  # 簽名驗證失敗時回應400錯誤
    return 'OK'

# 處理來自LINE的文字訊息
@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    text = event.message.text  # 取得使用者輸入的文字訊息
    if  text == 'W' or text == 'w':
        # 使用者輸入'W'或'w'時，顯示區域選單
        buttons = [QuickReplyButton(action=MessageAction(label=region, text=region)) for region in REGIONS.keys()]
        reply = TextSendMessage(
            text="請選擇區域：",
            quick_reply=QuickReply(items=buttons)
        )
    elif text in REGIONS:
        # 使用者選擇區域後，顯示該區域的縣市選單
        buttons = [QuickReplyButton(action=MessageAction(label=city, text=city)) for city in REGIONS[text]]
        reply = TextSendMessage(
            text=f"請選擇 {text} 的縣市：",
            quick_reply=QuickReply(items=buttons)
        )
    elif any(text in cities for cities in REGIONS.values()):
        # 使用者選擇縣市後，顯示該縣市的天氣資訊
        reply = TextSendMessage(text=get_weather(text))
    elif text == 'E' or text == 'e':
        # 使用者輸入'E'或'e'時，顯示最新的地震資訊
        msg = earthquake()
        reply = [
            TextSendMessage(text=msg[0]),
            ImageSendMessage(original_content_url=msg[1], preview_image_url=msg[1])
        ]
    elif text == 'A' or text == 'a':
        # 使用者輸入'A'或'a'時，顯示空氣品質資訊
        reply = TextSendMessage(text=get_air_quality())
    elif text == 'R' or text == 'r':
        # 使用者輸入'R'或'r'時，顯示雷達回波圖
        reply = ImageSendMessage(
            original_content_url=f'https://cwaopendata.s3.ap-northeast-1.amazonaws.com/Observation/O-A0058-001.png?{time.time_ns()}',
            preview_image_url=f'https://cwaopendata.s3.ap-northeast-1.amazonaws.com/Observation/O-A0058-001.png?{time.time_ns()}'
        )
    else:
        # 其他情況下，提示使用者重新輸入
        reply = TextSendMessage(text="請輸入'W'查詢天氣資訊，'E'來查詢地震資訊，'A'查詢空氣品質，'R'查詢雷達回波")
    
    line_bot_api.reply_message(event.reply_token, reply)  # 回應使用者的訊息

# 主程式入口
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)  # 啟動Flask服務，監聽所有IP地址的5000端口