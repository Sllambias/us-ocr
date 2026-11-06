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
    if args.root:
        config["root"] = args.root
    if args.batch_size:
        config["batch_size"] = args.batch_size
    if args.save_text:
        config["save_text"] = True
    if args.num_workers:
        config["num_workers"] = args.num_workers
    if args.threads_per_worker:
        config["threads_per_worker"] = args.threads_per_worker
    if args.save_every:
        config["save_every"] = args.save_every
    if args.num_chunks:
        config["num_chunks"] = args.num_chunks
    # 0 is a valid index, so check for None rather than truthiness
    if args.chunk_index is not None:
        config["chunk_index"] = args.chunk_index

    for key in ("input", "output"):
        if key not in config:
            parser.error(f"'{key}' must be given via --{key} or the config file")
    num_chunks = int(config.get("num_chunks", 1))
    if num_chunks > 1 and "chunk_index" not in config:
        parser.error("--chunk-index must be given with --num-chunks")
    if not 0 <= int(config.get("chunk_index", 0)) < num_chunks:
        parser.error(f"--chunk-index must be from 0 to {num_chunks - 1}, one less than --num-chunks")
    return config


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--config", help="YAML config (see ocr_config.yaml); CLI flags override it")
    parser.add_argument("--input", help="CSV with a path column, or a .txt with one path per line")
    parser.add_argument("--output", help="Output CSV path")
    parser.add_argument("--path-column", help="Name of the path column (default: file_path)")
    parser.add_argument("--root", help="Directory prepended to each path when loading; the output keeps the paths as given")
    parser.add_argument("--batch-size", type=int)
    parser.add_argument("--save-text", action="store_true", help="Include the raw OCR text in the output")
    parser.add_argument("--num-workers", type=int, help="Parallel OCR processes (default: 1)")
    parser.add_argument("--threads-per-worker", type=int, help="Torch CPU threads in each OCR process (default: 1)")
    parser.add_argument("--save-every", type=int, help="Append to the output CSV every N batches (default: 100)")
    parser.add_argument("--num-chunks", type=int, help="Split the input into N chunks, e.g. one per array job (default: 1)")
    parser.add_argument("--chunk-index", type=int, help="Chunk to process, from 0 to N-1, e.g. $SLURM_ARRAY_TASK_ID")
    args = parser.parse_args()
    run_ocr(build_config(args, parser))


if __name__ == "__main__":
    main()
