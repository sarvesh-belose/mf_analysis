import sys
import os
sys.path.append(os.path.abspath('backend'))

from app.database import engine
import pandas as pd

df = pd.read_sql('SELECT MAX(nav_date) FROM navs', engine)
print('Max NAV Date overall:', df.iloc[0][0])
