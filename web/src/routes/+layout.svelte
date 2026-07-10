<script lang="ts">
	import '../app.css';
	import favicon from '$lib/assets/favicon.svg';
	import { page } from '$app/state';

	let { children } = $props();

	const nav = [
		{ href: '/onboarding', label: 'Connect' },
		{ href: '/viewer', label: 'Context' }
	];
</script>

<svelte:head>
	<link rel="icon" href={favicon} />
	<title>Contxt</title>
</svelte:head>

<header class="site-header">
	<div class="container bar">
		<a class="brand" href="/">
			<span class="brand-mark">◆</span>
			<span class="brand-name">Contxt</span>
			<span class="brand-tag">privacy-first context layer</span>
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

<footer class="container site-footer">
	<span
		>Contxt · AMD Developer Hackathon ACT II · two-tier context, your private data stays yours</span
	>
</footer>

<style>
	.site-header {
		border-bottom: 1px solid var(--border);
		background: rgba(10, 11, 15, 0.7);
		backdrop-filter: blur(10px);
		position: sticky;
		top: 0;
		z-index: 10;
	}
	.bar {
		display: flex;
		align-items: center;
		justify-content: space-between;
		height: 62px;
	}
	.brand {
		display: flex;
		align-items: baseline;
		gap: 9px;
		color: var(--text);
	}
	.brand:hover {
		text-decoration: none;
	}
	.brand-mark {
		color: var(--brand);
		font-size: 1.1rem;
	}
	.brand-name {
		font-weight: 700;
		font-size: 1.12rem;
		letter-spacing: -0.02em;
	}
	.brand-tag {
		color: var(--text-faint);
		font-size: 0.8rem;
	}
	@media (max-width: 620px) {
		.brand-tag {
			display: none;
		}
	}
	nav {
		display: flex;
		gap: 6px;
	}
	.nav-link {
		padding: 7px 14px;
		border-radius: 8px;
		color: var(--text-muted);
		font-size: 0.92rem;
		font-weight: 550;
	}
	.nav-link:hover {
		background: var(--surface);
		color: var(--text);
		text-decoration: none;
	}
	.nav-link.active {
		background: var(--brand-soft);
		color: var(--text);
	}
	main {
		padding: 40px 24px 64px;
		min-height: calc(100vh - 62px - 70px);
	}
	.site-footer {
		border-top: 1px solid var(--border);
		padding: 22px 24px;
		color: var(--text-faint);
		font-size: 0.82rem;
	}
</style>
