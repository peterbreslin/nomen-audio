import { sidecarFetch } from './sidecar';

export async function waitForBackend(timeoutMs = 30000, intervalMs = 200): Promise<void> {
	const deadline = Date.now() + timeoutMs;
	while (Date.now() < deadline) {
		try {
			const res = await sidecarFetch('/health');
			if (res.ok) return;
		} catch {
			// Backend not ready yet — retry
		}
		await new Promise((r) => setTimeout(r, intervalMs));
	}
	throw new Error('Backend did not start within timeout');
}
