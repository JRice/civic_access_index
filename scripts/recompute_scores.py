from app.workers.tasks.score import recompute_scores


def main() -> None:
    print(recompute_scores())


if __name__ == "__main__":
    main()

