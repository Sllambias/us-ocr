# us-ocr

Extracts on-screen values (caliper lengths, frequency, gain, zoom, depth, acquisition protocol)
from ultrasound images using OCR ([docTR](https://github.com/mindee/doctr)).

## Install

```
pip install -r requirements.txt
```

## Usage

Input is a CSV with a column of image paths (DICOM, PNG or JPEG), or a `.txt` file with one path per line.

```
python main.py --input image_paths.csv --path-column file_path --output ocr_results.csv
# or
python main.py --config ocr_config.yaml
```

### Parallel runs and resuming

`--num-workers N` runs N OCR processes in parallel, each with its own copy of the model.
The output CSV is written every `--save-every` batches (default 100) and at the end.

If the output CSV already exists, paths already in it are skipped and new rows are appended,
so an interrupted run can be restarted with the same command. Rows with an `error` are not
retried; delete them from the output CSV to re-run them.

## Output

The input columns, plus:

| column | meaning |
|---|---|
| `lengths_mm` | all caliper lengths found, in mm, `;`-separated |
| `CL_sum`, `CL_max` | sum and max of those lengths (0 if none) |
| `protocol` | `Cervix` / `Cervix dybde 1-3` (study-specific) |
| `frequency` | `HI H PI` / `HI M PI` / `HI L PI` / `Augment` (empty if not found) |
| `gain`, `zoom`, `depth` | parsed settings (empty if not found); depth is the `<n> cm` after a `/` if there is one, else the first `<n> cm` |
| `error` | set if the image could not be loaded or OCR failed |
| `ocr_text` | raw OCR text (only with `--save-text`) |

Fields can be disabled under `fields:` in `ocr_config.yaml`.

## Stats

`get_OCR_stats.py` summarises the cervix scans in an output CSV, with counts and percentages:
(A) how many subjects have each of the 4 cervix protocols and how many have 0-4 of them, (B) how many
cervix scans have frequency, gain, sector width / zoom and depth, and (C) how many subjects have a
`CervixL` length in at least one cervix scan, and (D) how many subjects have all 4 protocols and a
`CervixL`, and how many of those also have frequency, gain, sector width / zoom and depth in at least
one scan of each protocol. `--output` saves the per-subject protocol counts.

`--patients-excel` adds (E): how many IDs in the Excel file's `Patient` column have 0-4 of the
protocols, and how many are not in the input. IDs are matched to the image's parent folder in
`--path-column` (`path/PATIENT-ID/filename.ext`), so it needs `--path-column`.

```
python get_OCR_stats.py --input ocr_results.csv --subject-column subject_id
python get_OCR_stats.py --input ocr_results.csv --path-column file_path --output protocols_per_subject.csv
python get_OCR_stats.py --input ocr_results.csv --path-column file_path --patients-excel patients.xlsx
```

Subjects are taken from `--subject-column` if given, otherwise from the parent folder of each image in
`--path-column`. One of the two is required.

## Code layout

| file | responsibility |
|---|---|
| `main.py` | entry point, argument parsing and config merging |
| `pipeline.py` | batching, parallel docTR OCR, resuming, writing the CSV |
| `image_io.py` | reading the path list; loading DICOM/PNG/JPEG as RGB arrays |
| `parsers.py` | regex extractors for lengths, frequency, gain, zoom, depth, protocol |
| `get_OCR_stats.py` | per-subject protocol counts and field coverage of an output CSV |
