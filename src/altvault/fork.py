import asyncio
from typing import Literal, NamedTuple

from githubkit.versions.latest.models import MinimalRepository

from altvault.helpers.config import config
from altvault.helpers.github import create_github_client

github_client = create_github_client()
CONCURRENCY_LIMIT: int = 5

RESET = "\x1b[0m"
GRAY = "\x1b[0;38;5;244;49m"
RED = "\x1b[0;31;49m"
YELLOW = "\x1b[0;33;49m"
PINK = "\x1b[0;35;49m"


class CheckResult(NamedTuple):
    url: str
    status: Literal["diverged", "ahead", "behind", "identical"]
    behind_by: int
    ahead_by: int


async def check_behind(minimal_repo: MinimalRepository, sem: asyncio.Semaphore):
    async with sem:
        repo = (
            await github_client.rest.repos.async_get(
                owner=minimal_repo.owner.login, repo=minimal_repo.name
            )
        ).parsed_data
        print(f"{GRAY}.{RESET}", end="", flush=True)
        parent = repo.parent
        if parent:
            base = f"{parent.owner.login}:{parent.default_branch}"
            head = f"{repo.owner.login}:{repo.default_branch}"
            compared = (
                await github_client.rest.repos.async_compare_commits(
                    owner=repo.owner.login, repo=repo.name, basehead=f"{base}...{head}"
                )
            ).parsed_data

            print(f"{GRAY}.{RESET}", end="", flush=True)
            return CheckResult(
                url=repo.html_url,
                status=compared.status,
                behind_by=compared.behind_by,
                ahead_by=compared.ahead_by,
            )


async def amain():
    forks = [
        repo
        async for repo in github_client.rest.paginate(
            github_client.rest.repos.async_list_for_org,
            org=config.owner,
            type="forks",
            per_page=100,
        )
    ]
    print(GRAY, len(forks), "forks", RESET)

    sem = asyncio.Semaphore(CONCURRENCY_LIMIT)
    tasks = [check_behind(repo, sem) for repo in forks]
    results = await asyncio.gather(*tasks)

    print()
    results.sort(key=lambda x: (x.status, x.url))
    for item in results:
        match item.status:
            case "identical":
                print(GRAY, item.status, item.url, RESET)
            case "behind":
                print(RED, item.status, item.behind_by, item.url, RESET)
            case "ahead":
                print(YELLOW, item.status, item.ahead_by, item.url, RESET)
            case "diverged":
                print(PINK, item.status, item.url, RESET)


def main():
    asyncio.run(amain())


if __name__ == "__main__":
    main()
