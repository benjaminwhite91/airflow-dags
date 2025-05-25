import polars as pl
import requests
from io import StringIO

WEEKLY_TSV_URL = "https://www.netflix.com/tudum/top10/data/all-weeks-countries.tsv"



def get_latest_netflix_weekly_data(tsv_path: str, logger=print):
    """" This gets the weekly netflix data. It does a total overwrite because this data is small""""

    logger("Downloading full weekly TSV data from Netflix...")
    response = requests.get(WEEKLY_TSV_URL)
    response.raise_for_status()
zz
    df = pl.read_csv(StringIO(response.text), separator="\t", try_parse_dates=True)

    logger(f"Fetched {df.height} rows. Writing to {tsv_path}...")
    df.write_csv(tsv_path, separator="\t")

    logger("Raw Netflix weekly TSV successfully saved.")