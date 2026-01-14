"""Cryptographic utilities for encrypted compliance storage.

This module provides envelope encryption for compliance records using
AES-256-GCM authenticated encryption. Each record is encrypted with a
unique Data Encryption Key (DEK), which is then encrypted with the
Key Encryption Key (KEK).

Design:
- Envelope encryption: DEK per record, KEK for DEK encryption
- Hash chain: Computed over plaintext before encryption
- Algorithm: AES-256-GCM for authenticated encryption
- Nonce: 12 bytes (96 bits) per encryption operation

Wire format:
    [encrypted_dek (44 bytes)] [dek_nonce (12 bytes)] [data_nonce (12 bytes)] [ciphertext]

Where:
- encrypted_dek: DEK encrypted with KEK (32 byte key + 16 byte auth tag)
- dek_nonce: Nonce used for DEK encryption
- data_nonce: Nonce used for data encryption
- ciphertext: Data encrypted with DEK + auth tag
"""

import base64
import os
import secrets
from pathlib import Path
from typing import Optional, Union

from cryptography.hazmat.primitives.ciphers.aead import AESGCM


# Constants
KEK_SIZE = 32  # 256 bits
DEK_SIZE = 32  # 256 bits
NONCE_SIZE = 12  # 96 bits (standard for GCM)
AUTH_TAG_SIZE = 16  # 128 bits (standard for GCM)
ENCRYPTED_DEK_SIZE = DEK_SIZE + AUTH_TAG_SIZE  # 48 bytes


class CryptoError(Exception):
    """Base exception for cryptographic errors."""

    pass


class KeyLoadError(CryptoError):
    """Error loading encryption key."""

    pass


class EncryptionError(CryptoError):
    """Error during encryption."""

    pass


class DecryptionError(CryptoError):
    """Error during decryption (includes tampering detection)."""

    pass


class EnvelopeEncryptor:
    """Envelope encryption for compliance records.

    Uses AES-256-GCM with envelope encryption pattern:
    - Each record gets a unique Data Encryption Key (DEK)
    - DEK is encrypted with the Key Encryption Key (KEK)
    - Both keys use AES-256-GCM authenticated encryption

    Example:
        >>> encryptor = EnvelopeEncryptor(Path("keys/master.key"))
        >>> ciphertext = encryptor.encrypt(b"sensitive data")
        >>> plaintext = encryptor.decrypt(ciphertext)
        >>> assert plaintext == b"sensitive data"

    The KEK should be:
    - 32 bytes (256 bits) of cryptographically secure random data
    - Stored securely (file permissions, HSM, KMS, etc.)
    - Rotated periodically according to security policy
    """

    # Header sizes for parsing encrypted blob
    HEADER_SIZE = ENCRYPTED_DEK_SIZE + NONCE_SIZE + NONCE_SIZE  # 72 bytes

    def __init__(self, kek: Union[Path, bytes]):
        """Initialize encryptor with Key Encryption Key.

        Args:
            kek: Either a Path to a file containing the KEK, or the KEK bytes directly.
                 KEK must be exactly 32 bytes (256 bits).

        Raises:
            KeyLoadError: If the key file cannot be read or key is invalid size.
        """
        if isinstance(kek, Path):
            self._kek = self._load_kek(kek)
        else:
            if len(kek) != KEK_SIZE:
                raise KeyLoadError(
                    f"KEK must be {KEK_SIZE} bytes, got {len(kek)} bytes"
                )
            self._kek = kek

        # Validate KEK works
        self._kek_cipher = AESGCM(self._kek)

    def _load_kek(self, kek_path: Path) -> bytes:
        """Load KEK from file.

        Args:
            kek_path: Path to file containing the 32-byte KEK.
                      File can contain raw bytes or base64-encoded key.

        Returns:
            32-byte KEK.

        Raises:
            KeyLoadError: If file cannot be read or contains invalid key.
        """
        if not kek_path.exists():
            raise KeyLoadError(f"KEK file not found: {kek_path}")

        try:
            raw_content = kek_path.read_bytes()

            # Try raw bytes first (exactly 32 bytes)
            if len(raw_content) == KEK_SIZE:
                return raw_content

            # Try base64-encoded (with possible whitespace/newlines)
            try:
                decoded = base64.b64decode(raw_content.strip())
                if len(decoded) == KEK_SIZE:
                    return decoded
            except Exception:
                pass

            # Try hex-encoded
            try:
                hex_content = raw_content.decode("utf-8").strip()
                decoded = bytes.fromhex(hex_content)
                if len(decoded) == KEK_SIZE:
                    return decoded
            except Exception:
                pass

            raise KeyLoadError(
                f"KEK file must contain {KEK_SIZE} bytes "
                f"(raw, base64, or hex encoded), got {len(raw_content)} bytes"
            )

        except OSError as e:
            raise KeyLoadError(f"Failed to read KEK file: {e}")

    def encrypt(self, plaintext: bytes) -> bytes:
        """Encrypt plaintext using envelope encryption.

        Args:
            plaintext: Data to encrypt (any size).

        Returns:
            Encrypted blob containing:
            - Encrypted DEK (48 bytes: 32 key + 16 auth tag)
            - DEK nonce (12 bytes)
            - Data nonce (12 bytes)
            - Ciphertext with auth tag

        Raises:
            EncryptionError: If encryption fails.
        """
        try:
            # Generate unique DEK for this record
            dek = AESGCM.generate_key(bit_length=256)
            dek_cipher = AESGCM(dek)

            # Generate nonces
            dek_nonce = secrets.token_bytes(NONCE_SIZE)
            data_nonce = secrets.token_bytes(NONCE_SIZE)

            # Encrypt DEK with KEK
            encrypted_dek = self._kek_cipher.encrypt(dek_nonce, dek, None)

            # Encrypt data with DEK
            ciphertext = dek_cipher.encrypt(data_nonce, plaintext, None)

            # Assemble envelope: encrypted_dek || dek_nonce || data_nonce || ciphertext
            return encrypted_dek + dek_nonce + data_nonce + ciphertext

        except Exception as e:
            raise EncryptionError(f"Encryption failed: {e}")

    def decrypt(self, blob: bytes) -> bytes:
        """Decrypt envelope-encrypted data.

        Args:
            blob: Encrypted blob from encrypt().

        Returns:
            Original plaintext.

        Raises:
            DecryptionError: If decryption fails (wrong key, tampered data, etc.)
        """
        if len(blob) < self.HEADER_SIZE:
            raise DecryptionError(
                f"Encrypted blob too small: {len(blob)} bytes, "
                f"minimum {self.HEADER_SIZE} bytes required"
            )

        try:
            # Parse envelope
            offset = 0
            encrypted_dek = blob[offset : offset + ENCRYPTED_DEK_SIZE]
            offset += ENCRYPTED_DEK_SIZE

            dek_nonce = blob[offset : offset + NONCE_SIZE]
            offset += NONCE_SIZE

            data_nonce = blob[offset : offset + NONCE_SIZE]
            offset += NONCE_SIZE

            ciphertext = blob[offset:]

            # Decrypt DEK with KEK
            dek = self._kek_cipher.decrypt(dek_nonce, encrypted_dek, None)

            # Decrypt data with DEK
            dek_cipher = AESGCM(dek)
            plaintext = dek_cipher.decrypt(data_nonce, ciphertext, None)

            return plaintext

        except Exception as e:
            raise DecryptionError(f"Decryption failed: {e}")

    def encrypt_string(self, plaintext: str, encoding: str = "utf-8") -> str:
        """Encrypt a string and return base64-encoded result.

        Convenience method for encrypting text data.

        Args:
            plaintext: String to encrypt.
            encoding: String encoding (default: utf-8).

        Returns:
            Base64-encoded encrypted blob.
        """
        encrypted = self.encrypt(plaintext.encode(encoding))
        return base64.b64encode(encrypted).decode("ascii")

    def decrypt_string(self, blob_b64: str, encoding: str = "utf-8") -> str:
        """Decrypt a base64-encoded blob to string.

        Convenience method for decrypting text data.

        Args:
            blob_b64: Base64-encoded encrypted blob.
            encoding: String encoding (default: utf-8).

        Returns:
            Decrypted string.

        Raises:
            DecryptionError: If decryption or decoding fails.
        """
        try:
            blob = base64.b64decode(blob_b64)
        except Exception as e:
            raise DecryptionError(f"Invalid base64 encoding: {e}")

        plaintext = self.decrypt(blob)
        try:
            return plaintext.decode(encoding)
        except UnicodeDecodeError as e:
            raise DecryptionError(f"Failed to decode plaintext: {e}")


def generate_key() -> bytes:
    """Generate a new 256-bit encryption key.

    Returns:
        32 bytes of cryptographically secure random data.

    Example:
        >>> key = generate_key()
        >>> Path("master.key").write_bytes(key)
    """
    return secrets.token_bytes(KEK_SIZE)


def generate_key_file(path: Path, format: str = "raw") -> None:
    """Generate a new key and save to file.

    Args:
        path: Path to save the key.
        format: Output format - "raw" (binary), "base64", or "hex".

    Raises:
        ValueError: If format is invalid.
        OSError: If file cannot be written.
    """
    key = generate_key()

    if format == "raw":
        path.write_bytes(key)
    elif format == "base64":
        path.write_text(base64.b64encode(key).decode("ascii"))
    elif format == "hex":
        path.write_text(key.hex())
    else:
        raise ValueError(f"Invalid format: {format}. Use 'raw', 'base64', or 'hex'")
