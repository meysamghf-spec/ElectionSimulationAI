const IPV4 =
  /^(?:25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)(?:\.(?:25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)){3}$/;

function canonicalIp(value: string): string | null {
  if (IPV4.test(value)) return value;
  if (!value.includes(":") || value.includes("%") || value.includes("/")) return null;
  try {
    const hostname = new URL(`http://[${value}]/`).hostname;
    if (hostname.toLowerCase() !== `[${value.toLowerCase()}]`) return null;
    return hostname.slice(1, -1);
  } catch {
    return null;
  }
}

/** Keep a forwarded address only when it is exactly one IP, not a client-supplied chain. */
export function clientAddressFromEdge(header: string | null): string | null {
  if (header == null) return null;
  const value = header.trim();
  if (!value || value.includes(",") || /\s/.test(value)) return null;
  const candidate = value.startsWith("[") && value.endsWith("]") ? value.slice(1, -1) : value;
  return canonicalIp(candidate);
}
