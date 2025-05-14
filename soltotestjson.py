# split_solidity_to_inputs.py  (patch)

from __future__ import annotations
import re, json, sys, argparse, pathlib
from typing import List, Dict

# ── 패턴 ──────────────────────────────────────────────────────────────
_only_ws   = re.compile(r"^\s*$")          # 공백/탭 뿐
_open_blk  = re.compile(r"\{\s*$")         # … {
_one_liner = re.compile(r";\s*$")          # … ;
_only_clo  = re.compile(r"^\s*}\s*$")      # }

def slice_solidity(source: str) -> List[Dict[str, str | int]]:
    """
    (1) 세미콜론 한 줄
    (2) 헤더 + ‘}’ 를 같은 청크로 갖는 1-line-block
    (3) 완전히 빈 줄
    위 3종만 생성하며, 독립적인 ‘}’ 는 JSON으로 **내보내지 않는다.**
    """
    lines: List[str] = source.splitlines()
    inputs: List[Dict[str, str | int]] = []

    cur_line = 1        # 실제 소스 라인 번호 (1-based)
    i = 0               # lines[] 인덱스

    while i < len(lines):
        raw = lines[i]
        txt = raw.rstrip()                # 우측 공백 제거
        txt = txt.lstrip()                # 좌측 들여쓰기 제거

        # 1) 빈 줄 ──────────────────────────────────────────────
        if _only_ws.match(raw):
            inputs.append({"code": "\n", "startLine": cur_line, "endLine": cur_line})
            cur_line += 1
            i += 1
            continue

        # 2) 단독 '}'  ── JSON으로는 내보내지 않고 라인만 소비 ──
        if _only_clo.match(txt):
            cur_line += 1
            i += 1
            continue

        # 3) '{' 로 끝나는 헤더 줄  ──────────────────────────────
        if _open_blk.search(txt):
            block_code = f"{txt}\n}}"                    # header + 가짜 닫는 괄호
            inputs.append({
                "code":      block_code,
                "startLine": cur_line,
                "endLine":   cur_line + 1                # 헤더+1 ⇒ 2-line block
            })
            cur_line += 1        # ※ 실제 소스엔 닫는 ‘}’ 가 없으므로 +1만
            i += 1
            continue

        # 4) 세미콜론으로 끝나는 한 줄 문장  ─────────────────────
        if _one_liner.search(txt):
            inputs.append({"code": txt, "startLine": cur_line, "endLine": cur_line})
            cur_line += 1
            i += 1
            continue

        # 5) 그밖의 형식은 아직 지원하지 않음 ────────────────────
        raise ValueError(f"지원되지 않는 형식: {raw!r} (line {cur_line})")

    return inputs


# ─────────────── CLI entry ───────────────
if __name__ == "__main__":
    p = argparse.ArgumentParser(
        description="Split a Solidity file into websocket-server input chunks (JSON).")
    p.add_argument("solidity_file")
    p.add_argument("-o", "--output")
    args = p.parse_args()

    try:
        src = pathlib.Path(args.solidity_file).read_text(encoding="utf-8")
    except FileNotFoundError:
        sys.exit(f"✖ File not found: {args.solidity_file}")

    try:
        chunks = slice_solidity(src)
    except ValueError as e:
        sys.exit(f"✖ Parsing error: {e}")

    json_str = json.dumps(chunks, indent=2, ensure_ascii=False)
    if args.output:
        pathlib.Path(args.output).write_text(json_str, encoding="utf-8")
        print(f"✓ JSON written to {args.output}")
    else:
        print(json_str)
