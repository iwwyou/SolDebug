import json
from Analyzer.EnhancedSolidityVisitor import EnhancedSolidityVisitor
from Analyzer.ContractAnalyzer import ContractAnalyzer
from Analyzer.DebugUnitAnalyzer import DebugBatchManager
from Utils.util                        import ParserHelpers     # ★ here


contract_analyzer = ContractAnalyzer()
snapman           = contract_analyzer.snapman
batch_mgr         = DebugBatchManager(contract_analyzer, snapman)


def simulate_inputs(records):

    in_testcase = False          # ── 현재 @TestCase 블록 안인지

    for rec in records:
        code, s, e, ev = rec["code"], rec["startLine"], rec["endLine"], rec["event"]
        contract_analyzer.update_code(s, e, code, ev)

        stripped = code.lstrip()

        # ─────────────────────────────────────────────
        # ①  BEGIN / END 마커
        # ─────────────────────────────────────────────
        if stripped.startswith("// @TestCase BEGIN"):
            # 이전 덩어리 남아 있으면 먼저 flush
            batch_mgr.flush()
            in_testcase = True
            continue

        if stripped.startswith("// @TestCase END"):
            batch_mgr.flush()     # ← 지금까지 모은 거 처리
            in_testcase = False
            continue

        # ─────────────────────────────────────────────
        # ②  디버그 주석 (@StateVar 등)
        # ─────────────────────────────────────────────
        if in_testcase and stripped.startswith("// @"):
            # 배치에 축적
            batch_mgr.add_line(code, s, e)
            continue

        # ─────────────────────────────────────────────
        # ③  일반 Solidity 코드
        # ─────────────────────────────────────────────
        if code.strip() == "":
            continue

        ctx  = contract_analyzer.get_current_context_type()
        tree = ParserHelpers.generate_parse_tree(code, ctx, True)

        EnhancedSolidityVisitor(contract_analyzer).visit(tree)

        print("--------------------------------------------------------")


test_inputs = [
  {
    "code": "contract Dai {\n}",
    "startLine": 1,
    "endLine": 2,
    "event": "add"
  },
  {
    "code": "mapping (address => uint) public wards;",
    "startLine": 2,
    "endLine": 2,
    "event": "add"
  },
  {
    "code": "\n",
    "startLine": 3,
    "endLine": 3,
    "event": "add"
  },
  {
    "code": "uint256 public totalSupply;",
    "startLine": 4,
    "endLine": 4,
    "event": "add"
  },
  {
    "code": "mapping (address => uint) public balanceOf;",
    "startLine": 5,
    "endLine": 5,
    "event": "add"
  },
  {
    "code": "mapping (address => mapping (address => uint)) public allowance;",
    "startLine": 6,
    "endLine": 6,
    "event": "add"
  },
  {
    "code": "\n",
    "startLine": 7,
    "endLine": 7,
    "event": "add"
  },
  {
    "code": "modifier auth {\n}",
    "startLine": 8,
    "endLine": 9,
    "event": "add"
  },
  {
    "code": "require(wards[msg.sender] == 1, \"Dai/not-authorized\");",
    "startLine": 9,
    "endLine": 9,
    "event": "add"
  },
  {
    "code": "_;",
    "startLine": 10,
    "endLine": 10,
    "event": "add"
  },
  {
    "code": "\n",
    "startLine": 12,
    "endLine": 12,
    "event": "add"
  },
  {
    "code": "function add(uint x, uint y) internal pure returns (uint z) {\n}",
    "startLine": 13,
    "endLine": 14,
    "event": "add"
  },
  {
    "code": "require((z = x + y) >= x);",
    "startLine": 14,
    "endLine": 14,
    "event": "add"
  },
  {
    "code": "function sub(uint x, uint y) internal pure returns (uint z) {\n}",
    "startLine": 16,
    "endLine": 17,
    "event": "add"
  },
  {
    "code": "require((z = x - y) <= x);",
    "startLine": 17,
    "endLine": 17,
    "event": "add"
  },
  {
    "code": "\n",
    "startLine": 19,
    "endLine": 19,
    "event": "add"
  },
  {
    "code": "function transferFrom(address src, address dst, uint wad) public returns (bool) {\n}",
    "startLine": 20,
    "endLine": 21,
    "event": "add"
  },
  {
    "code": "require(balanceOf[src] >= wad, \"Dai/insufficient-balance\");",
    "startLine": 21,
    "endLine": 21,
    "event": "add"
  },
  {
    "code": "if (src != msg.sender && allowance[src][msg.sender] != uint(-1)) {\n}",
    "startLine": 22,
    "endLine": 23,
    "event": "add"
  },
  {
    "code": "require(allowance[src][msg.sender] >= wad, \"Dai/insufficient-allowance\");",
    "startLine": 23,
    "endLine": 23,
    "event": "add"
  },
  {
    "code": "allowance[src][msg.sender] = sub(allowance[src][msg.sender], wad);",
    "startLine": 24,
    "endLine": 24,
    "event": "add"
  },
  {
    "code": "balanceOf[src] = sub(balanceOf[src], wad);",
    "startLine": 26,
    "endLine": 26,
    "event": "add"
  },
  {
    "code": "balanceOf[dst] = add(balanceOf[dst], wad);",
    "startLine": 27,
    "endLine": 27,
    "event": "add"
  },
  {
    "code": "\n",
    "startLine": 28,
    "endLine": 28,
    "event": "add"
  },
  {
    "code": "return true;",
    "startLine": 29,
    "endLine": 29,
    "event": "add"
  },
  {
    "code": "\n",
    "startLine": 31,
    "endLine": 31,
    "event": "add"
  },
  {
    "code": "function transfer(address dst, uint wad) external returns (bool) {\n}",
    "startLine": 32,
    "endLine": 33,
    "event": "add"
  },
  {
    "code": "return transferFrom(msg.sender, dst, wad);",
    "startLine": 33,
    "endLine": 33,
    "event": "add"
  },
  {
    "code": "\n",
    "startLine": 35,
    "endLine": 35,
    "event": "add"
  },
  {
    "code": "function mint(address usr, uint wad) external auth {\n}",
    "startLine": 36,
    "endLine": 37,
    "event": "add"
  },
  {
    "code": "balanceOf[usr] = add(balanceOf[usr], wad);",
    "startLine": 37,
    "endLine": 37,
    "event": "add"
  },
  {
    "code": "totalSupply    = add(totalSupply, wad);",
    "startLine": 38,
    "endLine": 38,
    "event": "add"
  },
  {
    "code": "\n",
    "startLine": 40,
    "endLine": 40,
    "event": "add"
  },
  {
    "code": "function burn(address usr, uint wad) external {\n}",
    "startLine": 41,
    "endLine": 42,
    "event": "add"
  },
  {
    "code": "require(balanceOf[usr] >= wad, \"Dai/insufficient-balance\");",
    "startLine": 42,
    "endLine": 42,
    "event": "add"
  },
  {
    "code": "if (usr != msg.sender && allowance[usr][msg.sender] != uint(-1)) {\n}",
    "startLine": 43,
    "endLine": 44,
    "event": "add"
  },
  {
    "code": "require(allowance[usr][msg.sender] >= wad, \"Dai/insufficient-allowance\");",
    "startLine": 44,
    "endLine": 44,
    "event": "add"
  },
  {
    "code": "allowance[usr][msg.sender] = sub(allowance[usr][msg.sender], wad);",
    "startLine": 45,
    "endLine": 45,
    "event": "add"
  },
  {
    "code": "balanceOf[usr] = sub(balanceOf[usr], wad);",
    "startLine": 47,
    "endLine": 47,
    "event": "add"
  },
  {
    "code": "totalSupply    = sub(totalSupply, wad);",
    "startLine": 48,
    "endLine": 48,
    "event": "add"
  }
]



"""
# ──────────────────────────────────────────────────────────────
# ❸  CLI 엔트리포인트
# ----------------------------------------------------------------
def main(argv: list[str]) -> None:
    ap = argparse.ArgumentParser(
        description="Replay JSON input chunks into the incremental analyzer"
    )
    ap.add_argument("json_file", help="input file produced by split_solidity_to_inputs")
    ap.add_argument("-q", "--quiet", action="store_true",
                    help="suppress per‑line analysis dumps")
    args = ap.parse_args(argv)

    try:
        raw = pathlib.Path(args.json_file).read_text(encoding="utf-8")
        inputs = json.loads(raw)
    except FileNotFoundError:
        sys.exit(f"✖ file not found: {args.json_file}")
    except json.JSONDecodeError as e:
        sys.exit(f"✖ JSON parse error: {e}")

    simulate_inputs(inputs, silent=args.quiet)


if __name__ == "__main__":
    main(sys.argv[1:])
"""

simulate_inputs(test_inputs)