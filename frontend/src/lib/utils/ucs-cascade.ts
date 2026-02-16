import type { UCSCategory } from '$lib/types';
import { fileStore } from '$lib/stores/files.svelte';

/**
 * Handle UCS category change — cascade subcategory/cat_id/category_full if invalid.
 */
export function cascadeCategory(
	fileId: string,
	newCategory: string,
	categories: UCSCategory[]
): void {
	fileStore.updateFieldLocally(fileId, 'category', newCategory);

	const catObj = categories.find((c) => c.name === newCategory);
	if (!catObj) return;

	const file = fileStore.files.get(fileId);
	if (!file) return;

	const match = catObj.subcategories.find((s) => s.name === file.subcategory);
	if (!match) {
		fileStore.updateFieldLocally(fileId, 'subcategory', null);
		fileStore.updateFieldLocally(fileId, 'cat_id', null);
		fileStore.updateFieldLocally(fileId, 'category_full', null);
	}
}

/**
 * Handle UCS subcategory change — set cat_id + category_full from UCS data.
 */
export function cascadeSubcategory(
	fileId: string,
	newSubcategory: string,
	categories: UCSCategory[]
): void {
	const file = fileStore.files.get(fileId);
	if (!file) return;

	fileStore.updateFieldLocally(fileId, 'subcategory', newSubcategory);

	const catObj = categories.find((c) => c.name === file.category);
	const subObj = catObj?.subcategories.find((s) => s.name === newSubcategory);
	if (subObj) {
		fileStore.updateFieldLocally(fileId, 'cat_id', subObj.cat_id);
		fileStore.updateFieldLocally(fileId, 'category_full', subObj.category_full);
	}
}
