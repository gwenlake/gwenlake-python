# Gwenlake Python Library

The Gwenlake Python library provides convenient access to the Gwenlake API
from applications written in the Python language. It includes a
pre-defined set of classes for API resources that initialize
themselves dynamically from API responses which makes it compatible
with a wide range of versions of the Gwenlake API.


## Installation

You don't need this source code unless you want to modify the package. If you just
want to use the package, just run:

```sh
pip install -U git+https://github.com/gwenlake/gwenlake-python
```

## Usage

The library needs to be configured with your account's secret key which is available on the [website](https://console.gwenlake.com/account). Either set it as the `GWENLAKE_API_KEY` environment variable before using the library:

```bash
export GWENLAKE_API_KEY='sk-...'
```

Or set `gwenlake.api_key` to its value:

```python
import gwenlake
gwenlake.api_key = "sk-..."

