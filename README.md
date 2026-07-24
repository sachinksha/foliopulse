# foliopulse
FolioPulse — A real-time Indian equity portfolio tracker with stop-loss visualizer and live P&amp;L monitoring built with Streamlit &amp; Python

# Pre-requisite
Install Python 3.14

Setup python virtual environment

```bash
python3 -m venv myenv   
```
Activate

```bash
source myenv/bin/activate
```

OR in CachyOS

```bash
source myenv/bin/activate.fish
```
Once done running the program, deactivate the virtual environment

```bash
myenv > deactivate
```
# Getting Started

Install dependencies

``` bash
myenv > pip install streamlit yfinance pandas plotly streamlit-autorefresh
```

Run the app
``` bash
myenv > streamlit run app.py
```

Press Ctrl + C to kill the app