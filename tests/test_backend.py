import pytest
from castmasta.backend import DeviceBackend


def test_cannot_instantiate_abc():
    with pytest.raises(TypeError, match="abstract"):
        DeviceBackend()
