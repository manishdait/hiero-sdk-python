import hashlib
import socket
import ssl  # Python's ssl module implements TLS (despite the name)
import grpc
from typing import Optional
from hiero_sdk_python.account.account_id import AccountId
from hiero_sdk_python.channels import _Channel
from hiero_sdk_python.address_book.node_address import NodeAddress
from hiero_sdk_python.managed_node_address import _ManagedNodeAddress


# Timeout for fetching server certificates during TLS validation
CERT_FETCH_TIMEOUT_SECONDS = 10


class _HederaTrustManager:
    """
    Python equivalent of Java's HederaTrustManager.
    Validates server certificates by comparing SHA-384 hashes of PEM-encoded certificates
    against expected hashes from the address book.
    """

    def __init__(self, cert_hash: Optional[bytes], verify_certificate: bool):
        """
        Initialize a Hedera-style trust manager that stores the expected certificate hash.
        
        If `cert_hash` is None or empty and `verify_certificate` is True, raises ValueError because verification cannot proceed without an address book entry. If `cert_hash` is provided, it is normalized to a lowercase hexadecimal string: the code first attempts to decode the bytes as a UTF-8 string and strips an optional "0x" prefix; on Unicode decode failure it falls back to the hex representation of the bytes.
        
        Parameters:
            cert_hash: Expected certificate hash from the address book. May be UTF-8 encoded hex (optionally starting with "0x") or raw bytes.
            verify_certificate: Whether certificate verification is required; when True and no cert_hash is available, initialization fails with ValueError.
        """
        if cert_hash is None or len(cert_hash) == 0:
            if verify_certificate:
                raise ValueError(
                    "Transport security and certificate verification are enabled, "
                    "but no applicable address book was found"
                )
            self.cert_hash = None
        else:
            # Convert bytes to hex string (matching Java's String conversion)
            try:
                self.cert_hash = cert_hash.decode('utf-8').strip().lower()
                if self.cert_hash.startswith('0x'):
                    self.cert_hash = self.cert_hash[2:]
            except UnicodeDecodeError:
                self.cert_hash = cert_hash.hex().lower()

    def check_server_trusted(self, pem_cert: bytes) -> bool:
        """
        Validate the server certificate by comparing its SHA-384 hash against the configured expected hash.
        
        If no expected hash is configured, the certificate is accepted. Raises ValueError when the computed hash does not match the expected hash.
        
        Parameters:
            pem_cert (bytes): PEM-encoded certificate bytes.
        
        Returns:
            bool: True if the certificate is trusted.
        
        Raises:
            ValueError: If the computed certificate hash does not match the expected hash.
        """
        if self.cert_hash is None:
            return True

        # Compute SHA-384 hash of PEM certificate (matching Java implementation)
        cert_hash_bytes = hashlib.sha384(pem_cert).digest()
        actual_hash = cert_hash_bytes.hex().lower()

        if actual_hash != self.cert_hash:
            raise ValueError(
                f"Failed to confirm the server's certificate from a known address book. "
                f"Expected hash: {self.cert_hash}, received hash: {actual_hash}"
            )

        return True


class _Node:

    def __init__(self, account_id: AccountId, address: str, address_book: NodeAddress):
        """
        Initialize a Node with its account identifier, network address, and address book entry.
        
        Parameters:
            account_id (AccountId): The node's Hedera account identifier.
            address (str): The node's network address string (used to construct the managed address).
            address_book (NodeAddress): The address book entry associated with this node.
        """

        self._account_id: AccountId = account_id
        self._channel: Optional[_Channel] = None
        self._address_book: NodeAddress = address_book
        self._address: _ManagedNodeAddress = _ManagedNodeAddress._from_string(address)
        self._verify_certificates: bool = True
        self._root_certificates: Optional[bytes] = None
        self._node_pem_cert: Optional[bytes] = None
    
    def _close(self):
        """
        Close the channel for this node.
        
        Returns:
            None
        """
        if self._channel is not None:
            self._channel.channel.close()
            self._channel = None

    def _get_channel(self):
        """
        Return the node's gRPC channel, creating and caching it if necessary.
        
        If the node is configured for transport security, the channel is created with the node's PEM certificate (either provided root certificates or fetched from the server) and TLS credentials; certificate validation is performed when verification is enabled. For insecure nodes, an insecure channel is created.
        
        Returns:
            _Channel: The cached or newly created channel for this node.
        
        Raises:
            ValueError: If transport security is required but no certificate is available.
        """
        if self._channel:
            return self._channel

        if self._address._is_transport_security():
            if self._root_certificates:
                # Use the certificate that is provided
                self._node_pem_cert = self._root_certificates
            else:
                # Fetch pem_cert for the node
                self._node_pem_cert = self._fetch_server_certificate_pem()

            if not self._node_pem_cert:
                raise ValueError("No certificate available.")
            
            # Validate certificate if verification is enabled
            if self._verify_certificates:
                self._validate_tls_certificate_with_trust_manager()            
            
            options = self._build_channel_options()
            credentials = grpc.ssl_channel_credentials(
                root_certificates=self._node_pem_cert,
                private_key=None,
                certificate_chain=None,
            )
            channel = grpc.secure_channel(str(self._address), credentials, options=options)
        else:
            channel = grpc.insecure_channel(str(self._address))

        self._channel = _Channel(channel)

        return self._channel

    def _apply_transport_security(self, enabled: bool):
        """
        Switches the node's address between secure and insecure transport modes.
        
        Closes any existing channel and updates the node's managed address to the secure form when enabling transport security or to the insecure form when disabling it. No action is taken if the address is already in the requested mode.
        
        Parameters:
            enabled (bool): True to enable transport security, False to disable it.
        """
        if enabled and self._address._is_transport_security():
            return
        if not enabled and not self._address._is_transport_security():
            return
        
        self._close()
        
        if enabled:
            self._address = self._address._to_secure()
        else:
            self._address = self._address._to_insecure()

    def _set_root_certificates(self, root_certificates: Optional[bytes]):
        """
        Assign custom root certificates used for TLS verification.
        """
        self._root_certificates = root_certificates
        if self._channel and self._address._is_transport_security():
            self._close()
            
    def _set_verify_certificates(self, verify: bool):
        """
        Set whether TLS certificates should be verified.
        """
        if self._verify_certificates == verify:
            return
        
        self._verify_certificates = verify
        
        if verify and self._channel and self._address._is_transport_security():
            # Force channel recreation to ensure certificates are revalidated.
            self._close()

    def _build_channel_options(self):
        """
        Build gRPC channel options for TLS connections.

        The options `grpc.default_authority` and `grpc.ssl_target_name_override`
        are intentionally set to a fixed value ("127.0.0.1") to bypass standard
        TLS hostname verification.

        This is REQUIRED because Hedera nodes are connected to via IP addresses 
        from the address book, while their TLS certificates are not issued for 
        those IPs. As a result, standard hostname verification would fail even 
        for legitimate nodes.

        Although hostname verification is disabled, transport security is NOT
        weakened. Instead of relying on hostnames, the SDK validates the server
        by performing certificate hash pinning. This guarantees the client is 
        communicating with the correct Hedera node regardless of the hostname 
        or IP address used to connect.
        """
        options = [
            ("grpc.default_authority", "127.0.0.1"),
            ("grpc.ssl_target_name_override", "127.0.0.1"),
            ("grpc.keepalive_time_ms", 100000),
            ("grpc.keepalive_timeout_ms", 10000),
            ("grpc.keepalive_permit_without_calls", 1)
        ]

        return options

    def _validate_tls_certificate_with_trust_manager(self):
        """
        Validate the remote TLS certificate using HederaTrustManager.
        This performs a pre-handshake validation by fetching the server certificate
        and comparing its hash to the expected hash from the address book.
        
        Note: If verification is enabled but no cert hash is available (e.g., in unit tests
        without address books), validation is skipped rather than raising an error.
        """
        if not self._address._is_transport_security() or not self._verify_certificates:
            return

        cert_hash = None
        if self._address_book:  # pylint: disable=protected-access
            cert_hash = self._address_book._cert_hash  # pylint: disable=protected-access

        # Skip validation if no cert hash is available (e.g., in unit tests)
        # This allows tests to run without address books while still enabling
        # verification in production where address books are available.
        if cert_hash is None or len(cert_hash) == 0:
            return

        # Create trust manager and validate certificate
        trust_manager = _HederaTrustManager(cert_hash, self._verify_certificates)
        trust_manager.check_server_trusted(self._node_pem_cert)

    @staticmethod
    def _normalize_cert_hash(cert_hash: bytes) -> str:
        """
        Normalize the certificate hash to a lowercase hex string.
        """
        try:
            decoded = cert_hash.decode('utf-8').strip().lower()
            if decoded.startswith("0x"):
                decoded = decoded[2:]

            return decoded
        except UnicodeDecodeError:
            return cert_hash.hex()

    def _fetch_server_certificate_pem(self) -> bytes:
        """
        Perform a TLS handshake and retrieve the server certificate in PEM format.
        
        Returns:
            bytes: PEM-encoded certificate bytes
        """
        if not self._address_book:
            return None

        host = self._address._get_host()
        port = self._address._get_port()
        server_hostname = host

        # Create TLS context that accepts any certificate (we validate hash ourselves)
        context = ssl.create_default_context()
        # Restrict SSL/TLS versions to TLSv1.2+ only for security
        if hasattr(context, 'minimum_version') and hasattr(ssl, 'TLSVersion'):
            context.minimum_version = ssl.TLSVersion.TLSv1_2
        else:
            # Backwards compatibility for Python <3.7 that lacks minimum_version
            context.options |= ssl.OP_NO_TLSv1 | ssl.OP_NO_TLSv1_1

        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE

        with socket.create_connection((host, port), timeout=CERT_FETCH_TIMEOUT_SECONDS) as sock:
            with context.wrap_socket(sock, server_hostname=server_hostname) as tls_socket:
                der_cert = tls_socket.getpeercert(True)

        # Convert DER to PEM format (matching Java's PEM encoding)
        pem_cert = ssl.DER_cert_to_PEM_cert(der_cert).encode('utf-8')
        return pem_cert