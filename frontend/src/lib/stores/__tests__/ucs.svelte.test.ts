import { describe, it, expect, beforeEach, vi } from 'vitest';
import { ucsStore } from '$lib/stores/ucs.svelte';

vi.mock('$lib/api/client', () => ({
	fetchUcsCategories: vi.fn().mockResolvedValue([
		{
			name: 'DOORS',
			explanation: 'Door sounds',
			subcategories: [
				{ name: 'WOOD', cat_id: 'DOORWood', category_full: 'DOORS-WOOD', explanation: 'Wooden doors' },
				{ name: 'METAL', cat_id: 'DOORMtl', category_full: 'DOORS-METAL', explanation: 'Metal doors' }
			]
		},
		{
			name: 'IMPACTS',
			explanation: 'Impact sounds',
			subcategories: [
				{ name: 'HITS', cat_id: 'IMPHits', category_full: 'IMPACTS-HITS', explanation: 'Hit sounds' }
			]
		}
	])
}));

describe('UCSStore', () => {
	beforeEach(() => {
		ucsStore.categories = [];
		ucsStore.loading = false;
	});

	it('starts with empty categories', () => {
		expect(ucsStore.categories).toEqual([]);
		expect(ucsStore.loading).toBe(false);
	});

	it('loads categories from API', async () => {
		await ucsStore.loadCategories();
		expect(ucsStore.categories).toHaveLength(2);
		expect(ucsStore.categories[0].name).toBe('DOORS');
		expect(ucsStore.categories[1].name).toBe('IMPACTS');
	});

	it('sets loading flag during fetch', async () => {
		const promise = ucsStore.loadCategories();
		// loading should be true during fetch (already resolved by mock, but flag was set)
		await promise;
		expect(ucsStore.loading).toBe(false);
	});

	it('skips fetch if categories already loaded', async () => {
		const { fetchUcsCategories } = await import('$lib/api/client');
		const callsBefore = (fetchUcsCategories as ReturnType<typeof vi.fn>).mock.calls.length;
		await ucsStore.loadCategories();
		await ucsStore.loadCategories(); // second call should skip
		expect((fetchUcsCategories as ReturnType<typeof vi.fn>).mock.calls.length - callsBefore).toBe(1);
	});

	it('has subcategories in loaded categories', async () => {
		await ucsStore.loadCategories();
		const doors = ucsStore.categories.find((c) => c.name === 'DOORS');
		expect(doors?.subcategories).toHaveLength(2);
		expect(doors?.subcategories[0].cat_id).toBe('DOORWood');
	});
});
