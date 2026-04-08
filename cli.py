import click
import os
import orchestrator

@click.command()
@click.argument('legacy_path') # The GitHub URL or local path
@click.option('--target', default='python', help='Target language for modernization.')
@click.option('--output', default='./workspaces', type=click.Path(), help='Output directory for generated microservices.')
@click.option('--mode', type=click.Choice(['incremental', 'batch']), default='batch', help='Migration mode: incremental (strangler fig) or batch (big bang).')
@click.option('--review', default='none', help='Comma-separated list of review gates to enable (e.g., gate1,gate2 or all).')
@click.option('--deterministic', is_flag=True, help='Force translation cache lookup before LLM calls.')
@click.option('--force-retranslate', is_flag=True, help='Bypass cache and force re-translation of all modules.')
def modernize(legacy_path, target, output, mode, review, deterministic, force_retranslate):
    """
    🏢 Mitra/UoM Legacy Modernization Engine v3.0
    Translates COBOL codebases into Python microservices.
    """
    click.secho("\n==================================================", fg="blue", bold=True)
    click.secho("🚀 INITIATING MODERNIZATION CLI (v3.0)", fg="blue", bold=True)
    click.secho("==================================================", fg="blue", bold=True)

    click.secho(f"🔗 Target Repository : {legacy_path}", fg="cyan")
    click.secho(f"🎯 Target Language   : {target.upper()}", fg="cyan")
    click.secho(f"⚙️  Migration Mode    : {mode.upper()}", fg="cyan")
    
    if review != "none":
        click.secho(f"🛑 Human Review Gates: ENABLED ({review})", fg="yellow")
    else:
        click.secho(f"⚡ Human Review Gates: DISABLED (Fully Automated)", fg="red")

    if deterministic:
        click.secho("🔒 Deterministic Mode: ENABLED (Using AI Translation Cache)", fg="green")

    click.secho("\nHanding off to Worker 0 (Celery/Redis Orchestrator)...", fg="yellow")

    # The Orchestrator now returns the enforced unique ID
    task, final_job_id = orchestrator.start_enterprise_pipeline(legacy_path, "cli")
    
    click.secho(f"\n✅ Command accepted! Assigned Job ID: {final_job_id}", fg="green")
    click.secho(f"⏳ Monitoring Task ID: {task.id}", fg="white")

if __name__ == '__main__':
    modernize()