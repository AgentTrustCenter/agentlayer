declare global {
  interface Window {
    ethereum?: {
      request: (input: { method: string; params?: unknown[] }) => Promise<unknown>;
    };
    solana?: {
      isPhantom?: boolean;
      connect: () => Promise<{ publicKey: { toString: () => string } }>;
      signMessage: (message: Uint8Array, encoding: "utf8") => Promise<{ signature: Uint8Array }>;
    };
  }
}

function uint8ToBase64(bytes: Uint8Array): string {
  let binary = "";
  bytes.forEach((byte) => {
    binary += String.fromCharCode(byte);
  });
  return window.btoa(binary);
}

export async function signEvmMessage(message: string) {
  if (!window.ethereum) {
    throw new Error("No EVM wallet detected. Install MetaMask or another injected wallet.");
  }
  const accounts = (await window.ethereum.request({ method: "eth_requestAccounts" })) as string[];
  const address = accounts?.[0];
  if (!address) {
    throw new Error("No EVM account returned by the wallet.");
  }
  const signature = (await window.ethereum.request({
    method: "personal_sign",
    params: [message, address],
  })) as string;
  return { address, signature };
}

export async function connectEvmWallet() {
  if (!window.ethereum) {
    throw new Error("No EVM wallet detected. Install MetaMask or another injected wallet.");
  }
  const accounts = (await window.ethereum.request({ method: "eth_requestAccounts" })) as string[];
  const address = accounts?.[0];
  if (!address) {
    throw new Error("No EVM account returned by the wallet.");
  }
  return { address };
}

export async function signSolanaMessage(message: string) {
  if (!window.solana?.signMessage || !window.solana?.connect) {
    throw new Error("No Solana wallet detected. Install Phantom or another injected wallet.");
  }
  const connection = await window.solana.connect();
  const encoded = new TextEncoder().encode(message);
  const signed = await window.solana.signMessage(encoded, "utf8");
  return {
    address: connection.publicKey.toString(),
    signature: uint8ToBase64(signed.signature),
  };
}

export async function connectSolanaWallet() {
  if (!window.solana?.connect) {
    throw new Error("No Solana wallet detected. Install Phantom or another injected wallet.");
  }
  const connection = await window.solana.connect();
  return { address: connection.publicKey.toString() };
}
