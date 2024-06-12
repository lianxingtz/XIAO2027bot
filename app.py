from flask import Flask, request, render_template, redirect, url_for, flash, session
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

app = Flask(__name__)
app.secret_key = 'your_secret_key'

client = Client("https://api.mainnet-beta.solana.com")

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
        return render_template('log.html', log=log)
    return render_template('buy_sell.html')

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
    app.run(host='0.0.0.0', port=port)
