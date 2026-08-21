# Container for the report/analysis side and for reproducible CI bring-up.
# The core has zero runtime dependencies, so this image is tiny. Live microphone
# capture needs host audio device passthrough and the [live] extra; for that, run
# on the Pi host directly (see deploy/olive-monitor.service) rather than in a container.
#
# Base pinned by digest (REL-18): Renovate (renovate.json) tracks the `3.12-slim`
# tag and opens a PR to bump the digest on updates, same mechanism as the
# Actions SHA-pins in .github/workflows/ci.yml. Digest resolved 2026-07-05 via
# the registry API for `python:3.12-slim`.
FROM python:3.12-slim@sha256:423ed6ab25b1921a477529254bfeeabf5855151dc2c3141699a1bfc852199fbf AS base

# Apply Debian security updates on top of the pinned digest.
#
# The digest pin gives a reproducible base, but it also freezes the package set
# at whatever the upstream image was built with. CVE-2026-53615 (integer
# overflow in util-linux libblkid) is fixed in Debian's 2.41.5-0+deb13u1, and
# that package is available from the security suite today, but the upstream
# python:*-slim image has not been rebuilt since. Without this step the image
# ships the vulnerable 2.41-5 no matter how recently the digest was bumped, and
# the container CVE scan fails on a finding a rebase cannot clear.
RUN apt-get update \
 && apt-get upgrade -y --no-install-recommends \
 && apt-get clean \
 && rm -rf /var/lib/apt/lists/*


WORKDIR /app
COPY pyproject.toml README.md ./
COPY monitor ./monitor
COPY store ./store
COPY report ./report
COPY scripts ./scripts

RUN pip install --no-cache-dir . \
    && useradd --create-home --uid 10001 olive
USER olive

# Liveness proxy for a one-shot CLI image (REL-18): confirms the installed
# console script still resolves and runs without touching mounted data.
HEALTHCHECK CMD ["olive-report", "--help"]

# Default: print CLI help. Override to generate a report from a mounted event log, e.g.
#   docker run -v "$PWD:/data" olive olive-report --db /data/olive.db --out /data/report.html
ENTRYPOINT ["olive-report"]
CMD ["--help"]
