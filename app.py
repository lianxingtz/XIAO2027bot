import logging
import asyncio
from flask import Flask, request, render_template, redirect, url_for, flash, session, jsonify
from flask_socketio import SocketIO, emit
from solana.rpc.api import Client
from solana.keypair import Keypair
from solana.publickey import PublicKey
from solana.transaction import Transaction
from solana.system_program import TransferParams, transfer
import requests
from bs4 import BeautifulSoup
import time
import socket
from bip_utils import Bip39SeedGenerator, Bip44, Bip44Coins
from telethon.sync import TelegramClient
from telethon import functions, types

app = Flask(__name__)
app.secret_key = 'your_secret_key'
socketio = SocketIO(app)

client = Client("https://api.mainnet-beta.solana.com")

# Telegram 配置
telegram_api_id = '24937201'
telegram_api_hash = 'f4095fe464700e33528dbef82c168698'
telegram_phone_number = '+85265786847'
telegram_client = TelegramClient('session_name', telegram_api_id, telegram_api_hash)

# 保存所有订阅信息
subscriptions_data = []

# 保存全局日志
global_logs = []

# 记录日志的函数
def log_event(message):
    global_logs.append(message)
    socketio.emit('update_logs', {'logs': global_logs})

# 验证Solana地址的有效性
def is_valid_solana_address(address):
    try:
        PublicKey(address)
        return True
    except:
        return False

# 从助记词生成Keypair
def keypair_from_mnemonic(mnemonic):
    seed_bytes = Bip39SeedGenerator(mnemonic).Generate()
    bip44_mst_ctx = Bip44.FromSeed(seed_bytes, Bip44Coins.SOLANA)
    bip44_acc_ctx = bip44_mst_ctx.Purpose().Coin().Account(0).Change(0).AddressIndex(0)
    return Keypair.from_secret_key(bip44_acc_ctx.PrivateKey().Raw().ToBytes())

# 创建钱包
@app.route('/wallet', methods=['GET', 'POST'])
def wallet():
    if request.method == 'POST':
        action = request.form['action']
        if action == 'create':
            new_wallet = Keypair()
            if 'wallets' not in session:
                session['wallets'] = []
            session['wallets'].append({
                'secret_key': new_wallet.secret_key.hex(),
                'public_key': str(new_wallet.public_key)
            })
            session['current_wallet'] = len(session['wallets']) - 1
            session['initial_balance'] = client.get_balance(new_wallet.public_key)['result']['value']
            flash(f'钱包已创建，地址：{new_wallet.public_key}')
            log_event(f'创建新钱包，地址：{new_wallet.public_key}')
        elif action == 'import':
            import_key = request.form['import_key']
            if len(import_key.split()) in [12, 24]:  # 判断是否是助记词
                imported_wallet = keypair_from_mnemonic(import_key)
            else:  # 否则视为私钥
                imported_wallet = Keypair.from_secret_key(bytes.fromhex(import_key))
            if 'wallets' not in session:
                session['wallets'] = []
            session['wallets'].append({
                'secret_key': imported_wallet.secret_key.hex(),
                'public_key': str(imported_wallet.public_key)
            })
            session['current_wallet'] = len(session['wallets']) - 1
            session['initial_balance'] = client.get_balance(imported_wallet.public_key)['result']['value']
            flash(f'钱包已导入，地址：{imported_wallet.public_key}')
            log_event(f'导入钱包，地址：{imported_wallet.public_key}')
        return redirect(url_for('index'))
    return render_template('wallet.html')

# 转账
@app.route('/transfer', methods=['GET', 'POST'])
def transfer():
    if request.method == 'POST':
        to_address = request.form['to_address']
        amount = int(request.form['amount'])
        transaction = Transaction()
        wallet_secret_key = session['wallets'][session['current_wallet']]['secret_key']
        from_wallet = Keypair.from_secret_key(bytes.fromhex(wallet_secret_key))
        transaction.add(
            transfer(
                TransferParams(
                    from_pubkey=from_wallet.public_key,
                    to_pubkey=PublicKey(to_address),
                    lamports=amount,
                )
            )
        )
        response = client.send_transaction(transaction, from_wallet)
        flash(f'转账成功: {response}')
        log_event(f'转账 {amount} lamports 到 {to_address}，交易ID：{response["result"]}')
        return redirect(url_for('index'))
    return render_template('transfer.html')

# 显示私钥和助记词
@app.route('/show_keys')
def show_keys():
    if 'current_wallet' in session and session['current_wallet'] is not None:
        private_key = session['wallets'][session['current_wallet']]['secret_key']
        return render_template('show_keys.html', private_key=private_key)
    else:
        flash('请先创建或导入钱包', 'danger')
        return redirect(url_for('wallet'))

# 获取钱包信息和持仓列表
@app.route('/wallet_info')
def wallet_info():
    if 'current_wallet' not in session or session['current_wallet'] is None:
        flash('请先创建或导入钱包', 'danger')
        return redirect(url_for('wallet'))
    
    wallet_secret_key = session['wallets'][session['current_wallet']]['secret_key']
    wallet_address = PublicKey(session['wallets'][session['current_wallet']]['public_key'])
    current_balance = client.get_balance(wallet_address)['result']['value']
    initial_balance = session.get('initial_balance', 0)
    if initial_balance > 0:
        profit_percentage = ((current_balance - initial_balance) / initial_balance) * 100
    else:
        profit_percentage = 0

    holdings = get_holdings(wallet_address)
    wallets = session['wallets']

    log_event(f'获取钱包信息，地址：{wallet_address}，余额：{current_balance}')
    return render_template('wallet_info.html', wallet_address=wallet_address, current_balance=current_balance, profit_percentage=profit_percentage, holdings=holdings, wallets=wallets)

def get_holdings(wallet_address):
    # 这里你需要根据实际情况获取钱包中的代币信息
    # 以下是一个示例，假设获取到了一些代币信息
    return [
        {"name": "BNB", "amount": "0.00956"},
        {"name": "USDT", "amount": "0"},
        {"name": "DAI", "amount": "0"},
        {"name": "ST-2025", "amount": "0.0032"},
        {"name": "X314", "amount": "0"},
        {"name": "BEFE", "amount": "0"},
    ]

@app.route('/switch_wallet/<int:index>')
def switch_wallet(index):
    if 'wallets' not in session or index >= len(session['wallets']):
        flash('无效的钱包索引', 'danger')
    else:
        session['current_wallet'] = index
        flash('已切换钱包', 'success')
        log_event(f'切换到钱包，地址：{session["wallets"][index]["public_key"]}')
    return redirect(url_for('wallet_info'))

# 交易策略设置
@app.route('/buy_sell', methods=['GET', 'POST'])
def buy_sell():
    if request.method == 'POST':
        batches = []
        for i in range(1, len(request.form) // 5 + 1):
            batch = {
                'url': request.form[f'url{i}'],
                'amount': int(request.form[f'amount{i}']),
                'delay_seconds': int(request.form[f'delay_seconds{i}']),
                'profit_ratio': float(request.form[f'profit_ratio{i}']),
                'loss_ratio': float(request.form[f'loss_ratio{i}'])
            }
            batches.append(batch)
        
        log = trading_strategy(batches)
        flash("交易机器人已启动，查看日志获取详细信息。")
        log_event("启动交易机器人")
        return render_template('log.html', log=log)
    return render_template('buy_sell.html')

# 获取 Telegram 订阅信息并显示在网页上
@app.route('/telegram_subscriptions')
def telegram_subscriptions():
    return render_template('telegram_subscriptions.html')

@socketio.on('connect')
def handle_connect():
    print('Client connected')
    socketio.start_background_task(target=background_task)

def background_task():
    global subscriptions_data
    while True:
        async def get_subscriptions():
            async with telegram_client:
                await telegram_client.start(telegram_phone_number)
                dialogs = await telegram_client.get_dialogs()
                return [dialog.name for dialog in dialogs if dialog.is_channel or dialog.is_group]
        
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        new_subscriptions = loop.run_until_complete(get_subscriptions())
        loop.close()

        if new_subscriptions:
            subscriptions_data = new_subscriptions + subscriptions_data
            log_event(f'更新订阅信息：{subscriptions_data[:50]}')
            socketio.emit('update_subscriptions', {'subscriptions': subscriptions_data[:50]})
        socketio.sleep(5)

@app.route('/api/telegram_subscriptions')
def api_telegram_subscriptions():
    start = int(request.args.get('start', 0))
    end = int(request.args.get('end', 50))
    return jsonify(subscriptions_data[start:end])

@app.route('/global_logs')
def global_logs_page():
    return render_template('global_logs.html', logs=global_logs)

@socketio.on('fetch_logs')
def handle_fetch_logs():
    emit('update_logs', {'logs': global_logs})

@app.route('/')
def index():
    logs = []
    try:
        with open("log.txt", "r") as log_file:
            logs = log_file.readlines()
    except FileNotFoundError:
        logs = ["日志文件不存在。"]

    return render_template('index.html', logs=logs)

if __name__ == '__main__':
    # 获取本地IP地址
    hostname = socket.gethostname()
    local_ip = socket.gethostbyname(hostname)
    port = 5000
    print(f"应用已启动，可以通过以下链接访问：http://{local_ip}:{port}")
    socketio.run(app, host='0.0.0.0', port=port)
