import os
import json
from dotenv import load_dotenv
from web3 import Web3
from web3.middleware import ExtraDataToPOAMiddleware
import solcx

# Carrega variáveis do .env
load_dotenv()

RPC_URL = os.getenv("RPC_URL", os.getenv("GANACHE_RPC_URL", "http://127.0.0.1:7545"))
PRIVATE_KEY = os.getenv("PRIVATE_KEY")

if not PRIVATE_KEY or PRIVATE_KEY == "0000000000000000000000000000000000000000000000000000000000000000":
    print("ERRO: Configure sua PRIVATE_KEY real no arquivo .env!")
    exit(1)

def compile_contract():
    print("Instalando compilador Solidity (Pode demorar alguns segundos na 1a vez)...")
    solcx.install_solc("0.8.0")
    
    print("Compilando IpeVault.sol...")
    with open("contracts/IpeVault.sol", "r", encoding="utf-8") as f:
        source_code = f.read()

    compiled_sol = solcx.compile_source(
        source_code,
        output_values=["abi", "bin"],
        solc_version="0.8.0"
    )

    contract_interface = compiled_sol["<stdin>:IpeVault"]
    return contract_interface

def deploy():
    w3 = Web3(Web3.HTTPProvider(RPC_URL))
    w3.middleware_onion.inject(ExtraDataToPOAMiddleware, layer=0)

    if not w3.is_connected():
        print(f"Falha ao conectar no provedor RPC: {RPC_URL}")
        return

    account = w3.eth.account.from_key(PRIVATE_KEY)
    print(f"Conta Carregada: {account.address}")
    
    balance = w3.eth.get_balance(account.address)
    print(f"Saldo atual: {w3.from_wei(balance, 'ether')} ETH")
    
    contract_interface = compile_contract()
    IpeVault = w3.eth.contract(abi=contract_interface['abi'], bytecode=contract_interface['bin'])
    
    print("Preparando Transação de Deploy (MultiSig)...")
    nonce = w3.eth.get_transaction_count(account.address)
    chain_id = w3.eth.chain_id
    
    # Obtem os signatários do .env, caso não existam, tenta pegar do nó (Ganache), por último fallback.
    env_signers = os.getenv("SIGNERS")
    if env_signers:
        signers = [s.strip() for s in env_signers.split(",") if s.strip()]
        if len(signers) < 3:
            print("Aviso: Menos de 3 signatários definidos no .env. Completando repetidos.")
            while len(signers) < 3:
                signers.append(signers[0] if signers else account.address)
        # Limita a 3 pro nosso caso
        signers = signers[:3]
    else:
        try:
            signers = w3.eth.accounts[1:4]
            if len(signers) < 3:
                raise ValueError
        except:
            # Fallback mock se accounts falhar (testnets como Sepolia não possuem w3.eth.accounts)
            signers = [account.address, account.address, account.address] 
    
    print(f"Comitê de Signatários (2 de 3): {signers}")
    
    transaction = IpeVault.constructor(signers, 2).build_transaction({
        "chainId": chain_id,
        "gasPrice": w3.eth.gas_price,
        "from": account.address,
        "nonce": nonce
    })
    
    gas_estimate = w3.eth.estimate_gas(transaction)
    transaction["gas"] = int(gas_estimate * 1.5)

    print("Assinando Transação...")
    signed_txn = w3.eth.account.sign_transaction(transaction, private_key=PRIVATE_KEY)
    
    print(f"Enviando para a rede (Chain ID: {chain_id})...")
    tx_hash = w3.eth.send_raw_transaction(signed_txn.raw_transaction)
    
    print(f"Transação enviada! Hash: {w3.to_hex(tx_hash)}")
    print("Aguardando confirmação... (Isso pode demorar alguns minutos na rede Sepolia)")
    
    tx_receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=400)
    
    contract_address = tx_receipt.contractAddress
    print(f"\n======================================")
    print(f"DEPLOY CONCLUÍDO COM SUCESSO!")
    print(f"Endereço do IpeVault: {contract_address}")
    
    # Se a rede for Sepolia ou outra testnet (não local), fund com valor baixo para não gastar faucet à toa
    fund_amount = 0.01 if chain_id not in [1337, 5777] else 10
    
    print(f"Enviando {fund_amount} ETH para financiar o cofre (Vault)...")
    try:
        tx_fund = {
            'to': contract_address,
            'value': w3.to_wei(fund_amount, 'ether'),
            'gas': 2000000,
            'gasPrice': w3.eth.gas_price,
            'nonce': w3.eth.get_transaction_count(account.address),
            'chainId': chain_id
        }
        signed_tx_fund = w3.eth.account.sign_transaction(tx_fund, private_key=PRIVATE_KEY)
        tx_fund_hash = w3.eth.send_raw_transaction(signed_tx_fund.raw_transaction)
        w3.eth.wait_for_transaction_receipt(tx_fund_hash, timeout=400)
        print(f"Cofre financiado com {fund_amount} ETH!")
    except Exception as e:
        print(f"Erro ao tentar financiar o cofre: {e}")
        print("Você precisará depositar manualmente o saldo inicial depois.")
    
    print(f"======================================")
    
    # Salvar config para o Graph Engine ler depois
    config_data = {
        "address": contract_address,
        "abi": contract_interface['abi'],
        "human_signers": signers
    }
    with open("contract_config.json", "w") as f:
        json.dump(config_data, f, indent=4)
        
    print("Arquivo 'contract_config.json' salvo! O graph_engine.py utilizará isso automaticamente.")

if __name__ == "__main__":
    try:
        deploy()
    except Exception as e:
        print(f"Erro durante o processo: {e}")
