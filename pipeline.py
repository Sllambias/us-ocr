import os
from concurrent.futures import ProcessPoolExecutor, as_completed
from functools import cache

import pandas as pd
import torch
from doctr.models import ocr_predictor
from tqdm import tqdm

from image_io import load_image, read_paths
from parsers import ALL_FIELDS, parse_text


@cache
def build_predictor():
    """Build the docTR predictor once per process."""
    return ocr_predictor(
        det_arch="db_resnet50", reco_arch="crnn_vgg16_bn", pretrained=True
    )


def page_text(page) -> str:
    """Flatten a docTR page into a single string of words."""
    return " ".join(w.value for b in page.blocks for l in b.lines for w in l.words)


def ocr_batch(batch: list, fields: dict, save_text: bool) -> dict:
    """OCR and parse one batch of (index, path) pairs."""
    predictor = build_predictor()
    results = {}
    batch_idx, batch_imgs = [], []
    for idx, path in batch:
        try:
            batch_imgs.append(load_image(path))
            batch_idx.append(idx)
        except Exception as e:
            results[idx] = {"error": f"load failed: {e}"}

    if not batch_imgs:
        return results
    try:
        pages = predictor(batch_imgs).pages
    except Exception as e:
        for idx in batch_idx:
            results[idx] = {"error": f"OCR failed: {e}"}
        return results

    for idx, page in zip(batch_idx, pages):
        text = page_text(page)
        row = parse_text(text, fields)
        if save_text:
            row["ocr_text"] = text
        results[idx] = row
    return results


def read_existing(output_path: str):
    """Read the output CSV from a previous run, or None if there is none."""
    if not os.path.exists(output_path):
        return None
    return pd.read_csv(output_path)


def write_output(df, results, existing, output_path) -> pd.DataFrame:
    """Write the existing rows plus the processed rows of df to the output CSV."""
    new = pd.DataFrame.from_dict(results, orient="index").sort_index()
    out = pd.concat([df.loc[new.index], new], axis=1)
    if existing is not None:
        out = pd.concat([existing, out], ignore_index=True)
    # Write to a temp file first so an interrupted save can't corrupt the output
    tmp_path = output_path + ".tmp"
    out.to_csv(tmp_path, index=False)
    os.replace(tmp_path, output_path)
    return out


def run_ocr(config: dict) -> pd.DataFrame:
    fields = {f: True for f in ALL_FIELDS}
    fields.update(config.get("fields") or {})
    path_column = config.get("path_column", "file_path")
    batch_size = int(config.get("batch_size", 8))
    num_workers = int(config.get("num_workers", 1))
    save_every = int(config.get("save_every", 100))
    save_text = bool(config.get("save_text", False))
    output_path = config["output"]

    df = read_paths(config["input"], path_column).reset_index(drop=True)

    existing = read_existing(output_path)
    if existing is not None:
        done = df[path_column].astype(str).isin(existing[path_column].astype(str))
        print(f"Skipping {done.sum()} paths already in {output_path}")
        df = df[~done].reset_index(drop=True)

    paths = df[path_column].astype(str)
    batches = []
    for start in range(0, len(df), batch_size):
        batches.append(list(paths.iloc[start : start + batch_size].items()))

    # Split the CPU threads between workers so they don't oversubscribe the cores
    threads = max(1, (os.cpu_count() or 1) // num_workers)
    results = {}
    with ProcessPoolExecutor(
        num_workers, initializer=torch.set_num_threads, initargs=(threads,)
    ) as executor:
        futures = []
        for batch in batches:
            futures.append(executor.submit(ocr_batch, batch, fields, save_text))
        for i, future in enumerate(tqdm(as_completed(futures), total=len(futures))):
            results.update(future.result())
            if (i + 1) % save_every == 0:
                write_output(df, results, existing, output_path)

    out = write_output(df, results, existing, output_path)
    print(f"Wrote {len(out)} rows to {output_path}")
    return out
