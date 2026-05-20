from __future__ import annotations

from hiero_sdk_python.account.account_create_transaction import AccountCreateTransaction
from hiero_sdk_python.account.account_id import AccountId
from hiero_sdk_python.crypto.private_key import PrivateKey
from hiero_sdk_python.transaction.transaction import Transaction
from hiero_sdk_python.transaction.transaction_id import TransactionId


def test_to_bytes():
    tx = (
        AccountCreateTransaction()
        .set_key_without_alias(PrivateKey.generate())
        .set_initial_balance(1)
        .set_transaction_id(TransactionId.generate(AccountId(0, 0, 2)))
        .set_node_account_ids([AccountId(0, 0, 3), AccountId(0, 0, 4)])
        .freeze()
    )

    print(tx.node_account_ids)
    print(tx.node_account_id)
    print(tx._transaction_body_bytes)

    bytes_tx = tx.to_bytes()

    print(bytes_tx)

    from_bytes = Transaction.from_bytes(bytes_tx)
    print(tx._transaction_body_bytes)
    print(from_bytes._transaction_body_bytes)
