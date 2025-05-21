INFINITY = float('inf')
NEG_INFINITY = float('-inf')

class Interval:
    """
    모든 Interval의 기본 클래스.
    min_value, max_value가 모두 None이면 bottom(빈 집합)을 의미한다.
    """
    def __init__(self, min_value=None, max_value=None):
        self.min_value = min_value
        self.max_value = max_value

    def is_bottom(self):
        return self.min_value is None and self.max_value is None

    def is_top(self):
        """
        자식 클래스에서 override해서 사용.
        기본 Interval은 top/bottom 개념이 모호하므로 False로 둠.
        """
        return False

    def make_bottom(self):
        """bottom(빈 집합)을 만들어 반환"""
        return type(self)(None, None)

    def encompass(self, intended_interval):
        """
        실제 interval이 intended_interval(개발자 의도)에 포함되는지 여부.
        """
        if self.is_bottom() or intended_interval.is_bottom():
            # bottom인 경우 비교가 모호하므로 우선 False 처리
            return False
        return (self.min_value >= intended_interval.min_value
                and self.max_value <= intended_interval.max_value)

    def equals(self, other):
        return (self.min_value == other.min_value
                and self.max_value == other.max_value)

    def copy(self):
        return type(self)(self.min_value, self.max_value)

    def __repr__(self):
        if self.is_bottom():
            return f"{type(self).__name__}(BOTTOM)"
        return f"{type(self).__name__}([{self.min_value}, {self.max_value}])"


# ----------------------------------------------------------------------------
# IntegerInterval (signed)
# ----------------------------------------------------------------------------

class IntegerInterval(Interval):
    def __init__(self, min_value=None, max_value=None, type_length=256):
        super().__init__(min_value, max_value)
        self.type_length = type_length

    # ---------- Top / Bottom ----------
    def is_top(self):
        return (self.min_value == NEG_INFINITY
                and self.max_value == INFINITY)

    def top(self):
        """
        signed int의 top = [-2^(bits-1), 2^(bits-1) - 1]
        내부적으로는 '이론적 -∞, +∞' 대신 실제 비트 범위를 사용합니다.
        """
        min_value = -2 ** (self.type_length - 1)
        max_value = 2 ** (self.type_length - 1) - 1
        return IntegerInterval(min_value, max_value, self.type_length)

    def theoretical_top(self):
        """
        실제로는 위 top()을 사용하는 게 맞지만,
        만약 '완전히 무한대' 개념을 쓰고 싶다면 이 메서드를 호출할 수 있음.
        """
        return IntegerInterval(NEG_INFINITY, INFINITY, self.type_length)

    @staticmethod
    def bottom(type_len: int = 256) -> "IntegerInterval":
        """빈 집합 (⊥)"""
        return IntegerInterval(None, None, type_len)


    def initialize_range(self, type_name: str) -> None:
        """
        type_name : 'int', 'int8', 'int256' …
        지정된 비트 수에 맞춰 min/max 를 설정한다.
        """
        if not type_name.startswith("int"):
            raise ValueError(f"Unsupported signed integer type: {type_name}")

        # 방법 ① 컴프리헨션 ─ 타입-체커 경고 無
        digits = ''.join(c for c in type_name if c.isdigit())

        # ▸ 방법 ② 정규식 (주석 처리; 취향에 따라 사용 가능)
        # m = re.search(r'\d+', type_name)
        # digits = m.group(0) if m else ""

        bits = int(digits) if digits else 256  # 'int' → 256
        self.type_length = bits
        self.min_value = -2 ** (bits - 1)
        self.max_value = 2 ** (bits - 1) - 1

    # ---------- Lattice 연산 ----------
    def join(self, other):
        """
        Join(합집합) : [min(self, other), max(self, other)]
        """
        if self.is_bottom():
            return other
        if other.is_bottom():
            return self

        if self.type_length != other.type_length:
            # 여기서는 간단히 에러. 필요시 더 유연하게 처리 가능.
            raise ValueError("Cannot join intervals of different type lengths.")

        new_min = min(self.min_value, other.min_value)
        new_max = max(self.max_value, other.max_value)
        return IntegerInterval(new_min, new_max, self.type_length)

    def meet(self, other):
        """
        Meet(교집합) : [max(min), min(max)]
        """
        if self.is_bottom() or other.is_bottom():
            return self.bottom(self.type_length)

        if self.type_length != other.type_length:
            raise ValueError("Cannot meet intervals of different type lengths.")

        new_min = max(self.min_value, other.min_value)
        new_max = min(self.max_value, other.max_value)
        if new_min > new_max:
            return self.bottom(self.type_length)
        return IntegerInterval(new_min, new_max, self.type_length)

    def widen(self, current_interval):
        """
        widen: 만약 현재 min/max가 더 작거나 큰 경우 무한대로 확장
        여기선 실제론 비트 범위가 있으므로 'theoretical_top' 사용 여부는 정책 선택.
        """
        # (1) 오른쪽이 bottom 이면 self 그대로
        if current_interval is None or current_interval.is_bottom():
            return self.copy()

        if self.is_bottom():
            return current_interval

        new_min = (NEG_INFINITY
                   if self.min_value > current_interval.min_value
                   else self.min_value)
        new_max = (INFINITY
                   if self.max_value < current_interval.max_value
                   else self.max_value)
        # 이 예시에서는 실제 비트 범위를 무시하고 이론적 무한대 사용
        return IntegerInterval(new_min, new_max, self.type_length)

    def narrow(self, new_interval):
        """
        narrow: 만약 현재가 -∞ 이었다면 new_interval의 min_value로 좁히고,
        +∞였으면 new_interval의 max_value로 좁힘
        """
        if self.is_bottom():
            return new_interval

        cur_min = self.min_value if self.min_value != NEG_INFINITY else new_interval.min_value
        cur_max = self.max_value if self.max_value != INFINITY else new_interval.max_value
        if cur_min is None or cur_max is None:
            return self.bottom(self.type_length)
        return IntegerInterval(cur_min, min(cur_max, new_interval.max_value), self.type_length)

    # ---------- 논리/비교 (Interval 축소) ----------
    def less_than(self, other):
        # a < b  => a.max < b.min
        # 추상 해석에서는 a <= b.min - 1로 제한
        if self.is_bottom() or other.is_bottom():
            return self.bottom(self.type_length)

        new_max = min(self.max_value, other.min_value - 1)
        if new_max < self.min_value:
            return self.bottom(self.type_length)
        return IntegerInterval(self.min_value, new_max, self.type_length)

    def greater_than(self, other):
        if self.is_bottom() or other.is_bottom():
            return self.bottom(self.type_length)

        new_min = max(self.min_value, other.max_value + 1)
        if new_min > self.max_value:
            return self.bottom(self.type_length)
        return IntegerInterval(new_min, self.max_value, self.type_length)

    def less_than_or_equal(self, other):
        if self.is_bottom() or other.is_bottom():
            return self.bottom(self.type_length)

        new_max = min(self.max_value, other.max_value)
        if new_max < self.min_value:
            return self.bottom(self.type_length)
        return IntegerInterval(self.min_value, new_max, self.type_length)

    def greater_than_or_equal(self, other):
        if self.is_bottom() or other.is_bottom():
            return self.bottom(self.type_length)

        new_min = max(self.min_value, other.min_value)
        if new_min > self.max_value:
            return self.bottom(self.type_length)
        return IntegerInterval(new_min, self.max_value, self.type_length)

    # ---------- 산술 연산 ----------
    def add(self, other):
        min_sum = self.min_value + other.min_value
        max_sum = self.max_value + other.max_value
        # 비트 범위 고려 (optionally clamp)
        # 여기서는 단순히 그대로
        return IntegerInterval(min_sum, max_sum, self.type_length)

    def subtract(self, other):
        """
        a - b = [ (a.min - b.max), (a.max - b.min) ]
        """
        min_diff = self.min_value - other.max_value
        max_diff = self.max_value - other.min_value
        return IntegerInterval(min_diff, max_diff, self.type_length)

    def multiply(self, other):
        # 가능한 조합 중 최소/최대
        vals = [
            self.min_value * other.min_value,
            self.min_value * other.max_value,
            self.max_value * other.min_value,
            self.max_value * other.max_value
        ]
        min_product = min(vals)
        max_product = max(vals)
        return IntegerInterval(min_product, max_product, self.type_length)

    def divide(self, other):
        """
        0이 들어갈 가능성이 있으면 bottom 처리(즉, 실행 불가)
        그렇지 않다면 단순히 각 끝점끼리 // 연산(부호 주의)
        """
        if (other.min_value <= 0 <= other.max_value):
            # 0 포함
            return self.bottom(self.type_length)

        # safe div helper
        def safe_div(n, d):
            # Python의 //는 음수에서 floor toward -∞
            # Solidity는 0 방향 truncation → 약간 다를 수 있음
            # 여기서는 단순화
            return n // d

        candidates = []
        candidates.append(safe_div(self.min_value, other.min_value))
        candidates.append(safe_div(self.min_value, other.max_value))
        candidates.append(safe_div(self.max_value, other.min_value))
        candidates.append(safe_div(self.max_value, other.max_value))

        new_min = min(candidates)
        new_max = max(candidates)
        return IntegerInterval(new_min, new_max, self.type_length)

    # ---------- 산술 연산 ----------
    def exponentiate(self, other):
        """
        a ** b  (b ≥ 0 를 전제로 한다)
        - 지수 범위가 0 미만이면 ⊥
        - 가능한 모든 끝점(a.min/max, b.min/max) 조합을 계산해서
          [min, max] 보수적 범위 반환
        - 오버플로는 signed int bit-width에 맞춰 클램프
        """

        # ─── 공통: 내부에서 사용할 상한 계산 헬퍼 ──────────────────────────
        def _clamp(value, type_bits, signed=False):
            if signed:
                lo, hi = -2 ** (type_bits - 1), 2 ** (type_bits - 1) - 1
            else:
                lo, hi = 0, 2 ** type_bits - 1
            if value < lo:  return lo
            if value > hi:  return hi
            return value

        if self.is_bottom() or other.is_bottom():
            return self.bottom(self.type_length)

        # 음수 지수 → 지원 안 함 ⇒ bottom
        if other.min_value < 0:
            return self.bottom(self.type_length)

        # 후보 값 계산 (큰 지수에서 pow overflow 가능 → try/except)
        base_candidates   = [self.min_value, self.max_value]
        exp_candidates    = [other.min_value, other.max_value]
        results = []
        for a in base_candidates:
            for b in exp_candidates:
                try:
                    results.append(pow(a, b))
                except OverflowError:
                    # overflow → 최고값으로 보수
                    if a >= 0:
                        results.append(INFINITY)
                    else:
                        # 부호가 바뀔 수 있어 –∞, +∞ 둘 다 고려
                        results.extend([NEG_INFINITY, INFINITY])

        new_min = min(results)
        new_max = max(results)

        # type-width 클램프
        new_min = _clamp(new_min, self.type_length, signed=True)
        new_max = _clamp(new_max, self.type_length, signed=True)

        return IntegerInterval(new_min, new_max, self.type_length)


    def modulo(self, other):
        """
        0이 들어갈 가능성이 있으면 bottom
        그 외엔 결과 범위를 0~(divisor-1) 정도로 보수적 처리
        음수 처리시 복잡하나, 간단히 최대 절댓값 기준
        """
        if other.is_bottom():
            return self.bottom(self.type_length)

        # 0 포함?
        if other.min_value <= 0 <= other.max_value:
            return self.bottom(self.type_length)

        # 절댓값이 가장 큰 divisor:
        abs_divs = [abs(other.min_value), abs(other.max_value)]
        max_div = max(abs_divs)

        # 결과는 - (max_div-1) ~ (max_div-1) 가능성이 있지만,
        # 실제로는 0 ~ max_div-1 (unsigned-like) 혹은 음수 가능
        # 여기서는 간단히 [-max_div+1, max_div-1]
        return IntegerInterval(-max_div+1, max_div-1, self.type_length)

    # ---------- 쉬프트/비트연산 ----------
    def shift(self, shift_interval, operator):
        if shift_interval.is_bottom():
            return self.bottom(self.type_length)

        # 시프트 양에 0보다 작은 값 포함 → 보수적으로 bottom or top?
        if shift_interval.min_value < 0:
            # Solidity에서는 음수 시프트 불가
            return self.bottom(self.type_length)

        if operator == '<<':
            return self.left_shift(shift_interval)
        else:
            # '>>' or '>>>'
            return self.right_shift(shift_interval)

    def left_shift(self, shift_interval):
        # 단순: [min << maxShift, max << minShift]에서 최소/최대 계산
        min_val = self.min_value << shift_interval.min_value
        max_val = self.max_value << shift_interval.max_value
        return IntegerInterval(min_val, max_val, self.type_length)

    def right_shift(self, shift_interval):
        # signed >>는 부호비트 유지. 일단 단순히 Python >>와 같다고 가정
        min_val = self.min_value >> shift_interval.max_value
        max_val = self.max_value >> shift_interval.min_value
        return IntegerInterval(min_val, max_val, self.type_length)

    def bitwise(self, op, other):
        """
        &, |, ^ 연산 -> 굉장히 보수적 추정
        """
        if op == '&':
            # 결과는 0 이상?
            # 사실 음수가 될 수도 있어서 정확치 않음.
            # 매우 보수적으로 [-∞, max(...)] 등등
            # 일단 음수 환경에서 정확 추정은 복잡하므로 bottom 또는 wide
            return self.theoretical_top()
        elif op == '|':
            return self.theoretical_top()
        elif op == '^':
            return self.theoretical_top()

    def negate(self):
        """
        단항 - (음수화)
        """
        if self.is_bottom():
            return self

        return IntegerInterval(-self.max_value, -self.min_value, self.type_length)

    def prefix_increment(self):
        if self.is_bottom():
            return self
        return IntegerInterval(self.min_value + 1, self.max_value + 1, self.type_length)

    def prefix_decrement(self):
        if self.is_bottom():
            return self
        return IntegerInterval(self.min_value - 1, self.max_value - 1, self.type_length)

    def postfix_increment(self):
        if self.is_bottom():
            return self
        old = IntegerInterval(self.min_value, self.max_value, self.type_length)
        self.min_value += 1
        self.max_value += 1
        return old

    def postfix_decrement(self):
        if self.is_bottom():
            return self
        old = IntegerInterval(self.min_value, self.max_value, self.type_length)
        self.min_value -= 1
        self.max_value -= 1
        return old


# ----------------------------------------------------------------------------
# UnsignedIntegerInterval
# ----------------------------------------------------------------------------

class UnsignedIntegerInterval(Interval):
    def __init__(self, min_value=None, max_value=None, type_length=256):
        super().__init__(min_value, max_value)
        self.type_length = type_length

    # ---------- Top / Bottom ----------
    def is_top(self):
        """
        top = [0, 2^bits - 1]
        """
        return (self.min_value == 0 and
                self.max_value == 2 ** self.type_length - 1)

    def top(self):
        min_val = 0
        max_val = 2 ** self.type_length - 1
        return UnsignedIntegerInterval(min_val, max_val, self.type_length)

    def theoretical_top(self):
        """
        이론적 top(무한대)을 쓰고 싶다면 여기서 [0, +∞] 처리를 할 수도 있음.
        """
        return UnsignedIntegerInterval(0, INFINITY, self.type_length)

    @staticmethod
    def bottom(type_len: int = 256) -> "UnsignedIntegerInterval":
        return UnsignedIntegerInterval(None, None, type_len)

    # ---------- 범위 초기화 ----------
    def initialize_range(self, type_name: str) -> None:
        """
        type_name : 'uint', 'uint8', 'uint256' …
        지정된 비트 수(bit-width)에 맞춰 min/max 를 설정한다.
        """
        if not type_name.startswith("uint"):
            raise ValueError(f"Unsupported unsigned integer type: {type_name}")

        # ────────────────────────────────────────────────
        # ① 컴프리헨션 ― IDE 경고 無
        digits = ''.join(c for c in type_name if c.isdigit())

        # ▸ ② 정규식 사용 예시  (원한다면)
        # import re
        # m = re.search(r'\d+', type_name)
        # digits = m.group(0) if m else ""
        # ────────────────────────────────────────────────

        bits = int(digits) if digits else 256  # 'uint' ⇒ 기본 256-bit
        self.type_length = bits
        self.min_value = 0
        self.max_value = (1 << bits) - 1  # 2**bits − 1

    # ---------- Lattice 연산 ----------
    def join(self, other):
        if self.is_bottom():
            return other
        if other.is_bottom():
            return self

        if self.type_length != other.type_length:
            raise ValueError("Cannot join intervals of different type lengths")

        new_min = min(self.min_value, other.min_value)
        new_max = max(self.max_value, other.max_value)
        return UnsignedIntegerInterval(new_min, new_max, self.type_length)

    def meet(self, other):
        if self.is_bottom() or other.is_bottom():
            return self.bottom(self.type_length)

        if self.type_length != other.type_length:
            raise ValueError("Cannot meet intervals of different type lengths")

        new_min = max(self.min_value, other.min_value)
        new_max = min(self.max_value, other.max_value)
        if new_min > new_max:
            return self.bottom(self.type_length)
        return UnsignedIntegerInterval(new_min, new_max, self.type_length)

    def widen(self, current_interval):
        """
        간단히 min은 0, max는 ∞(또는 2^bits-1)로 확장
        """
        # (1) 오른쪽이 bottom 이면 self 그대로
        if current_interval is None or current_interval.is_bottom():
            return self.copy()

        if self.is_bottom():
            return current_interval

        new_min = 0 if self.min_value > current_interval.min_value else self.min_value
        # 이 예시에서는 이론적 무한대로 간주
        new_max = INFINITY if self.max_value < current_interval.max_value else self.max_value
        return UnsignedIntegerInterval(new_min, new_max, self.type_length)

    def narrow(self, new_interval):
        if self.is_bottom():
            return new_interval

        cur_min = self.min_value
        cur_max = self.max_value
        if cur_max == INFINITY:
            cur_max = new_interval.max_value

        # 간단 처리
        return UnsignedIntegerInterval(max(cur_min, new_interval.min_value),
                                       min(cur_max, new_interval.max_value),
                                       self.type_length)

    # ---------- 산술 연산 (실제 빼기) ----------
    def subtract(self, other):
        """
        unsigned a - b = [ (a.min - b.max), (a.max - b.min) ]
        단, 결과가 <0이면 0으로 컷? (Solidity에선 언더플로?)
        일단 보수적으로 negative 값 나오면 bottom 처리 가능, or clamp to 0
        여기선 clamp 예시
        """
        min_diff = self.min_value - other.max_value
        max_diff = self.max_value - other.min_value

        # clamp to >= 0
        if max_diff < 0:
            # 전부 음수 가능성이면 => 0 미만 => 언더플로 => 실제론 revert
            # 여기서는 bottom 처리
            return self.bottom(self.type_length)

        cmin = max(min_diff, 0)
        cmax = max(max_diff, 0)
        return UnsignedIntegerInterval(cmin, cmax, self.type_length)

    def difference(self, other):
        """
        집합 차 (원래 subtract()에 있던 로직).
        interval A에서 interval B 교집합 부분을 빼는 연산.
        """
        if self.is_bottom() or other.is_bottom():
            return self
        inter_min = max(self.min_value, other.min_value)
        inter_max = min(self.max_value, other.max_value)
        if inter_min > inter_max:
            # 교집합 없음
            return self

        # 교집합이 전체 덮으면 bottom
        if inter_min <= self.min_value and inter_max >= self.max_value:
            return self.bottom(self.type_length)

        # 부분 차
        # 간단히 하한 부분만 남긴다거나, 상한 부분만 남긴다거나 해야 하나,
        # 여기서는 하한부분만 남긴다고 가정
        new_max = inter_min - 1
        if new_max < self.min_value:
            # 하한 부분이 없는 경우, 상한 부분 남김
            new_min2 = inter_max + 1
            if new_min2 > self.max_value:
                return self.bottom(self.type_length)
            return UnsignedIntegerInterval(new_min2, self.max_value, self.type_length)

        return UnsignedIntegerInterval(self.min_value, new_max, self.type_length)

    def add(self, other):
        smin = self.min_value + other.min_value
        smax = self.max_value + other.max_value
        # clamp to type_max
        type_max = 2 ** self.type_length - 1

        if smax > type_max:
            smax = type_max
        if smin > type_max:
            smin = type_max
        return UnsignedIntegerInterval(smin, smax, self.type_length)

    def multiply(self, other):
        vals = [
            self.min_value * other.min_value,
            self.min_value * other.max_value,
            self.max_value * other.min_value,
            self.max_value * other.max_value
        ]
        result_min = min(vals)
        result_max = max(vals)
        if result_min < 0:
            # unsigned라서 음수는 실제로 불가능 → 0으로 clamp
            result_min = 0

        type_max = 2 ** self.type_length - 1
        if result_max > type_max:
            result_max = type_max

        return UnsignedIntegerInterval(result_min, result_max, self.type_length)

    def divide(self, other):
        # 0 들어가면 bottom
        if other.min_value == 0 or other.max_value == 0:
            return self.bottom(self.type_length)

        # 단순 각 끝점 //로 계산
        def safe_div(a, b):
            return a // b if b != 0 else None

        candidates = []
        candidates.append(safe_div(self.min_value, other.max_value))
        candidates.append(safe_div(self.max_value, max(other.min_value,1)))

        # None 제거
        candidates = [c for c in candidates if c is not None]
        if not candidates:
            return self.bottom(self.type_length)

        new_min = min(candidates)
        new_max = max(candidates)
        return UnsignedIntegerInterval(new_min, new_max, self.type_length)

    # ---------- 산술 연산 ----------
    def exponentiate(self, other):
        """
        unsigned a ** b  (b ≥ 0)
        overflow 시 type 최댓값으로 클램프
        """

        if self.is_bottom() or other.is_bottom():
            return self.bottom(self.type_length)

        if other.min_value < 0:
            return self.bottom(self.type_length)

        base_candidates = [self.min_value, self.max_value]
        exp_candidates  = [other.min_value, other.max_value]
        results = []
        for a in base_candidates:
            for b in exp_candidates:
                try:
                    results.append(pow(a, b))
                except OverflowError:
                    results.append(INFINITY)

        new_min = max(0, min(results))
        new_max = min(max(results), 2 ** self.type_length - 1)
        return UnsignedIntegerInterval(new_min, new_max, self.type_length)


    def modulo(self, other):
        # 제수가 0을 포함? → ⊥
        if other.min_value <= 0 <= other.max_value:
            return self.bottom(self.type_length)

        # 제수 singleton 인 양수 d
        if other.min_value == other.max_value and other.min_value > 0:
            d = other.min_value
            # 피제수 singleton   ↦ 정확한 값
            if self.min_value == self.max_value:
                v = self.min_value % d
                return UnsignedIntegerInterval(v, v, self.type_length)
            # 피제수 범위가 d 보다 좁다 ↦ 그대로
            if self.max_value < d:
                return UnsignedIntegerInterval(self.min_value,
                                               self.max_value,
                                               self.type_length)
            # 그 외는 0..d-1 (보수)
            return UnsignedIntegerInterval(0, d - 1, self.type_length)

        # 제수가 구간이지만 전부 양수일 때 → 가장 보수적인 0..(max_d-1)
        max_d = other.max_value
        return UnsignedIntegerInterval(0, max_d - 1, self.type_length)

    def shift(self, shift_interval, operator):
        if shift_interval.is_bottom():
            return self.bottom(self.type_length)

        # 0 이하 시프트 → bottom
        if shift_interval.min_value < 0:
            return self.bottom(self.type_length)

        if operator == '<<':
            return self.left_shift(shift_interval)
        else:
            # '>>' or '>>>'
            return self.right_shift(shift_interval)

    def left_shift(self, shift_interval):
        smin = self.min_value << shift_interval.min_value
        smax = self.max_value << shift_interval.max_value
        type_max = 2 ** self.type_length - 1

        smin = min(smin, type_max)
        smax = min(smax, type_max)
        return UnsignedIntegerInterval(smin, smax, self.type_length)

    def right_shift(self, shift_interval):
        smin = self.min_value >> shift_interval.max_value
        smax = self.max_value >> shift_interval.min_value
        # 음수될 일은 없으니 그냥 사용
        return UnsignedIntegerInterval(smin, smax, self.type_length)

    def bitwise(self, op, other):
        """
        &, |, ^ 에 대한 보수적 추정
        """
        if op == '&':
            # 최소값은 0, 최대값은 min(self.max, other.max)
            return UnsignedIntegerInterval(0, min(self.max_value, other.max_value), self.type_length)
        elif op == '|':
            # 최소값 0, 최대값은 max(self.max, other.max)
            return UnsignedIntegerInterval(0, max(self.max_value, other.max_value), self.type_length)
        elif op == '^':
            # 최소값 0, 최대값은 max(self.max, other.max)
            return UnsignedIntegerInterval(0, max(self.max_value, other.max_value), self.type_length)

    # ------------------------------------------------------------------------


class BoolInterval(Interval):
    """
    BoolInterval:
      - top = [0,1]
      - bottom = [None, None]
      - always True = [1,1]
      - always False = [0,0]
    """
    def __init__(self, min_value=None, max_value=None):
        super().__init__(min_value, max_value)

    def is_top(self):
        return (self.min_value == 0 and self.max_value == 1)

    @staticmethod
    def top():
        return BoolInterval(0, 1)

    @staticmethod
    def bottom() -> "BoolInterval":
        return BoolInterval(None, None)

    def calculate_interval(self, right_interval, operator):
        if self.is_bottom() or right_interval.is_bottom():
            return self.bottom()

        if operator == '&&':
            return self.logical_and(right_interval)
        elif operator == '||':
            return self.logical_or(right_interval)
        elif operator == '!':
            return self.logical_not()
        elif operator in ['==', '!=', '<', '>', '<=', '>=']:
            # 비교 결과는 불리언
            return BoolInterval(0,1)
        else:
            raise ValueError(f"Unsupported operator for bool: {operator}")

    def join(self, other):
        if self.is_bottom():
            return other
        if other.is_bottom():
            return self

        new_min = min(self.min_value, other.min_value)
        new_max = max(self.max_value, other.max_value)
        return BoolInterval(new_min, new_max)

    def meet(self, other):
        if self.is_bottom() or other.is_bottom():
            return self.bottom()

        new_min = max(self.min_value, other.min_value)
        new_max = min(self.max_value, other.max_value)
        if new_min > new_max:
            return self.bottom()
        return BoolInterval(new_min, new_max)

    def widen(self, current_interval):
        # bool에선 widen => top
        return self.top()

    def narrow(self, new_interval):
        if self.is_bottom():
            return new_interval

        cur_min = self.min_value
        cur_max = self.max_value
        new_min = max(cur_min, new_interval.min_value)
        new_max = min(cur_max, new_interval.max_value)
        if new_min > new_max:
            return self.bottom()
        return BoolInterval(new_min, new_max)

    def less_than(self, other):
        # Boolean에서 < 연산, 크게 의미 X. 여기서는 그대로 자신 반환 혹은 top
        return self

    # 그 외 greater_than, etc. 마찬가지로 특수처리

    def logical_and(self, other):
        """
        - 둘 다 [1,1]이면 결과 [1,1]
        - 하나라도 [0,0]이면 [0,0]
        - 그 외 [0,1]
        """
        if (self.min_value == 1 and self.max_value == 1 and
            other.min_value == 1 and other.max_value == 1):
            return BoolInterval(1,1)
        if (self.max_value == 0) or (other.max_value == 0):
            return BoolInterval(0,0)
        return BoolInterval(0,1)

    def logical_or(self, other):
        """
        - 하나라도 [1,1]이면 [1,1]
        - 둘 다 [0,0]이면 [0,0]
        - 그 외 [0,1]
        """
        if (self.min_value == 1 and self.max_value == 1) or \
           (other.min_value == 1 and other.max_value == 1):
            return BoolInterval(1,1)
        if (self.max_value == 0 and other.max_value == 0):
            return BoolInterval(0,0)
        return BoolInterval(0,1)

    def logical_not(self):
        if self.is_bottom():
            return self
        # always True -> always False
        if self.min_value == 1 and self.max_value == 1:
            return BoolInterval(0,0)
        # always False -> always True
        if self.min_value == 0 and self.max_value == 0:
            return BoolInterval(1,1)
        # 그 외 => [0,1]
        return BoolInterval(0,1)

    def __repr__(self):
        if self.is_bottom():
            return "BoolInterval(BOTTOM)"
        return f"BoolInterval([{self.min_value}, {self.max_value}])"
