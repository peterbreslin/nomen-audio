import type { ModelsStatus } from '$lib/types';
import { fetchModelsStatus } from '$lib/api/client';

export type LlmRerankState = 'on' | 'off' | 'unreachable';

const FAST_POLL_MS = 2000;
const SLOW_POLL_MS = 5000;

class ModelsStore {
	status = $state<ModelsStatus | null>(null);

	get isReady() {
		return this.status?.embeddings_ready ?? false;
	}

	get isLoading() {
		return this.status?.loading ?? true;
	}

	get statusMessage() {
		return this.status?.status_message ?? 'Initializing...';
	}

	get hasError() {
		return !!this.status?.error;
	}

	get llmRerankState(): LlmRerankState {
		const s = this.status;
		if (!s || !s.llm_rerank_enabled) return 'off';
		return s.llm_provider_reachable ? 'on' : 'unreachable';
	}

	private _timer: ReturnType<typeof setInterval> | null = null;
	private _currentInterval = 0;

	async poll() {
		await this._fetchStatus();
		this._scheduleNext();
	}

	stopPolling() {
		if (this._timer) {
			clearInterval(this._timer);
			this._timer = null;
		}
		this._currentInterval = 0;
	}

	private _scheduleNext() {
		const desired = this.isReady ? SLOW_POLL_MS : FAST_POLL_MS;
		if (this._timer && this._currentInterval === desired) return;
		if (this._timer) clearInterval(this._timer);
		this._currentInterval = desired;
		this._timer = setInterval(async () => {
			await this._fetchStatus();
			this._scheduleNext();
		}, desired);
	}

	private async _fetchStatus() {
		try {
			this.status = await fetchModelsStatus();
		} catch {
			// Backend may not be ready yet — keep polling
		}
	}
}

export const modelsStore = new ModelsStore();
