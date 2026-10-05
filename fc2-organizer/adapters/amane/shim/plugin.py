from ._ffcc_locator import ensure_core
from . import _ffcc_pin
ensure_core(_ffcc_pin, __file__)
from ._impl.plugin import Plugin   # noqa: E402  —— 宿主要求模块字典中存在名为 Plugin 的类
