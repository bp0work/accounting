<script module lang="ts">
  export const ssr = false;
</script>

<h1>Travel requests</h1>

<div class="card">
  <p>
    Travel requests are submitted by employees via email to
    <strong>accexp.mmlogistix@bp0.work</strong>.
  </p>
  <p>
    Once approved by the Accounts Manager, the system assigns a <strong>transaction reference number</strong>.
    The traveller must quote this reference when submitting expense claims.
  </p>
  <p>
    Travel request management is handled through the <strong>escalation email workflow</strong> — not through this admin UI.
  </p>
</div>

<style>
  .card {
    background: #fff;
    border: 1px solid #e2e8f0;
    padding: 1.25rem;
    border-radius: 8px;
    line-height: 1.6;
  }
  p { margin: 0 0 1rem; }
  p:last-child { margin-bottom: 0; }
</style>
