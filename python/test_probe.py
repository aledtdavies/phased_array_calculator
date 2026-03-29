import pytest
import sys
from unittest.mock import MagicMock, patch

@pytest.fixture(scope="module", autouse=True)
def mock_numpy():
    """Safely mock numpy for this module's imports without polluting sys.modules globally."""
    with patch.dict(sys.modules, {'numpy': MagicMock()}):
        yield

def test_probe_initialization_invalid_pitch_y():
    """
    Test that ValueError is raised when num_elements_y > 1 and pitch_y <= 0
    """
    from probe import Probe

    # Testing pitch_y = 0
    with pytest.raises(ValueError, match="pitch_y must be > 0 when num_elements_y > 1"):
        Probe(num_elements=10, pitch=0.1, num_elements_y=2, pitch_y=0.0)

    # Testing pitch_y < 0
    with pytest.raises(ValueError, match="pitch_y must be > 0 when num_elements_y > 1"):
        Probe(num_elements=10, pitch=0.1, num_elements_y=2, pitch_y=-0.5)

def test_probe_initialization_valid_pitch_y():
    """
    Test that initialization succeeds when num_elements_y > 1 and pitch_y > 0
    """
    from probe import Probe

    probe = Probe(num_elements=10, pitch=0.1, num_elements_y=2, pitch_y=0.1)
    assert probe.num_elements_y == 2
    assert probe.pitch_y == 0.1

def test_probe_initialization_num_elements_y_one():
    """
    Test that initialization succeeds when num_elements_y == 1 and pitch_y <= 0
    """
    from probe import Probe

    probe = Probe(num_elements=10, pitch=0.1, num_elements_y=1, pitch_y=0.0)
    assert probe.num_elements_y == 1
    assert probe.pitch_y == 0.0
