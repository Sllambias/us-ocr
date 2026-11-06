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

`--root DIR` prepends `DIR` to each path when loading the images, e.g. when the paths are relative or
the data is mounted somewhere else. The output CSV keeps the paths as they are in the input, and resuming
matches on those, so the same output can be continued with a different root.

### Parallel runs and resuming

`--num-workers N` runs N OCR processes in parallel, each with its own copy of the model, and
`--threads-per-worker T` gives each of them T torch CPU threads (both default to 1), so a run uses
N × T CPUs. Neither is inferred from the machine. Each worker needs about 4 GB of memory with
`batch_size` 8 (2.5 GB for the model, the rest for the batch), and the main process about 0.5 GB.
If a worker runs out of memory and is killed, the run stops with `BrokenProcessPool`, after saving
the rows that finished.
New rows are appended to the output CSV every `--save-every` batches (default 100) and at the end,
so the rows are roughly, but not exactly, in input order.

If the output CSV already exists, paths already in it are skipped and new rows are appended,
so an interrupted run can be restarted with the same command. Rows with an `error` are not
retried; delete them from the output CSV to re-run them.

### Array jobs

`--num-chunks N --chunk-index I` splits the input into N contiguous chunks and processes only chunk `I`
(0 to N-1). This way each task of an HPC array job processes its own chunk, and all tasks append to the
same output CSV:

```
#!/bin/bash
#SBATCH --array=0-9
#SBATCH --cpus-per-task=8
#SBATCH --mem=10G

python main.py --config ocr_config.yaml --num-workers 2 --threads-per-worker 4 \
    --num-chunks 10 --chunk-index $SLURM_ARRAY_TASK_ID
```

The input is split before skipping paths already in the output, so a task gets the same chunk when it is
resubmitted. To re-run only some tasks, resubmit their indices (e.g. `--array=3,7`) with the same
`--num-chunks`. Set `--cpus-per-task` to `num_workers × threads_per_worker`, and `--mem` to at
least `num_workers × 4 GB + 1 GB`.

The tasks take turns writing to the output through a lock on `<output>.lock`. This needs the output
to be on a file system where file locks work across nodes, as they do on NFS and GPFS. Lustre
needs the `flock` mount option.

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
`--path-column` (`path/PATIENT-ID/filename.ext`), so it needs `--path-column`. It also prints, for
each month folder (`path/MONTH/PATIENT-ID/filename.ext`), how many of these patients have 0-4 of the
protocols and the percentage with all 4, followed by how many of the patients with 0 protocols are in
the input without cervix scans and how many are not in the input at all.

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
| `pipeline.py` | chunking, batching, parallel docTR OCR, resuming, appending to the CSV |
| `image_io.py` | reading the path list; loading DICOM/PNG/JPEG as RGB arrays |
| `parsers.py` | regex extractors for lengths, frequency, gain, zoom, depth, protocol |
| `get_OCR_stats.py` | per-subject protocol counts and field coverage of an output CSV |
