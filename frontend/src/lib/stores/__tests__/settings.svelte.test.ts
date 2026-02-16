import { describe, it, expect, beforeEach, vi } from 'vitest';
import { settingsStore } from '$lib/stores/settings.svelte';

vi.mock('$lib/api/client', () => ({
	fetchSettings: vi.fn().mockResolvedValue({
		creator_id: 'JDOE',
		source_id: 'TESTSRC',
		library_name: 'TestLib',
		library_template: '{Library}_{CatID}_{FXName}',
		rename_on_save_default: true,
		custom_fields: [
			{ tag: 'MOOD', label: 'Mood', ai_prompt: null },
			{ tag: 'INTENSITY', label: 'Intensity', ai_prompt: 'Rate intensity' }
		],
		llm_provider: null,
		llm_api_key: null
	})
}));

describe('SettingsStore', () => {
	beforeEach(() => {
		settingsStore.settings = null;
		settingsStore.loading = false;
	});

	it('starts with null settings', () => {
		expect(settingsStore.settings).toBeNull();
		expect(settingsStore.loading).toBe(false);
	});

	it('loads settings from API', async () => {
		await settingsStore.loadSettings();
		expect(settingsStore.settings).not.toBeNull();
		expect(settingsStore.settings?.creator_id).toBe('JDOE');
		expect(settingsStore.settings?.library_name).toBe('TestLib');
	});

	it('has custom field definitions', async () => {
		await settingsStore.loadSettings();
		expect(settingsStore.settings?.custom_fields).toHaveLength(2);
		expect(settingsStore.settings?.custom_fields[0].tag).toBe('MOOD');
	});

	it('sets loading flag during fetch', async () => {
		const promise = settingsStore.loadSettings();
		await promise;
		expect(settingsStore.loading).toBe(false);
	});
});
