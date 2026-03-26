import pytest

from phone_normalization import normalize_phone_for_storage, phone_digit_variants


def test_phone_digit_variants_e164_us():
    assert set(phone_digit_variants("+1 (555) 123-4567")) == {"15551234567", "5551234567"}


def test_phone_digit_variants_ten_digit():
    assert set(phone_digit_variants("5551234567")) == {"5551234567", "15551234567"}


def test_phone_digit_variants_empty():
    assert phone_digit_variants("") == []
    assert phone_digit_variants(None) == []


def test_normalize_storage_strips_country_code():
    assert normalize_phone_for_storage("+15551234567") == "5551234567"
    assert normalize_phone_for_storage("555-123-4567") == "5551234567"


def test_normalize_storage_non_us_passthrough_digits():
    long_d = "441234567890"
    assert normalize_phone_for_storage("+" + long_d) == long_d
