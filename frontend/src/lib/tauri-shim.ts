/**
 * Runtime shim around the `@tauri-apps/*` API surface used by this app.
 *
 * Why: `npm run dev` (plain Vite, no Tauri shell) is the fast iteration loop
 * for UI work. Calling Tauri APIs in a plain browser throws because the
 * `__TAURI_INTERNALS__` bridge is absent. This shim detects Tauri vs browser
 * and provides no-op (or browser-native) fallbacks so the page renders and
 * basic flows proceed far enough to verify styling.
 *
 * The Tauri path still uses the real modules; nothing here changes behavior
 * inside `npm run tauri dev`.
 *
 * Extending: to add a new Tauri call site, add a wrapper here that branches on
 * `isTauri()` and import from `$lib/tauri-shim` instead of `@tauri-apps/*`.
 * Example:
 *
 *   export async function showMessage(msg: string): Promise<void> {
 *     if (isTauri()) {
 *       const { message } = await import('@tauri-apps/plugin-dialog');
 *       return message(msg);
 *     }
 *     window.alert(msg);
 *   }
 */

import { invoke as _tauriInvoke } from '@tauri-apps/api/core';
import { getCurrentWebview as _tauriGetCurrentWebview } from '@tauri-apps/api/webview';
import { getCurrentWindow as _tauriGetCurrentWindow } from '@tauri-apps/api/window';
import { open as _tauriOpen } from '@tauri-apps/plugin-dialog';
import { fetch as _tauriFetch } from '@tauri-apps/plugin-http';
import type {
	OpenDialogOptions,
	OpenDialogReturn
} from '@tauri-apps/plugin-dialog';
import type { Webview } from '@tauri-apps/api/webview';
import type { Window } from '@tauri-apps/api/window';

/** True when running inside a Tauri webview. */
export function isTauri(): boolean {
	return typeof window !== 'undefined' && '__TAURI_INTERNALS__' in window;
}

// ---------------------------------------------------------------------------
// open() — folder/file picker
// ---------------------------------------------------------------------------

export async function open<T extends OpenDialogOptions>(
	options?: T
): Promise<OpenDialogReturn<T>> {
	if (isTauri()) {
		return _tauriOpen(options);
	}
	return _browserOpen(options) as Promise<OpenDialogReturn<T>>;
}

function _browserOpen(options?: OpenDialogOptions): Promise<string | string[] | null> {
	return new Promise((resolve) => {
		const input = document.createElement('input');
		input.type = 'file';
		input.style.display = 'none';

		if (options?.directory) {
			// Non-standard but widely supported in Chromium-based browsers.
			(input as HTMLInputElement & { webkitdirectory: boolean }).webkitdirectory = true;
		}
		if (options?.multiple) {
			input.multiple = true;
		}
		if (options?.filters && options.filters.length > 0) {
			const exts = options.filters.flatMap((f) => f.extensions.map((e) => `.${e}`));
			input.accept = exts.join(',');
		}

		let settled = false;
		const cleanup = () => {
			input.remove();
			window.removeEventListener('focus', onFocus);
		};

		input.addEventListener('change', () => {
			settled = true;
			const files = Array.from(input.files ?? []);
			if (files.length === 0) {
				cleanup();
				resolve(null);
				return;
			}

			if (options?.directory) {
				// Browsers don't expose absolute paths. Derive a synthetic folder
				// "path" from the first file's webkitRelativePath. The backend
				// won't be able to open this; that's expected in browser dev mode.
				const rel =
					(files[0] as File & { webkitRelativePath?: string }).webkitRelativePath ??
					files[0].name;
				const folder = rel.split('/')[0] || files[0].name;
				cleanup();
				resolve(options.multiple ? [folder] : folder);
				return;
			}

			const paths = files.map((f) => f.name);
			cleanup();
			resolve(options?.multiple ? paths : paths[0]);
		});

		// User cancelling a native file dialog fires no event in most browsers.
		// Detect it via window focus returning without a `change`.
		const onFocus = () => {
			setTimeout(() => {
				if (settled) return;
				if ((input.files?.length ?? 0) === 0) {
					settled = true;
					cleanup();
					resolve(null);
				}
			}, 300);
		};
		window.addEventListener('focus', onFocus, { once: true });

		document.body.appendChild(input);
		input.click();
	});
}

// ---------------------------------------------------------------------------
// getCurrentWebview / getCurrentWindow — no-op stubs in browser mode
// ---------------------------------------------------------------------------

type UnlistenFn = () => void;
const _noopUnlisten: UnlistenFn = () => {};

/** Minimal subset of the Webview API the app actually uses. */
type WebviewLike = Pick<Webview, 'onDragDropEvent'>;
/** Minimal subset of the Window API the app actually uses. */
type WindowLike = Pick<Window, 'onCloseRequested' | 'destroy'>;

export function getCurrentWebview(): WebviewLike {
	if (isTauri()) {
		return _tauriGetCurrentWebview();
	}
	return {
		onDragDropEvent: async () => _noopUnlisten
	} as WebviewLike;
}

export function getCurrentWindow(): WindowLike {
	if (isTauri()) {
		return _tauriGetCurrentWindow();
	}
	return {
		onCloseRequested: async () => _noopUnlisten,
		destroy: async () => {}
	} as WindowLike;
}

// ---------------------------------------------------------------------------
// invoke — Rust command bridge
// ---------------------------------------------------------------------------

export async function invoke<T>(cmd: string, args?: Record<string, unknown>): Promise<T> {
	if (isTauri()) {
		return _tauriInvoke<T>(cmd, args);
	}
	// Browser-mode fallbacks for the small set of commands the app calls.
	if (cmd === 'get_sidecar_port') {
		const fromEnv = import.meta.env.VITE_SIDECAR_PORT;
		return Number(fromEnv ?? 8000) as unknown as T;
	}
	throw new Error(`invoke('${cmd}') is not supported in browser mode`);
}

// ---------------------------------------------------------------------------
// fetch — HTTP requests
// ---------------------------------------------------------------------------

/**
 * In Tauri builds, routes through `@tauri-apps/plugin-http` (WebView2's fetch
 * was stalling — see state/decisions.md Phase 5). In browser dev mode, falls
 * back to native fetch.
 */
export const fetch: typeof globalThis.fetch = (input, init) => {
	if (isTauri()) {
		return _tauriFetch(input as RequestInfo, init);
	}
	return globalThis.fetch(input, init);
};
