<script lang="ts">
	import '../app.css';
	import favicon from '$lib/assets/favicon.svg';
	import { page } from '$app/state';
	import { base } from '$app/paths';
	import { demo, setDemo } from '$lib/demo.svelte';

	let { children } = $props();

	const nav = [
		{ href: '/onboarding', label: 'Connect' },
		{ href: '/viewer', label: 'Context' },
		{ href: '/multi-device', label: 'Devices' }
	];
</script>

<svelte:head>
	<link rel="icon" href={favicon} />
	<title>Contxt</title>
</svelte:head>

<header class="site-header">
	<div class="container bar">
		<a class="brand" href="{base}/">
			<svg class="brand-mark" viewBox="0 0 32 32" aria-hidden="true">
				<path d="M20 6 H6 V26 H26 V20 M26 6 L6 26" fill="none" stroke="currentColor"
					stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round" />
			</svg>
			<span class="wordmark">CONTXT</span>
		</a>
		<div class="right">
			<nav>
				{#each nav as item (item.href)}
					<a
						class="nav-link"
						class:active={page.url.pathname.startsWith(base + item.href)}
						href="{base}{item.href}">{item.label}</a
					>
				{/each}
			</nav>
			<button
				class="demo-toggle"
				onclick={() => setDemo(!demo.on)}
				aria-pressed={demo.on}
				title={demo.on
					? 'Demo mode ON — showing the built-in demo. Turn off to use your installed extension.'
					: 'Live mode — reading your context from the Contxt extension. Turn on for the demo.'}
			>
				<span class="dt-label">{demo.on ? 'Demo' : 'Live'}</span>
				<span class="dt-switch" class:on={demo.on}><span class="dt-knob"></span></span>
			</button>
		</div>
	</div>
</header>

<main class="container">
	{@render children()}
</main>

<footer class="site-footer">
	<div class="container foot-inner">
		<span class="wordmark small">CONTXT</span>
		<span class="mono foot-note">AMD Developer Hackathon ACT II — your private data stays yours</span>
	</div>
</footer>

<style>
	.site-header {
		border-bottom: 1px solid var(--rule);
		background: var(--lacquer);
		position: sticky;
		top: 0;
		z-index: 10;
	}
	.bar {
		display: flex;
		align-items: center;
		justify-content: space-between;
		height: 66px;
	}
	.brand {
		display: flex;
		align-items: center;
		gap: 11px;
		color: var(--champagne);
	}
	.brand-mark {
		width: 20px;
		height: 20px;
		color: var(--gold);
	}
	.wordmark {
		font-family: var(--font-display);
		font-weight: 400;
		font-size: 1.3rem;
		letter-spacing: 0.15em;
		color: var(--champagne);
	}
	nav {
		display: flex;
		gap: 4px;
	}
	.nav-link {
		padding: 8px 14px;
		border-radius: var(--r-xs);
		color: var(--text-muted);
		font-size: 0.92rem;
		font-weight: 500;
	}
	.nav-link:hover {
		color: var(--gold);
	}
	.nav-link.active {
		color: var(--champagne);
		box-shadow: inset 0 -2px 0 var(--gold);
	}
	.right {
		display: flex;
		align-items: center;
		gap: 18px;
	}
	.demo-toggle {
		display: inline-flex;
		align-items: center;
		gap: 8px;
		background: transparent;
		border: 1px solid var(--rule);
		border-radius: var(--r-pill);
		padding: 5px 10px 5px 13px;
		cursor: pointer;
		color: var(--text-muted);
		font-family: var(--font-mono);
		font-size: 0.66rem;
		letter-spacing: 0.1em;
		text-transform: uppercase;
		transition:
			border-color 0.15s var(--ease),
			color 0.15s var(--ease);
	}
	.demo-toggle:hover {
		border-color: var(--rule-strong);
		color: var(--champagne);
	}
	.dt-switch {
		position: relative;
		width: 30px;
		height: 16px;
		border-radius: var(--r-pill);
		background: var(--graphite-2);
		border: 1px solid var(--rule);
		transition: background 0.15s var(--ease);
	}
	.dt-switch.on {
		background: var(--gold-soft);
		border-color: var(--rule-strong);
	}
	.dt-knob {
		position: absolute;
		top: 1px;
		left: 1px;
		width: 12px;
		height: 12px;
		border-radius: 50%;
		background: var(--text-faint);
		transition:
			transform 0.15s var(--ease),
			background 0.15s var(--ease);
	}
	.dt-switch.on .dt-knob {
		transform: translateX(14px);
		background: var(--gold);
	}
	main {
		padding: 56px 32px 80px;
		min-height: calc(100vh - 66px - 88px);
	}
	.site-footer {
		border-top: 1px solid var(--rule);
		background: var(--lacquer-deep);
	}
	.foot-inner {
		display: flex;
		align-items: center;
		justify-content: space-between;
		gap: 16px;
		padding-top: 26px;
		padding-bottom: 26px;
		flex-wrap: wrap;
	}
	.wordmark.small {
		font-size: 0.95rem;
		letter-spacing: 0.2em;
		color: var(--text-muted);
	}
	.foot-note {
		color: var(--text-faint);
		font-size: 0.72rem;
		letter-spacing: 0.04em;
	}
</style>
