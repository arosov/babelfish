import pytest
from pydantic import BaseModel
from babelfish_stt.reconfigurable import Reconfigurable

class DummyConfig(BaseModel):
    value: int = 10
    static: str = "fixed"

class ReconfigurableComponent:
    def __init__(self):
        self.value = 0
        self.static = ""

    def reconfigure(self, config: DummyConfig) -> None:
        self.value = config.value
        self.static = config.static

def test_reconfigurable_protocol_check():
    component = ReconfigurableComponent()
    assert isinstance(component, Reconfigurable)

def test_reconfigurable_apply_config():
    component = ReconfigurableComponent()
    config = DummyConfig(value=42, static="changed")
    
    component.reconfigure(config)
    
    assert component.value == 42
    assert component.static == "changed"

class NonReconfigurableComponent:
    pass

def test_non_reconfigurable_protocol_check():
    component = NonReconfigurableComponent()
    assert not isinstance(component, Reconfigurable)
