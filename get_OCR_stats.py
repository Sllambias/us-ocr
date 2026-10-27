"""Summary statistics for the cervix scans in an OCR results CSV written by main.py."""
import argparse
from pathlib import Path

import pandas as pd


def read_results(input_path: str, path_column: str, subject_column: str) -> pd.DataFrame:
    """Read the OCR results and add a 'subject' column from subject_column, or else the image's parent folder."""
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


def has_all_fields(df: pd.DataFrame) -> pd.Series:
    """Whether each scan has frequency, gain, sector width / zoom and depth."""
    return (
        df["frequency"].notna()
        & df["gain"].notna()
        & df["sector_width"].notna()
        & df["zoom"].notna()
        & df["depth"].notna()
    )


def complete_subjects(df: pd.DataFrame, per_subject: pd.DataFrame) -> pd.DataFrame:
    """Subjects with all 4 protocols and a CervixL, and those of them with all fields in a scan of each protocol."""
    cervix = df[df["protocol"].notna()]
    all_protocols = per_subject.index[per_subject["n_protocols"] == 4]
    with_lengths = cervix.loc[cervix["lengths_mm"].notna(), "subject"].unique()
    complete = all_protocols.intersection(with_lengths)

    per_subject_all_fields = protocols_per_subject(cervix[has_all_fields(cervix)])
    all_fields = per_subject_all_fields.index[per_subject_all_fields["n_protocols"] == 4]
    counts = pd.Series({
        "4 protocols + CervixL": len(complete),
        "4 protocols + CervixL + all fields in each protocol": len(complete.intersection(all_fields)),
    })
    return with_percent(counts.rename_axis("subjects"), len(per_subject), "n_subjects")


def excel_patients_by_protocol_count(df: pd.DataFrame, path_column: str, excel_path: str) -> pd.DataFrame:
    """Patients in the Excel file's 'Patient' column by how many of the 4 protocols they have, matched on the image's parent folder."""
    patients = pd.read_excel(excel_path, dtype={"Patient": str})["Patient"].dropna().str.strip().unique()
    by_folder = df.assign(subject=[Path(path).parent.name for path in df[path_column].astype(str)])
    per_patient = protocols_per_subject(by_folder)
    found = per_patient[per_patient.index.isin(patients)]
    counts = found["n_protocols"].value_counts().reindex(range(5), fill_value=0)
    counts["not in input"] = len(patients) - len(found)
    return with_percent(counts.rename_axis("n_protocols"), len(patients), "n_patients")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, help="OCR results CSV written by main.py")
    parser.add_argument("--subject-column", help="Column with the subject ID")
    parser.add_argument("--path-column", help="Column with the image path, whose parent folder is the subject ID if --subject-column is not given")
    parser.add_argument("--output", help="Optional CSV to save the per-subject protocol counts to")
    parser.add_argument("--patients-excel", help="Optional Excel file whose 'Patient' IDs are matched to the image's parent folder in --path-column")
    args = parser.parse_args()
    if not args.subject_column and not args.path_column:
        parser.error("give --subject-column or --path-column")
    if args.patients_excel and not args.path_column:
        parser.error("--patients-excel needs --path-column")

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
    print()

    print(f"(D) Subjects with all 4 protocols and CervixL in at least one cervix scan, out of {n_subjects} subjects")
    print("All fields means frequency, gain, sector width / zoom and depth in at least one scan of each protocol")
    print(complete_subjects(df, per_subject).to_string())

    if args.patients_excel:
        print()
        print(f"(E) Patients in {args.patients_excel} by how many of the 4 protocols they have")
        print(excel_patients_by_protocol_count(df, args.path_column, args.patients_excel).to_string())


if __name__ == "__main__":
    main()
