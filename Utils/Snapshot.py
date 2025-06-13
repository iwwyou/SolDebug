import copy
from collections.abc import Callable

class SnapshotManager:
    """
    * register(obj, serializer)              : 객체별 최초 스냅
    * restore(obj, deserializer)             : 단일 객체 롤백   (기존 인터페이스)
    * snapshot() -> dict                     : 전체 스냅          (새로 추가)
    * restore(snap_dict)                     : 전체 롤백          (새로 추가, 오버로드)
    """

    def __init__(self) -> None:
        # id(obj) -> { "__dict__": deep-copied dict, "serializer": fn }
        self._store: dict[int, dict] = {}
        # id(obj) -> 실객체 참조 (전역 롤백 시 필요)
        self._ref:   dict[int, object] = {}

    # ───────────────────────────────────────── register
    def register(self, obj: object, serializer: Callable[[object], dict]) -> None:
        """
        처음 보는 변수라면 serializer(obj) 결과를 깊은 복사로 저장
        (이미 등록돼 있으면 재등록하지 않음)
        """
        oid = id(obj)
        if oid not in self._store:
            self._store[oid] = {
                "snap": copy.deepcopy(serializer(obj)),
                "serializer": serializer,
            }
            self._ref[oid] = obj

    # ───────────────────────────────────────── 단일 객체 롤백 (기존용)
    def restore(self, target, deserializer: Callable[[object, dict], None] | None = None):
        """
        ‣ (a) 인자가 2개   → 단일 객체 롤백   : restore(obj, deser)
        ‣ (b) 인자가 1개   → 전역 롤백       : restore(snap_dict)
        """
        # -------- (a) 단일 객체
        if deserializer is not None:
            snap_info = self._store.get(id(target))
            if snap_info is not None:
                deserializer(target, copy.deepcopy(snap_info["snap"]))
            return

        # -------- (b) 전역 롤백 (target == snap_dict)
        snap_dict: dict[int, dict] = target       # type: ignore
        for oid, saved_state in snap_dict.items():
            obj = self._ref.get(oid)
            if obj is None:           # 아직 register 안 된 객체일 수 있음
                continue
            # 객체 내부 상태를 원본으로 되돌림
            obj.__dict__.clear()
            obj.__dict__.update(copy.deepcopy(saved_state))

    # ───────────────────────────────────────── 전체 스냅
    # 전체 스냅-샷을 반환
    def snapshot(self):
        return copy.deepcopy(self._store)

    # 외부에서 받은 snap(dict) 전체를 되돌린다
    def restore_from_snap(self, snap):
        self._store = snap