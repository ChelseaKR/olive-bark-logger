# Container for the report/analysis side and for reproducible CI bring-up.
# The core has zero runtime dependencies, so this image is tiny. Live microphone
# capture needs host audio device passthrough and the [live] extra; for that, run
# on the Pi host directly (see deploy/olive-monitor.service) rather than in a container.
FROM python:3.12-slim AS base

WORKDIR /app
COPY pyproject.toml README.md ./
COPY monitor ./monitor
COPY store ./store
COPY report ./report
COPY scripts ./scripts

RUN pip install --no-cache-dir . \
    && useradd --create-home --uid 10001 olive
USER olive

# Default: print CLI help. Override to generate a report from a mounted event log, e.g.
#   docker run -v "$PWD:/data" olive olive-report --db /data/olive.db --out /data/report.html
ENTRYPOINT ["olive-report"]
CMD ["--help"]
