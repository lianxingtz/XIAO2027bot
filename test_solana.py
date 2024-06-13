import logging
from telethon import TelegramClient

# 设置日志记录
logging.basicConfig(level=logging.DEBUG)

# 应用程序配置
api_id = 24937201
api_hash = 'f4095fe464700e33528dbef82c168698'
phone_number = '+85265786847'
channel_id = -1002211930915  # 指定频道的ID

# 创建客户端
client = TelegramClient('session_name', api_id, api_hash)

async def get_channel_messages():
    try:
        # 获取频道信息
        channel = await client.get_entity(channel_id)

        # 获取频道中的最新消息
        async for message in client.iter_messages(channel, limit=50):
            print(f"Message ID: {message.id} - Text: {message.text}")
    except Exception as e:
        print(f"Error: {e}")

async def main():
    await client.start(phone_number)
    await get_channel_messages()

with client:
    client.loop.run_until_complete(main())
