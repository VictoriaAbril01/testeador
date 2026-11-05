"""Start the single-purpose RQ worker. Private targets require explicit worker settings."""

import os

from redis import Redis
from rq import Worker


def main() -> None:
    connection = Redis.from_url(os.getenv("REDIS_URL", "redis://redis:6379/0"))
    Worker(["testlab"], connection=connection).work()


if __name__ == "__main__":
    main()
