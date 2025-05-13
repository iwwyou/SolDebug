# soltotestjson.py  (split Solidity → websocket-inputs JSON)

from __future__ import annotations
import re, json, sys, argparse, pathlib
from typing import List, Dict

# ───────────────── 정규식 ─────────────────
_just_ws   = re.compile(r"^\s*$")          # 공백 줄
_open_blk  = re.compile(r".*\{\s*$")       # 줄 끝이 '{'
_one_liner = re.compile(r".*;\s*$")        # 줄 끝이 ';'
_close_blk = re.compile(r"^\s*}\s*$")      # '}' 단독 줄   ★ NEW

# ───────────────── 슬라이싱 ─────────────────
def slice_solidity(source: str) -> List[Dict[str, str | int]]:
    """
    ① ‘한 줄 세미콜론 문장’
    ② ‘두 줄 블록(<line with {> + 가짜 })’
    ③ ‘공백 줄’
    ④ ‘진짜 }’  → 무시
    로 잘라 websocket-server 입력용 dict 리스트를 만든다.
    """
    lines = source.splitlines()
    cur_line = 1                 # 1-based
    close_stack: List[int] = []  # placeholder '}' 가 있는 라인 모음
    inputs: List[Dict[str, str | int]] = []

    i = 0
    while i < len(lines):
        line = lines[i]

        # 0) '}' 단독 줄은 이미 placeholder 로 처리돼 있으므로 건너뛴다 ★
        if _close_blk.match(line):
            cur_line += 1
            i += 1
            continue

        # 1) 빈 줄
        if _just_ws.match(line):
            inputs.append({
                "code": "\n",
                "startLine": cur_line,
                "endLine": cur_line
            })
            cur_line += 1
            i += 1
            continue

        # 2) '{' 로 끝나는 줄  → 2-줄 블록으로 변환
        if _open_blk.match(line):
            block_code = f"{line}\n}}"
            inputs.append({
                "code":      block_code,
                "startLine": cur_line,
                "endLine":   cur_line + 1
            })

            # placeholder 위치 기록
            close_stack.append(cur_line + 1)

            # 이후 라인 번호는 ‘1 줄’ 만큼만 앞당김 ★
            close_stack = [p + 1 if p >= cur_line + 1 else p for p in close_stack]
            cur_line += 1              # ★  ←  기존 +2 에서 +1 로 수정
            i += 1
            continue

        # 3) 세미콜론으로 끝나는 한 줄
        if _one_liner.match(line):
            inputs.append({
                "code":      line,
                "startLine": cur_line,
                "endLine":   cur_line
            })

            close_stack = [p + 1 if p >= cur_line + 1 else p for p in close_stack]
            cur_line += 1
            i += 1
            continue

        # 4) 지원하지 않는 형식
        raise ValueError(f"지원되지 않는 형식: {line!r} (line {cur_line})")

    return inputs

# ──────────────────── CLI ────────────────────
if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Split a Solidity file into websocket-server input chunks "
                    "and output as JSON."
    )
    parser.add_argument("solidity_file", help="Path to the .sol source file")
    parser.add_argument("-o", "--output", help="Output JSON file (default: STDOUT)")
    args = parser.parse_args()

    try:
        src_text = pathlib.Path(args.solidity_file).read_text(encoding="utf-8")
    except FileNotFoundError:
        sys.exit(f"✖ File not found: {args.solidity_file}")

    try:
        inputs = slice_solidity(src_text)
    except ValueError as e:
        sys.exit(f"✖ Parsing error: {e}")

    json_str = json.dumps(inputs, indent=2, ensure_ascii=False)

    if args.output:
        pathlib.Path(args.output).write_text(json_str, encoding="utf-8")
        print(f"✓ JSON written to {args.output}")
    else:
        print(json_str)
