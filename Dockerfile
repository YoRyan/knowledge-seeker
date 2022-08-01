# first stage
FROM python:3 as builder
# Add a proper server for production.
RUN pip install --user --no-cache-dir waitress
# Build the app.
WORKDIR /code
COPY . .
RUN pip install --user --no-cache-dir --no-warn-script-location .

# second stage
FROM python:3-slim
# Add ffmpeg.
RUN apt-get update && apt-get install -y --no-install-recommends \
  ffmpeg
RUN groupadd -r ks && useradd --no-log-init -r -g ks ks
USER ks
COPY --from=builder --chown=ks:ks /root/.local/ /home/ks/.local/
ENV PATH=/home/ks/.local/bin/:$PATH
EXPOSE 8080
ENTRYPOINT ["waitress-serve", "--call", "knowledgeseeker:create_app"]
VOLUME /home/ks/.local/var/knowledgeseeker-instance