<script lang="ts">
	import { anyConnected } from '$lib/state.svelte';

	const connected = $derived(anyConnected());
</script>

<section class="hero">
	<span class="eyebrow">Two-tier context · local processing · client-side encryption</span>
	<h1>One context layer<br />every AI talks to.</h1>
	<p class="lede">
		Contxt remembers you and acts for you across ChatGPT, Claude, and Gemini — while your private
		data stays yours. A Crown-Jewels Gateway sorts every item into <span class="kw-private"
			>Private</span
		>
		or <span class="kw-shared">Shared</span>, so sensitive context never leaves your device.
	</p>
	<div class="cta">
		{#if connected}
			<a class="btn btn-primary" href="/viewer">View your context →</a>
			<a class="btn" href="/onboarding">Manage sources</a>
		{:else}
			<a class="btn btn-primary" href="/onboarding">Connect a source →</a>
			<a class="btn" href="/viewer">See the viewer</a>
		{/if}
	</div>
</section>

<section class="tiers">
	<div class="tier tier-shared">
		<span class="tag tag-shared">↗ Shared</span>
		<h3>Cloud-readable</h3>
		<p>Distilled by cloud Gemma, lightly encrypted. Any AI can use it directly through MCP.</p>
	</div>
	<div class="tier tier-private">
		<span class="tag tag-private">🔒 Private</span>
		<h3>Crown jewels</h3>
		<p>
			Classified on-device, E2E-encrypted. The cloud is a blind relay — it only ever holds
			ciphertext.
		</p>
	</div>
</section>

<style>
	.hero {
		padding: 28px 0 44px;
		max-width: 720px;
	}
	.eyebrow {
		display: inline-block;
		color: var(--brand);
		font-size: 0.82rem;
		font-weight: 600;
		letter-spacing: 0.02em;
		margin-bottom: 18px;
		padding: 5px 12px;
		border: 1px solid var(--border-strong);
		border-radius: 999px;
		background: var(--brand-soft);
	}
	h1 {
		font-size: 3rem;
		line-height: 1.05;
		margin-bottom: 20px;
	}
	.lede {
		font-size: 1.1rem;
		color: var(--text-muted);
		max-width: 640px;
	}
	.kw-private {
		color: var(--private);
		font-weight: 600;
	}
	.kw-shared {
		color: var(--shared);
		font-weight: 600;
	}
	.cta {
		display: flex;
		gap: 12px;
		margin-top: 28px;
		flex-wrap: wrap;
	}
	.tiers {
		display: grid;
		grid-template-columns: 1fr 1fr;
		gap: 16px;
		margin-top: 8px;
	}
	@media (max-width: 620px) {
		.tiers {
			grid-template-columns: 1fr;
		}
		h1 {
			font-size: 2.2rem;
		}
	}
	.tier {
		background: var(--surface);
		border: 1px solid var(--border);
		border-radius: var(--radius);
		padding: 20px;
	}
	.tier h3 {
		margin: 12px 0 6px;
	}
	.tier p {
		margin: 0;
		color: var(--text-muted);
		font-size: 0.9rem;
	}
	.tier-private {
		border-left: 3px solid var(--private);
	}
	.tier-shared {
		border-left: 3px solid var(--shared);
	}
</style>
