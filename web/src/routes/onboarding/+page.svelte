<script lang="ts">
	import { goto } from '$app/navigation';
	import { base } from '$app/paths';
	import { SOURCES, conn, connectSource, disconnectSource, connectedSources } from '$lib/state.svelte';

	const count = $derived(connectedSources().length);
</script>

<section class="head">
	<span class="step eyebrow">Step 1 of 2 · Connect sources</span>
	<h1>Bring your context in.</h1>
	<p class="lede">
		Connect a source and Contxt ingests it, then the Crown-Jewels Gateway sorts each item into
		Private or Shared. Connect at least one to continue — nothing is shared until the Gateway decides
		it's safe.
	</p>
</section>

<div class="sources">
	{#each SOURCES as s (s.id)}
		{@const status = conn[s.id]}
		<div class="source" class:connected={status === 'connected'}>
			<div class="source-icon">{s.icon}</div>
			<div class="source-body">
				<div class="source-title">{s.label}</div>
				<div class="source-blurb">{s.blurb}</div>
			</div>
			<div class="source-action">
				{#if status === 'connected'}
					<span class="done mono">Connected</span>
					<button class="btn ghost" onclick={() => disconnectSource(s.id)}>Disconnect</button>
				{:else if status === 'connecting'}
					<button class="btn" disabled>
						<span class="spinner"></span> Ingesting…
					</button>
				{:else}
					<button class="btn btn-primary" onclick={() => connectSource(s.id)}>Connect</button>
				{/if}
			</div>
		</div>
	{/each}
</div>

<div class="foot">
	<span class="count mono">{count} of {SOURCES.length} connected</span>
	<button class="btn btn-primary" disabled={count === 0} onclick={() => goto(`${base}/viewer`)}>
		Continue to your context →
	</button>
</div>

<style>
	.head {
		max-width: 640px;
		margin-bottom: 36px;
	}
	.step {
		display: block;
		margin-bottom: 16px;
	}
	.lede {
		color: var(--text-muted);
		margin: 20px 0 0;
		font-size: 1.02rem;
		line-height: 1.7;
		max-width: 64ch;
	}
	.sources {
		display: flex;
		flex-direction: column;
		gap: 10px;
	}
	.source {
		display: flex;
		align-items: center;
		gap: 16px;
		background: var(--raised);
		border: 1px solid var(--rule);
		border-radius: var(--r-lg);
		padding: 18px 20px;
		transition: border-color 0.15s var(--ease);
	}
	.source.connected {
		border-color: var(--rule-strong);
	}
	.source-icon {
		font-size: 1.4rem;
		width: 42px;
		height: 42px;
		display: grid;
		place-items: center;
		background: var(--graphite);
		border: 1px solid var(--rule);
		border-radius: var(--r-md);
		flex-shrink: 0;
	}
	.source-body {
		flex: 1;
		min-width: 0;
	}
	.source-title {
		font-weight: 500;
		font-size: 1.05rem;
		color: var(--champagne);
	}
	.source-blurb {
		color: var(--text-muted);
		font-size: 0.86rem;
	}
	.source-action {
		display: flex;
		align-items: center;
		gap: 10px;
		flex-shrink: 0;
	}
	.done {
		color: var(--gold);
		font-size: 0.72rem;
		letter-spacing: 0.12em;
		text-transform: uppercase;
	}
	.btn.ghost {
		background: transparent;
		border-color: var(--rule);
		color: var(--text-muted);
		min-height: 38px;
		padding: 0 14px;
		font-size: 0.85rem;
	}
	.btn.ghost:hover {
		color: var(--vermilion);
		border-color: var(--vermilion);
	}
	.foot {
		display: flex;
		align-items: center;
		justify-content: space-between;
		gap: 16px;
		margin-top: 32px;
		padding-top: 24px;
		border-top: 1px solid var(--rule);
		flex-wrap: wrap;
	}
	.count {
		color: var(--text-muted);
		font-size: 0.78rem;
		letter-spacing: 0.06em;
	}
	.spinner {
		width: 13px;
		height: 13px;
		border: 2px solid var(--graphite-2);
		border-top-color: var(--gold);
		border-radius: 50%;
		display: inline-block;
		animation: spin 0.7s linear infinite;
	}
	@keyframes spin {
		to {
			transform: rotate(360deg);
		}
	}
</style>
