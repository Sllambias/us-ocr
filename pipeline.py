import pandas as pd
from doctr.models import ocr_predictor
from tqdm import tqdm

from image_io import load_image, read_paths
from parsers import ALL_FIELDS, parse_text


def build_predictor():
    return ocr_predictor(det_arch="db_resnet50", reco_arch="crnn_vgg16_bn", pretrained=True)


def page_text(page) -> str:
    """Flatten a docTR page into a single string of words."""
    return " ".join(w.value for b in page.blocks for l in b.lines for w in l.words)


def run_ocr(config: dict) -> pd.DataFrame:
    fields = {f: True for f in ALL_FIELDS}
    fields.update(config.get("fields") or {})
    path_column = config.get("path_column", "file_path")
    batch_size = int(config.get("batch_size", 8))

    df = read_paths(config["input"], path_column).reset_index(drop=True)
    predictor = build_predictor()

    results = {} 
    for start in tqdm(range(0, len(df), batch_size)):
        batch_idx, batch_imgs = [], []
        for idx in range(start, min(start + batch_size, len(df))):
            try:
                batch_imgs.append(load_image(str(df.at[idx, path_column])))
                batch_idx.append(idx)
            except Exception as e:
                results[idx] = {"error": f"load failed: {e}"}

        if not batch_imgs:
            continue
        try:
            pages = predictor(batch_imgs).pages
        except Exception as e:
            for idx in batch_idx:
                results[idx] = {"error": f"OCR failed: {e}"}
            continue

        for idx, page in zip(batch_idx, pages):
            text = page_text(page)
            row = parse_text(text, fields)
            if config.get("save_text"):
                row["ocr_text"] = text
            results[idx] = row

    out = pd.concat([df, pd.DataFrame.from_dict(results, orient="index").sort_index()], axis=1)
    out.to_csv(config["output"], index=False)
    print(f"Wrote {len(out)} rows to {config['output']}")
    return out
