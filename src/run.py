from pathlib import Path
import pandas as pd

#Get the directory where the current file is located(src/)
CURRENT_DIR = Path(__file__).resolve().parent
#Get the root directory of the project (CLMTA/)
PROJECT_ROOT = CURRENT_DIR.parent
#Get the data directory (CLMTA/data/)
DATA_PATH = PROJECT_ROOT / "data" / "data.csv"

#Read via absolute path
df = pd.read_csv(DATA_PATH, skiprows = 4)
print(f"读取成功！数据共有 {len(df)} 行，前 3 行如下：\n{df.head(3)}")