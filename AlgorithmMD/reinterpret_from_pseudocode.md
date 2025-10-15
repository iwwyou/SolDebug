# Reinterpret_From Algorithm Pseudocode

## Overview
The `reinterpret_from` function performs incremental re-analysis of a control flow graph (CFG) starting from one or more seed nodes. This algorithm is crucial for efficiently updating analysis results when conditions change (e.g., after applying debugging annotations).

## Key Concepts
- **Seed Nodes**: Starting points for re-analysis (typically nodes affected by changes)
- **Transfer Function**: Computes the output state of a node based on its input state
- **Edge Refinement**: Updates variable states based on branch conditions
- **Incremental Analysis**: Only re-analyzes nodes whose input states have changed

---

## Algorithm

```
FUNCTION reinterpret_from(function_cfg, starting_nodes):
    // ──────────────────────────────────────────
    // 1. INITIALIZATION
    // ──────────────────────────────────────────
    cfg_graph ← function_cfg.control_flow_graph
    affected_nodes ← normalize_to_list(starting_nodes)

    analysis_worklist ← empty_queue
    pending_nodes ← empty_set
    previous_output_states ← empty_map  // Maps nodes to their output states

    cleared_source_lines ← empty_set      // Lines whose records have been cleared
    modified_lines ← empty_set            // Lines affected in this run

    enable_recording()                    // Activate statement recording

    // ──────────────────────────────────────────
    // 2. INITIALIZE WORKLIST WITH STARTING NODES
    // ──────────────────────────────────────────
    FOR each starting_node IN affected_nodes:
        IF starting_node is not sink_node AND starting_node not in pending_nodes:
            analysis_worklist.enqueue(starting_node)
            pending_nodes.add(starting_node)

    // ──────────────────────────────────────────
    // 3. MAIN WORKLIST ITERATION
    // ──────────────────────────────────────────
    WHILE analysis_worklist is not empty:
        current_node ← analysis_worklist.dequeue()
        pending_nodes.remove(current_node)

        // ──────────────────────────────────────
        // 3.1 Compute Input State
        // ──────────────────────────────────────
        input_state ← JOIN(edge_flow(predecessor, current_node)
                          for predecessor in predecessors(current_node))

        // ──────────────────────────────────────
        // 3.2 Handle Loop Heads Specially
        // ──────────────────────────────────────
        IF current_node is loop_head:
            loop_condition_line ← current_node.source_line
            IF loop_condition_line exists:
                modified_lines.add(loop_condition_line)

            // Clear cached fixpoint state for join nodes
            FOR each predecessor IN predecessors(current_node):
                IF predecessor is fixpoint_join_node:
                    clear_cached_fixpoint_state(predecessor)

            // Re-run fixpoint computation for the loop
            loop_exit_node ← compute_fixpoint(current_node)

            // Enqueue successors of loop exit
            FOR each successor IN successors(loop_exit_node):
                IF successor is not sink_node AND successor not in pending_nodes:
                    analysis_worklist.enqueue(successor)
                    pending_nodes.add(successor)

            CONTINUE  // Skip normal processing

        // ──────────────────────────────────────
        // 3.3 Clear Analysis Records for This Node
        // ──────────────────────────────────────
        IF current_node is condition_node:
            condition_line ← current_node.source_line
            clear_line_once(condition_line, cleared_source_lines)
            IF condition_line exists:
                modified_lines.add(condition_line)
        ELSE:
            FOR each statement IN current_node.statements:
                statement_line ← statement.source_line
                clear_line_once(statement_line, cleared_source_lines)
                IF statement_line exists:
                    modified_lines.add(statement_line)

        // ──────────────────────────────────────
        // 3.4 Apply Transfer Function
        // ──────────────────────────────────────
        output_state ← transfer_function(current_node, input_state)
        current_node.variables ← copy(output_state)

        // ──────────────────────────────────────
        // 3.5 Detect State Changes
        // ──────────────────────────────────────
        state_changed ← (previous_output_states[current_node] ≠ output_state)
        previous_output_states[current_node] ← copy(output_state)

        // ──────────────────────────────────────
        // 3.6 Propagate Changes to Successors
        // ──────────────────────────────────────
        IF state_changed:
            FOR each successor IN successors(current_node):
                IF successor is not sink_node AND successor not in pending_nodes:
                    analysis_worklist.enqueue(successor)
                    pending_nodes.add(successor)

    // ──────────────────────────────────────────
    // 4. FINALIZATION
    // ──────────────────────────────────────────
    IF modified_lines is not empty:
        save_touched_lines_for_reporting(modified_lines)

    return


// ──────────────────────────────────────────
// HELPER FUNCTIONS
// ──────────────────────────────────────────

FUNCTION edge_flow(predecessor_node, successor_node):
    // Compute the variable state flowing from predecessor to successor
    inherited_state ← copy(predecessor_node.variables)

    IF predecessor_node is condition_node:
        branch_condition ← predecessor_node.condition_expression
        edge_metadata ← get_edge_metadata(predecessor_node, successor_node)

        IF branch_condition exists AND edge_metadata contains "condition":
            branch_direction ← edge_metadata["condition"]  // true or false

            // Apply condition refinement to narrow variable ranges
            refine_variables_by_condition(inherited_state, branch_condition, branch_direction)

            // Check if this branch is feasible
            IF NOT is_branch_feasible(inherited_state, branch_condition, branch_direction):
                return NULL  // Infeasible path - pruned

    return inherited_state


FUNCTION clear_line_once(source_line, already_cleared_set):
    // Clear analysis records for a source line (avoid duplicate clearing)
    IF source_line is NULL OR source_line IN already_cleared_set:
        return

    clear_analysis_records(source_line)
    already_cleared_set.add(source_line)


FUNCTION is_sink_node(cfg_node):
    // Check if node is a terminal node (EXIT, ERROR, RETURN)
    return (cfg_node.function_exit_node OR
            cfg_node.error_exit_node OR
            cfg_node.return_exit_node OR
            cfg_node.name IN {"EXIT", "ERROR", "RETURN"})
```

---

## Key Features

### 1. **Incremental Processing**
- Only re-analyzes nodes affected by changes
- Uses output snapshots to detect state changes
- Propagates changes only when necessary

### 2. **Loop Handling**
- Detects loop head nodes specially
- Re-runs fixpoint computation when loop conditions change
- Clears cached fixpoint state before re-computation

### 3. **Recording Management**
- Clears old analysis records for affected lines
- Tracks which lines are "touched" for reporting
- Prevents duplicate clearing with `cleared_source_lines` set

### 4. **Edge Refinement**
- Applies branch condition constraints to variable states
- Checks path feasibility (prunes infeasible branches)
- Handles conditional flow accurately

### 5. **Efficient Worklist**
- Uses queue-based propagation
- Prevents duplicate enqueueing with `pending_nodes` set
- Stops at sink nodes (EXIT, ERROR, RETURN)

---

## Complexity
- **Time**: O(N + E) where N = nodes, E = edges in affected region
- **Space**: O(N) for previous_output_states and worklist tracking

---

## Use Cases
1. **After Debug Annotation**: When a user adds `@debug` comments, re-analyze affected paths
2. **Interactive Refinement**: Incrementally update analysis as conditions are refined
3. **Conditional Breakpoint**: Re-analyze when a specific condition is assumed true/false
4. **Partial Re-analysis**: Avoid full re-interpretation when only small changes occur
