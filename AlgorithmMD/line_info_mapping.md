# Line Info Mapping by Statement Type

## 1. Function Definition
```solidity
function foo() {  // start: ENTRY node
    ...
}                 // end: EXIT node
```
- **start_line**: ENTRY 노드
- **end_line**: EXIT 노드

---

## 2. Contract Definition
```solidity
contract MyContract {  // start: ContractCFG
    ...
}
```
- **start_line**: ContractCFG 객체
- **end_line**: 없음

---

## 3. Enum Definition
```solidity
enum State {  // start: EnumDefinition
    Active,
    Inactive
}
```
- **start_line**: EnumDefinition 객체
- **end_line**: 없음

---

## 4. Struct Definition
```solidity
struct Person {  // start: structDefs dictionary
    string name;
    uint age;
}
```
- **start_line**: structDefs 딕셔너리
- **end_line**: 없음

---

## 5. State Variable
```solidity
uint public count = 0;  // start: state_variable_node
```
- **start_line**: state_variable_node
- **end_line**: 없음

---

## 6. Constant Variable
```solidity
uint constant MAX = 100;  // start: state_variable_node
```
- **start_line**: state_variable_node
- **end_line**: 없음

---

## 7. Modifier Definition
```solidity
modifier onlyOwner() {  // start: modifier ENTRY node
    ...
}
```
- **start_line**: modifier ENTRY 노드
- **end_line**: 없음

---

## 8. Constructor Definition
```solidity
constructor() {  // start: constructor ENTRY node
    ...
}
```
- **start_line**: constructor ENTRY 노드
- **end_line**: 없음

---

## 9. Variable Declaration
```solidity
uint x = 10;  // statement block node
```
- **start_line**: VarDecl_{line_no} statement block
- **end_line**: 없음

---

## 10. Assignment Statement
```solidity
x = 5;  // statement block node
```
- **start_line**: Assign_{line_no} statement block
- **end_line**: 없음

---

## 11. Unary Operations
```solidity
++x;      // statement block node
--y;      // statement block node
delete z; // statement block node
```
- **start_line**: Unary_{line_no} statement block
- **end_line**: 없음

---

## 12. Function Call
```solidity
foo(a, b);  // statement block node
```
- **start_line**: FuncCall_{line_no} statement block
- **end_line**: 없음

---

## 13. If Statement
```solidity
if (x > 0) {  // start: if_condition node
    ...
}             // end: if_join node
```
- **start_line**: if_condition_{line_no} (condition node)
- **end_line**: if_join_{line_no} (join point node)

---

## 14. Else-If Statement
```solidity
else if (x < 0) {  // start: else_if_condition node
    ...
}                  // end: else_if_join node (local join)
```
- **start_line**: else_if_condition_{line_no} (condition node)
- **end_line**: else_if_join_{line_no} (local join node)
- **참고**: outer join은 별도로 존재하며 line_info에는 local join만 등록

---

## 15. Else Statement
```solidity
else {  // start: else_block node
    ...
}       // end: target_join node (재사용된 join)
```
- **start_line**: else_block_{line_no} (branch node)
- **end_line**: target_join (if 또는 else-if의 join 재사용)

---

## 16. While Statement
```solidity
while (x > 0) {  // start: while_cond node
    ...
}                // end: while_exit node (loop exit)
```
- **start_line**: while_cond_{line_no} (condition node)
- **end_line**: while_exit_{line_no} (loop exit node)
- **참고**: while_join (fixpoint evaluation node)은 그래프에만 존재, line_info 미등록

---

## 17. For Statement
```solidity
for (uint i=0; i<10; i++) {  // start: for_cond node
    ...
}                            // end: for_exit node (loop exit)
```
- **start_line**: for_cond_{line_no} (condition node)
- **end_line**: for_exit_{line_no} (loop exit node)
- **참고**:
  - for_init, for_join, for_incr 노드는 그래프에만 존재
  - line_info에는 cond와 exit만 등록

---

## 18. Continue Statement
```solidity
continue;  // statement block node
```
- **start_line**: Continue_{line_no} statement block
- **end_line**: 없음

---

## 19. Break Statement
```solidity
break;  // statement block node
```
- **start_line**: Break_{line_no} statement block
- **end_line**: 없음

---

## 20. Return Statement
```solidity
return x;  // statement block node
```
- **start_line**: Return_{line_no} statement block
- **end_line**: 없음

---

## 21. Revert Statement
```solidity
revert("Error");  // current block (새 블록 생성 안 함)
```
- **start_line**: cur_block (현재 블록을 직접 등록)
- **end_line**: 없음

---

## 22. Require Statement
```solidity
require(x > 0);  // condition node
```
- **start_line**: require_condition_{line_no} (condition node)
- **end_line**: 없음
- **참고**: require_true 블록은 그래프에만 존재

---

## 23. Assert Statement
```solidity
assert(x > 0);  // condition node
```
- **start_line**: assert_condition_{line_no} (condition node)
- **end_line**: 없음
- **참고**: assert_true 블록은 그래프에만 존재

---

## 24. Modifier Placeholder
```solidity
_;  // placeholder node (modifier 내부에서만)
```
- **start_line**: MOD_PLACEHOLDER_{idx}
- **end_line**: 없음

---

## 25. Unchecked Block
```solidity
unchecked {  // unchecked node
    ...
}
```
- **start_line**: unchecked_{line_no}
- **end_line**: 없음

---

## 26. Do Statement
```solidity
do {  // start: do_body node (do-entry)
    ...
```
- **start_line**: do_body_{line_no} (do-entry node)
- **end_line**: 없음
- **참고**: do_end 노드는 그래프에만 존재, line_info 미등록

---

## 27. Do-While Statement
```solidity
} while (x > 0);  // do_while_cond node
```
- **start_line**: do_while_cond_{line_no} (condition node)
- **end_line**: 없음 (현재 구현에서는 exit 미등록)
- **참고**:
  - do_while_phi (fixpoint node)는 그래프에만 존재
  - do_while_exit는 그래프에만 존재 (line_info 미등록)

---

## 28. Try Statement
```solidity
try foo.bar() {  // start: try_cond node
    ...
}
```
- **start_line**: try_cond_{line_no} (condition node)
- **end_line**: 없음
- **참고**:
  - try_true, try_false_stub, try_join은 그래프에만 존재
  - catch가 붙으면 false_stub는 제거됨

---

## 29. Catch Clause
```solidity
catch {  // start: catch_entry node
    ...
}
```
- **start_line**: catch_entry_{line_no}
- **end_line**: 없음
- **참고**: catch_end는 그래프에만 존재, line_info 미등록

---

## Summary Table

| Statement Type | Start Line Node | End Line Node | Note |
|---------------|-----------------|---------------|------|
| Function | ENTRY | EXIT | 함수 시작/끝 |
| Contract | ContractCFG | - | 컨트랙트 정의 |
| Enum | EnumDefinition | - | 열거형 정의 |
| Struct | structDefs | - | 구조체 정의 |
| State Variable | state_variable_node | - | 상태 변수 |
| Constant | state_variable_node | - | 상수 |
| Modifier Def | ENTRY | - | 모디파이어 정의 |
| Constructor | ENTRY | - | 생성자 |
| Variable Decl | VarDecl block | - | 변수 선언 |
| Assignment | Assign block | - | 대입문 |
| Unary Op | Unary block | - | 단항 연산 |
| Function Call | FuncCall block | - | 함수 호출 |
| If | if_condition | if_join | 조건문 |
| Else-If | else_if_condition | else_if_join | 추가 조건 |
| Else | else_block | target_join | 대체 분기 |
| While | while_cond | while_exit | 반복문 |
| For | for_cond | for_exit | 반복문 |
| Continue | Continue block | - | 루프 계속 |
| Break | Break block | - | 루프 탈출 |
| Return | Return block | - | 함수 반환 |
| Revert | cur_block | - | 실행 중단 |
| Require | require_condition | - | 조건 검증 |
| Assert | assert_condition | - | 단언문 |
| Placeholder | MOD_PLACEHOLDER | - | 모디파이어 위치 |
| Unchecked | unchecked | - | 오버플로우 무시 |
| Do | do_body | - | do-while 시작 |
| Do-While | do_while_cond | - | do-while 조건 |
| Try | try_cond | - | 예외 처리 시도 |
| Catch | catch_entry | - | 예외 처리 |

---

## Node Naming Convention

- **Statement blocks**: `{Type}_{line_no}` (예: `VarDecl_42`, `Assign_55`)
- **Condition nodes**: `{type}_condition_{line_no}` (예: `if_condition_10`)
- **Join nodes**: `{type}_join_{line_no}` (예: `if_join_15`)
- **Exit nodes**: `{type}_exit_{line_no}` (예: `while_exit_20`)
- **Entry nodes**: `ENTRY` 또는 modifier/constructor에서는 각각의 ENTRY
- **Special nodes**:
  - `state_variable_node`: 상태 변수용
  - `MOD_PLACEHOLDER_{idx}`: 모디파이어 플레이스홀더
  - `unchecked_{line_no}`: unchecked 블록

---

## Important Notes

1. **Control Flow 구조**:
   - If/Else-If/Else는 condition과 join을 line_info에 등록
   - Loop(While/For)는 condition과 exit을 line_info에 등록
   - Join과 phi 노드는 구분됨 (phi는 fixpoint evaluation용)

2. **Line Info에 등록되지 않는 노드들**:
   - Branch nodes (true/false 분기 블록): if_true, if_false 등
   - Join baseline nodes: while_join, for_join (fixpoint용)
   - Intermediate nodes: for_init, for_incr, do_end, catch_end
   - Stub nodes: try_false_stub

3. **재사용되는 노드**:
   - Else statement의 end_line은 if/else-if의 join을 재사용
   - Else-if는 local join과 outer join 두 개를 가짐

4. **새 블록 생성 vs 기존 블록 사용**:
   - 대부분의 statement는 `insert_new_statement_block()`으로 새 블록 생성
   - Revert는 예외적으로 현재 블록(cur_block)을 직접 사용
