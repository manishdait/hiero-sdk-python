from hiero_sdk_python.account.account_create_transaction import AccountCreateTransaction
from hiero_sdk_python.account.account_id import AccountId
from hiero_sdk_python.client.client import Client
from hiero_sdk_python.crypto.private_key import PrivateKey
from hiero_sdk_python.transaction.transaction import Transaction
from hiero_sdk_python.transaction.transaction_id import TransactionId


def main():
    client = Client.from_env()
    key = PrivateKey.generate_ecdsa()

    tx = (
        AccountCreateTransaction()
        .set_key_with_alias(key)
        .set_initial_balance(1)
        .set_account_memo("test_account")
        .set_node_account_ids([AccountId(0, 0, 3)])
        .set_transaction_id(TransactionId.generate(client.operator_account_id))
        .freeze()
    )
    tx_bytes = tx.to_bytes()
    from_bytes_tx = Transaction.from_bytes(tx_bytes)

    print(from_bytes_tx.initial_balance)
    print(from_bytes_tx)

    receipt = from_bytes_tx.execute(client)
    print(receipt)


if __name__ == "__main__":
    main()
