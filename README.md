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

## Output

The input columns, plus:

| column | meaning |
|---|---|
| `lengths_mm` | all caliper lengths found, in mm, `;`-separated |
| `CL_sum`, `CL_max` | sum and max of those lengths (0 if none) |
| `protocol` | `Cervix` / `Cervix dybde 1-3` (study-specific) |
| `frequency`, `gain`, `zoom`, `depth` | parsed settings (empty if not found) |
| `error` | set if the image could not be loaded or OCR failed |
| `ocr_text` | raw OCR text (only with `--save-text`) |

Fields can be disabled under `fields:` in `ocr_config.yaml`.

## Code layout

| file | responsibility |
|---|---|
| `main.py` | entry point, argument parsing and config merging |
| `pipeline.py` | batching, docTR OCR, assembling and writing the CSV |
| `image_io.py` | reading the path list; loading DICOM/PNG/JPEG as RGB arrays |
| `parsers.py` | regex extractors for lengths, frequency, gain, zoom, depth, protocol |
