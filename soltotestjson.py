# soltotestjson.py  — Solidity → test JSON slicer (skeleton ON by default)
from __future__ import annotations
import re, json, sys, argparse, pathlib
from typing import List, Dict, Tuple

# ── 헤더 키워드(블록 여는 토큰) ─────────────────────────────────────────
#  * 'event' 는 블록이 아니라 세미콜론 문장이라 제외
_BLOCK_HEAD_RE = re.compile(
    r"^\s*(?:abstract\s+contract|contract|library|interface|function|constructor|modifier|"
    r"struct|enum|if|else(?:\s+if)?\b|for|while|do\b|try|catch|unchecked|assembly)\b"
)

# ── 라인 패턴 ─────────────────────────────────────────────────────────
_ONLY_WS   = re.compile(r"^\s*$")
_ONLY_CLO  = re.compile(r"^\s*}\s*$")
_SEMI_END  = re.compile(r";\s*(?://.*)?$")  # 라인 끝 세미콜론 (주석 허용)

# `} else` / `} while` 를 두 줄로 쪼개기 위한 정규식
_COMPOUND_SPLIT_RE = re.compile(r"}\s*(?=(?:else\b|while\b))")

def _normalize_compound_lines(lines: List[str]) -> List[str]:
    """한 물리 라인에 `} else …` 또는 `} while …` 이 붙어 있으면
    `}` 과 뒤 토큰을 서로 다른 라인으로 분리한다."""
    out: List[str] = []
    for raw in lines:
        rest = raw
        while True:
            m = _COMPOUND_SPLIT_RE.search(rest)
            if not m:
                out.append(rest)
                break
            left = rest[:m.start()] + "}"
            right = rest[m.end():].lstrip()
            out.append(left)
            rest = right
    return out

# ── 문자열/주석을 고려해 (), [], {} 델타를 계산 (블록 주석跨라인 지원) ──
def _scan_line_delta(s: str, in_block_comment: bool) -> Tuple[int, int, int, bool]:
    pd = bd = cd = 0
    in_s = in_d = False
    i = 0
    while i < len(s):
        ch = s[i]

        # 블록 주석 종료?
        if in_block_comment:
            if ch == '*' and i + 1 < len(s) and s[i + 1] == '/':
                in_block_comment = False
                i += 2
            else:
                i += 1
            continue

        # 라인 주석 시작? → 이후 무시
        if not in_s and not in_d and ch == '/' and i + 1 < len(s) and s[i + 1] == '/':
            break
        # 블록 주석 시작?
        if not in_s and not in_d and ch == '/' and i + 1 < len(s) and s[i + 1] == '*':
            in_block_comment = True
            i += 2
            continue

        # 문자열 토글 (escape 간소 처리: \" \' 만 고려)
        if ch == '"' and not in_s and not in_block_comment:
            in_d = not in_d; i += 1; continue
        if ch == "'" and not in_d and not in_block_comment:
            in_s = not in_s; i += 1; continue

        # 문자열 내부/주석 내부는 스킵
        if in_s or in_d:
            # 간단 escape
            if ch == '\\':
                i += 2
            else:
                i += 1
            continue

        # 델타 집계
        if ch == '(':
            pd += 1
        elif ch == ')':
            pd -= 1
        elif ch == '[':
            bd += 1
        elif ch == ']':
            bd -= 1
        elif ch == '{':
            cd += 1
        elif ch == '}':
            cd -= 1
        i += 1

    return pd, bd, cd, in_block_comment

def _ends_with_semi_outside(s: str, in_block_comment: bool) -> bool:
    """주석/문자열 밖에서 세미콜론으로 끝나는지 검사."""
    in_s = in_d = False
    i = 0
    last_nonspace = None
    while i < len(s):
        ch = s[i]
        if in_block_comment:
            if ch == '*' and i + 1 < len(s) and s[i + 1] == '/':
                in_block_comment = False; i += 2; continue
            i += 1; continue
        if not in_s and not in_d and ch == '/' and i + 1 < len(s) and s[i + 1] == '/':
            break
        if not in_s and not in_d and ch == '/' and i + 1 < len(s) and s[i + 1] == '*':
            in_block_comment = True; i += 2; continue
        if ch == '"' and not in_s: in_d = not in_d; i += 1; continue
        if ch == "'" and not in_d: in_s = not in_s; i += 1; continue
        if in_s or in_d:
            if ch == '\\': i += 2
            else: i += 1
            continue
        if not ch.isspace():
            last_nonspace = ch
        i += 1
    return last_nonspace == ';'

def slice_solidity(source: str, *, skeleton: bool = True, emit_blank: bool = True) -> List[Dict[str, str | int]]:
    """
    완성된 Solidity 소스를 (에디터 이벤트 스트림처럼) 청크 배열로 변환.
      - skeleton=True: 블록 헤더를 만나면 '...{' 까지 모아 바로 다음 줄에 '}'를 인위적으로 붙여 한 청크로 보냄.
                       실제 소스에 나오는 단독 '}' 라인은 건너뜀.
      - skeleton=False: 인위적인 '}'를 붙이지 않음. 실제 '}'도 각각 이벤트로 출력.
      - emit_blank=False: 빈 줄 이벤트('\n') 생략.
    """
    raw_lines = source.splitlines()
    lines = _normalize_compound_lines(raw_lines)

    inputs: List[Dict[str, str | int]] = []
    i = 0
    cur = 1
    in_block_comment = False

    def _emit(code_lines: List[str], start: int):
        code = "\n".join(code_lines)
        end = start + len(code_lines) - 1
        inputs.append({"code": code, "startLine": start, "endLine": end, "event": "add"})

    while i < len(lines):
        raw = lines[i]
        txt = raw.rstrip("\n")

        # 1) 빈 줄
        if _ONLY_WS.match(txt):
            if emit_blank:
                inputs.append({"code": "\n", "startLine": cur, "endLine": cur, "event": "add"})
            i += 1; cur += 1; continue

        # 2) 단독 '}' (스켈레톤이면 무시, 아니면 출력)
        if _ONLY_CLO.match(txt):
            if not skeleton:
                _emit([txt], cur)
            i += 1; cur += 1; continue

        # 3) 블록 헤더인지?  (event 제외)
        if _BLOCK_HEAD_RE.match(txt) and not txt.lstrip().startswith("event"):
            # 헤더 줄부터 '{' 가 최초로 등장할 때까지 누적
            start = cur
            buf = [txt]
            pd, bd, cd, in_block_comment = _scan_line_delta(txt, in_block_comment)
            j = i + 1
            # '{' 가 나올 때까지(= cd > 0 될 때까지) 라인 추가
            while cd <= 0:
                if j >= len(lines):
                    # '{' 를 못 찾았으면, 그냥 지금까지 누적된 라인으로 마감
                    break
                nxt = lines[j]
                buf.append(nxt)
                dp, db, dc, in_block_comment = _scan_line_delta(nxt, in_block_comment)
                pd += dp; bd += db; cd += dc
                j += 1

            if skeleton:
                # 스켈레톤: 헤더(+ '{'가 포함된 라인들) 뒤에 '}' 한 줄을 인위적으로 추가
                code_lines = list(buf) + ["}"]
                _emit(code_lines, start)
                # 실제 소스의 닫는 괄호는 이후에 만나도 무시되므로,
                # 스캐너는 '{' 라인이 위치한 곳까지 전진 (j는 '{' 이후 라인 인덱스)
                i = j
                cur = start + len(buf)
                continue
            else:
                # 스켈레톤 아님: 실제 라인만 그대로 emit (인위적인 '}' 없음)
                _emit(buf, start)
                i = j
                cur = start + len(buf)
                continue

        # 4) 일반 문장: 세미콜론이 문자열/주석 밖에서 나올 때까지 누적
        start = cur
        buf = [txt]
        pd, bd, cd, in_block_comment = _scan_line_delta(txt, in_block_comment)
        j = i + 1
        semi_ok = _ends_with_semi_outside(txt, in_block_comment) and (pd == 0 and bd == 0 and cd == 0)

        while not semi_ok:
            if j >= len(lines):
                # 마지막에 세미콜론이 없으면, 지금까지 누적된 걸 문장으로 취급해서 내보냄
                break
            nxt = lines[j]
            buf.append(nxt)
            dp, db, dc, in_block_comment = _scan_line_delta(nxt, in_block_comment)
            pd += dp; bd += db; cd += dc
            semi_ok = _ends_with_semi_outside(nxt, in_block_comment) and (pd == 0 and bd == 0 and cd == 0)
            j += 1

        _emit(buf, start)
        i = j
        cur = start + len(buf)

    return inputs

# ───────────── CLI ─────────────
if __name__ == "__main__":
    p = argparse.ArgumentParser(
        description="Split a Solidity file into websocket-server input chunks (JSON)."
    )
    p.add_argument("solidity_file")
    p.add_argument("-o", "--output")
    p.add_argument("--no-skeleton", action="store_true",
                   help="헤더 스켈레톤을 끄고 실제 '}' 라인도 각각 이벤트로 출력합니다 (기본은 스켈레톤 ON).")
    p.add_argument("--no-blank", action="store_true",
                   help="빈 줄('\\n') 이벤트를 출력하지 않습니다.")
    args = p.parse_args()

    try:
        src = pathlib.Path(args.solidity_file).read_text(encoding="utf-8")
    except FileNotFoundError:
        sys.exit(f"✖ File not found: {args.solidity_file}")

    try:
        chunks = slice_solidity(
            src,
            skeleton=(not args.no_skeleton),
            emit_blank=(not args.no_blank),
        )
    except ValueError as e:
        sys.exit(f"✖ Parsing error: {e}")

    s = json.dumps(chunks, indent=2, ensure_ascii=False)
    if args.output:
        pathlib.Path(args.output).write_text(s, encoding="utf-8")
        print(f"✓ JSON written to {args.output}")
    else:
        print(s)
