from typing import Any, Protocol, runtime_checkable
from pydantic import BaseModel

@runtime_checkable
class Reconfigurable(Protocol):
    """
    Protocol for components that can be reconfigured at runtime.
    """
    def reconfigure(self, config: BaseModel) -> None:
        """
        Apply new configuration to the component.
        """
        ...
