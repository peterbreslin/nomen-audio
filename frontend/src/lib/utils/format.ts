/** Format a duration in seconds to "MM:SS.s" */
export function formatDuration(seconds: number): string {
	const totalTenths = Math.round(seconds * 10);
	const mins = Math.floor(totalTenths / 600);
	const secs = Math.floor((totalTenths % 600) / 10);
	const tenths = totalTenths % 10;
	return `${String(mins).padStart(2, '0')}:${String(secs).padStart(2, '0')}.${tenths}`;
}

/** Format file size in bytes to human-readable string */
export function formatFileSize(bytes: number): string {
	if (bytes < 1024) return `${bytes} B`;
	const kb = bytes / 1024;
	if (kb < 1024) return `${kb.toFixed(1)} KB`;
	const mb = kb / 1024;
	if (mb < 1024) return `${mb.toFixed(1)} MB`;
	const gb = mb / 1024;
	return `${gb.toFixed(1)} GB`;
}

/** Format sample rate in Hz to "48 kHz" style */
export function formatSampleRate(hz: number): string {
	return `${(hz / 1000).toFixed(hz % 1000 === 0 ? 0 : 1)} kHz`;
}
