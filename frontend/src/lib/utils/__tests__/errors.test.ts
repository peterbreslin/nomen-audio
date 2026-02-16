import { describe, it, expect } from 'vitest';
import { friendlyMessage } from '../errors';
import { ApiError } from '$lib/api/client';

describe('friendlyMessage', () => {
	it('returns friendly message for known error code', () => {
		const err = new ApiError(403, 'raw message', 'FILE_READ_ONLY');
		expect(friendlyMessage(err)).toBe(
			'This file is read-only. Try saving to a different location.'
		);
	});

	it('falls back to raw message for unknown error code', () => {
		const err = new ApiError(500, 'something weird', 'UNKNOWN_CODE');
		expect(friendlyMessage(err)).toBe('something weird');
	});

	it('returns message for ApiError without code', () => {
		const err = new ApiError(500, 'server error');
		expect(friendlyMessage(err)).toBe('server error');
	});

	it('returns message for plain Error', () => {
		expect(friendlyMessage(new Error('oops'))).toBe('oops');
	});

	it('returns fallback for non-Error', () => {
		expect(friendlyMessage('string error')).toBe('An unexpected error occurred.');
		expect(friendlyMessage(null)).toBe('An unexpected error occurred.');
	});

	it('maps all known backend error codes', () => {
		const codes = [
			'FILE_NOT_FOUND',
			'FILE_READ_ONLY',
			'FILE_LOCKED',
			'FILE_CHANGED',
			'DISK_FULL',
			'INVALID_WAV',
			'VALIDATION_ERROR',
			'MODEL_NOT_READY',
			'ANALYSIS_FAILED',
			'RENAME_CONFLICT',
			'WRITE_FAILED'
		];
		for (const code of codes) {
			const err = new ApiError(500, 'raw', code);
			const msg = friendlyMessage(err);
			expect(msg).not.toBe('raw'); // Should map to a friendly message
			expect(msg.length).toBeGreaterThan(5);
		}
	});
});
