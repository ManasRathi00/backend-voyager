from typing import TypedDict, Optional, Sequence, Union, Dict
from pathlib import Path

# You can import ProxySettings from Playwright if you want accurate typing:
# from playwright._impl._api_structures import ProxySettings

class ProxySettings(TypedDict, total=False):
    server: str
    username: Optional[str]
    password: Optional[str]
    bypass: Optional[str]

class LaunchOptions(TypedDict, total=False):
    headless: Optional[bool]
    args: Optional[Sequence[str]]
    executable_path: Optional[Union[Path, str]]
    timeout: Optional[float]
    slow_mo: Optional[float]
    devtools: Optional[bool]
    downloads_path: Optional[Union[Path, str]]
    proxy: Optional[ProxySettings]
    env: Optional[Dict[str, Union[str, float, bool]]]