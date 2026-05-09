import argparse

from app.workers.tasks.ingest import run_source_ingestion


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("source_name")
    args = parser.parse_args()
    result = run_source_ingestion(args.source_name)
    print(result)


if __name__ == "__main__":
    main()

