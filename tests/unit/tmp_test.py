from __future__ import annotations

from hiero_sdk_python.account.account_create_transaction import AccountCreateTransaction
from hiero_sdk_python.account.account_id import AccountId
from hiero_sdk_python.client.client import Client
from hiero_sdk_python.crypto.private_key import PrivateKey
from hiero_sdk_python.transaction.transaction import Transaction


def test_to_bytes():
    client = Client.for_testnet()
    client.set_operator(
        AccountId.from_string("0.0.6105114"),
        PrivateKey.from_string(
            "302e020100300506032b657004220420608d13e07cab4bd92b0d56e43d15f589663d3b974db35906c4791a735389c2c5"
        ),
    )

    tx = (
        AccountCreateTransaction()
        .set_key_without_alias(PrivateKey.generate())
        .set_initial_balance(1)
        .freeze_with(client)
    )

    print(tx.node_account_ids)
    print(tx.node_account_id)
    print(len(tx._transaction_body_bytes))

    bytes_tx = tx.to_bytes()

    from_bytes = Transaction.from_bytes(bytes_tx)
    print("\n")
    print(from_bytes.node_account_ids)
    print(from_bytes.node_account_id)
    print(len(from_bytes._transaction_body_bytes))
