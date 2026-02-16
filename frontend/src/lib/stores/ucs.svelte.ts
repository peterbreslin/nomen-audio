import type { UCSCategory } from '$lib/types';
import { fetchUcsCategories } from '$lib/api/client';

class UCSStore {
	categories = $state<UCSCategory[]>([]);
	loading = $state(false);

	async loadCategories() {
		if (this.categories.length > 0) return;
		this.loading = true;
		try {
			this.categories = await fetchUcsCategories();
		} finally {
			this.loading = false;
		}
	}
}

export const ucsStore = new UCSStore();
