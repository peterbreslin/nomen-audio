import { describe, it, expect, beforeEach } from 'vitest';
import { uiStore } from '$lib/stores/ui.svelte';

describe('UIStore', () => {
	beforeEach(() => {
		uiStore.sidebarWidth = 280;
		uiStore.isImporting = false;
		uiStore.isDragOver = false;
	});

	it('has correct defaults', () => {
		expect(uiStore.sidebarWidth).toBe(280);
		expect(uiStore.isImporting).toBe(false);
		expect(uiStore.isDragOver).toBe(false);
	});

	it('tracks importing state', () => {
		uiStore.isImporting = true;
		expect(uiStore.isImporting).toBe(true);
	});

	it('tracks drag-over state', () => {
		uiStore.isDragOver = true;
		expect(uiStore.isDragOver).toBe(true);
	});

	it('updates sidebar width', () => {
		uiStore.sidebarWidth = 350;
		expect(uiStore.sidebarWidth).toBe(350);
	});
});
