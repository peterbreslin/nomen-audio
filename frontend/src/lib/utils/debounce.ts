export interface DebouncedFn<T extends (...args: any[]) => any> {
	(...args: Parameters<T>): void;
	cancel(): void;
}

/** Returns a debounced version of `fn` that delays invocation by `ms`. */
export function debounce<T extends (...args: any[]) => any>(
	fn: T,
	ms: number
): DebouncedFn<T> {
	let timer: ReturnType<typeof setTimeout>;
	const debounced = (...args: Parameters<T>) => {
		clearTimeout(timer);
		timer = setTimeout(() => fn(...args), ms);
	};
	debounced.cancel = () => clearTimeout(timer);
	return debounced;
}
