from Domain.Variable import *

class AddressSymbolicManager:
    """
    160-bit 주소 공간의 심볼릭 ID ↔ Interval ↔ 변수 alias 를 한 곳에서 관리
    """
    ADDR_BITS = 160
    MAX_ADDR = (1 << ADDR_BITS) - 1
    TOP_INTERVAL = UnsignedIntegerInterval(0, MAX_ADDR, ADDR_BITS)
    _typeinfo = SolType()                 # 빈 객체 먼저 만들고
    _typeinfo.typeCategory = "elementary" # 필드 수동 설정
    _typeinfo.elementaryTypeName = "address"

    def __init__(self):
        self._next_id: int = 1                    # fresh ID counter
        self._id_to_iv: dict[int, UnsignedIntegerInterval] = {}
        self._id_to_vars: dict[int, set[str]] = {}  # 해당 ID를 쓰는 변수명 모음

    @staticmethod
    def top_interval() -> UnsignedIntegerInterval:
        return UnsignedIntegerInterval(0, 2 ** 160 - 1, type_length=160)

    # ───────────────────────────────── fresh / fixed  ID 발급
    def fresh_id(self) -> int:
        nid = self._next_id
        self._next_id += 1
        return nid

    def alloc_fresh_interval(self) -> UnsignedIntegerInterval:
        """새 ID 하나 -> Interval [id,id] 반환"""
        nid = self.fresh_id()
        iv  = UnsignedIntegerInterval(nid, nid, self.ADDR_BITS)
        self._id_to_iv[nid] = iv
        self._id_to_vars[nid] = set()
        return iv                                  # value 필드에 그대로 쓰면 됨

    def register_fixed_id(self, nid: int,
                          iv: UnsignedIntegerInterval | None = None):
        """
        주석처럼 `symbolicAddress 101` 이 들어왔을 때 호출.
        이미 등록돼 있으면 그대로 두고, 없으면 Interval을 결정해 추가.
        """
        if nid not in self._id_to_iv:
            if iv is None:
                iv = UnsignedIntegerInterval(nid, nid, self.ADDR_BITS)
            self._id_to_iv[nid] = iv
            self._id_to_vars[nid] = set()

    # ───────────────────────────────── 변수-ID 바인딩
    def bind_var(self, var_name: str, nid: int):
        self._id_to_vars.setdefault(nid, set()).add(var_name)

    # ───────────────────────────────── 조회
    def get_interval(self, nid: int) -> UnsignedIntegerInterval:
        return self._id_to_iv[nid]

    def get_alias_set(self, nid: int) -> set[str]:
        return self._id_to_vars.get(nid, set())

    # ───────────────────────────────── ranged 할당 예시
    def alloc_range(self, start: int, end: int) -> int:
        """
        [start,end] Interval 로 묶인 새 ID 발급 후 ID 반환
        """
        nid = self.fresh_id()
        self._id_to_iv[nid] = UnsignedIntegerInterval(start, end, self.ADDR_BITS)
        self._id_to_vars[nid] = set()
        return nid