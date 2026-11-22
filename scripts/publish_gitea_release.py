"""Publishes a release on Gitea: creates it (and its tag) or updates it, then uploads its files.

Used by .gitea/workflows/release.yml:
    python3 scripts/publish_gitea_release.py <tag> <commit> <title> <notes file> <prerelease true|false> <file>...
(the files are what build_package.py put in dist/: the integration's zip and its SHA256SUMS)

GitHub's workflow uses the `gh` tool for this; Gitea has no such tool on its runners, so this talks to Gitea's
API directly, with Python's standard library only (so it runs on any runner, with nothing to install).

It reads from the environment, as Gitea's runner sets it:
    GITHUB_SERVER_URL   the Gitea address (Gitea keeps GitHub's variable names, so workflows work on both); must
                        be an https:// address
    GITEA_INTERNAL_URL  optional: Gitea's address as the runner's jobs reach it, used instead when set (a runner
                        next to Gitea often can't reach its public address, ROOT_URL). https:// as well, except
                        that http:// is accepted for an address that can't leave the runner's own network: a
                        loopback or private IP address, or a bare container name such as http://gitea-server:3000
    GITHUB_REPOSITORY   owner/repo on Gitea
    RELEASE_TOKEN       a token that may create releases (the workflow passes the job's own token)

Safe to run again for the same tag: an existing release gets the new title, notes and files, so a release made by
hand on Gitea, or one whose upload failed halfway, ends up complete. Exits non-zero, with the reason, on any error.

The token only ever goes to the address checked above (redirects are refused), and only the release's own files (ASSETS) are uploaded:
anything else named on the command line stops the script before it reads a file or calls Gitea. Gitea's replies
are never printed, since a reply can echo what was sent.
"""

import ipaddress
import json
import os
from pathlib import Path
import sys
import urllib.error
import urllib.parse
import urllib.request
import uuid

# The only files a release may carry, with the type each is uploaded as.
ASSETS = {"nationalgrid.zip": "application/zip", "SHA256SUMS": "text/plain"}


def checked_server(url, name, allow_local_http=False):
    """Return Gitea's address without a trailing slash, or raise ValueError if it isn't a safe place to send the
    token: an absolute https:// address with no user name, password, query or fragment (http:// only when
    `allow_local_http` and the host can't be outside the runner's network)."""
    parsed = urllib.parse.urlsplit(url)
    if not parsed.hostname:
        raise ValueError(f"{name} must be an absolute https:// address")
    if parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise ValueError(f"{name} must not contain a user name, password, query or fragment")
    if parsed.scheme == "http" and allow_local_http and _local_host(parsed.hostname):
        return url.rstrip("/")
    if parsed.scheme != "https":
        raise ValueError(f"{name} must use https://" + (" (or http:// to a local address)" if allow_local_http else ""))
    return url.rstrip("/")


def _local_host(host):
    """True for a loopback or private IP address, localhost, or a bare name with no dots (a container name)."""
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        return "." not in host
    return address.is_loopback or address.is_private


def checked_assets(file_paths):
    """Return the files to upload, or raise ValueError if one isn't a release file or doesn't exist."""
    for file_path in file_paths:
        name = Path(file_path).name
        if name not in ASSETS:
            raise ValueError(f"{name!r} isn't a release file (only {', '.join(ASSETS)})")
        if not Path(file_path).is_file():
            raise ValueError(f"{name} doesn't exist")
    if len({Path(file_path).name for file_path in file_paths}) != len(file_paths):
        raise ValueError("the same file is named twice")
    return file_paths


class _NoRedirects(urllib.request.HTTPRedirectHandler):
    """Refuse redirects: urllib would follow one to any address, with the token still attached."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise urllib.error.HTTPError(req.full_url, code, f"{msg} (redirects aren't followed)", headers, fp)


_OPENER = urllib.request.build_opener(_NoRedirects)


class Gitea:
    """The few calls of Gitea's API a release needs."""

    def __init__(self, server, repository, token):
        """Talk to the repository `repository` on the Gitea at `server`, as the owner of `token`."""
        self.base = f"{server.rstrip('/')}/api/v1/repos/{repository}"
        self.token = token

    def call(self, method, path, body=None, content_type="application/json"):
        """One API call; returns the decoded JSON reply (None when there isn't one).
        Raises urllib.error.HTTPError with Gitea's message on a refusal."""
        if isinstance(body, (dict, list)):
            body = json.dumps(body).encode()
        request = urllib.request.Request(self.base + path, data=body, method=method)
        request.add_header("Authorization", f"token {self.token}")
        request.add_header("Accept", "application/json")
        if body is not None:
            request.add_header("Content-Type", content_type)
        with _OPENER.open(request, timeout=120) as reply:
            data = reply.read()
        return json.loads(data) if data else None

    def release_for(self, tag):
        """The release for a tag, or None if there isn't one yet."""
        try:
            return self.call("GET", f"/releases/tags/{urllib.parse.quote(tag)}")
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return None
            raise

    def upload(self, release_id, file_path):
        """Attaches a file to a release (multipart form, field "attachment", as Gitea's API expects)."""
        boundary = uuid.uuid4().hex
        name = Path(file_path).name
        content_type = ASSETS[name]  # checked_assets() has made sure the name is one of these
        body = (
            (
                f"--{boundary}\r\n"
                f'Content-Disposition: form-data; name="attachment"; filename="{name}"\r\n'
                f"Content-Type: {content_type}\r\n\r\n"
            ).encode()
            + Path(file_path).read_bytes()
            + f"\r\n--{boundary}--\r\n".encode()
        )
        query = urllib.parse.urlencode({"name": name})
        return self.call(
            "POST", f"/releases/{release_id}/assets?{query}", body, f"multipart/form-data; boundary={boundary}"
        )


def publish(gitea, tag, commit, title, notes, prerelease, file_paths):
    """Create or update the release for `tag` (made on `commit` if the tag doesn't exist yet), and make each
    file its only file of that name. Returns the release."""
    fields = {"name": title, "body": notes, "prerelease": prerelease, "draft": False}
    release = gitea.release_for(tag)
    if release is None:
        release = gitea.call("POST", "/releases", {"tag_name": tag, "target_commitish": commit, **fields})
        print(f"Created release {title} ({tag})")
    else:
        release = gitea.call("PATCH", f"/releases/{release['id']}", fields)
        print(f"Updated release {title} ({tag})")
    for file_path in file_paths:
        name = Path(file_path).name
        for asset in release.get("assets") or []:
            if asset["name"] == name:  # replace, rather than end up with two files of the same name
                gitea.call("DELETE", f"/releases/{release['id']}/assets/{asset['id']}")
        gitea.upload(release["id"], file_path)
        print(f"Uploaded {name}")
    return release


def main():
    """Read the arguments and environment, and publish."""
    tag, commit, title, notes_file, prerelease = sys.argv[1:6]
    file_paths = sys.argv[6:]
    if not file_paths:
        sys.exit("Nothing to upload: name the release's files after the pre-release flag")
    missing = [v for v in ("GITHUB_SERVER_URL", "GITHUB_REPOSITORY", "RELEASE_TOKEN") if not os.environ.get(v)]
    if missing:
        sys.exit(f"Not set: {', '.join(missing)}")
    try:
        file_paths = checked_assets(file_paths)
        if os.environ.get("GITEA_INTERNAL_URL"):
            server = checked_server(os.environ["GITEA_INTERNAL_URL"], "GITEA_INTERNAL_URL", allow_local_http=True)
        else:
            server = checked_server(os.environ["GITHUB_SERVER_URL"], "GITHUB_SERVER_URL")
    except ValueError as e:
        sys.exit(f"Not publishing: {e}")
    gitea = Gitea(server, os.environ["GITHUB_REPOSITORY"], os.environ["RELEASE_TOKEN"])
    try:
        publish(gitea, tag, commit, title, Path(notes_file).read_text(), prerelease == "true", file_paths)
    except urllib.error.HTTPError as e:
        # The status and reason only: Gitea's reply body can echo the request back
        sys.exit(f"Gitea refused {urllib.parse.urlsplit(e.url).path}: {e.code} {e.reason}")
    except urllib.error.URLError as e:
        sys.exit(f"Can't reach Gitea at {server}: {e.reason}")


if __name__ == "__main__":
    main()
