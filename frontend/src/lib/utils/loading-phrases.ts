export type LoadingContext = 'models' | 'generating' | 'importing';

const PHRASES: Record<LoadingContext, string[]> = {
	models: [
		'Warming up the signal chain...',
		'Calibrating audio classifiers...',
		'Tuning the neural oscillators...',
		'Loading frequency models...',
		'Initializing spectral analysis...',
		'Powering up the listening engine...',
		'Spinning up the audio cortex...',
		'Preparing acoustic fingerprints...'
	],
	generating: [
		'Listening closely...',
		'Decoding spectral signatures...',
		'Classifying sonic textures...',
		'Parsing harmonic content...',
		'Analyzing transient profiles...',
		'Reading the waveforms...',
		'Identifying tonal characteristics...',
		'Processing acoustic features...'
	],
	importing: [
		'Scanning the vault...',
		'Reading waveform headers...',
		'Cataloging audio assets...',
		'Indexing your sound library...',
		'Unpacking metadata...',
		'Surveying the collection...'
	]
};

/** Tracks recently shown indices per context to avoid repetition */
const recentIndices = new Map<LoadingContext, number[]>();
const RECENCY_WINDOW = 3;

export function getPhrase(context: LoadingContext): string {
	const pool = PHRASES[context];
	const recent = recentIndices.get(context) ?? [];

	// Pick a random index not in the recent window
	const available = pool
		.map((_, i) => i)
		.filter((i) => !recent.includes(i));

	// If all exhausted (pool smaller than window), reset
	const candidates = available.length > 0 ? available : pool.map((_, i) => i);
	const idx = candidates[Math.floor(Math.random() * candidates.length)];

	// Update recency tracker
	const next = [...recent, idx].slice(-RECENCY_WINDOW);
	recentIndices.set(context, next);

	return pool[idx];
}
