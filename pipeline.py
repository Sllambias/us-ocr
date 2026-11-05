import fcntl
import os
from concurrent.futures import ProcessPoolExecutor, as_completed
from concurrent.futures.process import BrokenProcessPool
from contextlib import contextmanager
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


@contextmanager
def output_lock(output_path: str):
    """Hold an exclusive lock on '<output>.lock', so array jobs take turns with the output CSV."""
    with open(output_path + ".lock", "a") as lock_file:
        fcntl.flock(lock_file, fcntl.LOCK_EX)
        yield


def result_columns(fields: dict, save_text: bool) -> list:
    """The columns added to the input columns in the output, in order."""
    columns = list(parse_text("", fields))
    if save_text:
        columns.append("ocr_text")
    columns.append("error")
    return columns


def read_existing(output_path: str, columns: list):
    """Read the output CSV from a previous run, or None if there is none.

    Any of columns that it lacks, e.g. 'error' if no image failed, are added to it,
    so new rows can be appended under its header.
    """
    with output_lock(output_path):
        if not os.path.exists(output_path):
            return None
        existing = pd.read_csv(output_path)
        missing = [c for c in columns if c not in existing.columns]
        if missing:
            existing = existing.reindex(columns=list(existing.columns) + missing)
            # Write to a temp file first so an interrupted save can't corrupt the output
            tmp_path = output_path + ".tmp"
            existing.to_csv(tmp_path, index=False)
            os.replace(tmp_path, output_path)
    return existing


def append_output(df, results, columns, output_path):
    """Append the processed rows of df to the output CSV, with a header if the file is new."""
    if not results:
        return
    # Sort rows into input order, since batches finish out of order
    indices = sorted(results)
    new = pd.DataFrame([results[idx] for idx in indices], index=indices)
    rows = pd.concat([df.loc[new.index], new], axis=1).reindex(columns=columns)
    # Open the output only while holding the lock, so on a network file system
    # each job sees the rows other jobs appended before it
    with output_lock(output_path), open(output_path, "a") as f:
        write_header = f.tell() == 0
        f.write(rows.to_csv(index=False, header=write_header))


def run_ocr(config: dict):
    fields = {f: True for f in ALL_FIELDS}
    fields.update(config.get("fields") or {})
    path_column = config.get("path_column", "file_path")
    root = config.get("root") or ""
    batch_size = int(config.get("batch_size", 8))
    num_workers = int(config.get("num_workers", 1))
    threads_per_worker = int(config.get("threads_per_worker", 1))
    save_every = int(config.get("save_every", 100))
    save_text = bool(config.get("save_text", False))
    num_chunks = int(config.get("num_chunks", 1))
    chunk_index = int(config.get("chunk_index", 0))
    output_path = config["output"]

    df = read_paths(config["input"], path_column).reset_index(drop=True)
    columns = list(df.columns) + result_columns(fields, save_text)

    # Split before skipping done paths, so a resubmitted array job gets the same chunk
    if num_chunks > 1:
        start = len(df) * chunk_index // num_chunks
        end = len(df) * (chunk_index + 1) // num_chunks
        print(f"Chunk {chunk_index} of {num_chunks}: input rows {start}-{end - 1} of {len(df)}")
        df = df.iloc[start:end]

    existing = read_existing(output_path, columns)
    if existing is not None:
        # Append under the header the output already has
        columns = list(existing.columns)
        done = df[path_column].astype(str).isin(existing[path_column].astype(str))
        print(f"Skipping {done.sum()} paths already in {output_path}")
        df = df[~done].reset_index(drop=True)

    # Only the loaded paths get the root, the output keeps path_column as given
    paths = df[path_column].astype(str)
    if root:
        # Strip leading slashes so root is prepended to absolute paths too
        paths = paths.str.lstrip("/").apply(lambda p: os.path.join(root, p))
    batches = []
    for start in range(0, len(df), batch_size):
        batches.append(list(paths.iloc[start : start + batch_size].items()))

    results = {}
    try:
        with ProcessPoolExecutor(
            num_workers, initializer=torch.set_num_threads, initargs=(threads_per_worker,)
        ) as executor:
            futures = []
            for batch in batches:
                futures.append(executor.submit(ocr_batch, batch, fields, save_text))
            for i, future in enumerate(tqdm(as_completed(futures), total=len(futures))):
                results.update(future.result())
                if (i + 1) % save_every == 0:
                    append_output(df, results, columns, output_path)
                    results = {}
    except BrokenProcessPool as e:
        e.add_note(
            "An OCR worker was killed, most likely for running out of memory. Each worker needs "
            "about 4 GB with batch_size 8, so request num_workers x 4 GB plus 1 GB, or use fewer "
            "workers. The finished rows are saved, so running the same command again continues."
        )
        raise
    finally:
        # Save the finished rows even if a worker crashed, so they aren't redone
        append_output(df, results, columns, output_path)
    print(f"Appended {len(df)} rows to {output_path}")
