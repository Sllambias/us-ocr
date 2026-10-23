"""Summary statistics for the cervix scans in an OCR results CSV written by main.py."""
import argparse
from pathlib import Path

import pandas as pd


def read_results(input_path: str, path_column: str, subject_column: str) -> pd.DataFrame:
    """Read the OCR results and add a 'subject' column (default: the image's parent folder)."""
    df = pd.read_csv(input_path)
    if subject_column:
        df["subject"] = df[subject_column]
    else:
        df["subject"] = [Path(path).parent.name for path in df[path_column].astype(str)]
    return df


def protocols_per_subject(df: pd.DataFrame) -> pd.DataFrame:
    """Scans per cervix protocol for each subject, and how many of the 4 protocols they have."""
    protocols = ["Cervix", "Cervix dybde 1", "Cervix dybde 2", "Cervix dybde 3"]
    counts = pd.crosstab(df["subject"], df["protocol"])
    counts = counts.reindex(index=df["subject"].unique(), columns=protocols, fill_value=0)
    counts = counts.sort_index()
    counts.columns.name = None
    counts["n_protocols"] = (counts[protocols] > 0).sum(axis=1)
    return counts


def field_coverage(df: pd.DataFrame) -> pd.DataFrame:
    """How many cervix scans have each of frequency, gain, sector width / zoom and depth."""
    cervix = df[df["protocol"].notna()]
    found = {
        "frequency": cervix["frequency"].notna(),
        "gain": cervix["gain"].notna(),
        "sector width / zoom": cervix["sector_width"].notna() & cervix["zoom"].notna(),
        "depth": cervix["depth"].notna(),
    }
    rows = []
    for field, mask in found.items():
        rows.append({"field": field, "n_scans": int(mask.sum()), "percent": round(100 * mask.mean(), 1)})
    return pd.DataFrame(rows).set_index("field")


def subjects_with_lengths(df: pd.DataFrame) -> tuple:
    """Subjects with a CervixL length in at least one cervix scan, and subjects with any cervix scan."""
    cervix = df[df["protocol"].notna()]
    with_lengths = cervix.loc[cervix["lengths_mm"].notna(), "subject"].nunique()
    return with_lengths, cervix["subject"].nunique()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, help="OCR results CSV written by main.py")
    parser.add_argument("--path-column", default="file_path", help="Name of the path column (default: file_path)")
    parser.add_argument("--subject-column", help="Column with the subject ID (default: the image's parent folder)")
    parser.add_argument("--output", help="Optional CSV to save the per-subject protocol counts to")
    args = parser.parse_args()

    df = read_results(args.input, args.path_column, args.subject_column)
    cervix_scans = int(df["protocol"].notna().sum())

    per_subject = protocols_per_subject(df)
    if args.output:
        per_subject.to_csv(args.output)
    print("(A) Cervix protocols per subject")
    print(per_subject.to_string())
    print()
    print("Subjects by number of the 4 cervix protocols they have")
    n_subjects = per_subject["n_protocols"].value_counts().reindex(range(5), fill_value=0)
    print(n_subjects.rename_axis("n_protocols").rename("n_subjects").to_string())
    print()

    print(f"(B) Cervix scans with each field, out of {cervix_scans} cervix scans")
    print(field_coverage(df).to_string())
    print()

    with_lengths, with_cervix = subjects_with_lengths(df)
    print(f"(C) {with_lengths} of {with_cervix} subjects with cervix scans have CervixL in at least one of them")
    print(f"    ({len(per_subject)} subjects in total)")


if __name__ == "__main__":
    main()
