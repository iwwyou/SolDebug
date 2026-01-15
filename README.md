# SolQDebug

Official implementation for the paper **"SolQDebug: Debug Solidity Quickly for Interactive Immediacy in Smart Contract Development"**

## Overview

SolQDebug is an incremental abstract interpreter for Solidity that enables interactive debugging without requiring compilation or deployment. The system maintains an evolving abstract interpretation of smart contract programs, providing immediate feedback on variable values and potential errors as developers write code.

## Features

- **Incremental Analysis**: Statement-by-statement processing with immediate feedback
- **No Deployment Required**: Debug without blockchain deployment
- **Abstract Interpretation**: Interval-based abstract domain for precise analysis
- **Interactive Debugging**: Real-time variable value tracking and error detection

## Installation

### Prerequisites

- Python 3.8 or higher
- pip package manager

### Setup

1. Clone the repository:
```bash
git clone https://github.com/iwwyou/SolDebug.git
cd SolDebug
```

2. Create a virtual environment (recommended):
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

## Project Structure

```
SolDebug/
├── Analyzer/          # Core analysis components
├── Domain/            # Abstract domain implementations
├── Interpreter/       # Abstract interpreter
├── Parser/            # Solidity parser (ANTLR4-based)
├── Utils/             # Helper utilities
├── Evaluation/        # Experimental evaluation scripts
├── dataset/           # Benchmark dataset (30 contracts)
├── main.py            # Main entry point
└── README.md
```

## Usage

### Basic Usage

Run the main analyzer:
```bash
python main.py
```

### Debugging with Annotations

SolQDebug uses special annotations to specify test cases:

```solidity
function example(uint256 amount) public {
    // @Debugging BEGIN
    // @StateVar balances[msg.sender] = [100,200]
    // @LocalVar amount = [50,70]
    // @Debugging END

    uint256 bal = balances[msg.sender];
    // SolQDebug will show: bal = [100,200]

    if (bal >= amount) {
        balances[msg.sender] = bal - amount;
        // SolQDebug will show: balances[msg.sender] = [30,150]
    }
}
```

## Benchmark Dataset

The `dataset/` directory contains 30 real-world Solidity contracts curated from DAppSCAN, covering various DeFi protocols including:
- Token contracts
- DeFi protocols (lending, staking, vesting)
- Governance systems
- NFT marketplaces

See [dataset/README.md](dataset/README.md) for details.

## Evaluation

The `Evaluation/RQ1_Latency/` directory contains the benchmark scripts to reproduce the latency comparison results.

```bash
cd Evaluation/RQ1_Latency
install_dependencies.bat
python solqdebug_benchmark.py
```

See [Evaluation/RQ1_Latency/README.md](Evaluation/RQ1_Latency/README.md) for details.

## Citation

If you use SolQDebug in your research, please cite:

```bibtex
@article{soldebug2025,
  title={SolQDebug: Debug Solidity Quickly for Interactive Immediacy in Smart Contract Development},
  author={Jeon, Inseong and Kim, Sundeuk and Kim, Hyunwoo and In, Hoh Peter},
  year={2025}
}
```

## License

[To be specified]

## Contact

- Inseong Jeon: iwwyou@korea.ac.kr
- Issues: https://github.com/iwwyou/SolDebug/issues

## Acknowledgments

This work was supported by the Institute of Information & communications Technology Planning & Evaluation (IITP) grant funded by the Korean government (MSIT).
