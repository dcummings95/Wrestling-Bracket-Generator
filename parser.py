import pandas as pd
from models import Wrestler


def parse_grade(grade_raw) -> int:
    grade_str = str(grade_raw).strip().lower()
    if grade_str in ('pre-k', 'prek', 'pre k'):
        return -1
    elif grade_str == 'k':
        return 0
    else:
        return int(grade_raw)


def parse_dataframe(df: pd.DataFrame) -> list[Wrestler]:
    df.columns = df.columns.str.strip().str.lower().str.replace(' ', '_')
    
    expected_cols = ['grade', 'first_name', 'last_name', 'weight', 'rank', 'school']
    missing = [col for col in expected_cols if col not in df.columns]
    if missing:
        raise ValueError(f"Missing required columns: {missing}")
    
    wrestlers = []
    for idx, row in df.iterrows():
        try:
            wrestler = Wrestler(
                id=idx,
                first_name=str(row['first_name']).strip(),
                last_name=str(row['last_name']).strip(),
                grade=parse_grade(row['grade']),
                weight=float(row['weight']),
                rank=int(row['rank']),
                school=str(row['school']).strip()
            )
            wrestlers.append(wrestler)
        except (ValueError, TypeError) as e:
            raise ValueError(f"Error parsing row {idx + 2}: {e}")
    
    return wrestlers


def parse_excel(file_path: str) -> list[Wrestler]:
    df = pd.read_excel(file_path)
    return parse_dataframe(df)


def parse_csv(file_path: str) -> list[Wrestler]:
    df = pd.read_csv(file_path)
    return parse_dataframe(df)
