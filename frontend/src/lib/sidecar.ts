import { invoke } from '@tauri-apps/api/core';
import { fetch as tauriFetch } from '@tauri-apps/plugin-http';

let cachedPort: number | null = null;

export async function getSidecarPort(): Promise<number> {
	if (cachedPort !== null) return cachedPort;
	cachedPort = await invoke<number>('get_sidecar_port');
	return cachedPort;
}

export async function sidecarFetch(path: string, init?: RequestInit): Promise<Response> {
	const port = await getSidecarPort();
	return tauriFetch(`http://127.0.0.1:${port}${path}`, init);
}
