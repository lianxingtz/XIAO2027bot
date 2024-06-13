import logging
import asyncio
from flask import Flask, request, render_template, jsonify
from telethon import TelegramClient
from datetime import datetime

# 设置日志记录
logging.basicConfig(level=logging.DEBUG)

# 应用程序配置
api_id = 24937201
api_hash = 'f4095fe464700e33528dbef82c168698'
phone_number = '+85265786847'
channel_id = -1002211930915  # 指定频道的ID

# 创建客户端
client = TelegramClient('session_name', api_id, api_hash)

# 创建Flask应用
app = Flask(__name__)

# 保存所有订阅信息的全局变量
subscriptions_data = []

@app.route('/')
def index():
    try:
        messages = fetch_messages()
        logging.debug(f"Fetched messages: {messages}")
        return render_template('test_telegram.html', messages=messages)
    except Exception as e:
        logging.error(f"Error: {e}")
        return "An error occurred: {}".format(e)

@app.route('/api/telegram_subscriptions')
def api_telegram_subscriptions():
    start = int(request.args.get('start', 0))
    end = int(request.args.get('end', 50))
    return jsonify(subscriptions_data[start:end])

async def get_channel_messages():
    try:
        # 获取频道信息
        channel = await client.get_entity(channel_id)
        logging.debug(f"Fetched channel: {channel}")

        # 获取频道中的最新消息
        messages = []
        async for message in client.iter_messages(channel, limit=50):
            logging.debug(f"Fetched message: {message}")

            # 检查消息文本是否为 None
            if message.text is None:
                logging.error(f"Message ID {message.id} has no text.")
                continue

            push_date = message.date.astimezone().strftime('%Y-%m-%d %H:%M:%S')  # 将消息时间转换为有时区的日期时间对象
            try:
                # 假设消息文本以某种格式包含所需的所有数据，解析这些数据
                text_parts = message.text.split(' ')
                message_data = {
                    "id": message.id,
                    "text": message.text,
                    "date": message.date.strftime('%Y-%m-%d %H:%M:%S'),
                    "push_date": push_date,  # 推送日期为消息日期
                    "address": text_parts[3],
                    "name": text_parts[5],
                    "symbol": text_parts[7],
                    "holders": text_parts[9],
                    "dev_balance": text_parts[11],
                    "initial_pool_ratio": text_parts[13],
                    "pool_initial": text_parts[15],
                    "pool_current": text_parts[17],
                    "price": text_parts[19],
                    "fdv": text_parts[21],
                    "circulating_market_cap": text_parts[23],
                    "top20_strategic_wallets": text_parts[25],
                    "top50_strategic_wallets": text_parts[27],
                    "top50_whales": text_parts[29],
                    "buy_sell_count": text_parts[31],
                    "transaction_volume": text_parts[33],
                    "pool_creation_time": text_parts[35],
                    "top10_holding_ratio": text_parts[37],
                    "monitor_link": text_parts[39]
                }
            except (IndexError, ValueError) as e:
                logging.error(f"Error parsing message {message.id}: {e}")
                message_data = {
                    "id": message.id,
                    "text": message.text,
                    "date": message.date.strftime('%Y-%m-%d %H:%M:%S'),
                    "push_date": push_date,
                    "address": "N/A",
                    "name": "N/A",
                    "symbol": "N/A",
                    "holders": "N/A",
                    "dev_balance": "N/A",
                    "initial_pool_ratio": "N/A",
                    "pool_initial": "N/A",
                    "pool_current": "N/A",
                    "price": "N/A",
                    "fdv": "N/A",
                    "circulating_market_cap": "N/A",
                    "top20_strategic_wallets": "N/A",
                    "top50_strategic_wallets": "N/A",
                    "top50_whales": "N/A",
                    "buy_sell_count": "N/A",
                    "transaction_volume": "N/A",
                    "pool_creation_time": "N/A",
                    "top10_holding_ratio": "N/A",
                    "monitor_link": "N/A"
                }
            logging.debug(f"Processed message: {message_data}")
            messages.append(message_data)
        return messages
    except Exception as e:
        logging.error(f"Error: {e}")
        return []

async def main():
    await client.start(phone_number)
    return await get_channel_messages()

def fetch_messages():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    with client:
        return loop.run_until_complete(main())

# 全局错误处理
@app.errorhandler(Exception)
def handle_exception(e):
    logging.error(f"Unhandled Exception: {e}")
    return "An unhandled exception occurred: {}".format(e), 500

# 启动Flask应用
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5001)
