# restonks
The tool for rebalancing your Freedom24 portfolio.

## Dependencies
- pandas
- tradenet-sdk
- Fredom24 API key

## Installation
```bash
git clone git@github.com:konmenel/restonks
cd restonks
pip install .
```

## Usage
```bash
restonks [-h] [-w WEIGHTS] [-k API_KEY] <investment_amount>
```

## Freedom24 API key
The Freedom24 API key can be obtained from the [Freedom24 API documentation](https://freedom24.com/tradernet-api/auth-api). The keys are provided using an INI file. By default the script looks at the current working directory for a file called "tradernet.ini". However, the file path can be provided using the `-k` or `--api-key` options.

The file containing the keys should be provided with the following format:
```ini
[auth]
public   =  <public-key>
private  = <private-key>
```

## Weights TOML file
The target weights are provided using a TOML file. The target weights' sum should never greater than 1, however, the can be less than 1. By default the script looks at the current working directory for a file called "weights.toml". However, the file path can be provided using the `-w` or `--weights` options.

The weights file should have the following format:

```toml
tickers = [
    { name = "TICKER1.L", target_weight = 0.6  },
    { name = "TICKER2.US", target_weight = 0.2  },
    { name = "TICKER3.EU", target_weight = 0.05 },
    etc..
]
```

or
```toml
[[tickers]]
name = "TICKER1.L"
target_weight = 0.6

[[tickers]]
name = "TICKER2.US"
target_weight = 0.2

[[tickers]]
name = "TICKER3.EU"
target_weight = 0.05

etc..
```
