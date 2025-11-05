from decimal import Decimal
import pytest

from hiero_sdk_python.hbar import Hbar


pytestmark = pytest.mark.unit

def test_from_string():
    assert Hbar.from_string("1").to_tinybars() == 100_000_000
    assert Hbar.from_string("1 ℏ").to_tinybars() == 100_000_000
    assert Hbar.from_string("1.5 mℏ").to_tinybars() == 150_000
    assert Hbar.from_string("+1.5 mℏ").to_tinybars() == 150_000
    assert Hbar.from_string("-1.5 mℏ").to_tinybars() == -150_000
    assert Hbar.from_string("+3").to_tinybars() == 300_000_000
    assert Hbar.from_string("-3").to_tinybars() == -300_000_000