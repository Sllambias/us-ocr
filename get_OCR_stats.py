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


def with_percent(counts: pd.Series, total: int, name: str) -> pd.DataFrame:
    """Counts and their percentage of total as a two-column table."""
    return pd.DataFrame({name: counts, "percent": (100 * counts / total).round(1)})


def subjects_per_protocol(per_subject: pd.DataFrame) -> pd.DataFrame:
    """Subjects with at least one scan of each cervix protocol."""
    protocols = per_subject.columns.drop("n_protocols")
    counts = (per_subject[protocols] > 0).sum().rename_axis("protocol")
    return with_percent(counts, len(per_subject), "n_subjects")


def subjects_by_protocol_count(per_subject: pd.DataFrame) -> pd.DataFrame:
    """Subjects by how many of the 4 cervix protocols they have."""
    counts = per_subject["n_protocols"].value_counts().reindex(range(5), fill_value=0)
    return with_percent(counts.rename_axis("n_protocols"), len(per_subject), "n_subjects")


def field_coverage(df: pd.DataFrame) -> pd.DataFrame:
    """How many cervix scans have each of frequency, gain, sector width / zoom and depth."""
    cervix = df[df["protocol"].notna()]
    counts = pd.Series({
        "frequency": cervix["frequency"].notna().sum(),
        "gain": cervix["gain"].notna().sum(),
        "sector width / zoom": (cervix["sector_width"].notna() & cervix["zoom"].notna()).sum(),
        "depth": cervix["depth"].notna().sum(),
    })
    return with_percent(counts.rename_axis("field"), len(cervix), "n_scans")


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
    per_subject = protocols_per_subject(df)
    if args.output:
        per_subject.to_csv(args.output)
    n_subjects = len(per_subject)

    print(f"(A) Cervix protocols, out of {n_subjects} subjects")
    print("Subjects with at least one scan of each protocol")
    print(subjects_per_protocol(per_subject).to_string())
    print()
    print("Subjects by how many of the 4 protocols they have")
    print(subjects_by_protocol_count(per_subject).to_string())
    print()

    cervix_scans = int(df["protocol"].notna().sum())
    print(f"(B) Cervix scans with each field, out of {cervix_scans} cervix scans")
    print(field_coverage(df).to_string())
    print()

    with_lengths, with_cervix = subjects_with_lengths(df)
    print("(C) Subjects with CervixL in at least one cervix scan")
    print(f"{with_lengths} of {with_cervix} subjects with cervix scans ({100 * with_lengths / with_cervix:.1f}%)")
    print(f"{with_lengths} of {n_subjects} subjects in total ({100 * with_lengths / n_subjects:.1f}%)")


if __name__ == "__main__":
    main()
