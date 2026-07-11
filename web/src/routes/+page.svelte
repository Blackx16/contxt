<script lang="ts">
	import { anyConnected } from '$lib/state.svelte';
	import { base } from '$app/paths';

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
			<a class="btn btn-primary" href="{base}/viewer">View your context →</a>
			<a class="btn btn-secondary" href="{base}/onboarding">Manage sources</a>
		{:else}
			<a class="btn btn-primary" href="{base}/onboarding">Connect a source →</a>
			<a class="btn btn-secondary" href="{base}/viewer">See the viewer</a>
		{/if}
	</div>
</section>

<section class="tiers">
	<div class="tier">
		<span class="tag tag-shared">Shared</span>
		<h3>Cloud-readable</h3>
		<p>Distilled by cloud Gemma, lightly encrypted. Any AI can use it directly through MCP.</p>
	</div>
	<div class="seam" aria-hidden="true"></div>
	<div class="tier">
		<span class="tag tag-private">Private</span>
		<h3>Crown jewels</h3>
		<p>
			Classified on-device, E2E-encrypted. The cloud is a blind relay — it only ever holds
			ciphertext.
		</p>
	</div>
</section>

<style>
	.hero {
		padding: 24px 0 56px;
		max-width: 760px;
	}
	.eyebrow {
		display: block;
		margin-bottom: 24px;
	}
	.lede {
		font-size: 1.12rem;
		line-height: 1.75;
		color: var(--text-muted);
		max-width: 68ch;
		margin: 24px 0 0;
	}
	.kw-private {
		color: var(--gold);
	}
	.kw-shared {
		color: var(--patina-text);
	}
	.cta {
		display: flex;
		gap: 12px;
		margin-top: 36px;
		flex-wrap: wrap;
	}

	/* Two-tier block on a single dark plinth, split by a hairline seam — not two nested cards */
	.tiers {
		display: grid;
		grid-template-columns: 1fr 1px 1fr;
		background: var(--raised);
		border: 1px solid var(--rule);
		border-radius: var(--r-lg);
		overflow: hidden;
	}
	.tier {
		padding: 28px;
	}
	.tier h3 {
		margin: 14px 0 8px;
	}
	.tier p {
		margin: 0;
		color: var(--text-muted);
		font-size: 0.95rem;
		max-width: 42ch;
	}
	.seam {
		background: var(--rule);
	}
	@media (max-width: 640px) {
		.tiers {
			grid-template-columns: 1fr;
		}
		.seam {
			height: 1px;
		}
	}
</style>
