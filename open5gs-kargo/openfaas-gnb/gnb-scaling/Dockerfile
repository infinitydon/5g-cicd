FROM openfaas/of-watchdog:0.8.4 as watchdog
FROM python:3.9-slim-buster

COPY --from=watchdog /fwatchdog /usr/bin/fwatchdog
RUN chmod +x /usr/bin/fwatchdog

WORKDIR /home/app/

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY handler.py .

ENV fprocess="python handler.py"
ENV mode="http"
ENV upstream_url="http://127.0.0.1:8080"

HEALTHCHECK --interval=3s CMD [ -e /tmp/.lock ] || exit 1

CMD ["fwatchdog"]