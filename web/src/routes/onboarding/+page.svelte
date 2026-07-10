<script lang="ts">
	import { goto } from '$app/navigation';
	import { SOURCES, conn, connectSource, disconnectSource, connectedSources } from '$lib/state.svelte';

	const count = $derived(connectedSources().length);
</script>

<section class="head">
	<span class="step">Step 1 of 2 · Connect sources</span>
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
					<span class="done">✓ Connected</span>
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
	<span class="count">{count} of {SOURCES.length} connected</span>
	<button class="btn btn-primary" disabled={count === 0} onclick={() => goto('/viewer')}>
		Continue to your context →
	</button>
</div>

<style>
	.head {
		max-width: 640px;
		margin-bottom: 28px;
	}
	.step {
		color: var(--brand);
		font-size: 0.82rem;
		font-weight: 600;
	}
	h1 {
		font-size: 2.1rem;
		margin: 10px 0 12px;
	}
	.lede {
		color: var(--text-muted);
		margin: 0;
	}
	.sources {
		display: flex;
		flex-direction: column;
		gap: 12px;
	}
	.source {
		display: flex;
		align-items: center;
		gap: 16px;
		background: var(--surface);
		border: 1px solid var(--border);
		border-radius: var(--radius);
		padding: 16px 18px;
		transition: border-color 0.15s ease;
	}
	.source.connected {
		border-color: var(--shared-border);
	}
	.source-icon {
		font-size: 1.6rem;
		width: 44px;
		height: 44px;
		display: grid;
		place-items: center;
		background: var(--surface-2);
		border-radius: 11px;
		flex-shrink: 0;
	}
	.source-body {
		flex: 1;
		min-width: 0;
	}
	.source-title {
		font-weight: 600;
		font-size: 1.02rem;
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
		color: var(--shared);
		font-weight: 600;
		font-size: 0.9rem;
	}
	.btn.ghost {
		background: transparent;
		border-color: var(--border);
		color: var(--text-muted);
		padding: 7px 12px;
		font-size: 0.85rem;
	}
	.foot {
		display: flex;
		align-items: center;
		justify-content: space-between;
		margin-top: 28px;
		padding-top: 20px;
		border-top: 1px solid var(--border);
	}
	.count {
		color: var(--text-muted);
		font-size: 0.9rem;
	}
	.spinner {
		width: 13px;
		height: 13px;
		border: 2px solid var(--text-faint);
		border-top-color: var(--text);
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
