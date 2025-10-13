# get_current_block Algorithm Pseudocode

## Overview
This algorithm determines the insertion point for new CFG nodes during dynamic CFG construction. It returns a single CFG node that serves as the predecessor anchor for inserting new statement blocks.

## Input Parameters
- **context**: string indicating the statement type
  - `"statement"`: regular statements (assignments, function calls, etc.)
  - `"else_if"`: else-if branch
  - `"else"`: else branch
  - `"catch"`: catch clause
- **current_line**: the line number where new statement will be inserted
- **statement_end_line**: the ending line of the statement (for multi-line statements)

## Main Algorithm

**설명**: 이 알고리즘은 동적 CFG 구축 시 새로운 statement를 삽입할 위치를 결정한다. Context에 따라 두 가지 주요 경로로 분기된다:
- **분기문 처리** (else-if/else/catch): 이전에 생성된 조건 노드를 CFG predecessor를 역방향 탐색하여 찾는다
- **일반 statement 처리**: 다음 라인의 CFG 노드 타입을 분석하여 적절한 삽입 위치를 결정한다

```
function get_current_block(context, current_line, statement_end_line):
    // Determine insertion point based on context
    if context in ["else_if", "else", "catch"]:
        return find_branch_insertion_point(context, current_line)
    else:
        return find_statement_insertion_point(current_line, statement_end_line)
```

## Sub-algorithms

### 1. Finding Branch Insertion Point (for else-if, else, catch)

**설명**: else-if, else, catch 같은 분기문은 반드시 이전에 생성된 조건 노드(if, else-if, try)에 연결되어야 한다. 이 알고리즘은 현재 라인의 CFG 노드들에서 시작하여 BFS로 predecessor를 탐색하면서 매칭되는 조건 노드를 찾는다.

**동작 과정**:
1. 현재 라인에 있는 모든 CFG 노드를 큐에 넣어 BFS 시작
2. 각 노드를 방문하면서 조건 노드인지 확인
3. 조건 노드의 타입이 context와 일치하면 해당 노드 반환
   - else-if/else → if/else-if 조건 노드 찾기
   - catch → try 조건 노드 찾기
4. 조건이 맞지 않으면 predecessor로 계속 탐색

```
function find_branch_insertion_point(context, current_line):
    // Get CFG nodes at current line
    current_nodes ← get_cfg_nodes_at_line(current_line)

    // For else-if/else, look for join point at current line
    if context in ["else_if", "else"]:
        outer_join ← find_join_in(current_nodes)

    // BFS backward through CFG to find matching condition node
    visited ← empty_set
    queue ← current_nodes

    while queue is not empty:
        node ← dequeue(queue)

        if node in visited:
            continue
        add node to visited

        if is_condition_node(node):
            node_type ← get_condition_type(node)

            // Match condition type with context
            if context in ["else_if", "else"] and node_type in ["if", "else_if"]:
                return node

            if context == "catch" and node_type == "try":
                return node

        // Continue searching predecessors
        for pred in predecessors(node):
            if pred not in visited:
                enqueue(queue, pred)

    raise error "No matching condition node found"
```

### 2. Finding Statement Insertion Point (for regular statements)

**설명**: 일반 statement의 삽입 위치는 "다음에 실행될 코드가 무엇인가"를 파악하여 결정한다. 함수 정의 시 함수 끝 라인에 EXIT 노드가 line_info에 등록되므로, 순방향 검색으로 빈 라인들을 건너뛰다 보면 결국 다음 statement나 EXIT 노드를 찾게 된다.

**동작 과정**:
1. statement 끝 라인의 다음 라인부터 순방향으로 검색 시작
2. 빈 라인(CFG 노드가 없는 라인)을 건너뛰며 첫 번째 CFG 노드 찾기
3. 찾은 노드의 타입에 따라 적절한 서브알고리즘 호출:
   - **Merge point** (loop-exit/join): 여러 경로가 합쳐지는 지점 → 2.1 호출
   - **Regular node**: 일반 순차 실행 노드 → 2.2 호출

```
function find_statement_insertion_point(current_line, statement_end_line):
    // Search forward from next line to find first CFG node
    search_line ← statement_end_line + 1
    next_line_node ← None
    max_line ← maximum line number in line_info

    while search_line <= max_line:
        next_line_node ← get_first_node_at_line(search_line)
        if next_line_node is not None:
            break
        search_line ← search_line + 1

    if next_line_node is None:
        raise error "No CFG node found after statement_end_line"

    // Check the type of next line node
    if is_loop_exit(next_line_node) or is_join(next_line_node):
        return find_insertion_before_merge_point(current_line, next_line_node)
    else:
        return find_insertion_before_regular_node(current_line, next_line_node)
```

### 2.1. Insertion Before Merge Point (loop-exit or join)

**설명**: 다음 라인이 merge point(loop-exit 또는 join)인 경우, 이는 여러 실행 경로가 합쳐지는 지점이다. 새 statement는 merge 되기 전, 즉 현재 실행 경로상의 마지막 노드 뒤에 삽입되어야 한다.

**동작 과정**:
1. 현재 라인부터 역방향으로 검색하여 직전 CFG 노드들 찾기
2. 빈 라인을 건너뛰며 첫 번째 CFG 노드가 있는 라인 찾기
3. 찾은 노드가 조건 노드인 경우:
   - 조건의 TRUE 브랜치 반환 (if 문 내부에 삽입하는 경우)
4. 찾은 노드가 일반 노드인 경우:
   - 해당 라인의 마지막 노드 반환 (순차적으로 삽입)

```
function find_insertion_before_merge_point(current_line, merge_point_node):
    // Search backward from current line to find previous CFG nodes
    prev_line ← current_line - 1
    prev_line_nodes ← empty_list

    while prev_line >= 1:
        prev_line_nodes ← get_cfg_nodes_at_line(prev_line)
        if prev_line_nodes is not empty:
            break
        prev_line ← prev_line - 1

    // If no previous nodes found, use merge point's predecessor
    if prev_line_nodes is empty:
        return first_predecessor(merge_point_node)

    // Check if previous line contains a condition node
    cond_node ← find_condition_node_in(prev_line_nodes)

    if cond_node exists:
        // Insert in TRUE branch of condition
        return get_true_branch(cond_node)
    else:
        // Insert after last node of previous line
        return last_node(prev_line_nodes)
```

### 2.2. Insertion Before Regular Node

**설명**: 다음 라인이 일반 노드인 경우, 제어 흐름이 단순하게 순차적으로 진행된다. 새 statement는 다음 노드의 바로 앞, 즉 predecessor 위치에 삽입된다.

**동작 과정**:
1. 다음 노드의 predecessor들을 확인
2. Predecessor가 1개인 경우: 그 노드 반환 (일반적인 경우)
3. Predecessor가 여러 개인 경우: 현재 라인과 가장 가까운 노드 선택
4. Predecessor가 없는 경우: 함수 ENTRY 노드 반환 (함수 시작 부분)

```
function find_insertion_before_regular_node(current_line, next_node):
    // Get predecessors of next node
    preds ← predecessors(next_node)

    if length(preds) == 1:
        return preds[0]

    if length(preds) > 1:
        // Multiple predecessors: choose closest to current line
        return min(preds, key=lambda p: abs(p.line - current_line))

    // No predecessors: use function entry
    return ENTRY_node
```

## Helper Functions

```
function get_cfg_nodes_at_line(line):
    info ← line_info[line]
    if info is None:
        return empty_list
    return info.cfg_nodes

function find_condition_node_in(nodes):
    for node in reversed(nodes):
        if is_condition_node(node):
            return node
    return None

function get_true_branch(cond):
    for successor in successors(cond):
        if edge_condition(cond, successor) == True:
            return successor
    return None

function find_outer_join_from_graph(cond_node):
    // Find join point by following TRUE branch
    for succ in successors(cond_node):
        if edge_condition(cond_node, succ) == True:
            for join in successors(succ):
                if is_join(join):
                    return join
    return None
```

## Key Design Principles

1. **Single Return Value**: Always returns exactly one CFG node as the insertion anchor
2. **Context-Aware Dispatch**: Main function dispatches to appropriate sub-algorithm based on context
3. **Line-Based Analysis**: Uses relative line positions (current, previous, next) to locate relevant CFG nodes
4. **Backward Search**: Searches upward through source lines when needed to find CFG nodes
5. **BFS Predecessor Traversal**: For branch contexts, uses breadth-first search on CFG predecessors to find matching condition nodes
6. **Merge Point Detection**: Special handling when next line is a control flow merge point (loop-exit or join)
