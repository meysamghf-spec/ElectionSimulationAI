FROM caddy:2-alpine

# The stock image has no wget or curl. The health check needs one of them.
RUN apk add --no-cache wget

HEALTHCHECK --interval=10s --timeout=3s --start-period=10s --retries=10 \
  CMD wget -q -O /dev/null http://127.0.0.1:2019/config/
