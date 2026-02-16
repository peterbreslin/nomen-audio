/**
 * Maps backend error codes to user-friendly messages.
 */

import { ApiError } from '$lib/api/client';

const FRIENDLY_MESSAGES: Record<string, string> = {
	FILE_NOT_FOUND: 'The file could not be found.',
	FILE_READ_ONLY: 'This file is read-only. Try saving to a different location.',
	FILE_LOCKED: 'This file is locked by another program. Close it and try again.',
	FILE_CHANGED: 'This file was modified outside the app. Revert and retry.',
	DISK_FULL: 'Not enough disk space. Free up space and try again.',
	INVALID_WAV: 'This file is not a valid WAV file.',
	VALIDATION_ERROR: 'Invalid input. Please check your values.',
	MODEL_NOT_READY: 'AI models are still loading. Please wait.',
	ANALYSIS_FAILED: 'Analysis failed. Try again.',
	RENAME_CONFLICT: 'A file with that name already exists.',
	WRITE_FAILED: 'Failed to write file. Check permissions and try again.'
};

/** Return a user-friendly message for an error. */
export function friendlyMessage(error: unknown): string {
	if (error instanceof ApiError && error.code) {
		return FRIENDLY_MESSAGES[error.code] ?? error.message;
	}
	if (error instanceof Error) {
		return error.message;
	}
	return 'An unexpected error occurred.';
}
