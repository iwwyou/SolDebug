INFINITY = float('inf')
NEG_INFINITY = float('-inf')

class Interval:
    """
    모든 Interval의 기본 클래스.
    min_value, max_value가 모두 None이면 bottom(빈 집합)을 의미한다.
    """
    def __init__(self, min_value=None, max_value=None, type_length=None):
        self.min_value = min_value
        self.max_value = max_value
        self.type_length = type_length

    def is_bottom(self):
        return self.min_value is None and self.max_value is None

    def is_top(self):
        """
        자식 클래스에서 override해서 사용.
        기본 Interval은 top/bottom 개념이 모호하므로 False로 둠.
        """
        return False

    @staticmethod
    def _bottom_propagate(a, b, fn):
        """
        a 또는 b 가 ⊥(bottom) 이면 같은 타입의 bottom 을 반환.
        아니면 fn(a, b) 실행 결과 반환.
        """
        if a.is_bottom() or b.is_bottom():
            # a, b 두 클래스는 같다고 가정
            return a.__class__(None, None, a.type_length)
        return fn(a, b)

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
        super().__init__(min_value, max_value, type_length)

    # ---------- Top / Bottom ----------
    def is_top(self):
        return (self.min_value == NEG_INFINITY
                and self.max_value == INFINITY)


    def _bottom_propagate(a, b, fn):
        if a.is_bottom() or b.is_bottom():
            return a.__class__(None, None, a.type_length)
        return fn(a, b)

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
        return Interval._bottom_propagate(    # ① 클래스 이름으로
            self, other,
            lambda x, y: IntegerInterval(
                x.min_value + y.min_value,
                x.max_value + y.max_value,
                self.type_length)
        )

    def subtract(self, other):
        return Interval._bottom_propagate(self, other,
                                 lambda x, y: IntegerInterval(x.min_value - y.max_value,
                                                              x.max_value - y.min_value,
                                                              self.type_length))

    def multiply(self, other):
        def _mul(x, y):
            candidates = [
                x.min_value * y.min_value,
                x.min_value * y.max_value,
                x.max_value * y.min_value,
                x.max_value * y.max_value,
            ]
            return IntegerInterval(min(candidates), max(candidates), self.type_length)
        return Interval._bottom_propagate(self, other, _mul)

    def divide(self, other: "IntegerInterval") -> "IntegerInterval":
        """
        self / other
        · 분모 구간에 0 이 포함되면 ⊥
        · 아니면 4 개의 끝점 조합을 // 로 계산해 [min, max] 보수적 추정
          (Python // ≈ Solidity / 과 오차가 조금 있으나 분석용으론 충분)
        """
        def _impl(x: "IntegerInterval", y: "IntegerInterval") -> "IntegerInterval":
            # 0 포함 시 실행 불가 → bottom
            if y.min_value <= 0 <= y.max_value:
                return x.make_bottom()

            def _sdiv(a: int, b: int) -> int:
                return a // b  # 가장 단순한 floor-연산

            vals = [
                _sdiv(x.min_value, y.min_value),
                _sdiv(x.min_value, y.max_value),
                _sdiv(x.max_value, y.min_value),
                _sdiv(x.max_value, y.max_value),
            ]
            return IntegerInterval(min(vals), max(vals), x.type_length)

        return Interval._bottom_propagate(self, other, _impl)
    # ---------- 산술 연산 ----------
    def exponentiate(self, other: "IntegerInterval") -> "IntegerInterval":
        """
        a ** b  (b ≥ 0 가정).  음수 지수·bottom 전파·오버플로 클램프 포함.
        """
        def _clamp(v: int, bits: int) -> int:
            lo, hi = -(1 << (bits - 1)), (1 << (bits - 1)) - 1
            return max(lo, min(hi, v))

        def _impl(x: "IntegerInterval", y: "IntegerInterval") -> "IntegerInterval":
            # 음수 지수 → bottom
            if y.min_value < 0:
                return x.make_bottom()

            base_cand = [x.min_value, x.max_value]
            exp_cand  = [y.min_value, y.max_value]
            vals = []
            for a in base_cand:
                for b in exp_cand:
                    try:
                        vals.append(pow(a, b))
                    except OverflowError:
                        # 양·음수에 따라 ±∞ 취급
                        vals.extend([-(1 << 255), (1 << 255)-1])
            new_min = _clamp(min(vals), self.type_length)
            new_max = _clamp(max(vals), self.type_length)
            return IntegerInterval(new_min, new_max, self.type_length)

        return Interval._bottom_propagate(self, other, _impl)


    def modulo(self, other: "IntegerInterval") -> "IntegerInterval":
        """
        self % other  – 0 포함 / bottom 전파, 보수적 범위 추정.
        """
        def _impl(x: "IntegerInterval", y: "IntegerInterval") -> "IntegerInterval":
            # 분모가 0 범위 포함 → bottom
            if y.min_value <= 0 <= y.max_value:
                return x.make_bottom()
            max_div = max(abs(y.min_value), abs(y.max_value))
            return IntegerInterval(-max_div + 1, max_div - 1, x.type_length)

        return Interval._bottom_propagate(self, other, _impl)

    # ---------- 쉬프트/비트 연산 ----------
    def shift(self, shift_iv: "IntegerInterval", op: str) -> "IntegerInterval":
        """
        op ∈ {'<<', '>>', '>>>'}   (>>> : 양수 논리시프트로 동일 처리)
        """
        def _lshift(x: "IntegerInterval", s: "IntegerInterval") -> "IntegerInterval":
            lo = x.min_value << s.min_value
            hi = x.max_value << s.max_value
            return IntegerInterval(lo, hi, x.type_length)

        def _rshift(x: "IntegerInterval", s: "IntegerInterval") -> "IntegerInterval":
            lo = x.min_value >> s.max_value
            hi = x.max_value >> s.min_value
            return IntegerInterval(lo, hi, x.type_length)

        # 음수 시프트 양 ⇒ bottom
        if not shift_iv.is_bottom() and shift_iv.min_value < 0:
            return self.make_bottom()

        if op == '<<':
            return Interval._bottom_propagate(self, shift_iv, _lshift)
        elif op in ('>>', '>>>'):
            return Interval._bottom_propagate(self, shift_iv, _rshift)
        else:
            raise ValueError(f"Unsupported shift op {op}")

    def bitwise(self, op: str, other: "IntegerInterval") -> "IntegerInterval":
        """
        &, |, ^ – 매우 보수적: 동일 폭 signed top 으로 환원.
        """
        def _top_like(x: "IntegerInterval", _: "IntegerInterval") -> "IntegerInterval":
            w = x.type_length
            lo, hi = -(1 << (w - 1)), (1 << (w - 1)) - 1
            return IntegerInterval(lo, hi, w)

        if op not in {'&', '|', '^'}:
            raise ValueError(f"bad bit-op {op}")
        return Interval._bottom_propagate(self, other, _top_like)

    # ---------- 단항 연산 ----------
    def negate(self) -> "IntegerInterval":
        """
        단항 ‘-’  (bottom 전파)
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
        super().__init__(min_value, max_value, type_length)

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

    def negate(self) -> "UnsignedIntegerInterval":
        """
        uintN 범위에서의 단항 `-` (2^N 모듈러 보수).
        * [a,a]  단일값이면              → [-a mod 2^N , -a mod 2^N]
        * 구간이 여러 값을 포함하면       → 정보 손실을 피하기 어려우므로 TOP([0,max])
        """
        # ⊥ 그대로
        if self.is_bottom():
            return self

        bits = self.type_length
        modulus = 1 << bits  # 2^N

        # ① 싱글톤 [v,v] 만 정확히 처리
        if self.min_value == self.max_value:
            v = self.min_value % modulus
            neg_v = (-v) % modulus  # = 2^N - v, 단 v==0 이면 0
            return UnsignedIntegerInterval(neg_v, neg_v, bits)

        # ② 구간이 넓으면 정확한 역상(보수)이 '랩(wrap-around) 구간'이 되므로
        #    분석 단순화를 위해 TOP 으로 보수화
        return UnsignedIntegerInterval(0, modulus - 1, bits)

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
    def subtract(self, other: "UnsignedIntegerInterval") -> "UnsignedIntegerInterval":
        def _impl(a, b):
            min_diff = a.min_value - b.max_value
            max_diff = a.max_value - b.min_value

            # 전부 음수가 될 가능성이 있으면 실행 불가 → ⊥
            if max_diff < 0:
                return a.make_bottom()

            cmin = max(min_diff, 0)
            cmax = max(max_diff, 0)
            return UnsignedIntegerInterval(cmin, cmax, a.type_length)

        return Interval._bottom_propagate(self, other, _impl)

    def add(self, other: "UnsignedIntegerInterval") -> "UnsignedIntegerInterval":
        def _impl(a, b):
            type_max = (1 << a.type_length) - 1
            smin = min(a.min_value + b.min_value, type_max)
            smax = min(a.max_value + b.max_value, type_max)
            return UnsignedIntegerInterval(smin, smax, a.type_length)

        return Interval._bottom_propagate(self, other, _impl)

    def multiply(self, other: "UnsignedIntegerInterval") -> "UnsignedIntegerInterval":
        def _impl(a, b):
            vals = [
                a.min_value * b.min_value,
                a.min_value * b.max_value,
                a.max_value * b.min_value,
                a.max_value * b.max_value,
            ]
            type_max = (1 << a.type_length) - 1
            return UnsignedIntegerInterval(
                min(vals),
                min(max(vals), type_max),
                a.type_length,
            )

        return Interval._bottom_propagate(self, other, _impl)

    def divide(self, other: "UnsignedIntegerInterval") -> "UnsignedIntegerInterval":
        def _impl(a, b):
            # 분모가 0 포함 → ⊥
            if b.min_value <= 0 <= b.max_value:
                return a.make_bottom()

            nums = [a.min_value, a.max_value]
            dens = [b.min_value, b.max_value]
            cand = [n // d for n in nums for d in dens]
            return UnsignedIntegerInterval(min(cand), max(cand), a.type_length)

        return Interval._bottom_propagate(self, other, _impl)

    def exponentiate(self, other: "UnsignedIntegerInterval") -> "UnsignedIntegerInterval":
        def _impl(a, b):
            if b.min_value < 0:          # 음수 지수는 허용 안 함
                return a.make_bottom()

            type_max = (1 << a.type_length) - 1
            vals = []
            for base in (a.min_value, a.max_value):
                for exp in (b.min_value, b.max_value):
                    try:
                        vals.append(pow(base, exp))
                    except OverflowError:
                        vals.append(type_max)

            return UnsignedIntegerInterval(
                min(vals),
                min(max(vals), type_max),
                a.type_length,
            )

        return Interval._bottom_propagate(self, other, _impl)

    def modulo(self, other: "UnsignedIntegerInterval") -> "UnsignedIntegerInterval":
        def _impl(a, b):
            if b.min_value <= 0 <= b.max_value:
                return a.make_bottom()

            # divisor 가 단일 값(d)일 때 최적화
            if b.min_value == b.max_value:
                d = b.min_value
                if a.max_value < d:
                    return UnsignedIntegerInterval(a.min_value, a.max_value, a.type_length)
                return UnsignedIntegerInterval(0, d - 1, a.type_length)

            # 범위가 넓은 제수 → 0..(max_d-1)
            return UnsignedIntegerInterval(0, b.max_value - 1, a.type_length)

        return Interval._bottom_propagate(self, other, _impl)

    # ------------------------------------------------------------------
    # Shift / Bitwise
    # ------------------------------------------------------------------
    def shift(self, shift_iv: "UnsignedIntegerInterval", op: str) -> "UnsignedIntegerInterval":
        def _impl(a, s):
            if s.min_value < 0:
                return a.make_bottom()

            if op == '<<':
                return a.left_shift(s)
            return a.right_shift(s)      # '>>' 또는 '>>>'

        return Interval._bottom_propagate(self, shift_iv, _impl)

    def left_shift(self, s: "UnsignedIntegerInterval") -> "UnsignedIntegerInterval":
        type_max = (1 << self.type_length) - 1
        smin = min(self.min_value << s.min_value, type_max)
        smax = min(self.max_value << s.max_value, type_max)
        return UnsignedIntegerInterval(smin, smax, self.type_length)

    def right_shift(self, s: "UnsignedIntegerInterval") -> "UnsignedIntegerInterval":
        smin = self.min_value >> s.max_value
        smax = self.max_value >> s.min_value
        return UnsignedIntegerInterval(smin, smax, self.type_length)

    def bitwise(self, op: str, other: "UnsignedIntegerInterval") -> "UnsignedIntegerInterval":
        def _impl(a, b):
            if op == '&':
                return UnsignedIntegerInterval(0, min(a.max_value, b.max_value), a.type_length)
            else:  # '|' 또는 '^'
                return UnsignedIntegerInterval(0, max(a.max_value, b.max_value), a.type_length)

        return Interval._bottom_propagate(self, other, _impl)

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
        super().__init__(min_value, max_value, None)

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
