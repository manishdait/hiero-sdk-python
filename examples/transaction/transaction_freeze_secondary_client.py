"""
Demonstrate Manually freezing using secondary client, serializing, deserializing, signing,
and executing a Hedera transaction using hiero_sdk_python.

uv run examples/transaction/transaction_freeze_secondary_client.py
python examples/transaction/transaction_freeze_secondary_client.py 
"""

import os
import sys
from dotenv import load_dotenv

from hiero_sdk_python import (
    AccountId,
    PrivateKey,
    TopicCreateTransaction,
    TransactionId,
    Client,
    Network,
    Transaction,
    AccountCreateTransaction,
    ResponseCode
)


load_dotenv()

NETWORK_NAME = os.getenv("NETWORK", "testnet").lower()
OPERATOR_ID = os.getenv("OPERATOR_ID")
OPERATOR_KEY = os.getenv("OPERATOR_KEY")


def setup_client():
    """
    Create and configure a Hedera Client using operator credentials from environment variables.
    
    Returns:
        Client: A Client connected to the configured network with the operator set.
    
    Raises:
        RuntimeError: If OPERATOR_ID or OPERATOR_KEY are missing, or if client initialization fails.
    """
    if not OPERATOR_ID or not OPERATOR_KEY:
        raise RuntimeError("OPERATOR_ID or OPERATOR_KEY not set in .env")

    print(f"Connecting to Hedera {NETWORK_NAME} network!")

    try:
        client = Client(Network(NETWORK_NAME))

        operator_id = AccountId.from_string(OPERATOR_ID)
        operator_key = PrivateKey.from_string(OPERATOR_KEY)

        client.set_operator(operator_id, operator_key)

    except Exception as exc:
        raise RuntimeError(f"Failed to initialize client: {exc}") from exc

    print(f"Client initialized with operator {client.operator_account_id}")
    return client

def create_secondary_client(executor_client):
    """
    Create a new Hedera account on the network and return a Client configured for that account.
    
    The function generates a fresh private key, creates an account funded and created via the provided executor client, and returns a new Client whose operator is set to the created account and its private key.
    
    Returns:
        Client: A configured Client for the newly created secondary account.
    """
    private_key = PrivateKey.generate()

    receipt = (
        AccountCreateTransaction()
        .set_key_without_alias(private_key)
        .freeze_with(executor_client)
        .sign(executor_client.operator_private_key)
        .execute(executor_client)
    )

    account_id = receipt.account_id
    print(f"Secondary account created: {account_id}")

    secondary_client = Client(Network(NETWORK_NAME))
    secondary_client.set_operator(account_id, private_key)

    return secondary_client

def build_unsigned_bytes(executor_client, secondary_client):
    """
    Create a TopicCreateTransaction, freeze it with the secondary client, and serialize the unsigned (unsigned by the executor) transaction.
    
    Parameters:
        executor_client: Hedera client whose operator account is used to generate the transaction ID.
        secondary_client: Hedera client used to freeze the transaction before signing.
    
    Returns:
        bytes: Serialized bytes of the frozen, unsigned transaction.
    """
    tx_id = TransactionId.generate(executor_client.operator_account_id)

    tx = (
        TopicCreateTransaction()
        .set_memo("Test Topic Creation")
        .set_transaction_id(tx_id)
    )

    # Manually freeze the transaction using the secondary client
    tx.freeze_with(secondary_client)

    unsigned_bytes = tx.to_bytes()
    print(f"Transaction frozen and serialized ({len(unsigned_bytes)} bytes).")

    return unsigned_bytes

def sign_and_execute(unsigned_bytes, executor_client):
    """
    Deserialize an unsigned transaction, sign it with the executor's operator key, and submit it for execution.
    
    Parameters:
        unsigned_bytes (bytes): Serialized bytes of a frozen unsigned transaction.
        executor_client (Client): Hedera client whose operator private key will sign the transaction and which will be used to execute it.
    
    Raises:
        RuntimeError: If deserialization, signing, execution, or receipt validation fails. The exception message includes details from the underlying error.
    """
    try:
        tx = Transaction.from_bytes(unsigned_bytes)
        print("Transaction deserialized (unsigned).")

        tx.sign(executor_client.operator_private_key)
        print("Transaction signed by executor.")

        receipt = tx.execute(executor_client)
        if receipt.status != ResponseCode.SUCCESS:
            raise RuntimeError(f"Transaction failed with status: {ResponseCode(receipt.status).name}")
        
        print("Transaction executed successfully.")
        print("Receipt:", receipt)

    except Exception as exc:
        raise RuntimeError(f"Transaction execution failed: {exc}") from exc 


def main():
    """
    Run the example workflow that freezes a transaction using a secondary client, serializes the unsigned transaction, then deserializes, signs, and executes it.
    
    This sets up an executor client, creates a secondary client used to perform manual freezing, builds a TopicCreateTransaction with an explicit TransactionId and freezes it using the secondary client to produce unsigned bytes, and finally deserializes those bytes, signs the transaction with the executor client, and submits it to the network.
    """
    try:
        executor_client = setup_client()
        secondary_client = create_secondary_client(executor_client)

        unsigned_bytes = build_unsigned_bytes(
            executor_client,
            secondary_client,
        )

        sign_and_execute(unsigned_bytes, executor_client)

    except Exception as exc:
        print(f"Error: {exc}")
        sys.exit(1)


if __name__ == "__main__":
    main()