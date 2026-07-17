# restonks
The tool for rebalancing your Freedom24 portfolio.

## Dependencies
- pandas
- tradernet-sdk
- nicegui
- keyring
- Freedom24 API key

## TODOs
### Library
- [ ] Add sell action as option.
- [ ] Setup MYPY
- [ ] Setup CI
- [ ] Setup excludes. Exclude a ticker for the buy option, e.g. if exchange rate is unfavourable at the moment.

### GUI
- [x] Create/lookup configuration directory (linux: ~/.config/restonks, windows:%APPDATA%/restonks, macOS: ~/Library/Application Support/restonks)
- [x] Save last configuration of weights for next session
- [x] Save API keys using keyring
- [x] Add a button to clear everything
- [x] Add feature to update weights
- [x] Add needed currency exchange actions
- [ ] Setup excludes in the UI

### CLI
- [x] Lookup configuration directory (linux: ~/.config/restonks, windows:%APPDATA%/restonks, macOS: ~/Library/Application Support/restonks)
- [ ] Add needed currency exchange actions
- [ ] Sell option flag
- [ ] Exclude options

## Installation
```bash
git clone git@github.com:konmenel/restonks
cd restonks
pip install .
```

## CLI

### Usage
```bash
restonks [-h] [-w WEIGHTS] [-k API_KEY] <investment_amount>
```

### Freedom24 API key
The Freedom24 API key can be obtained from the [Freedom24 API documentation](https://freedom24.com/tradernet-api/auth-api). The keys are provided using an INI file. By default the script looks at the current working directory for a file called "tradernet.ini". However, the file path can be provided using the `-k` or `--api-key` options.

The file containing the keys should be provided with the following format:
```ini
[auth]
public   = <public-key>
private  = <private-key>
```

### Weights TOML file
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

## GUI 
```bash
restonks-gui
```

### Themes
The GUI ships with six built-in themes, defined in `restonks/themes.py`:

- **DarkMidnight** *(default)* — cool slate dark theme with a blue accent
- **DarkDracula** — the classic purple-accented Dracula palette
- **DarkEmerald** — deep green dark theme
- **LightArctic** — clean, cool light theme with a blue accent
- **LightSandstone** — warm light theme with an amber accent
- **LightMint** — fresh light theme with a teal/green accent

Use the **Theme** dropdown in the top-right of the app to switch instantly. To add your own, add a `Theme(...)` entry to the `THEMES` dict in `restonks/themes.py` — no other code needs to change.
