const textEncoder = new TextEncoder();

function arrayBufferToBase64(buffer: ArrayBuffer): string {
  const bytes = new Uint8Array(buffer);
  let binary = "";
  bytes.forEach((byte) => {
    binary += String.fromCharCode(byte);
  });
  return window.btoa(binary);
}

function base64ToArrayBuffer(base64: string): ArrayBuffer {
  const binary = window.atob(base64);
  const bytes = new Uint8Array(binary.length);
  for (let index = 0; index < binary.length; index += 1) {
    bytes[index] = binary.charCodeAt(index);
  }
  return bytes.buffer;
}

function wrapPem(label: string, base64: string): string {
  const chunks = base64.match(/.{1,64}/g) || [];
  return [`-----BEGIN ${label}-----`, ...chunks, `-----END ${label}-----`].join("\n");
}

function unwrapPem(pem: string): string {
  return pem.replace(/-----BEGIN [^-]+-----/g, "").replace(/-----END [^-]+-----/g, "").replace(/\s+/g, "");
}

function sortValue(value: unknown): unknown {
  if (Array.isArray(value)) {
    return value.map(sortValue);
  }
  if (value && typeof value === "object") {
    return Object.fromEntries(
      Object.entries(value as Record<string, unknown>)
        .sort(([left], [right]) => left.localeCompare(right))
        .map(([key, nested]) => [key, sortValue(nested)]),
    );
  }
  return value;
}

export function stableStringify(value: unknown): string {
  return JSON.stringify(sortValue(value));
}

export async function generateIdentity() {
  const keyPair = await crypto.subtle.generateKey(
    {
      name: "ECDSA",
      namedCurve: "P-256",
    },
    true,
    ["sign", "verify"],
  );

  const privateKey = await crypto.subtle.exportKey("pkcs8", keyPair.privateKey);
  const publicKey = await crypto.subtle.exportKey("spki", keyPair.publicKey);

  return {
    privateKeyPem: wrapPem("PRIVATE KEY", arrayBufferToBase64(privateKey)),
    publicKeyPem: wrapPem("PUBLIC KEY", arrayBufferToBase64(publicKey)),
  };
}

export async function importPrivateKey(privateKeyPem: string): Promise<CryptoKey> {
  const keyBuffer = base64ToArrayBuffer(unwrapPem(privateKeyPem));
  return crypto.subtle.importKey(
    "pkcs8",
    keyBuffer,
    {
      name: "ECDSA",
      namedCurve: "P-256",
    },
    false,
    ["sign"],
  );
}

export async function signPayload(privateKeyPem: string, payload: unknown): Promise<string> {
  const privateKey = await importPrivateKey(privateKeyPem);
  const signature = await crypto.subtle.sign(
    {
      name: "ECDSA",
      hash: "SHA-256",
    },
    privateKey,
    textEncoder.encode(stableStringify(payload)),
  );
  return arrayBufferToBase64(signature);
}

export async function fingerprintPublicKeyPem(publicKeyPem: string): Promise<string> {
  const bytes = textEncoder.encode(publicKeyPem);
  const digest = await crypto.subtle.digest("SHA-256", bytes);
  const hex = Array.from(new Uint8Array(digest))
    .map((byte) => byte.toString(16).padStart(2, "0"))
    .join("");
  return `sha256:${hex}`;
}
