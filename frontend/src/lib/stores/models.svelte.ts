import type { ModelsStatus } from '$lib/types';
import { fetchModelsStatus } from '$lib/api/client';

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

	private _timer: ReturnType<typeof setInterval> | null = null;

	async poll() {
		// Fetch immediately, then every 2s until ready
		await this._fetchStatus();
		if (this.isReady) return;

		this._timer = setInterval(async () => {
			await this._fetchStatus();
			if (this.isReady) this.stopPolling();
		}, 2000);
	}

	stopPolling() {
		if (this._timer) {
			clearInterval(this._timer);
			this._timer = null;
		}
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
