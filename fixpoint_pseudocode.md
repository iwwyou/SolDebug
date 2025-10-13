# Fixpoint Algorithm with Adaptive Widening - Pseudocode

## Core Algorithm

```
Algorithm: FIXPOINT(loop_head)
Input: loop_head - Loop condition node
Output: Converged variable states at loop exit

1. INITIALIZATION
   loop_nodes ← TRAVERSE_LOOP_NODES(loop_head)
   visit_count ← {} for all nodes
   in_vars, out_vars ← {} for all loop_nodes

   // Compute initial environment (excluding back edges)
   start_env ← JOIN predecessors of loop_head outside loop
   in_vars[loop_head] ← start_env

   // Estimate iterations based on loop condition
   threshold ← ESTIMATE_ITERATIONS(loop_head, start_env)

2. WIDENING PHASE (Ascending Chain)
   worklist ← {loop_head}

   while worklist ≠ ∅:
       node ← DEQUEUE(worklist)
       visit_count[node] ← visit_count[node] + 1

       // Apply transfer function
       out_raw ← TRANSFER(node, in_vars[node])

       // Decide widening based on visit count
       if node.is_join_node and visit_count[node] > threshold:
           out_new ← WIDEN(out_vars[node], out_raw)
       else:
           out_new ← JOIN(out_vars[node], out_raw)

       // Check loop condition convergence (early termination)
       if node.is_join_node and CONDITION_CONVERGED(node):
           out_vars[node] ← out_new
           break

       // Continue if changed
       if out_vars[node] ≠ out_new:
           out_vars[node] ← out_new
           for succ ∈ successors(node) ∩ loop_nodes:
               in_vars[succ] ← JOIN{FLOW(p, succ) | p ∈ predecessors(succ)}
               ENQUEUE(worklist, succ)

3. NARROWING PHASE (Descending Chain)
   worklist ← loop_nodes

   while worklist ≠ ∅:
       node ← DEQUEUE(worklist)

       // Recompute output with converged input
       out_raw ← TRANSFER(node, in_vars[node])

       // Narrow if join node
       if node.is_join_node:
           out_new ← NARROW(out_vars[node], out_raw)
       else:
           out_new ← out_raw

       // Continue if changed
       if out_vars[node] ≠ out_new:
           out_vars[node] ← out_new
           for succ ∈ successors(node) ∩ loop_nodes:
               ENQUEUE(worklist, succ)

   return out_vars
```

## Helper Functions

### Iteration Estimation
```
Function: ESTIMATE_ITERATIONS(head, env)
   if not head.is_condition_node:
       return 2  // default threshold

   cond ← head.condition_expr
   if cond.operator ∉ {<, ≤, >, ≥, ≠}:
       return 2

   left ← EVALUATE(cond.left, env)
   right ← EVALUATE(cond.right, env)

   if not (left.is_interval and right.is_interval):
       return 2

   // Calculate expected iterations
   if cond.operator ∈ {<, ≤}:
       iterations ← right.max - left.min
       if cond.operator = ≤: iterations ← iterations + 1
   else if cond.operator ∈ {>, ≥}:
       iterations ← left.max - right.min
       if cond.operator = ≥: iterations ← iterations + 1
   else:
       return 10  // conservative for ≠

   return CLAMP(iterations, 2, 20)
```

### Condition Convergence Check
```
Function: CONDITION_CONVERGED(node)
   if not exists prev_env: return false

   cond ← node.condition_expr
   curr_env ← node.current_env

   // Evaluate both operands in previous and current states
   prev_left ← EVALUATE(cond.left, prev_env)
   curr_left ← EVALUATE(cond.left, curr_env)
   prev_right ← EVALUATE(cond.right, prev_env)
   curr_right ← EVALUATE(cond.right, curr_env)

   // Check if both sides converged to singletons
   left_converged ← IS_SINGLETON(prev_left) and
                     IS_SINGLETON(curr_left) and
                     prev_left.value = curr_left.value

   right_converged ← IS_SINGLETON(prev_right) and
                      IS_SINGLETON(curr_right) and
                      prev_right.value = curr_right.value

   return left_converged and right_converged
```

### Edge Flow (Branch Refinement)
```
Function: FLOW(from_node, to_node)
   env ← COPY(from_node.out_vars)

   if from_node.is_condition_node:
       edge ← GET_EDGE(from_node, to_node)
       cond ← from_node.condition_expr
       branch ← edge.condition  // true or false

       // Refine environment based on branch condition
       REFINE(env, cond, branch)

       // Check feasibility
       if not FEASIBLE(env, cond, branch):
           return NULL  // infeasible path

   return env
```

### Widening Operator
```
Function: WIDEN(old_interval, new_interval)
   if old_interval = NULL: return new_interval

   // For each variable in intervals
   for var in variables:
       old ← old_interval[var]
       new ← new_interval[var]

       // Apply widening to unstable bounds
       if new.min < old.min:
           result[var].min ← -∞  // or type minimum
       else:
           result[var].min ← old.min

       if new.max > old.max:
           result[var].max ← +∞  // or type maximum
       else:
           result[var].max ← old.max

   return result
```

### Narrowing Operator
```
Function: NARROW(wide_interval, concrete_interval)
   // For each variable
   for var in variables:
       wide ← wide_interval[var]
       concrete ← concrete_interval[var]

       // Narrow bounds towards concrete values
       if wide.min = -∞ and concrete.min ≠ -∞:
           result[var].min ← concrete.min
       else:
           result[var].min ← wide.min

       if wide.max = +∞ and concrete.max ≠ +∞:
           result[var].max ← concrete.max
       else:
           result[var].max ← wide.max

   return result
```

## Key Features

1. **Adaptive Widening Threshold**: Dynamically computed based on loop condition analysis
   - Parses condition expressions (i < n, i <= bound, etc.)
   - Calculates expected iteration count from interval bounds
   - Clamped to [2, 20] for stability

2. **Early Termination**: Detects condition convergence
   - Monitors both operands of loop condition
   - Terminates when both sides reach singleton values
   - Prevents unnecessary iterations after convergence

3. **Branch Refinement**: Prunes infeasible paths
   - Refines variable ranges based on branch conditions
   - Marks infeasible branches (⊥)
   - Improves precision by eliminating dead paths

4. **Narrowing Phase**: Improves over-approximations
   - Recomputes states from converged fixed point
   - Tightens over-approximated bounds
   - Limited to 30 iterations for efficiency

## Complexity

- **Widening Phase**: O(N × T) where N = |loop_nodes|, T = adaptive threshold (typically < 20)
- **Narrowing Phase**: O(N × K) where K is small constant for convergence
- **Total**: O(N × (T + K)) for typical loops with bounded iteration counts
