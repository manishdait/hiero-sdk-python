import os
from dotenv import load_dotenv
from hiero_sdk_python import (
    AccountId,
    PrivateKey,
    TopicCreateTransaction,
    TransactionId,
    Client,
    Network,
    Transaction,
)

# Setup
load_dotenv(".env")
executor_id: AccountId = AccountId.from_string(os.getenv("OPERATOR_ID"))
executor_key: PrivateKey = PrivateKey.from_string(os.getenv("OPERATOR_KEY"))

# Create the client that will eventually execute the transaction
executor_client: Client = Client(Network(network="testnet"))
executor_client.set_operator(executor_id, executor_key)

freezer_id: AccountId = AccountId.from_string("0.0.4951978")  
freezer_key: PrivateKey = PrivateKey.from_string("3030020100300706052b8104000a0422042010a8f9b5fde8e64bdf2248e30dc6cc569d661be5a5e2f2b9c84a1d69c4cbc9a6")

tx_freezer_client: Client = Client(Network(network="testnet"))  
tx_freezer_client.set_operator(freezer_id, freezer_key)

## =====

tx = TopicCreateTransaction().set_memo("Test Topic Creation")  
print(executor_client.operator_account_id)
tx_id = TransactionId.generate(executor_client.operator_account_id)
tx.set_transaction_id(tx_id)
tx.freeze_with(tx_freezer_client)
unsigned_bytes = tx.to_bytes()
print(tx.transaction_id)
print(tx.node_account_id)
print("tx")
tx2 = Transaction.from_bytes(unsigned_bytes)
print(tx.transaction_id)
print(tx2.node_account_id)
receipt = tx2.execute(executor_client)