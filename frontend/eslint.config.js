import js from '@eslint/js';
import ts from 'typescript-eslint';
import svelte from 'eslint-plugin-svelte';

export default ts.config(
	js.configs.recommended,
	...ts.configs.recommended,
	...svelte.configs['flat/recommended'],
	{
		files: ['**/*.svelte', '**/*.svelte.ts'],
		languageOptions: {
			globals: {
				clearInterval: 'readonly',
				document: 'readonly',
				DragEvent: 'readonly',
				Event: 'readonly',
				HTMLDivElement: 'readonly',
				HTMLElement: 'readonly',
				HTMLInputElement: 'readonly',
				HTMLTextAreaElement: 'readonly',
				Node: 'readonly',
				PointerEvent: 'readonly',
				KeyboardEvent: 'readonly',
				MouseEvent: 'readonly',
				requestAnimationFrame: 'readonly',
				setInterval: 'readonly',
				window: 'readonly'
			},
			parserOptions: {
				parser: ts.parser
			}
		}
	},
	{
		rules: {
			'@typescript-eslint/no-unused-vars': ['warn', { argsIgnorePattern: '^_' }],
			'@typescript-eslint/no-explicit-any': 'off',
			'svelte/prefer-svelte-reactivity': 'off'
		}
	},
	{
		ignores: [
			'.svelte-kit/',
			'build/',
			'node_modules/',
			'src-tauri/',
			'src/lib/components/ui/',
			'*.config.*'
		]
	}
);
