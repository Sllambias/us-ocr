from pathlib import Path

import numpy as np
import pandas as pd
import pydicom
from PIL import Image


def load_image(path: str) -> np.ndarray:
    """Load a DICOM or standard image file as a uint8 RGB array (H, W, 3).

    Multi-frame DICOMs use the middle frame.
    """
    if Path(path).suffix.lower() in {".dcm", ".dicom"}:
        dcm = pydicom.dcmread(path)
        img = dcm.pixel_array
        samples = int(getattr(dcm, "SamplesPerPixel", 1))
        photometric = str(getattr(dcm, "PhotometricInterpretation", ""))

        # Drop the frame axis if multi-frame
        if (samples == 1 and img.ndim == 3) or (samples > 1 and img.ndim == 4):
            img = img[img.shape[0] // 2]
        if samples == 3 and photometric.startswith("YBR"):
            img = pydicom.pixels.convert_color_space(img, photometric, "RGB")
    else:
        img = np.array(Image.open(path))

    if img.ndim == 3 and img.shape[0] == 3 and img.shape[2] != 3:  # channels-first
        img = np.transpose(img, (1, 2, 0))
    if img.ndim == 2:
        img = np.stack([img] * 3, axis=-1)
    elif img.ndim == 3 and img.shape[2] == 4:
        img = img[:, :, :3]
    if img.ndim != 3 or img.shape[2] != 3:
        raise ValueError(f"Unsupported image shape {img.shape}")
    return img.astype(np.uint8)


def read_paths(input_path: str, path_column: str) -> pd.DataFrame:
    """Read the input list into a DataFrame with a path column."""
    if input_path.lower().endswith((".txt", ".lst")):
        with open(input_path) as f:
            paths = [line.strip() for line in f if line.strip()]
        return pd.DataFrame({path_column: paths})
    df = pd.read_csv(input_path)
    if path_column not in df.columns:
        raise KeyError(f"Column '{path_column}' not found in {input_path}. Columns: {list(df.columns)}")
    return df
