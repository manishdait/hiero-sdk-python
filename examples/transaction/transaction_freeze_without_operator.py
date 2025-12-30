"""
Demonstrate manually freezing with client having no operator set, 
serializing, signing, and executing a transaction.

uv run examples/transaction/transaction_freeze_without_operator.py
python examples/transaction/transaction_freeze_without_operator.py
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
    ResponseCode
)


load_dotenv()

NETWORK_NAME = os.getenv("NETWORK", "testnet").lower()
OPERATOR_ID = os.getenv("OPERATOR_ID")
OPERATOR_KEY = os.getenv("OPERATOR_KEY")


def setup_client():
    """
    Create and return a Hedera Client configured with the operator credentials from environment variables.
    
    Initializes a Client for the configured network, sets its operator account and key, and returns the configured client instance.
    
    Returns:
    	client (Client): A Hedera Client configured with the operator account.
    
    Raises:
    	RuntimeError: If OPERATOR_ID or OPERATOR_KEY are not set, or if client initialization fails.
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



def create_client_without_operator():
    """
    Create a Hedera SDK client for the configured network without assigning an operator.
    
    Returns:
        Client: A Hedera `Client` instance configured for NETWORK_NAME with no operator set.
    """
    secondary_client = Client(Network(NETWORK_NAME))

    return secondary_client

def build_unsigned_bytes(executor_client, secondary_client):
    """
    Constructs a TopicCreateTransaction, freezes it with the provided client that has no operator, and produces the serialized unsigned transaction.
    
    Parameters:
        executor_client (Client): Client whose operator account is used to generate the TransactionId.
        secondary_client (Client): Client without an operator used to perform the freeze.
    
    Returns:
        bytes: Serialized unsigned transaction bytes ready for signing and submission.
    """
    tx_id = TransactionId.generate(executor_client.operator_account_id)

    tx = (
        TopicCreateTransaction()
        .set_memo("Test Topic Creation")
        .set_transaction_id(tx_id)
    )

    # Manually freeze the transaction using the secondary client having no operator
    tx.freeze_with(secondary_client)

    unsigned_bytes = tx.to_bytes()
    print(f"Transaction frozen and serialized ({len(unsigned_bytes)} bytes).")

    return unsigned_bytes

def sign_and_execute(unsigned_bytes, executor_client):
    """
    Sign a deserialized transaction with the executor's operator key and submit it to the Hedera network.
    
    Parameters:
        unsigned_bytes (bytes): Serialized transaction bytes representing an unsigned transaction.
        executor_client (Client): Hedera client whose operator credentials will sign and execute the transaction.
    
    Raises:
        RuntimeError: If deserialization, signing, or execution fails, or if the transaction receipt status is not SUCCESS.
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
    Run the end-to-end example: build an unsigned TopicCreate transaction, sign it with the operator, and execute it on the Hedera network.
    
    Performs these steps: set up the executor client with operator credentials, create a secondary client without an operator to freeze and serialize the unsigned transaction, then deserialize, sign, and execute the transaction. Exits the process with status 1 on error.
    """
    try:
        executor_client = setup_client()
        secondary_client = create_client_without_operator()

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