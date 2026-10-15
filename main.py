import argparse
import yaml

from pipeline import run_ocr


def build_config(args, parser) -> dict:
    config = {}
    if args.config:
        with open(args.config) as f:
            config = yaml.safe_load(f) or {}
    if args.input:
        config["input"] = args.input
    if args.output:
        config["output"] = args.output
    if args.path_column:
        config["path_column"] = args.path_column
    if args.batch_size:
        config["batch_size"] = args.batch_size
    if args.save_text:
        config["save_text"] = True
    if args.num_workers:
        config["num_workers"] = args.num_workers
    if args.save_every:
        config["save_every"] = args.save_every

    for key in ("input", "output"):
        if key not in config:
            parser.error(f"'{key}' must be given via --{key} or the config file")
    return config


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--config", help="YAML config (see ocr_config.yaml); CLI flags override it")
    parser.add_argument("--input", help="CSV with a path column, or a .txt with one path per line")
    parser.add_argument("--output", help="Output CSV path")
    parser.add_argument("--path-column", help="Name of the path column (default: file_path)")
    parser.add_argument("--batch-size", type=int)
    parser.add_argument("--save-text", action="store_true", help="Include the raw OCR text in the output")
    parser.add_argument("--num-workers", type=int, help="Parallel OCR processes (default: 1)")
    parser.add_argument("--save-every", type=int, help="Write the output CSV every N batches (default: 100)")
    args = parser.parse_args()
    run_ocr(build_config(args, parser))


if __name__ == "__main__":
    main()
