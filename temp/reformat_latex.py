#!/usr/bin/env python3
"""
Reformat LaTeX file to fit within a specified line width while preserving structure.
"""

import re

def reformat_latex_line(line, max_width=100):
    """
    Reformat a single line to fit within max_width characters.
    Preserves LaTeX structure and doesn't break in inappropriate places.
    """
    if len(line) <= max_width:
        return [line]

    # Don't reformat certain special lines
    stripped = line.strip()

    # Skip special LaTeX commands and environments
    if (stripped.startswith('\\begin') or stripped.startswith('\\end') or
        stripped.startswith('\\documentclass') or stripped.startswith('\\usepackage') or
        stripped.startswith('\\caption') or stripped.startswith('\\label') or
        stripped.startswith('\\section') or stripped.startswith('\\subsection') or
        stripped.startswith('\\subsubsection') or stripped.startswith('\\paragraph') or
        stripped.startswith('\\item') or stripped.startswith('\\State') or
        stripped.startswith('\\If') or stripped.startswith('\\For') or
        stripped.startswith('\\While') or stripped.startswith('\\Require') or
        stripped.startswith('\\Ensure')):
        return [line]

    # Lines that are entirely comments
    if stripped.startswith('%'):
        return [line]

    # Get leading whitespace
    leading_space = len(line) - len(line.lstrip())
    indent = line[:leading_space]
    content = line[leading_space:].rstrip()

    # Check if there's an inline comment
    comment_pos = content.find('%')
    main_part = content
    comment_part = ""

    if comment_pos > 0 and (comment_pos == 0 or content[comment_pos-1] != '\\'):
        # Split at comment
        main_part = content[:comment_pos].rstrip()
        comment_part = content[comment_pos:]

    # If main part is short enough, keep it together with comment
    if len(indent + main_part + ' ' + comment_part) <= max_width:
        return [line]

    # If still too long, try to reformat main part only
    if len(indent + main_part) <= max_width:
        # Main part fits, just return as is with comment
        return [indent + main_part + ' ' + comment_part if comment_part else line]

    # Need to break the main part
    result = []
    current = main_part

    while len(indent + current) > max_width:
        # Find good break points
        break_point = -1
        search_start = max_width - leading_space

        # Try to break after space, comma, semicolon, closing brace, etc.
        for pos in range(min(search_start, len(current)), max(search_start // 2, 40), -1):
            if pos < len(current):
                char = current[pos]
                prev_char = current[pos-1] if pos > 0 else ''

                # Good break points
                if char == ' ' and prev_char != '\\':
                    break_point = pos
                    break
                elif char in ',.;)}]' and pos < len(current) - 1:
                    if current[pos+1] == ' ':
                        break_point = pos + 2
                    else:
                        break_point = pos + 1
                    break

        if break_point == -1 or break_point >= len(current):
            # Can't find good break point, just keep the line as is
            result.append(indent + current)
            current = ""
            break

        # Add the line
        result.append(indent + current[:break_point].rstrip())

        # Continue with remainder
        current = current[break_point:].lstrip()

    if current:
        result.append(indent + current)

    # Add comment to last line if exists
    if comment_part and result:
        result[-1] = result[-1] + ' ' + comment_part

    return result if result else [line]

def reformat_latex_file(input_path, output_path, max_width=100):
    """
    Reformat entire LaTeX file.
    """
    with open(input_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    new_lines = []
    in_lstlisting = False
    in_algorithm = False

    for line in lines:
        # Detect environments that should not be reformatted
        if '\\begin{lstlisting}' in line or '\\begin{verbatim}' in line:
            in_lstlisting = True
            new_lines.append(line)
            continue
        if '\\end{lstlisting}' in line or '\\end{verbatim}' in line:
            in_lstlisting = False
            new_lines.append(line)
            continue

        if '\\begin{algorithmic}' in line:
            in_algorithm = True
            new_lines.append(line)
            continue
        if '\\end{algorithmic}' in line:
            in_algorithm = False
            new_lines.append(line)
            continue

        # Don't reformat inside these environments
        if in_lstlisting or in_algorithm:
            new_lines.append(line)
            continue

        # Convert tabs to spaces
        if '\t' in line:
            line = line.replace('\t', '  ')

        reformatted = reformat_latex_line(line.rstrip('\n'), max_width)
        for new_line in reformatted:
            new_lines.append(new_line + '\n')

    with open(output_path, 'w', encoding='utf-8') as f:
        f.writelines(new_lines)

    print(f"Reformatted {input_path} -> {output_path}")
    print(f"Original lines: {len(lines)}, New lines: {len(new_lines)}")

if __name__ == "__main__":
    input_file = r"C:\Users\isjeon\PycharmProjects\pythonProject\SolDebug\paper\main.tex"
    output_file = r"C:\Users\isjeon\PycharmProjects\pythonProject\SolDebug\paper\main_reformatted.tex"

    reformat_latex_file(input_file, output_file, max_width=100)
