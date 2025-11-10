# SolQDebug Benchmark Dataset

This directory contains the benchmark dataset used to evaluate SolQDebug, consisting of 30 real-world Solidity smart contracts curated from DAppSCAN.

## Dataset Overview

- **Total Contracts**: 30
- **Source**: DAppSCAN (https://github.com/DAppSCAN-source)
- **Selection Criteria**: Contracts with diverse complexity levels, covering common DeFi patterns

## Dataset Structure

```
dataset/
├── dataset_all/           # All 30 benchmark contracts (.sol files)
├── dataset_select/        # Selected subset for quick testing
├── contraction/          # Preprocessed contracts
├── contraction_remix/    # Remix-compatible versions
├── evaluation_Dataset.xlsx  # Dataset metadata and statistics
└── README.md
```

## Contract Categories

The benchmark covers various contract types:

### DeFi Protocols
- **Lending/Borrowing**: Aave-related contracts (AaveAMO, AaveOracle, ACLManager)
- **Staking**: ATIDStaking, AlpacaFeeder
- **Token Management**: AgToken, AMPT, AOC_BEP

### Infrastructure
- **Bridges**: Abs_L1TokenGateway, AnyswapFacet
- **Oracles**: AprOracle
- **Access Control**: AccessControlEnumerable, AuthorizationUtils

### Specialized Applications
- **NFT Marketplace**: AvatarArtMarketPlace
- **AMM/DEX**: AloeBlend, Balancer
- **Governance**: Various governance token contracts

## Dataset Metadata

The `evaluation_Dataset.xlsx` file contains:
- Contract names and sources
- Lines of code (LOC) statistics
- Function complexity metrics
- Number of state variables
- Loop and control flow statistics

## Using the Dataset

### Loading Contracts

```python
from Evaluation.read_evaluation_dataset import load_contracts

contracts = load_contracts('dataset/dataset_all/')
for contract in contracts:
    print(f"Contract: {contract.name}, LOC: {contract.loc}")
```

### Running Analysis on Dataset

```python
from Analyzer.ContractAnalyzer import ContractAnalyzer

analyzer = ContractAnalyzer()
analyzer.analyze_file('dataset/dataset_all/AaveAMO.sol')
```

## Selection Criteria

Contracts were selected based on:

1. **Real-world usage**: Deployed and actively used protocols
2. **Complexity diversity**:
   - Simple token contracts
   - Complex DeFi protocols with multiple interactions
   - Contracts with various control flow patterns
3. **Feature coverage**:
   - State variables and mappings
   - Loops (for, while, do-while)
   - Complex arithmetic operations
   - External calls and interactions
   - Modifiers and inheritance

## Contract Statistics

| Metric | Min | Median | Max |
|--------|-----|--------|-----|
| LOC | 50 | 250 | 800 |
| Functions | 5 | 15 | 40 |
| State Variables | 3 | 10 | 25 |
| Loops | 0 | 2 | 8 |

## Data Source

All contracts are sourced from DAppSCAN, a large-scale dataset of real-world smart contracts:
- Repository: https://github.com/DAppSCAN-source
- Contracts are publicly available under their respective licenses
- Selection was made to ensure diversity and representativeness

## Preprocessing

### `dataset_select/`
Contains a smaller subset (10 contracts) for quick testing and development.

### `contraction/` and `contraction_remix/`
Preprocessed versions of contracts:
- Simplified for specific experiments
- Modified for Remix IDE compatibility
- Annotated with test cases

## Adding New Contracts

To add new contracts to the benchmark:

1. Place the `.sol` file in `dataset_all/`
2. Update `evaluation_Dataset.xlsx` with contract metadata
3. Run preprocessing scripts if needed:
   ```bash
   python dataset/add_headers.py <contract_file>
   ```

## Citation

If you use this dataset in your research, please cite both the SolQDebug paper and the original DAppSCAN source.

## License

Contracts retain their original licenses. See individual contract files for license information.

## Contact

For questions about the dataset:
- GitHub Issues: https://github.com/iwwyou/SolDebug/issues
- Email: iwwyou@korea.ac.kr
