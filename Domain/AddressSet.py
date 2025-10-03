from Domain.Interval import BoolInterval

class AddressSet:
    """
    Address를 set domain으로 추상화
    - 최대 K개의 구체적인 address ID를 추적
    - K 초과 시 Top으로 확장
    """
    __slots__ = ("ids", "is_top")
    K = 8  # cap

    def __init__(self, ids=None, is_top=False):
        self.ids = frozenset(ids or [])
        self.is_top = is_top

    @staticmethod
    def top():
        return AddressSet(is_top=True)

    @staticmethod
    def bot():
        return AddressSet(ids=frozenset())

    def leq(self, other: "AddressSet") -> bool:
        """Partial order: self ⊑ other"""
        if self.is_top:
            return other.is_top
        if other.is_top:
            return True
        return self.ids.issubset(other.ids)

    def join(self, other: "AddressSet") -> "AddressSet":
        """Least upper bound (union with cap)"""
        if self.is_top or other.is_top:
            return AddressSet.top()
        u = self.ids | other.ids
        return AddressSet(u) if len(u) <= AddressSet.K else AddressSet.top()

    def meet(self, other: "AddressSet") -> "AddressSet":
        """Greatest lower bound (intersection)"""
        if self.is_top:
            return other
        if other.is_top:
            return self
        return AddressSet(self.ids & other.ids)

    def equals(self, other: "AddressSet") -> BoolInterval:
        """Abstract equality: self == other"""
        if self.is_top or other.is_top:
            return BoolInterval(0, 1)  # Unknown
        inter = self.ids & other.ids
        if not inter:
            return BoolInterval(0, 0)  # Definitely false
        if len(self.ids) == 1 and self.ids == other.ids:
            return BoolInterval(1, 1)  # Definitely true
        return BoolInterval(0, 1)  # May be true or false

    def not_equals(self, other: "AddressSet") -> BoolInterval:
        """Abstract inequality: self != other"""
        eq = self.equals(other)
        # Negate: [0,0] -> [1,1], [1,1] -> [0,0], [0,1] -> [0,1]
        if eq.min_value == 0 and eq.max_value == 0:
            return BoolInterval(1, 1)
        if eq.min_value == 1 and eq.max_value == 1:
            return BoolInterval(0, 0)
        return BoolInterval(0, 1)

    def add_id(self, addr_id: int) -> "AddressSet":
        """Add a single address ID"""
        if self.is_top:
            return self
        new_ids = self.ids | {addr_id}
        return AddressSet(new_ids) if len(new_ids) <= AddressSet.K else AddressSet.top()

    def is_singleton(self) -> bool:
        """Check if this is a singleton set"""
        return not self.is_top and len(self.ids) == 1

    def get_singleton_id(self) -> int | None:
        """Get the single ID if singleton, else None"""
        return next(iter(self.ids)) if self.is_singleton() else None

    def __str__(self):
        if self.is_top:
            return "AddressSet(⊤)"
        if not self.ids:
            return "AddressSet(⊥)"
        return f"AddressSet({{{', '.join(map(str, sorted(self.ids)))}}})"

    def __repr__(self):
        return self.__str__()

    def __eq__(self, other):
        if not isinstance(other, AddressSet):
            return False
        return self.is_top == other.is_top and self.ids == other.ids

    def __hash__(self):
        return hash((self.is_top, self.ids))
