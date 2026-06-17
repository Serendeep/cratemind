# Security policy

## Supported versions

cratemind ships from the latest [GitHub release](https://github.com/Serendeep/cratemind/releases),
and `cratemind update` keeps installs on it. Fixes land on the latest release only.
If you're on an older version, update before reporting.

## Reporting a vulnerability

Please don't open a public issue for a security problem.

Use GitHub's private reporting: go to the repo's **Security** tab and choose
**Report a vulnerability**. That opens a private advisory only the maintainer can see.

When you report, include:

- What the issue is and where in the code (file/path).
- How to reproduce it, with a minimal example if you can.
- The impact you expect, and any version or OS details.

You'll get an acknowledgement, and once there's a fix it ships in the next release with
credit if you'd like it.

## Scope notes

cratemind runs locally and analyzes audio on your own machine. It shells out to external
tools (spotdl, ffmpeg) and can make optional network calls (a Spotify playlist fetch, an
opt-in Deezer genre lookup that sends only a track name, and the genre-model/ffmpeg
downloads). Reports about how cratemind handles those boundaries, untrusted file input,
or its subprocess calls are in scope.
