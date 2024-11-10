import context
import pandas as pd
import gwenlake


file = "docs/TAC ECONOMICS - Monthly Comments - Country Focus - October 2023.pdf"
response = gwenlake.Client().reader.get(file=file)
print(response)