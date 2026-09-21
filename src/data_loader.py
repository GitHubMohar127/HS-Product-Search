from pathlib import Path
import pandas as pd


# Project root directory
PROJECT_ROOT = Path(__file__).resolve().parent.parent

# Dataset location
DATASET_PATH = PROJECT_ROOT / "data" / "Hindcon_specility_TDS_MSDS.xlsx"


def load_product_data():
    """
    Load the Hindcon master Excel dataset.
    """

    if not DATASET_PATH.exists():
        raise FileNotFoundError(
            f"Dataset not found: {DATASET_PATH}"
        ) 

    df = pd.read_excel(DATASET_PATH)

    required_columns = [
        "Product_ID",
        "Category",
        "Product_Name",
        "TDS_Link",
        "MSDS_Link",
    ]

    missing_columns = [
        column
        for column in required_columns
        if column not in df.columns
    ]

    if missing_columns:
        raise ValueError(
            f"Missing columns in dataset: {missing_columns}"
        )

    # Keep only the columns required by our application
    df = df[required_columns].copy()

    # Clean product names
    df["Product_Name"] = (
        df["Product_Name"]
        .fillna("")
        .astype(str)
        .str.strip()
    )

    # Clean links
    df["TDS_Link"] = (
        df["TDS_Link"]
        .fillna("")
        .astype(str)
        .str.strip()
    )

    df["MSDS_Link"] = (
        df["MSDS_Link"]
        .fillna("")
        .astype(str)
        .str.strip()
    )

    # Remove rows without a product name
    df = df[df["Product_Name"] != ""]

    # Remove duplicate products
    df = df.drop_duplicates(
        subset=["Product_ID", "Product_Name"]
    )

    return df.reset_index(drop=True)