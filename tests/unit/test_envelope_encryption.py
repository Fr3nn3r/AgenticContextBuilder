"""Unit tests for envelope encryption.

Tests:
- Key generation and loading
- Encrypt/decrypt roundtrip
- String encryption/decryption
- Invalid key handling
- Tampering detection
- Error handling
"""

import base64
import os
from pathlib import Path

import pytest

from context_builder.services.compliance.crypto import (
    KEK_SIZE,
    CryptoError,
    DecryptionError,
    EncryptionError,
    EnvelopeEncryptor,
    KeyLoadError,
    generate_key,
    generate_key_file,
)


class TestKeyGeneration:
    """Tests for key generation functions."""

    def test_generate_key_returns_correct_length(self):
        """Generated key is 32 bytes."""
        key = generate_key()
        assert len(key) == KEK_SIZE

    def test_generate_key_returns_bytes(self):
        """Generated key is bytes type."""
        key = generate_key()
        assert isinstance(key, bytes)

    def test_generate_key_is_random(self):
        """Each generated key is unique."""
        keys = [generate_key() for _ in range(10)]
        unique_keys = set(keys)
        assert len(unique_keys) == 10

    def test_generate_key_file_raw_format(self, tmp_path: Path):
        """generate_key_file creates valid raw key file."""
        key_path = tmp_path / "test.key"
        generate_key_file(key_path, format="raw")

        assert key_path.exists()
        assert len(key_path.read_bytes()) == KEK_SIZE

    def test_generate_key_file_base64_format(self, tmp_path: Path):
        """generate_key_file creates valid base64 key file."""
        key_path = tmp_path / "test.key"
        generate_key_file(key_path, format="base64")

        assert key_path.exists()
        decoded = base64.b64decode(key_path.read_text())
        assert len(decoded) == KEK_SIZE

    def test_generate_key_file_hex_format(self, tmp_path: Path):
        """generate_key_file creates valid hex key file."""
        key_path = tmp_path / "test.key"
        generate_key_file(key_path, format="hex")

        assert key_path.exists()
        decoded = bytes.fromhex(key_path.read_text())
        assert len(decoded) == KEK_SIZE

    def test_generate_key_file_invalid_format(self, tmp_path: Path):
        """generate_key_file raises for invalid format."""
        key_path = tmp_path / "test.key"
        with pytest.raises(ValueError, match="Invalid format"):
            generate_key_file(key_path, format="invalid")


class TestEnvelopeEncryptorInit:
    """Tests for EnvelopeEncryptor initialization."""

    def test_init_with_bytes_key(self):
        """Encryptor accepts bytes key directly."""
        key = generate_key()
        encryptor = EnvelopeEncryptor(key)
        assert encryptor is not None

    def test_init_with_path_raw_key(self, tmp_path: Path):
        """Encryptor loads raw key from file."""
        key_path = tmp_path / "test.key"
        key = generate_key()
        key_path.write_bytes(key)

        encryptor = EnvelopeEncryptor(key_path)
        assert encryptor is not None

    def test_init_with_path_base64_key(self, tmp_path: Path):
        """Encryptor loads base64 key from file."""
        key_path = tmp_path / "test.key"
        key = generate_key()
        key_path.write_text(base64.b64encode(key).decode("ascii"))

        encryptor = EnvelopeEncryptor(key_path)
        assert encryptor is not None

    def test_init_with_path_hex_key(self, tmp_path: Path):
        """Encryptor loads hex key from file."""
        key_path = tmp_path / "test.key"
        key = generate_key()
        key_path.write_text(key.hex())

        encryptor = EnvelopeEncryptor(key_path)
        assert encryptor is not None

    def test_init_with_invalid_key_size_bytes(self):
        """Encryptor rejects incorrect key size."""
        with pytest.raises(KeyLoadError, match="must be 32 bytes"):
            EnvelopeEncryptor(b"tooshort")

    def test_init_with_missing_file(self, tmp_path: Path):
        """Encryptor raises for missing key file."""
        key_path = tmp_path / "nonexistent.key"
        with pytest.raises(KeyLoadError, match="not found"):
            EnvelopeEncryptor(key_path)

    def test_init_with_invalid_file_content(self, tmp_path: Path):
        """Encryptor raises for invalid key file content."""
        key_path = tmp_path / "bad.key"
        key_path.write_text("not a valid key")

        with pytest.raises(KeyLoadError, match="must contain 32 bytes"):
            EnvelopeEncryptor(key_path)


class TestEncryptDecrypt:
    """Tests for encrypt/decrypt roundtrip."""

    @pytest.fixture
    def encryptor(self) -> EnvelopeEncryptor:
        """Create an encryptor with a fresh key."""
        return EnvelopeEncryptor(generate_key())

    def test_roundtrip_empty_data(self, encryptor: EnvelopeEncryptor):
        """Empty data encrypts and decrypts."""
        plaintext = b""
        ciphertext = encryptor.encrypt(plaintext)
        result = encryptor.decrypt(ciphertext)
        assert result == plaintext

    def test_roundtrip_small_data(self, encryptor: EnvelopeEncryptor):
        """Small data encrypts and decrypts."""
        plaintext = b"Hello, World!"
        ciphertext = encryptor.encrypt(plaintext)
        result = encryptor.decrypt(ciphertext)
        assert result == plaintext

    def test_roundtrip_large_data(self, encryptor: EnvelopeEncryptor):
        """Large data encrypts and decrypts."""
        plaintext = os.urandom(1024 * 1024)  # 1 MB
        ciphertext = encryptor.encrypt(plaintext)
        result = encryptor.decrypt(ciphertext)
        assert result == plaintext

    def test_roundtrip_unicode_data(self, encryptor: EnvelopeEncryptor):
        """Unicode data encrypts and decrypts."""
        plaintext = "Hello, 世界! 🌍".encode("utf-8")
        ciphertext = encryptor.encrypt(plaintext)
        result = encryptor.decrypt(ciphertext)
        assert result == plaintext

    def test_ciphertext_different_from_plaintext(self, encryptor: EnvelopeEncryptor):
        """Ciphertext is different from plaintext."""
        plaintext = b"secret data"
        ciphertext = encryptor.encrypt(plaintext)
        assert ciphertext != plaintext
        assert plaintext not in ciphertext

    def test_ciphertext_unique_per_encryption(self, encryptor: EnvelopeEncryptor):
        """Each encryption produces unique ciphertext (different DEK)."""
        plaintext = b"same plaintext"
        ciphertext1 = encryptor.encrypt(plaintext)
        ciphertext2 = encryptor.encrypt(plaintext)
        assert ciphertext1 != ciphertext2


class TestStringEncryptDecrypt:
    """Tests for string encryption convenience methods."""

    @pytest.fixture
    def encryptor(self) -> EnvelopeEncryptor:
        """Create an encryptor with a fresh key."""
        return EnvelopeEncryptor(generate_key())

    def test_string_roundtrip(self, encryptor: EnvelopeEncryptor):
        """String encrypts and decrypts."""
        plaintext = "Hello, World!"
        ciphertext = encryptor.encrypt_string(plaintext)
        result = encryptor.decrypt_string(ciphertext)
        assert result == plaintext

    def test_string_ciphertext_is_base64(self, encryptor: EnvelopeEncryptor):
        """String ciphertext is base64 encoded."""
        plaintext = "test"
        ciphertext = encryptor.encrypt_string(plaintext)
        # Should not raise
        base64.b64decode(ciphertext)

    def test_unicode_string_roundtrip(self, encryptor: EnvelopeEncryptor):
        """Unicode string encrypts and decrypts."""
        plaintext = "日本語テスト 🎌"
        ciphertext = encryptor.encrypt_string(plaintext)
        result = encryptor.decrypt_string(ciphertext)
        assert result == plaintext

    def test_decrypt_string_invalid_base64(self, encryptor: EnvelopeEncryptor):
        """decrypt_string raises for invalid base64."""
        with pytest.raises(DecryptionError, match="Invalid base64"):
            encryptor.decrypt_string("not valid base64!!!")


class TestTamperDetection:
    """Tests for tampering detection."""

    @pytest.fixture
    def encryptor(self) -> EnvelopeEncryptor:
        """Create an encryptor with a fresh key."""
        return EnvelopeEncryptor(generate_key())

    def test_truncated_ciphertext_detected(self, encryptor: EnvelopeEncryptor):
        """Truncated ciphertext is detected."""
        plaintext = b"test data"
        ciphertext = encryptor.encrypt(plaintext)

        with pytest.raises(DecryptionError):
            encryptor.decrypt(ciphertext[:50])

    def test_modified_ciphertext_detected(self, encryptor: EnvelopeEncryptor):
        """Modified ciphertext is detected."""
        plaintext = b"test data"
        ciphertext = encryptor.encrypt(plaintext)

        # Flip a bit in the ciphertext
        tampered = bytearray(ciphertext)
        tampered[-1] ^= 0xFF
        tampered = bytes(tampered)

        with pytest.raises(DecryptionError):
            encryptor.decrypt(tampered)

    def test_modified_dek_detected(self, encryptor: EnvelopeEncryptor):
        """Modified encrypted DEK is detected."""
        plaintext = b"test data"
        ciphertext = encryptor.encrypt(plaintext)

        # Flip a bit in the encrypted DEK portion
        tampered = bytearray(ciphertext)
        tampered[10] ^= 0xFF
        tampered = bytes(tampered)

        with pytest.raises(DecryptionError):
            encryptor.decrypt(tampered)


class TestWrongKeyDecryption:
    """Tests for decryption with wrong key."""

    def test_wrong_key_fails(self):
        """Decryption with different key fails."""
        encryptor1 = EnvelopeEncryptor(generate_key())
        encryptor2 = EnvelopeEncryptor(generate_key())

        plaintext = b"secret data"
        ciphertext = encryptor1.encrypt(plaintext)

        with pytest.raises(DecryptionError):
            encryptor2.decrypt(ciphertext)


class TestEdgeCases:
    """Tests for edge cases."""

    @pytest.fixture
    def encryptor(self) -> EnvelopeEncryptor:
        """Create an encryptor with a fresh key."""
        return EnvelopeEncryptor(generate_key())

    def test_ciphertext_too_small(self, encryptor: EnvelopeEncryptor):
        """Very small ciphertext is rejected."""
        with pytest.raises(DecryptionError, match="too small"):
            encryptor.decrypt(b"tiny")

    def test_minimum_valid_size(self, encryptor: EnvelopeEncryptor):
        """Ciphertext at minimum header size still fails (no actual data)."""
        # Header is 72 bytes, but we need at least some ciphertext
        fake_header = b"\x00" * 72
        with pytest.raises(DecryptionError):
            encryptor.decrypt(fake_header)


class TestKeyFileFormats:
    """Tests for various key file formats."""

    def test_base64_with_newlines(self, tmp_path: Path):
        """Key file with base64 and trailing newline works."""
        key_path = tmp_path / "test.key"
        key = generate_key()
        key_path.write_text(base64.b64encode(key).decode("ascii") + "\n\n")

        encryptor = EnvelopeEncryptor(key_path)
        plaintext = b"test"
        assert encryptor.decrypt(encryptor.encrypt(plaintext)) == plaintext

    def test_hex_lowercase(self, tmp_path: Path):
        """Lowercase hex key file works."""
        key_path = tmp_path / "test.key"
        key = generate_key()
        key_path.write_text(key.hex().lower())

        encryptor = EnvelopeEncryptor(key_path)
        plaintext = b"test"
        assert encryptor.decrypt(encryptor.encrypt(plaintext)) == plaintext

    def test_hex_uppercase(self, tmp_path: Path):
        """Uppercase hex key file works."""
        key_path = tmp_path / "test.key"
        key = generate_key()
        key_path.write_text(key.hex().upper())

        encryptor = EnvelopeEncryptor(key_path)
        plaintext = b"test"
        assert encryptor.decrypt(encryptor.encrypt(plaintext)) == plaintext
