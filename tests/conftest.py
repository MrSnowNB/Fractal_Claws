import pytest
from src.operator_v7 import Operator


@pytest.fixture
def operator():
    return Operator(test_mode=True)