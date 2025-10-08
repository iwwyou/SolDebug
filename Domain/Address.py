# ═══════════════════════════════════════════════════════════════════
# DEPRECATED: AddressSymbolicManager는 더 이상 사용되지 않습니다.
# ═══════════════════════════════════════════════════════════════════
#
# 이 파일은 하위 호환성을 위해 유지되며, 새 코드에서는 사용하지 마세요.
# 대신 Domain/AddressSet.py의 AddressManager와 AddressSet을 사용하세요.
#
# Migration guide:
#   - AddressSymbolicManager() → address_manager (싱글톤)
#   - sm.alloc_fresh_interval() → address_manager.fresh_address()
#   - sm.register_fixed_id(nid) → address_manager.make_symbolic_address(nid)
#   - Interval [nid, nid] → AddressSet(ids={nid})
#
# ═══════════════════════════════════════════════════════════════════

import warnings

warnings.warn(
    "Domain.Address.AddressSymbolicManager is deprecated. "
    "Use Domain.AddressSet.AddressManager instead.",
    DeprecationWarning,
    stacklevel=2
)

# Backward compatibility shim (optional)
from Domain.AddressSet import AddressManager as AddressSymbolicManager

__all__ = ['AddressSymbolicManager']
