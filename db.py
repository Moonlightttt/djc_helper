from typing import Any, Dict, List, Tuple, Type

from dao import BuyInfo
from db_def import ConfigInterface, DBInterface

# ----------------- 数据定义 -----------------


class DemoDB(DBInterface):
    def __init__(self):
        super().__init__()
        self.int_val = 1
        self.bool_val = True


class FirstRunDB(DBInterface):
    def __init__(self):
        super().__init__()

    def get_update_at(self):
        from util import parse_time
        return parse_time(self.update_at)


class WelfareDB(DBInterface):
    def __init__(self):
        super().__init__()

        self.share_code_list = []  # type: List[str]
        self.exchanged_dict = {}  # type: Dict[str, bool]


class DianzanDB(DBInterface):
    def __init__(self):
        super().__init__()

        self.day_to_dianzan_count = {}  # type: Dict[str, int]
        self.used_content_ids = []  # type: List[str]
        self.content_ids = []  # type: List[str]


class CaptchaDB(DBInterface):
    def __init__(self):
        super().__init__()

        self.offset_to_history_succes_count = {}  # type: Dict[str, int]

    def increse_success_count(self, offset: int):
        success_key = str(offset)  # 因为json只支持str作为key，所以需要强转一下，使用时再转回int
        if success_key not in self.offset_to_history_succes_count:
            self.offset_to_history_succes_count[success_key] = 0

        self.offset_to_history_succes_count[success_key] += 1


class LoginRetryDB(DBInterface):
    def __init__(self):
        super().__init__()

        self.recommended_first_retry_timeout = 0.0  # type: float
        self.history_success_timeouts = []  # type: List[float]


class CacheDB(DBInterface):
    def __init__(self):
        super().__init__()

        self.cache = {}  # type: Dict[str, CacheInfo]

    def dict_fields_to_fill(self) -> List[Tuple[str, Type[ConfigInterface]]]:
        return [
            ('cache', CacheInfo)
        ]


class CacheInfo(DBInterface):
    def __init__(self):
        super().__init__()

        self.value = None  # type: Any


class FireCrackersDB(DBInterface):
    def __init__(self):
        super().__init__()

        self.friend_qqs = []  # type: List[str]


class UserBuyInfoDB(DBInterface):
    def __init__(self):
        super().__init__()

        self.buy_info = BuyInfo()


if __name__ == '__main__':
    print(DBInterface())
    print(DemoDB())
