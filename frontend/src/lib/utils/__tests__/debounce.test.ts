import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { debounce } from '../debounce';

describe('debounce', () => {
	beforeEach(() => vi.useFakeTimers());
	afterEach(() => vi.useRealTimers());

	it('delays execution', () => {
		const fn = vi.fn();
		const debounced = debounce(fn, 100);

		debounced();
		expect(fn).not.toHaveBeenCalled();

		vi.advanceTimersByTime(100);
		expect(fn).toHaveBeenCalledOnce();
	});

	it('resets timer on repeated calls', () => {
		const fn = vi.fn();
		const debounced = debounce(fn, 100);

		debounced();
		vi.advanceTimersByTime(50);
		debounced();
		vi.advanceTimersByTime(50);
		expect(fn).not.toHaveBeenCalled();

		vi.advanceTimersByTime(50);
		expect(fn).toHaveBeenCalledOnce();
	});

	it('passes arguments to the original function', () => {
		const fn = vi.fn();
		const debounced = debounce(fn, 100);

		debounced('a', 'b');
		vi.advanceTimersByTime(100);
		expect(fn).toHaveBeenCalledWith('a', 'b');
	});

	it('cancel prevents pending invocation', () => {
		const fn = vi.fn();
		const debounced = debounce(fn, 100);

		debounced();
		debounced.cancel();
		vi.advanceTimersByTime(200);
		expect(fn).not.toHaveBeenCalled();
	});
});
