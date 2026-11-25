"""Busca os dados públicos do perfil na API GraphQL do GitHub e grava data/stats.json.

Precisa de um token em GH_TOKEN ou GITHUB_TOKEN (no Actions o GITHUB_TOKEN padrão basta).
Localmente:  $env:GH_TOKEN = (gh auth token); python scripts/fetch_stats.py
"""
import json
import os
import urllib.request
from collections import Counter
from pathlib import Path

LOGIN = os.environ.get("PROFILE_LOGIN", "josevictoremiliano")
ROOT = Path(__file__).resolve().parent.parent

QUERY = """
query($login: String!) {
  user(login: $login) {
    followers { totalCount }
    contributionsCollection {
      contributionCalendar {
        totalContributions
        weeks { contributionDays { date contributionCount } }
      }
    }
    repositories(ownerAffiliations: OWNER, privacy: PUBLIC, isFork: false, first: 100) {
      totalCount
      nodes {
        stargazerCount
        languages(first: 6, orderBy: {field: SIZE, direction: DESC}) {
          edges { size node { name color } }
        }
      }
    }
  }
}
"""


def graphql(token: str) -> dict:
    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=json.dumps({"query": QUERY, "variables": {"login": LOGIN}}).encode(),
        headers={"Authorization": f"bearer {token}", "Content-Type": "application/json", "User-Agent": "profile-cards"},
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        body = json.load(r)
    if "errors" in body:
        raise SystemExit(body["errors"])
    return body["data"]["user"]


def main() -> None:
    token = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
    if not token:
        raise SystemExit("Defina GH_TOKEN ou GITHUB_TOKEN")
    user = graphql(token)
    cal = user["contributionsCollection"]["contributionCalendar"]
    days = [[d["date"], d["contributionCount"]] for w in cal["weeks"] for d in w["contributionDays"]]

    langs: Counter = Counter()
    colors = {}
    for repo in user["repositories"]["nodes"]:
        for e in repo["languages"]["edges"]:
            langs[e["node"]["name"]] += e["size"]
            colors[e["node"]["name"]] = e["node"]["color"] or "#8f8f8f"
    total = sum(langs.values()) or 1
    top = [{"name": n, "color": colors[n], "pct": round(s / total * 100, 1)} for n, s in langs.most_common(5)]

    stats = {
        "login": LOGIN,
        "total": cal["totalContributions"],
        "days": days,
        "repos": user["repositories"]["totalCount"],
        "stars": sum(r["stargazerCount"] for r in user["repositories"]["nodes"]),
        "followers": user["followers"]["totalCount"],
        "languages": top,
    }
    out = ROOT / "data" / "stats.json"
    out.parent.mkdir(exist_ok=True)
    out.write_text(json.dumps(stats, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"{out}: {stats['total']} contribuições, {stats['repos']} repos")


if __name__ == "__main__":
    main()
