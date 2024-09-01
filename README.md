# seclist

Collect and parse the history of SEC 13F [covered securities](https://www.sec.gov/divisions/investment/13flists.htm). 

## HOWTO

Linux only.

```bash
# install
sudo apt install poppler-utils
git clone https://github.com/mjudell/seclist.git
pip install ./seclist

# set up directories
mkdir -p 13f/raw
mkdir -p 13f/parsed

# pull historical indexes
seclist pull \
    --user-agent "Your Name name@domain.com" \
    --output 13f/raw

# parse historical indexes
seclist parse \
    --input 13f/raw \
    --output 13f/parsed
```
