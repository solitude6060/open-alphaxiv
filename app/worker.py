from __future__ import annotations

import time


def main() -> None:
    print("open-alphaxiv worker ready; MVP1 ingestion is synchronous in the API")
    while True:
        time.sleep(30)


if __name__ == "__main__":
    main()

