import { describe, it, expect } from 'vitest';
import { formatDuration, formatFileSize, formatSampleRate } from '../format';

describe('formatDuration', () => {
	it('formats zero', () => {
		expect(formatDuration(0)).toBe('00:00.0');
	});

	it('formats seconds with tenths', () => {
		expect(formatDuration(3.75)).toBe('00:03.8');
	});

	it('formats minutes and seconds', () => {
		expect(formatDuration(125.3)).toBe('02:05.3');
	});

	it('pads single-digit minutes', () => {
		expect(formatDuration(61)).toBe('01:01.0');
	});
});

describe('formatFileSize', () => {
	it('formats bytes', () => {
		expect(formatFileSize(500)).toBe('500 B');
	});

	it('formats kilobytes', () => {
		expect(formatFileSize(1536)).toBe('1.5 KB');
	});

	it('formats megabytes', () => {
		expect(formatFileSize(5_242_880)).toBe('5.0 MB');
	});

	it('formats gigabytes', () => {
		expect(formatFileSize(1_073_741_824)).toBe('1.0 GB');
	});
});

describe('formatSampleRate', () => {
	it('formats 48000 Hz', () => {
		expect(formatSampleRate(48000)).toBe('48 kHz');
	});

	it('formats 44100 Hz', () => {
		expect(formatSampleRate(44100)).toBe('44.1 kHz');
	});

	it('formats 96000 Hz', () => {
		expect(formatSampleRate(96000)).toBe('96 kHz');
	});
});
