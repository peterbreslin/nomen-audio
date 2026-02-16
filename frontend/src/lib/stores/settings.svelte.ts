import type { AppSettings } from '$lib/types';
import { fetchSettings, updateSettings } from '$lib/api/client';

class SettingsStore {
	settings = $state<AppSettings | null>(null);
	loading = $state(false);

	async loadSettings() {
		this.loading = true;
		try {
			this.settings = await fetchSettings();
		} finally {
			this.loading = false;
		}
	}

	async saveSettings(updates: Partial<AppSettings>) {
		this.settings = await updateSettings(updates);
	}
}

export const settingsStore = new SettingsStore();
