import pytest
from src.operator_v7 import Ticket


@pytest.fixture
def Ticket():
    return Ticket(test_mode=True)
