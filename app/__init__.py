from flask import Flask, render_template, request
from algosdk import kmd, util
from algosdk.future.transaction import PaymentTxn, AssetConfigTxn
from .constants import algo_precision
from algosdk.v2client import algod, indexer
from decimal import Decimal
import datetime

app = Flask(__name__)


# TODO: expose those tokens through a config file
acl = algod.AlgodClient("7c4abe856a04902a93a92321958ae34027da07fef4142f909e94a9aa559fdc69", "http://algorand-private-network:8081") 
kcl = kmd.KMDClient("376e3dba46b903c97fd083d056da80e93ad210f66c84cb2adfb77641dfaa8a5e", "http://algorand-private-network:9080")
icl = indexer.IndexerClient("", "http://algorand-private-network:8980")

# TODO: handle errors appropriately 
@app.route('/')
def index():
    #return render_template('index.html')
    if request.method == "POST":
        name = request.form["name"]
        password = request.form["password"]
        new_wallet = kcl.create_wallet(name, password)
    wallets = kcl.list_wallets()
    return render_template('wallets.html',wallets=wallets)

@app.route('/wallets', methods=['GET', 'POST'])
def wallets():
    if request.method == "POST":
        name = request.form["name"]
        password = request.form["password"]
        new_wallet = kcl.create_wallet(name, password)
    wallets = kcl.list_wallets()
    return render_template('wallets.html',wallets=wallets)

@app.route('/accounts', methods=['GET', 'POST'])
def accounts():
    accounts = []
    if request.method == "POST":
        min_balance = int(request.form["minBalance"]) if request.form["minBalance"] else None
        max_balance = int(request.form["maxBalance"]) if request.form["maxBalance"] else None
        accounts = icl.accounts(min_balance=min_balance, max_balance=max_balance)['accounts']
    else:
        accounts = icl.accounts()['accounts']
    for account in accounts:
        account['amount_str_formatted'] = f'{account["amount"]:,}'
        account['rewards_str_formatted'] = f'{account["rewards"]:,}'
    if request.method == "POST":
        return render_template('accounts.html',
                keys=accounts, 
                min_balance=min_balance, 
                max_balance=max_balance)
    return render_template('accounts.html',keys=accounts)

# TODO: Create NFT
@app.route('/wallet/<id>', methods=['GET', 'POST'])
def wallet(id=-1):
    accounts = []
    if request.method == "POST" and 'forgetPassword' not in request.form:
        name = id
        password = request.form["password"]
        wallet_handle = kcl.init_wallet_handle(name, password)
        if 'createAsset' in request.form:
            params = acl.suggested_params()
            unsigned_txn = AssetConfigTxn(
                    sender=request.form['assetFrom'],
                    sp=params,
                    total=request.form['assetAmount'],
                    default_frozen=False,
                    unit_name=request.form['assetUnit'],
                    asset_name=request.form['assetName'],
                    strict_empty_address_check=False,
                    )
            signed_txn = kcl.sign_transaction(wallet_handle, password, unsigned_txn)
            txid = acl.send_transaction(signed_txn)
            print(txid)
        elif 'sendTransaction' in request.form:
            from_account = request.form['transactionFrom']
            to_account = request.form['transactionTo']
            note = request.form['transactionNote']
            amount = int(request.form['transactionAmount'])
            params = acl.suggested_params()
            unsigned_txn = PaymentTxn(from_account, params, to_account, amount, None, note)
            signed_txn = kcl.sign_transaction(wallet_handle, password, unsigned_txn)
            txid = acl.send_transaction(signed_txn)
            print(txid)
        elif 'generateKey' in request.form:
            kcl.generate_key(wallet_handle)
        keys = kcl.list_keys(wallet_handle)
        balance = 0.0
        full_transactions_list={}
        for key in keys:
            account = acl.account_info(key)
            account['amount_str_formatted'] = f'{account["amount"]:,}'
            account['rewards_str_formatted'] = f'{account["rewards"]:,}'
            accounts.append(account)
            balance += float(account['amount'])
            transactions = icl.search_transactions_by_address(key)['transactions']
            for transaction in transactions:
                transaction['round-datetime'] = datetime.datetime.fromtimestamp(int(transaction['round-time']))
                if transaction['tx-type'] == 'pay':
                    transaction['calculated-receiver'] = transaction['payment-transaction']['receiver']
                    transaction['calculated-amount'] = f'{transaction["payment-transaction"]["amount"]:,}'
                elif transaction['tx-type'] == 'acfg':
                    transaction['calculated-receiver'] = "Asset: " + transaction['asset-config-transaction']['params']['name']
                    transaction['calculated-amount'] = f'{transaction["asset-config-transaction"]["params"]["total"]:,}'
                else:
                    transaction['calculated-receiver'] = transaction['receiver']
                    transaction['calculated-amount'] = f'{transaction["amount"]:,}'
                transaction['calculated-fee'] = f'{transaction["fee"]:,}'
                full_transactions_list[transaction['id']] = transaction
        algo_balance = util.microalgos_to_algos(Decimal(balance))
        return render_template('wallet.html', 
                wallet_id=id, 
                keys=accounts, 
                wallet_balance = f'{algo_balance:,.{algo_precision}f}', 
                set_password = password, 
                transactions=full_transactions_list.values())
    return render_template('wallet.html', wallet_id=id)


@app.route('/assets')
def assets():
    assets_raw = icl.search_assets()['assets']
    assets = []
    for asset_raw in assets_raw:
        asset = asset_raw['params']
        asset['total'] = f'{asset["total"]:,}' 
        assets.append(asset)
    return render_template('assets.html', assets=assets)

import json
@app.route('/transactions', methods=['GET', 'POST'])
def transactions():
    transactions = []
    if request.method == "POST":
        min_amount = int(request.form["minAmount"]) if request.form["minAmount"] else None
        max_amount = int(request.form["maxAmount"]) if request.form["maxAmount"] else None
        search_address = request.form["address"] if request.form["address"] else None
        transactions = icl.search_transactions(min_amount=min_amount, max_amount=max_amount, address=search_address)['transactions']
    else:
        transactions = icl.search_transactions()['transactions']
    for transaction in transactions:
        transaction['round-datetime'] = datetime.datetime.fromtimestamp(int(transaction['round-time']))
        if transaction['tx-type'] == 'pay':
            transaction['calculated-receiver'] = transaction['payment-transaction']['receiver']
            transaction['calculated-amount'] = f'{transaction["payment-transaction"]["amount"]:,}'
        elif transaction['tx-type'] == 'acfg':
            transaction['calculated-receiver'] = "Asset: " + transaction['asset-config-transaction']['params']['name']
            transaction['calculated-amount'] = f'{transaction["asset-config-transaction"]["params"]["total"]:,}'
        else:
            transaction['calculated-receiver'] = transaction['receiver']
            transaction['calculated-amount'] = f'{transaction["amount"]:,}'
        transaction['calculated-fee'] = f'{transaction["fee"]:,}'
    if request.method == "POST":
        return render_template('transactions.html',
                transactions=transactions, 
                address=search_address, 
                min_amount=min_amount, 
                max_amount=max_amount)
    return render_template('transactions.html',transactions=transactions)
