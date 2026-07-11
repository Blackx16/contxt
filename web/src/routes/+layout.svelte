<script lang="ts">
	import '../app.css';
	import favicon from '$lib/assets/favicon.svg';
	import { page } from '$app/state';

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
		<a class="brand" href="/">
			<svg class="brand-mark" viewBox="0 0 32 32" aria-hidden="true">
				<path d="M4 4 H28 V28 H4 Z M28 4 L4 28" fill="none" stroke="currentColor" stroke-width="2.4" />
			</svg>
			<span class="wordmark">CONTXT</span>
		</a>
		<nav>
			{#each nav as item (item.href)}
				<a
					class="nav-link"
					class:active={page.url.pathname.startsWith(item.href)}
					href={item.href}>{item.label}</a
				>
			{/each}
		</nav>
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
